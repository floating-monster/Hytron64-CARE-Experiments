package chipyard

import chisel3._
import chisel3.util._

/** One outstanding sequence: early acceptance, then settle both pairs.
  * Reuses the existing retirement record format.
  * Observer only: no architectural correction or write suppression.
  */
class Hytron64Care2P(
  depth: Int = 64,
  expectedRecords: Int = 3074,
  pairMap: Seq[Seq[Int]] = Seq(Seq(0, 1), Seq(2, 3))
) extends Module {
  require(depth > 0 && expectedRecords > 0)
  require(pairMap.size == 2 && pairMap.forall(_.size == 2))
  require(pairMap.flatten.sorted == Seq(0, 1, 2, 3))

  val io = IO(new Bundle {
    val in = Input(Vec(4, Valid(new Hytron64RetireRecord)))
    val fault = Input(Vec(4, Bool()))
    val holdPair = Input(UInt(2.W)) // 0=none, 1=pair0, 2=pair1
    val holdCycles = Input(UInt(32.W))
    val voted = Output(Valid(new Hytron64RetireRecord))
    val winner = Output(UInt(1.W))
    val passed = Output(Bool())
    val failed = Output(Bool())
    val accepted = Output(UInt(32.W))
    val settled = Output(UInt(32.W))
    val wins = Output(Vec(2, UInt(32.W)))
    val early = Output(UInt(32.W))
    val highWater = Output(Vec(4, UInt(log2Ceil(depth + 1).W)))
  })

  val failed = RegInit(false.B)
  val passed = RegInit(false.B)
  val finishing = RegInit(false.B)
  val accepted = RegInit(0.U(32.W))
  val settled = RegInit(0.U(32.W))
  val wins = RegInit(VecInit(Seq.fill(2)(0.U(32.W))))
  val early = RegInit(0.U(32.W))
  val ended = RegInit(VecInit(Seq.fill(4)(false.B)))
  val pending = RegInit(false.B)
  val saved = Reg(new Hytron64RetireRecord)
  val savedWinner = Reg(UInt(1.W))
  val tick = RegInit(0.U(64.W))
  tick := tick + 1.U

  val started = RegInit(false.B)
  val age = RegInit(0.U(32.W))
  when (!started && io.in.map(_.valid).reduce(_ || _)) {
    started := true.B
    age := 0.U
  }
  when (started && age =/= "hffffffff".U) { age := age + 1.U }

  val qs = Seq.fill(4)(Module(new Queue(
    new Hytron64RetireRecord, depth, pipe = false, flow = false)))

  for (h <- 0 until 4) {
    val q = qs(h)
    val in = io.in(h)
    val writes = in.bits.wen && in.bits.rd =/= 0.U
    q.io.enq.valid := in.valid && !failed && !passed && !finishing
    q.io.enq.bits := in.bits
    q.io.enq.bits.wen := writes
    q.io.enq.bits.rd := Mux(writes, in.bits.rd, 0.U)
    q.io.enq.bits.data := Mux(writes, in.bits.data, 0.U)

    val high = RegInit(0.U(log2Ceil(depth + 1).W))
    when (q.io.count > high) { high := q.io.count }
    io.highWater(h) := high

    when (in.valid && !failed) {
      when (ended(h) || finishing || passed || !q.io.enq.ready) {
        failed := true.B
        printf(p"[CARE2P] INPUT_ERROR hart=${h.U} seq=${in.bits.seq} count=${q.io.count}\n")
      }
      when (in.bits.last) { ended(h) := true.B }
    }
  }

  val heads = qs.map(_.io.deq.bits)
  val ready = Wire(Vec(2, Bool()))
  val equal = Wire(Vec(2, Bool()))
  val metadata = Wire(Vec(2, Bool()))
  val candidates = Wire(Vec(2, new Hytron64RetireRecord))
  val expectedLast = settled === (expectedRecords - 1).U
  for (p <- 0 until 2) {
    val a = pairMap(p)(0)
    val b = pairMap(p)(1)
    val held = io.holdPair === (p + 1).U &&
      (!started || age < io.holdCycles)
    ready(p) := qs(a).io.deq.valid && qs(b).io.deq.valid && !held
    candidates(p) := heads(a)
    val zero = 0.U(heads(a).getWidth.W)
    equal(p) := Mux(ready(p), heads(a).asUInt, zero) ===
      Mux(ready(p), heads(b).asUInt, zero)
    metadata(p) := heads(a).seq === settled &&
      heads(b).seq === settled &&
      heads(a).last === expectedLast &&
      heads(b).last === expectedLast
  }

  val running = !failed && !passed && !finishing &&
    !io.fault.asUInt.orR
  val good = VecInit((0 until 2).map(p =>
    ready(p) && metadata(p) && equal(p)))
  val badMetadata = (0 until 2).map(p =>
    ready(p) && !metadata(p)).reduce(_ || _)
  val bothReady = ready.asUInt.andR
  val bothGood = good.asUInt.andR

  // Cross-pair audit: not an additional majority vote.
  val simultaneousConflict = bothGood &&
    candidates(0).asUInt =/= candidates(1).asUInt
  val lateConflict = pending && (0 until 2).map(p =>
    good(p) && candidates(p).asUInt =/= saved.asUInt).reduce(_ || _)
  val conflict = simultaneousConflict || lateConflict
  val noAgreement = bothReady && !good.asUInt.orR
  val canProceed = running && !badMetadata && !conflict && !noAgreement

  // Same-cycle equal candidates use pair0 as a deterministic tie-break.
  val winner = Mux(good(0), 0.U(1.W), 1.U(1.W))
  val selected = Mux(good(0), candidates(0), candidates(1))
  val take = canProceed && !pending && good.asUInt.orR
  val finishSequence = canProceed && bothReady &&
    (pending || good.asUInt.orR)

  io.voted.valid := take
  io.voted.bits := selected
  io.winner := winner
  qs.foreach(_.io.deq.ready := finishSequence)

  when (take) {
    accepted := accepted + 1.U
    wins(winner) := wins(winner) + 1.U
    saved := selected
    savedWinner := winner
    pending := true.B
    when (!bothReady) { early := early + 1.U }
    when (settled === 0.U || settled === 1.U) {
      printf(p"[CARE2P] TOUCH tick=${tick} seq=${selected.seq} pair=${winner} otherReady=${bothReady} data=${Hexadecimal(selected.data)}\n")
    }
  }

  when (finishSequence) {
    settled := settled + 1.U
    pending := false.B
    when (expectedLast) { finishing := true.B }
  }

  when (running) {
    when (badMetadata) {
      failed := true.B
      printf(p"[CARE2P] ALIGNMENT_ERROR seq=${settled}\n")
    }.elsewhen (conflict) {
      failed := true.B
      printf(p"[CARE2P] CONFLICT seq=${settled} alreadyAccepted=${pending} savedPair=${savedWinner}\n")
    }.elsewhen (noAgreement) {
      failed := true.B
      printf(p"[CARE2P] NO_AGREEMENT seq=${settled}\n")
    }
  }

  when (finishing && !failed && !passed) {
    val empty = qs.map(q => !q.io.deq.valid).reduce(_ && _)
    when (empty && ended.asUInt.andR &&
          !io.in.map(_.valid).reduce(_ || _) &&
          accepted === expectedRecords.U &&
          settled === expectedRecords.U && !pending) {
      passed := true.B
      printf(p"[CARE2P] PASS accepted=${accepted} settled=${settled} wins=${wins(0)},${wins(1)} early=${early}\n")
    }.otherwise {
      failed := true.B
      printf(p"[CARE2P] END_ERROR\n")
    }
  }
  when (io.fault.asUInt.orR) {
    failed := true.B
    printf(p"[CARE2P] SOURCE_FAULT\n")
  }

  io.failed := failed
  io.passed := passed && !failed
  io.accepted := accepted
  io.settled := settled
  io.wins := wins
  io.early := early
}
