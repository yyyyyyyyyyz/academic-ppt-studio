"""CLI Script: Compile a DeckSpec v4.0 JSON to 100% Native Editable .pptx + Previews + Audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.builder.ppt_core import compile_deck_to_pptx
from app.figure_factory.factory import ScientificFigureFactory
from app.qa.audit_pptx import audit_pptx
from app.qa.slide_renderer import render_deck_previews
from app.schemas.deck_spec import DeckSpec


def main() -> int:
    parser = argparse.ArgumentParser(description="Build & audit native editable PPTX from DeckSpec v4.0 JSON.")
    parser.add_argument("--spec", required=True, help="Path to DeckSpec JSON file")
    parser.add_argument("--out", required=True, help="Output .pptx path")
    parser.add_argument("--previews", default=None, help="Optional directory to save slide preview PNGs")
    args = parser.parse_args()

    deck = DeckSpec.model_validate_json(Path(args.spec).read_text(encoding="utf-8"))
    factory = ScientificFigureFactory()
    work_dir = Path(args.out).parent / "figures"

    for slide in deck.slides:
        if slide.figure_spec:
            factory.render_figure_spec(
                slide.figure_spec,
                output_dir=work_dir / f"slide_{slide.slide_no:02d}",
                palette_id=deck.meta.palette_id,
                is_proposal=deck.meta.is_proposal,
            )

    pptx_path = compile_deck_to_pptx(deck, args.out)
    report = audit_pptx(pptx_path, deck_spec=deck)
    if args.previews:
        render_deck_previews(deck, args.previews, pptx_path=pptx_path)

    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
