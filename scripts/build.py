"""Run every asset build step before a deploy:  python scripts/build.py"""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for step in ("build_sold.py", "build_cross.py"):
    sys.argv = [step]
    try:
        runpy.run_path(str(HERE / step), run_name="__main__")
    except SystemExit as e:
        if e.code:
            raise
