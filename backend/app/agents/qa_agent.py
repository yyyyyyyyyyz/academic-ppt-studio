"""Slide Visual QA Agent — Runs audit_pptx + Previews & Auto-Patches DeckSpec JSON (up to 2 rounds)."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from ..builder.ppt_core import compile_deck_to_pptx
from ..figure_factory.factory import ScientificFigureFactory
from ..qa.audit_pptx import audit_pptx
from ..qa.slide_renderer import render_deck_previews
from ..schemas.deck_spec import AuditReport, DeckSpec, SlideType


class SlideVisualQAAgent:
    """Performs post-compilation visual + programmatic audit and repairs recoverable violations."""

    def __init__(self, factory: ScientificFigureFactory | None = None) -> None:
        self.factory = factory or ScientificFigureFactory()

    def build_and_verify(
        self,
        deck: DeckSpec,
        output_dir: Path | str,
        max_rounds: int = 2,
    ) -> Tuple[Path, AuditReport, list[Path]]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pptx_path = out_dir / f"{deck.meta.deck_id}.pptx"
        previews_dir = out_dir / "previews"
        figs_dir = out_dir / "figures"

        # Render any unrendered slide figures
        fonts = deck.locked_standards.fonts
        for slide in deck.slides:
            if slide.figure_spec and any(not a.png_path or not Path(a.png_path).exists() for a in slide.figure_spec.assets):
                self.factory.render_figure_spec(
                    slide.figure_spec,
                    output_dir=figs_dir / f"slide_{slide.slide_no:02d}",
                    palette_id=deck.meta.palette_id,
                    is_proposal=deck.meta.is_proposal,
                    fonts=fonts,
                )

        report: AuditReport | None = None
        for _ in range(max_rounds):
            compile_deck_to_pptx(deck, pptx_path)
            report = audit_pptx(pptx_path, deck_spec=deck)
            if report.passed:
                break

            # Auto-repair recoverable violations in DeckSpec
            for v in report.violations:
                if v.slide_no <= len(deck.slides):
                    sl = deck.slides[v.slide_no - 1]
                    if v.rule == "overlap":
                        sl.takeaway = sl.takeaway[:36]
                        sl.insights = sl.insights[:2]
                    elif v.rule in ("every_content_slide_has_figure", "figure_qa_score") and sl.slide_type == SlideType.content:
                        if sl.figure_spec:
                            self.factory.render_figure_spec(
                                sl.figure_spec,
                                output_dir=figs_dir / f"slide_{sl.slide_no:02d}",
                                palette_id=deck.meta.palette_id,
                                is_proposal=deck.meta.is_proposal,
                                fonts=fonts,
                            )

        assert report is not None
        previews = render_deck_previews(deck, previews_dir, pptx_path=pptx_path)
        return pptx_path, report, previews
