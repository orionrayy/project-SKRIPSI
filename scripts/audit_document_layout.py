#!/usr/bin/env python3
"""Run the Project-SKRIPSI DOCX/PDF layout audit from a source checkout."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project_skripsi.document_layout_qa import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
