OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS {
  . = 0x80000000;
  .text.hart0 : { *(.text.hart0) }
  . = 0x80001000;
  .text.hart1 : { *(.text.hart1) }
  . = 0x80002000;
  .text.hart2 : { *(.text.hart2) }
  . = 0x80003000;
  .text.common : { *(.text.common) }
  . = 0x80004000;
  .data : { *(.data*) }
  .tohost : { *(.tohost) }
  . = 0x80005000;
  .text.hart3 : { *(.text.hart3) }
  . = 0x80006000;
  .text.compare : { *(.text.compare) }
  /DISCARD/ : { *(.comment) *(.riscv.attributes) }
}
ASSERT(start0 == 0x80000100, "start0 PC mismatch")
ASSERT(start1 == 0x80001100, "start1 PC mismatch")
ASSERT(pair0 == 0x80000200, "pair0 PC mismatch")
ASSERT(pair1 == 0x80001200, "pair1 PC mismatch")
ASSERT(done_marker0 == 0x80000300, "done0 PC mismatch")
ASSERT(done_marker1 == 0x80001300, "done1 PC mismatch")
ASSERT(joined0 == 0x80000380, "join PC mismatch")

ASSERT(start2 == 0x80002100, "start2 PC mismatch")
ASSERT(pair2 == 0x80002200, "pair2 PC mismatch")
ASSERT(done_marker2 == 0x80002300, "done2 PC mismatch")

ASSERT(start3 == 0x80005100, "start3 PC mismatch")
ASSERT(pair3 == 0x80005200, "pair3 PC mismatch")
ASSERT(done_marker3 == 0x80005300, "done3 PC mismatch")

ASSERT(compare_begin == 0x80006100, "compare_begin PC mismatch")
ASSERT(compare_end == 0x80006110, "compare_end PC mismatch")
