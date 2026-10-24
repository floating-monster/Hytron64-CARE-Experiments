package chipyard

import chisel3._
import chisel3.util._

/** Initial scope: integer arithmetic, branches and NOPs.
  * Each producer supplies one ordered record per completed instruction.
  */
class Hytron64RetireRecord extends Bundle {
  val seq = UInt(32.W)
  val pc = UInt(64.W)
  val inst = UInt(32.W)
  val wen = Bool()
  val rd = UInt(5.W)
  val data = UInt(64.W)
  val last = Bool()
}

/** Passive observer. Valid inputs cannot be backpressured.
  * Overflow is fatal; records must never be silently dropped.
  */
class Hytron64RetireCompare(
  depth: Int = 16,
  expectedRecords: Int = 3074
) extends Module {
  require(depth > 0 && expectedRecords > 0)

  val io = IO(new Bundle {
    val in = Input(Vec(3, Valid(new Hytron64RetireRecord)))
    val fault = Input(Vec(3, Bool()))
    val passed = Output(Bool())
    val failed = Output(Bool())
    val compared = Output(UInt(32.W))
    val voted = Output(Valid(new Hytron64RetireRecord))
    // pair: 1=AB, 2=BC, 3=AC; valid only with voted.valid.
    val pair = Output(UInt(2.W))
    val stage2Used = Output(UInt(32.W))
    val noMajority = Output(Bool())
    val highWater = Output(Vec(3, UInt(log2Ceil(depth + 1).W)))
  })

  val failed = RegInit(false.B)
  val passed = RegInit(false.B)
  val finishing = RegInit(false.B)
  val compared = RegInit(0.U(32.W))
  val secondStage = RegInit(false.B)
  val stage2Used = RegInit(0.U(32.W))
  val noMajority = RegInit(false.B)
  val ended = RegInit(VecInit(Seq.fill(3)(false.B)))
  val queues = Seq.fill(3)(
    Module(new Queue(new Hytron64RetireRecord, depth,
      pipe = false, flow = false))
  )

  for (h <- 0 until 3) {
    val q = queues(h)
    val in = io.in(h)
    val writes = in.bits.wen && in.bits.rd =/= 0.U

    q.io.enq.valid := in.valid && !failed && !passed &&
      !finishing && !noMajority
    q.io.enq.bits := in.bits
    q.io.enq.bits.wen := writes
    q.io.enq.bits.rd := Mux(writes, in.bits.rd, 0.U)
    q.io.enq.bits.data := Mux(writes, in.bits.data, 0.U)

    val high = RegInit(0.U(log2Ceil(depth + 1).W))
    when (q.io.count > high) { high := q.io.count }
    io.highWater(h) := high

    when (in.valid && !failed && !noMajority) {
      when (ended(h) || finishing || passed || !q.io.enq.ready) {
        failed := true.B
        printf(p"[RETIRE-COMPARE] INPUT_ERROR slot=${h.U} seq=${in.bits.seq} full=${!q.io.enq.ready} count=${q.io.count} ended=${ended(h)} finishing=${finishing} passed=${passed}\n")
      }
      when (in.bits.last) { ended(h) := true.B }
    }
  }

  val allValid = queues.map(_.io.deq.valid).reduce(_ && _)
  val running = allValid && !failed && !passed &&
    !finishing && !noMajority && !io.fault.asUInt.orR
  val heads = queues.map(_.io.deq.bits)
  val recordWidth = heads.head.getWidth

  // Equality datapath 1: AB in stage 1, BC in stage 2.
  val cmp1Left = Mux(running,
    Mux(secondStage, heads(1).asUInt, heads(0).asUInt),
    0.U(recordWidth.W))
  val cmp1Right = Mux(running,
    Mux(secondStage, heads(2).asUInt, heads(1).asUInt),
    0.U(recordWidth.W))
  val equal1 = cmp1Left === cmp1Right

  // Equality datapath 2: AC, used only in stage 2.
  // Isolate its inputs during stage 1.
  val cmp2Left = Mux(running && secondStage,
    heads(0).asUInt, 0.U(recordWidth.W))
  val cmp2Right = Mux(running && secondStage,
    heads(2).asUInt, 0.U(recordWidth.W))
  val equal2 = cmp2Left === cmp2Right

  val found = Mux(secondStage, equal1 || equal2, equal1)
  val pair = Mux(!secondStage, 1.U(2.W),
    Mux(equal1, 2.U(2.W), 3.U(2.W)))
  val selected = Mux(secondStage && equal1, heads(1), heads(0))
  val expectedLast = compared === (expectedRecords - 1).U
  val metadataOK = selected.seq === compared &&
    selected.last === expectedLast
  val accept = running && found && metadataOK

  // Keep all three FIFO heads until an accepted decision.
  queues.foreach(_.io.deq.ready := accept)
  io.voted.valid := accept
  io.voted.bits := selected
  io.pair := Mux(accept, pair, 0.U)
  io.stage2Used := stage2Used
  io.noMajority := noMajority

  when (running) {
    when (found) {
      when (!metadataOK) {
        failed := true.B
        printf(p"[RETIRE-VOTER] ALIGNMENT_ERROR seq=${compared}\n")
      }.otherwise {
        compared := compared + 1.U
        secondStage := false.B
        when (secondStage) {
          stage2Used := stage2Used + 1.U
        }
        when (expectedLast) { finishing := true.B }
      }
    }.elsewhen (!secondStage) {
      secondStage := true.B
    }.otherwise {
      // Latch the request, stop recording and preserve FIFO heads.
      // This observer does not stop cores or suppress external writes.
      noMajority := true.B
      printf(p"[RETIRE-VOTER] NO_MAJORITY seq=${compared}\n")
      for (h <- 0 until 3) {
        val record = heads(h)
        printf(p"[RETIRE-VOTER] EVIDENCE slot=${h.U} seq=${record.seq} pc=${Hexadecimal(record.pc)} inst=${Hexadecimal(record.inst)} wen=${record.wen} rd=${record.rd} data=${Hexadecimal(record.data)} last=${record.last}\n")
      }
    }
  }

  when (finishing && !failed && !passed && !noMajority) {
    val empty = queues.map(q => !q.io.deq.valid).reduce(_ && _)
    when (empty && ended.asUInt.andR && !io.in.map(_.valid).reduce(_ || _)) {
      passed := true.B
      printf(p"[RETIRE-COMPARE] PASS records=${compared}\n")
    }.otherwise {
      failed := true.B
      printf(p"[RETIRE-COMPARE] END_ERROR\n")
    }
  }

  when (io.fault.asUInt.orR) {
    failed := true.B
  }

  io.failed := failed
  io.passed := passed && !failed && !noMajority
  io.compared := compared
}
