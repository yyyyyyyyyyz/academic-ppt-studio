"""CLI Script: Audit an existing .pptx against Academic PPT Design v4.0 hard gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.qa.audit_pptx import audit_pptx
from app.schemas.deck_spec import DeckSpec


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit .pptx against zero-fill, >=18pt, XML fonts, and figure gates.")
    parser.add_argument("--pptx", required=True, help="Path to .pptx file")
    parser.add_argument("--spec", default=None, help="Optional DeckSpec JSON for figure QA score validation")
    args = parser.parse_args()

    deck = DeckSpec.model_validate_json(Path(args.spec).read_text(encoding="utf-8")) if args.spec else None
    report = audit_pptx(args.pptx, deck_spec=deck)
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
