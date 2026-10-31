"""Shared pytest configuration.

Pins the environment so help widths, colors, and app-dir lookups are stable, and
makes clirelay importable from ``src`` without an editable install.
"""
from __future__ import annotations

import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# A fixed, reproducible environment for every comparison.
os.environ["COLUMNS"] = "80"
os.environ["LINES"] = "24"
os.environ["TERM"] = "xterm"
os.environ.setdefault("HOME", os.path.expanduser("~"))
os.environ["XDG_CONFIG_HOME"] = os.path.join(os.environ["HOME"], ".config")
os.environ["XDG_DATA_HOME"] = os.path.join(os.environ["HOME"], ".local", "share")
os.environ["XDG_CACHE_HOME"] = os.path.join(os.environ["HOME"], ".cache")
os.environ.pop("NO_COLOR", None)
os.environ.pop("FORCE_COLOR", None)
