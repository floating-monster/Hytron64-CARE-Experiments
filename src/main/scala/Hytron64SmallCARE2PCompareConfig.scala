package chipyard

import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils
import org.chipsalliance.cde.config.{Config, Parameters}
import freechips.rocketchip.tile.RocketTile

class Hytron64Care2PTop(implicit p: Parameters) extends DigitalTop {
  override lazy val module = new Hytron64Care2PTopModule(this)
}

class Hytron64Care2PTopModule(outer: Hytron64Care2PTop)
    extends DigitalTopModule(outer) {
  val tiles = outer.totalTiles.values.toSeq.map {
    case r: RocketTile => r
    case _ => throw new IllegalArgumentException("CARE requires Rocket")
  }.sortBy(_.rocketParams.tileId)
  require(tiles.size == 4)
  require(tiles.map(_.rocketParams.tileId) == Seq(0, 1, 2, 3))
  tiles.foreach(t => require(!t.rocketParams.core.clockGate))

  val monitors = tiles.map(t =>
    BoringUtils.bore(t.module.core.rocketImpl.coreMonitorBundle))
  monitors.foreach(m => require(m.xLen == 64))

  // Static pairing table, independent of record-producing hart IDs.
  val pairing = Seq(Seq(0, 1), Seq(2, 3))
  val checker = withClockAndReset(monitors.head.clock, monitors.head.reset) {
    Module(new Hytron64Care2P(64, 3074, pairing))
  }
  val injectSelect = freechips.rocketchip.util.PlusArg(
    "care_inject", default = 0)
  checker.io.holdPair := freechips.rocketchip.util.PlusArg(
    "care_hold_pair", default = 0)
  checker.io.holdCycles := freechips.rocketchip.util.PlusArg(
    "care_hold_cycles", default = 0)
  checker.io.holdSeq := freechips.rocketchip.util.PlusArg(
    "care_hold_seq", default = 0)

  for ((m, h) <- monitors.zipWithIndex) {
    withClockAndReset(m.clock, m.reset) {
      assert(m.hartid === h.U, "CARE hart mapping mismatch")
      val active = RegInit(false.B)
      val started = RegInit(false.B)
      val ended = RegInit(false.B)
      val seq = RegInit(0.U(32.W))
      val atBegin = m.pc === "h80006100".U
      val atEnd = m.pc === "h80006110".U
      val begin = m.valid && atBegin && !started
      val capture = m.valid && (active || begin)
      val writes = m.wrenx && m.wrdst =/= 0.U

      // 1..4: one hart; 5: same corruption in pair0;
      // 6: corrupt one member of each pair.
      val target = injectSelect === (h + 1).U ||
        (injectSelect === 5.U && (h < 2).B) ||
        (injectSelect === 6.U && (h == 0 || h == 2).B)
      val inject = target && capture && seq === 1.U && writes
      val data = Mux(writes, m.wrdata(63, 0), 0.U(64.W))
      checker.io.in(h).valid := capture
      checker.io.in(h).bits.seq := seq
      checker.io.in(h).bits.pc := m.pc
      checker.io.in(h).bits.inst := m.inst
      checker.io.in(h).bits.wen := writes
      checker.io.in(h).bits.rd := Mux(writes, m.wrdst, 0.U)
      checker.io.in(h).bits.data :=
        data ^ Mux(inject, 1.U(64.W), 0.U(64.W))
      checker.io.in(h).bits.last := atEnd
      checker.io.fault(h) := (m.excpt && (active || atBegin)) ||
        (m.valid && atBegin && started) ||
        (m.valid && atEnd && ended)
      when (inject) {
        printf(p"[CARE2P-INJECT] hart=${m.hartid} seq=${seq} original=${Hexadecimal(data)} flipped=${Hexadecimal(data ^ 1.U(64.W))}\n")
      }
      when (begin) { active := true.B; started := true.B }
      when (capture) {
        seq := seq + 1.U
        when (atEnd) { active := false.B; ended := true.B }
      }
    }
  }

  withClockAndReset(monitors.head.clock, monitors.head.reset) {
    val reported = RegInit(false.B)
    when (checker.io.passed && !reported) {
      reported := true.B
      printf(p"[CARE2P] HARDWARE_PASS records=${checker.io.settled} highWater=${checker.io.highWater(0)},${checker.io.highWater(1)},${checker.io.highWater(2)},${checker.io.highWater(3)}\n")
    }
    assert(!checker.io.failed, "CARE2P observation failed")
  }
}

class WithHytron64Care2PTop extends Config((site, here, up) => {
  case BuildSystem => (p: Parameters) => new Hytron64Care2PTop()(p)
})

class Hytron64SmallCARE2PCompareConfig extends Config(
  new WithHytron64Care2PTop ++
  new chipyard.config.WithNoTileClockGaters ++
  new chipyard.config.WithNoTileResetSetters ++
  new chipyard.clocking.WithClockGroupsCombinedByName(
    ("uncore",
      Seq("sbus", "mbus", "pbus", "fbus", "cbus", "obus",
          "implicit", "clock_tap", "tile"), Nil)
  ) ++
  new Hytron64SmallCARE2PConfig
)
