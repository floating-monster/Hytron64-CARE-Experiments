#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
gcc=${RISCV_GCC:-riscv64-unknown-elf-gcc}
objdump=${RISCV_OBJDUMP:-riscv64-unknown-elf-objdump}
mkdir -p build
for case_id in 0 1 2; do
  "$gcc" -march=rv64i_zicsr -mabi=lp64 -mcmodel=medany \
    -nostdlib -nostartfiles -static -Wl,--no-relax \
    -Wl,-T,link.ld -Wl,-Map,"build/case${case_id}.map" \
    -DCASE="$case_id" care2p.S -o "build/case${case_id}.elf"
  "$objdump" -d "build/case${case_id}.elf" > "build/case${case_id}.dump"
done
printf 'CARE2P_TEST_ELF_BUILD=PASS\n'
