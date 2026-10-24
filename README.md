# HYTRON64 CARE Experiments

**CARE: Context-Agreement Redundant Execution**

Experimental four-core CARE-2P observation and selection logic for
Chipyard Small Rocket cores. Pairs are (hart0, hart1) and (hart2, hart3).
This is a pair-agreement selector, not a four-input majority voter.

## Behavior

The first ready pair with matching context records can emit a selected
record. Equal simultaneous candidates use pair0 as a deterministic
tie-break. The selected record is retained for a later cross-pair audit.
Both pairs are settled before advancing to the next sequence.

Records contain sequence number, PC, instruction, normalized integer
register-write information, and an end marker.

## Evidence

- Initial TOUCH build: 11 tests PASS.
- Targeted-delay build: 3 tests PASS.

The 11 tests cover three normal cases, either pair arriving first,
four single-hart observation corruptions, conflicting agreeing pairs,
and disagreement within both pairs.

The three later tests cover normal execution and late conflict with
either the wrong or correct candidate selected first.

The full 11-test suite was NOT rerun after adding targeted delay.
These are not 14 tests of one identical executable.

Normal tests check 3074 records per hart. The observed local calculation
window is 6143 cycles per hart. FIFO depth is 64. The maximum reported
occupancy in the 11-test suite is 49. Local per-hart counters must not
be treated as a shared timestamp.

## Limits

Selection is an observer output, not architectural or external commitment.
A pair producing the same wrong record can be selected first.
Late conflict detection does not retract selection or identify the
correct pair. No core-state recovery, rollback, store gating, or MMIO
suppression is implemented.

Fault injection changes observation records, not actual register state.
Delay injection changes comparison readiness, not physical core execution.
Failing simulations end with assertions; this is not an on-chip recovery
controller. No radiation qualification or error probability is claimed.

## Layout

- src/main/scala: current targeted-delay source.
- snapshots/touch-11test: source matching the earlier 11-test evidence.
- tests: four-hart arithmetic program and software trace checker.
- evidence/touch: 11-test runner, logs and summary.
- evidence/late: 3-test runner, logs and summary.
- LICENSES: upstream notices.
- SHA256SUMS: file hashes.

Hytron64RetireCompare.scala also contains an earlier SMP3 comparator.
CARE reuses its retirement record type.

## Environment

Verified with Temurin JDK17, sbt 1.8.2, Chisel 6.7.0,
Verilator 5.032, and a RISC-V bare-metal toolchain.

This repository is an overlay, not a standalone Chipyard distribution.
Exact identity of the local Rocket baseline to an upstream revision
has not been certified. The baseline was restored from local pre-SMT
backups with initial experimental parameter checks removed.

## Reproduction

Back up the target environment before applying the overlay.
Copy src/main/scala/*.scala into
chipyard/generators/chipyard/src/main/scala/.

From the Chipyard root, build with:
make -C sims/verilator CONFIG=Hytron64SmallCARE2PCompareConfig -j2

Use Temurin JDK17 and unset USE_CHISEL7.
Build the ELF files with: bash tests/build.sh

The evidence runners retain the original experiment directory layout.
Set HYTRON_WORKSPACE to the directory containing chipyard and prepare
HYTRON64_CARE2P_CONTEXT_R0/tests/build/case0.elf through case2.elf there.
The tests directory in this repository supplies the corresponding
sources and build script.

tests/run_tests.py checks software retirement traces only.
The evidence runners additionally check CARE hardware events.

Use snapshots/touch-11test for the 11-test suite.
Use src/main/scala for the targeted-delay three-test suite.
Build the selected source version before running its evidence runner.
The runners write new logs beside themselves; use a separate copy
to preserve the published evidence.

## Runtime controls

- care_inject=0: no injection.
- care_inject=1..4: flip one bit in hart0..hart3 sequence-1 record.
- care_inject=5: identical corruption in hart0 and hart1.
- care_inject=6: corrupt hart0 and hart2.
- care_hold_pair=0/1/2: none / pair0 / pair1.
- care_hold_cycles=N: comparison-readiness delay.
- care_hold_seq=0: original startup hold.
- Nonzero care_hold_seq: targeted sequence, current source only.

Pass these as simulator plusargs, for example +care_inject=5.

## Licensing

Copied upstream notices are in LICENSES.
Applicable upstream terms remain in force for derived portions.
No additional license grant is made here for original experiment
material. Public availability is not a blanket redistribution license.
