#ifndef CASE
#define CASE 0
#endif
#define ROUNDS 1024
.option norvc
.option norelax
.section .text.hart0,"ax",@progbits
.globl _start
_start:
  csrr t6, mhartid
  beqz t6, init0
  li t5, 1
  beq t6, t5, context1
  li t5, 2
  beq t6, t5, context2
  li t5, 3
  beq t6, t5, context3
  j fail
init0:
  csrw mie, zero
  csrci mstatus, 8
  la t0, fail
  csrw mtvec, t0
  li a0, 0x02000000
  sw zero, 0(a0)
  li a1, 1
  sw a1, 4(a0)
  sw a1, 8(a0)
  sw a1, 12(a0)
  fence rw, rw
  li s0, ROUNDS
#if CASE == 0
  li t2, 17
#elif CASE == 1
  li t2, 17
  li t0, 25
#elif CASE == 2
  li t2, -1
#else
#error Unsupported_CASE
#endif
  la a2, ready1
1:
  lw a1, 0(a2)
  beqz a1, 1b
  la a2, ready2
8:
  lw a1, 0(a2)
  beqz a1, 8b
  la a2, ready3
10:
  lw a1, 0(a2)
  beqz a1, 10b
  fence rw, rw
  la a0, go
  j start0
.org 0x100
.globl start0
start0:
  nop
  li a1, 1
  fence rw, rw
  sw a1, 0(a0)
  fence rw, rw
  j pair0
.org 0x200
.globl pair0
pair0:
  la ra, done_marker0
  j compare_entry
.org 0x300
.globl done_marker0
done_marker0:
  nop
  la a0, done0
  li a1, 1
  fence rw, rw
  sw a1, 0(a0)
  fence rw, rw
  la a0, done1
3:
  lw a1, 0(a0)
  beqz a1, 3b
  fence rw, rw
  la a0, done2
9:
  lw a1, 0(a0)
  beqz a1, 9b
  fence rw, rw
  la a0, done3
11:
  lw a1, 0(a0)
  beqz a1, 11b
  fence rw, rw
  j joined0
.org 0x380
.globl joined0
joined0:
  nop
  li a1, 1
  j exit

.section .text.hart1,"ax",@progbits
.globl context1
context1:
  csrw mie, zero
  csrci mstatus, 8
  la t0, fail
  csrw mtvec, t0
  li a0, 0x02000004
  sw zero, 0(a0)
  fence rw, rw
  li s0, ROUNDS
#if CASE == 0 || CASE == 1
  li t2, 123
#elif CASE == 2
  li t2, 0x7fffffffffffffff
#endif
  la a0, ready1
  li a1, 1
  fence rw, rw
  sw a1, 0(a0)
  fence rw, rw
  la a0, go
4:
  lw a1, 0(a0)
  beqz a1, 4b
  fence rw, rw
  j start1
.org 0x100
.globl start1
start1:
  nop
  j pair1
.org 0x200
.globl pair1
pair1:
  la ra, done_marker1
  j compare_entry
.org 0x300
.globl done_marker1
done_marker1:
  nop
  la a0, done1
  li a1, 1
  fence rw, rw
  sw a1, 0(a0)
  fence rw, rw
6: j 6b

.section .text.hart2,"ax",@progbits
.globl context2
context2:
  csrw mie, zero
  csrci mstatus, 8
  la t0, fail
  csrw mtvec, t0
  li a0, 0x02000008
  sw zero, 0(a0)
  fence rw, rw
  li s0, ROUNDS
#if CASE == 0 || CASE == 1
  li t2, 123
#elif CASE == 2
  li t2, 0x7fffffffffffffff
#endif
  la a0, ready2
  li a1, 1
  fence rw, rw
  sw a1, 0(a0)
  fence rw, rw
  la a0, go
4:
  lw a1, 0(a0)
  beqz a1, 4b
  fence rw, rw
  j start2
.org 0x100
.globl start2
start2:
  nop
  j pair2
.org 0x200
.globl pair2
pair2:
  la ra, done_marker2
  j compare_entry
.org 0x300
.globl done_marker2
done_marker2:
  nop
  la a0, done2
  li a1, 1
  fence rw, rw
  sw a1, 0(a0)
  fence rw, rw
6: j 6b

.section .text.hart3,"ax",@progbits
.globl context3
context3:
  csrw mie, zero
  csrci mstatus, 8
  la t0, fail
  csrw mtvec, t0
  li a0, 0x0200000c
  sw zero, 0(a0)
  fence rw, rw
  li s0, ROUNDS
#if CASE == 0 || CASE == 1
  li t2, 123
#elif CASE == 2
  li t2, 0x7fffffffffffffff
#endif
  la a0, ready3
  li a1, 1
  fence rw, rw
  sw a1, 0(a0)
  fence rw, rw
  la a0, go
4:
  lw a1, 0(a0)
  beqz a1, 4b
  fence rw, rw
  j start3
.org 0x100
.globl start3
start3:
  nop
  j pair3
.org 0x200
.globl pair3
pair3:
  la ra, done_marker3
  j compare_entry
.org 0x300
.globl done_marker3
done_marker3:
  nop
  la a0, done3
  li a1, 1
  fence rw, rw
  sw a1, 0(a0)
  fence rw, rw
6: j 6b

.section .text.common,"ax",@progbits
.balign 4
fail:
  csrw mie, zero
  csrci mstatus, 8
  csrr a1, mhartid
  slli a1, a1, 1
  addi a1, a1, 3
exit:
  la a0, tohost
  fence rw, rw
  sd a1, 0(a0)
7: j 7b
.section .data,"aw",@progbits
.balign 64
ready1: .word 0
.balign 64
ready2: .word 0
.balign 64
ready3: .word 0
.balign 64
go: .word 0
.balign 64
done0: .word 0
.balign 64
done1: .word 0
.balign 64
done2: .word 0
.balign 64
done3: .word 0
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0

.section .text.compare,"ax",@progbits
.globl compare_entry
compare_entry:
  li s0, ROUNDS
  li t0, 25
#if CASE == 2
  li t2, -1
#else
  li t2, 17
#endif
  j compare_begin
.org 0x100
.globl compare_begin
compare_begin:
  nop
compare_loop:
#if CASE == 1
  add t2, t2, t0
#else
  addi t2, t2, 1
#endif
  addi s0, s0, -1
  bnez s0, compare_loop
.globl compare_end
compare_end:
  nop
#if CASE == 0
  li t3, 1041
#elif CASE == 1
  li t3, 25617
#else
  li t3, 1023
#endif
  bne t2, t3, compare_bad
  ret
compare_bad:
  j fail
