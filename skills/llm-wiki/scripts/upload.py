#!/usr/bin/env python3
"""兼容入口：转发到 wiki.py upload / kbs list。"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

args = sys.argv[1:]
if "--list-kbs" in args:
    rest = [a for a in args if a != "--list-kbs"]
    sys.argv = [sys.argv[0], "kbs", "list", *rest]
else:
    sys.argv = [sys.argv[0], "upload", *args]

runpy.run_path(str(Path(__file__).with_name("wiki.py")), run_name="__main__")
