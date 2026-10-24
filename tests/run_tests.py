#!/usr/bin/env python3
import argparse,datetime,os,pathlib,shutil,subprocess,sys,time
p=argparse.ArgumentParser();p.add_argument('chipyard',type=pathlib.Path);a=p.parse_args()
chip=a.chipyard.expanduser().resolve();here=pathlib.Path(__file__).resolve().parent
sim=chip/'sims/verilator'/('simulator-chipyard.harness-'+os.environ.get('CARE2P_CONFIG','Hytron64SmallCARE2PCompareConfig'))
if not sim.is_file():raise SystemExit('SIMULATOR_MISSING: '+str(sim))
for case in range(3):
    elf=here/f'build/case{case}.elf';log=here/f'build/case{case}.run.log'
    if not elf.is_file():raise SystemExit('ELF_MISSING: '+str(elf))
    if log.exists():shutil.copyfile(log,log.with_name(log.name+'.before_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')))
    start=time.perf_counter()
    with log.open('w') as stream:
        r=subprocess.run([str(sim),'+permissive','+verbose','+max-cycles=2000000','+permissive-off',str(elf)],
            cwd=chip/'sims/verilator',stdout=stream,stderr=subprocess.STDOUT)
    elapsed=time.perf_counter()-start
    if r.returncode:
        print(f'CARE2P_CASE{case}_SIMULATOR_EXIT={r.returncode}',file=sys.stderr)
        print('\n'.join(log.read_text(errors='replace').splitlines()[-45:]),file=sys.stderr)
        raise SystemExit(1)
    with log.open('a') as stream:stream.write('\nCARE2P_SOFTWARE_EXIT=0\n')
    r=subprocess.run([sys.executable,str(here/'check_log.py'),str(case),str(log),
        '--metrics',str(here/f'build/case{case}.metrics.json'),'--host-seconds',str(elapsed)])
    if r.returncode:raise SystemExit(r.returncode)
