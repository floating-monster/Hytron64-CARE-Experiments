from pathlib import Path
import json
import re
import subprocess
import sys

base = Path(__import__("os").environ.get("HYTRON_WORKSPACE", "/home/gwen/workspace"))
out = Path(__file__).resolve().parent
tests = base/"HYTRON64_CARE2P_CONTEXT_R0/tests"
simdir = base/"chipyard/sims/verilator"
sim = simdir/"simulator-chipyard.harness-Hytron64SmallCARE2PCompareConfig"
elf = tests/"build/case0.elf"
assert sim.is_file() and elf.is_file()

def require(ok, message):
    if not ok:
        raise SystemExit("CARE2P_LATE_FAIL: " + message)

jobs = [
    # label, injection, delayed pair, expected first pair/value
    ("normal_control", 0, 0, None, None),
    ("wrong_ab_first", 5, 2, 0, 0x13),
    ("correct_cd_first", 5, 1, 1, 0x12),
]
results = []

for label, inject, hold, winner, value in jobs:
    print("=== " + label + " ===", flush=True)
    log = out/f"{label}.run.log"
    with log.open("x") as stream:
        r = subprocess.run([
            str(sim), "+permissive", "+verbose",
            "+max-cycles=2000000",
            f"+care_inject={inject}",
            f"+care_hold_pair={hold}",
            "+care_hold_seq=1",
            "+care_hold_cycles=16",
            "+permissive-off", str(elf)
        ], cwd=simdir, stdout=stream, stderr=subprocess.STDOUT)

    text = log.read_text(errors="replace")
    lines = text.splitlines()
    for line in lines:
        if "[CARE2P]" in line or "[CARE2P-INJECT]" in line:
            print(line, flush=True)

    require(not re.search(
        r"\[CARE2P\] (INPUT_ERROR|ALIGNMENT_ERROR|END_ERROR|SOURCE_FAULT|NO_AGREEMENT)",
        text), label + ": unrelated failure")

    touches = []
    for i,line in enumerate(lines):
        if "[CARE2P] TOUCH" not in line:
            continue
        m = re.search(
            r"tick=\s*(\d+)\s+seq=\s*(\d+)\s+pair=\s*(\d+)"
            r"\s+otherReady=\s*(\d+)\s+data=([0-9a-fA-F]+)",
            line)
        require(m is not None, label + ": TOUCH format")
        touches.append((i, int(m[1]), int(m[2]), int(m[3]),
                        int(m[4]), int(m[5],16)))

    if inject == 0:
        require(r.returncode == 0 and "*** PASSED ***" in text,
                label + ": simulation success absent")
        require(not re.search(r"Assertion failed|%Error|%Fatal", text),
                label + ": simulator error")
        require("[CARE2P-INJECT]" not in text and
                "[CARE2P] CONFLICT" not in text,
                label + ": unexpected injection/conflict")

        passes = [s for s in lines if "[CARE2P] PASS " in s]
        hardware = [s for s in lines if "[CARE2P] HARDWARE_PASS " in s]
        require(len(passes) == len(hardware) == 1,
                label + ": completion count")
        m = re.search(
            r"accepted=\s*(\d+)\s+settled=\s*(\d+)"
            r"\s+wins=\s*(\d+),\s*(\d+)\s+early=\s*(\d+)",
            passes[0])
        require(m is not None and int(m[1]) == int(m[2]) == 3074
                and int(m[3])+int(m[4]) == 3074,
                label + ": completion counters")
        require(re.search(r"records=\s*3074\b", hardware[0]),
                label + ": hardware record count")

        with log.open("a") as stream:
            stream.write("\nCARE2P_SOFTWARE_EXIT=0\n")
        subprocess.run([
            sys.executable, str(tests/"check_log.py"), "0", str(log),
            "--metrics", str(out/f"{label}.metrics.json")
        ], check=True)
    else:
        require(r.returncode != 0 and
                "CARE2P observation failed" in text,
                label + ": expected assertion absent")
        require("[CARE2P] HARDWARE_PASS" not in text and
                "[CARE2P] PASS " not in text and
                "*** PASSED ***" not in text,
                label + ": unexpected completion")

        injections = [s for s in lines if "[CARE2P-INJECT]" in s]
        require(len(injections) == 2, label + ": injection count")
        for h in (0,1):
            hits = [s for s in injections if re.search(
                rf"hart=\s*{h}\s+seq=\s*1\b", s)]
            require(len(hits) == 1, label + ": injection target")
            m = re.search(
                r"original=([0-9a-fA-F]+)\s+flipped=([0-9a-fA-F]+)",
                hits[0])
            require(m is not None and
                    (int(m[1],16),int(m[2],16)) == (0x12,0x13),
                    label + ": injected value")

        target = [t for t in touches if t[2] == 1]
        require(len(target) == 1, label + ": seq1 acceptance count")
        touch = target[0]
        require((touch[3],touch[4],touch[5]) == (winner,0,value),
                label + ": early selected pair/value")

        conflicts = [(i,s) for i,s in enumerate(lines)
                     if "[CARE2P] CONFLICT " in s]
        require(len(conflicts) == 1, label + ": conflict count")
        line_number,line = conflicts[0]
        m = re.search(
            r"seq=\s*(\d+)\s+alreadyAccepted=\s*([01])"
            r"\s+savedPair=\s*(\d+)", line)
        require(m is not None and
                (int(m[1]),int(m[2]),int(m[3])) == (1,1,winner),
                label + ": late conflict state")
        require(touch[0] < line_number,
                label + ": conflict did not follow acceptance")

    results.append({
        "test": label, "verdict": "PASS",
        "simulator_exit": r.returncode,
        "first_pair": winner,
        "first_value": None if value is None else hex(value),
        "log": str(log)
    })
    (out/"summary.json").write_text(json.dumps(results,indent=2)+"\n")
    print(label.upper()+"=PASS", flush=True)

print("CARE2P_LATE_CONFLICT_3TESTS=PASS", flush=True)
print("RESULT_DIRECTORY=" + str(out), flush=True)
