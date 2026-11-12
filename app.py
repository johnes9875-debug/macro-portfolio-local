"""Streamlit entry point.

Run the dashboard file fresh on every Streamlit rerun. A plain
`from macro_portfolio.dashboard import *` only executes on the first run
(Python caches imported modules), so any click left a blank page.
"""
import runpy
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

runpy.run_path(str(_SRC / "macro_portfolio" / "dashboard.py"), run_name="__main__")
