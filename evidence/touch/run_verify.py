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

assert sim.is_file(), "SIMULATOR_MISSING"
for case in range(3):
    assert (tests/f"build/case{case}.elf").is_file()

results = []
def require(ok, message):
    if not ok:
        raise SystemExit("CARE2P_VERIFY_FAIL: " + message)

def execute(label, case=0, inject=0, hold=0, cycles=0,
            expected_error=None, expected_winner=None):
    print("=== " + label + " ===", flush=True)
    log = out/f"{label}.run.log"
    with log.open("x") as stream:
        r = subprocess.run([
            str(sim), "+permissive", "+verbose",
            "+max-cycles=2000000",
            f"+care_inject={inject}",
            f"+care_hold_pair={hold}",
            f"+care_hold_cycles={cycles}",
            "+permissive-off", str(tests/f"build/case{case}.elf")
        ], cwd=simdir, stdout=stream, stderr=subprocess.STDOUT)

    text = log.read_text(errors="replace")
    lines = text.splitlines()
    care = [s for s in lines
            if "[CARE2P]" in s or "[CARE2P-INJECT]" in s]
    for line in care:
        print(line, flush=True)

    require(not re.search(
        r"\[CARE2P\] (INPUT_ERROR|ALIGNMENT_ERROR|END_ERROR|SOURCE_FAULT)",
        text), label + ": unrelated hardware failure; " + str(log))

    injections = [s for s in lines if "[CARE2P-INJECT]" in s]
    expected_harts = (
        [] if inject == 0 else
        [inject-1] if inject <= 4 else
        [0,1] if inject == 5 else [0,2]
    )
    require(len(injections) == len(expected_harts),
            label + ": injection count")
    for h in expected_harts:
        hits = [s for s in injections
                if re.search(rf"hart=\s*{h}\s+seq=\s*1\b", s)]
        require(len(hits) == 1, label + ": injected hart/sequence")
        m = re.search(
            r"original=([0-9a-fA-F]+)\s+flipped=([0-9a-fA-F]+)",
            hits[0])
        require(m is not None and
                (int(m[1],16),int(m[2],16)) == (0x12,0x13),
                label + ": injected value")

    touches = []
    for line in lines:
        if "[CARE2P] TOUCH" not in line:
            continue
        m = re.search(
            r"tick=\s*(\d+)\s+seq=\s*(\d+)\s+pair=\s*(\d+)"
            r"\s+otherReady=\s*(\d+)\s+data=([0-9a-fA-F]+)", line)
        require(m is not None, label + ": TOUCH format")
        touches.append(tuple(int(m[i],16 if i == 5 else 10)
                             for i in range(1,6)))

    if expected_error:
        require(r.returncode != 0 and
                "CARE2P observation failed" in text,
                label + ": expected assertion absent")
        require("[CARE2P] HARDWARE_PASS" not in text and
                "*** PASSED ***" not in text and
                "[CARE2P] PASS " not in text,
                label + ": unexpected completion")
        errors = [s for s in lines
                  if f"[CARE2P] {expected_error} " in s]
        require(len(errors) == 1 and
                re.search(r"seq=\s*1\b", errors[0]),
                label + ": expected error/sequence")
        other_error = "NO_AGREEMENT" if expected_error == "CONFLICT" else "CONFLICT"
        require(f"[CARE2P] {other_error} " not in text,
                label + ": unexpected failure classification")
        if expected_error == "NO_AGREEMENT":
            require(not any(t[1] == 1 for t in touches),
                    label + ": accepted a record without agreement")
        else:
            m = re.search(r"alreadyAccepted=\s*([01])", errors[0])
            require(m is not None, label + ": conflict timing absent")
            print("CONFLICT_ALREADY_ACCEPTED=" + m[1], flush=True)
    else:
        if r.returncode or "*** PASSED ***" not in text:
            print("\n".join(lines[-35:]))
            raise SystemExit(label + ": simulation failed")
        require(not re.search(r"Assertion failed|%Error|%Fatal", text),
                label + ": simulator error")
        require("[CARE2P] CONFLICT " not in text and
                "[CARE2P] NO_AGREEMENT " not in text,
                label + ": unexpected conflict")
        passes = [s for s in lines if "[CARE2P] PASS " in s]
        hardware = [s for s in lines if "[CARE2P] HARDWARE_PASS " in s]
        require(len(passes) == len(hardware) == 1,
                label + ": completion count")
        m = re.search(
            r"accepted=\s*(\d+)\s+settled=\s*(\d+)"
            r"\s+wins=\s*(\d+),\s*(\d+)\s+early=\s*(\d+)",
            passes[0])
        require(m is not None, label + ": PASS format")
        accepted, settled, w0, w1, early = map(int,m.groups())
        require(accepted == settled == w0+w1 == 3074,
                label + ": accepted/settled/win counters")
        require(re.search(r"records=\s*3074\b", hardware[0]),
                label + ": hardware record count")
        require(len(touches) == 2 and
                sorted(t[1] for t in touches) == [0,1],
                label + ": duplicate/missing first TOUCH records")

        if expected_winner is not None:
            first = next(t for t in touches if t[1] == 0)
            require(first[2] == expected_winner and first[3] == 0 and early > 0,
                    label + ": expected early pair did not win")
        if inject in (1,2,3,4):
            target = next(t for t in touches if t[1] == 1)
            winner = 1 if inject in (1,2) else 0
            require(target[2] == winner and target[4] == 0x12,
                    label + ": healthy pair/value selection")

        with log.open("a") as stream:
            stream.write("\nCARE2P_SOFTWARE_EXIT=0\n")
        subprocess.run([
            sys.executable, str(tests/"check_log.py"), str(case), str(log),
            "--metrics", str(out/f"{label}.metrics.json")
        ], check=True)

    results.append({
        "test": label, "case": case, "inject": inject,
        "hold_pair": hold, "hold_cycles": cycles,
        "expected_error": expected_error,
        "simulator_exit": r.returncode, "verdict": "PASS",
        "log": str(log)
    })
    (out/"summary.json").write_text(json.dumps(results,indent=2)+"\n")
    print(label.upper()+"=PASS", flush=True)

for case in range(3):
    execute(f"case{case}_normal", case=case)

# Delay pair comparison readiness, not the physical cores.
execute("ab_first_cd_held", hold=2, cycles=96, expected_winner=0)
execute("cd_first_ab_held", hold=1, cycles=96, expected_winner=1)

for h in range(4):
    execute(f"single_corruption_hart{h}", inject=h+1)

# Both members of AB produce the same corrupted observation.
execute("agreeing_pairs_conflict", inject=5, expected_error="CONFLICT")

# Each pair has one corrupted member: neither pair qualifies.
execute("both_pairs_disagree", inject=6, expected_error="NO_AGREEMENT")

print("CARE2P_TOUCH_11TESTS=PASS", flush=True)
print("RESULT_DIRECTORY=" + str(out), flush=True)
