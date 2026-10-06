"""Run the whole pipeline in order: python run_all.py [first_step]"""
import subprocess
import sys
from pathlib import Path

STEPS = sorted((Path(__file__).parent / "scripts").glob("[0-9][0-9]_*.py"))
start = sys.argv[1] if len(sys.argv) > 1 else "00"
for step in STEPS:
    if step.name[:2] >= start:
        print(f"=== {step.name} ===", flush=True)
        if subprocess.run([sys.executable, str(step)]).returncode:
            sys.exit(f"stopped: {step.name} failed")
