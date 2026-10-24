#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("case", type=int, choices=range(3))
p.add_argument("log", type=Path)
p.add_argument("--metrics", type=Path)
p.add_argument("--host-seconds", type=float)
a = p.parse_args()
text = a.log.read_text(errors="replace")

def require(ok, msg):
    if not ok:
        raise SystemExit("CARE2P_COMPARE_FAIL: " + msg)

require(text.splitlines().count("CARE2P_SOFTWARE_EXIT=0") == 1,
        "software/simulator success absent")
require(not re.search(r"Assertion failed|%Error|%Fatal|\*\*\* FAILED \*\*\*", text),
        "simulator failure")
pat = re.compile(
    r"^C(\d+):\s*(\d+)\s+\[([01])\]\s+pc=\[([0-9a-fA-F]+)\]"
    r"\s+W\[r\s*(\d+)=([0-9a-fA-F]+)\]\[([01])\].*?"
    r"inst=\[([0-9a-fA-F]+)\]"
)
rows = {h: [] for h in range(4)}
for line in text.splitlines():
    m = pat.search(line)
    if not m:
        continue
    h, cycle, valid, pc, rd, value, wen, inst = m.groups()
    h, cycle, valid = int(h), int(cycle), int(valid)
    pc, rd, value = int(pc,16), int(rd), int(value,16)
    wen, inst = int(wen), int(inst,16)
    require(h in rows, "unexpected hart ID")
    if valid == 0:
        require(pc == 0x10038 and inst == 0xffdff06f
                and not any(r[1] == 0x80006100 for r in rows[h]),
                f"hart{h}: unexpected exception pc={pc:x}")
        continue
    rows[h].append((cycle,pc,inst,wen,rd,value))

begin, end = 0x80006100, 0x80006110
mask = (1 << 64) - 1
records = {}
metrics = {"case": a.case, "harts": [],
           "host_seconds_with_verbose": a.host_seconds}
for h, trace in rows.items():
    starts = [i for i,r in enumerate(trace) if r[1] == begin]
    ends = [i for i,r in enumerate(trace) if r[1] == end]
    require(len(starts) == len(ends) == 1, f"hart{h}: markers")
    first, last = starts[0], ends[0]
    require(first < last, f"hart{h}: marker order")
    region = trace[first:last+1]
    require(len(region) == 3074, f"hart{h}: record count {len(region)}")

    normalized = []
    for cycle,pc,inst,wen,rd,value in region:
        writes = bool(wen and rd != 0)
        normalized.append((pc,inst,int(writes),
                           rd if writes else 0,
                           value if writes else 0))
    require(normalized[0] == (begin,0x13,0,0,0), "begin NOP")
    require(normalized[-1] == (end,0x13,0,0,0), "end NOP")

    value = mask if a.case == 2 else 17
    step = 25 if a.case == 1 else 1
    add_inst = 0x005383b3 if a.case == 1 else 0x00138393
    for i in range(1024):
        add, dec, branch = normalized[1+3*i:4+3*i]
        value = (value + step) & mask
        require(add == (begin+4,add_inst,1,7,value),
                f"hart{h}: op{i} arithmetic/RF")
        require(dec == (begin+8,0xfff40413,1,8,1023-i),
                f"hart{h}: op{i} counter/RF")
        require(branch[0] == begin+12 and branch[2:] == (0,0,0),
                f"hart{h}: op{i} branch")
        require(branch[1] == 0xfe041ce3,
                f"hart{h}: op{i} branch opcode")

    donepc = [0x80000300,0x80001300,0x80002300,0x80005300][h]
    require(sum(r[1] == donepc for r in trace) == 1,
            f"hart{h}: software RF check completion")
    require(any(r[1] == donepc for r in trace[last+1:]),
            f"hart{h}: done marker order")
    records[h] = normalized
    metrics["harts"].append({
        "hart": h, "records": len(region),
        "local_begin_cycle": region[0][0],
        "local_end_cycle": region[-1][0],
        "local_window_cycles": region[-1][0]-region[0][0]+1,
        "final_rf": f"0x{value:016x}"
    })

for h in (1,2,3):
    for seq,(left,right) in enumerate(zip(records[0],records[h])):
        require(left == right, f"hart0/hart{h}: mismatch at seq={seq}")

require(sum(r[1] == 0x80000380 for r in rows[0]) == 1,
        "hart0 all-hart join marker")
metrics["records_per_hart"] = 3074
metrics["comparison"] = "PC, instruction, normalized integer register write"
if a.metrics:
    a.metrics.write_text(json.dumps(metrics,indent=2)+"\n")
print(f"CARE2P_CASE{a.case}_4HART_RETIRE_SEQUENCE_COMPARE=PASS")
print(f"CARE2P_CASE{a.case}_RECORDS_PER_HART=3074")
for item in metrics["harts"]:
    print(f'CARE2P_CASE{a.case}_HART{item["hart"]}_LOCAL_WINDOW_CYCLES={item["local_window_cycles"]}')
