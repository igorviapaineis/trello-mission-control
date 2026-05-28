"""Shared test helpers.

Adds the scripts/ directory to sys.path so tests can import the CLI modules
as plain Python modules without invoking them as subprocesses.
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
