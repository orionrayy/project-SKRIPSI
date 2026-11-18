#!/usr/bin/env python3
"""Source-checkout entry point for the visual composition PDF auditor."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_skripsi.visual_composition_qa import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
