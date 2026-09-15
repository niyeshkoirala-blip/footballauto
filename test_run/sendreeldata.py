#!/usr/bin/env python3
"""Run the root Reel URL setup test from inside test_run/."""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "sendreeldata.py"), run_name="__main__")
