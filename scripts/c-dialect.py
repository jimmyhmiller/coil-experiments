#!/usr/bin/env python3
import pathlib, shutil, subprocess, tempfile, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
CASES=[ROOT/'tests/c/fib.c']
with tempfile.TemporaryDirectory() as td:
  td=pathlib.Path(td)
  for src in CASES:
    generated=subprocess.run(['python3',str(ROOT/'src/dialects/c/c_ast_to_coil.py'),str(src)],cwd=ROOT,capture_output=True,text=True,check=True).stdout
    assert '(module c_program)' in generated and 'ast-dump' not in generated
    print(f'{src.name}: translated {len(generated)} bytes')
    clang=td/(src.stem+'-clang'); subprocess.run(['clang','-O2',str(src),'-o',clang],check=True)
    t=time.perf_counter(); p=subprocess.run([clang]); elapsed=time.perf_counter()-t
    print(f'  clang -O2: exit={p.returncode} size={clang.stat().st_size} run={elapsed*1000:.2f}ms')
    coil=shutil.which('coil')
    if coil:
      native=td/(src.stem+'-coil')
      b=subprocess.run([coil,'build',str(src),'--use','experiments.c.lang','-o',native],cwd=ROOT,capture_output=True,text=True)
      if b.returncode: raise SystemExit(b.stderr or b.stdout)
      t=time.perf_counter(); p=subprocess.run([native]); elapsed=time.perf_counter()-t
      print(f'  Coil native: exit={p.returncode} size={native.stat().st_size} run={elapsed*1000:.2f}ms')
    else: print('  Coil native: skipped (coil not on PATH)')
