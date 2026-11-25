"""Standard MCP Server exposing Academic PPT Design Studio v4.0 Tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

try:
    from mcp.server.mcpserver import MCPServer as _MCPServer
except ImportError:  # mcp < 2.0 fallback
    from mcp.server.fastmcp import FastMCP as _MCPServer  # type: ignore

from .agents.art_director_agent import build_default_figure_spec
from .agents.planner_agent import PlannerAgent
from .agents.qa_agent import SlideVisualQAAgent
from .builder.word_sync import sync_word_into_pptx
from .config import get_settings
from .figure_factory.factory import ScientificFigureFactory
from .figure_factory.palettes import list_palettes
from .qa.audit_pptx import audit_pptx
from .schemas.deck_spec import ArchetypeId, DeckSpec, ScenarioType


mcp = _MCPServer("academic-ppt-design")


@mcp.tool()
def list_palettes_and_archetypes() -> str:
    """List all 15 publication color palettes and 10 scientific figure archetypes (A01–A10)."""
    return json.dumps(
        {
            "palettes": [{"id": p["id"], "name": p["name"], "series": p["series"]} for p in list_palettes()],
            "archetypes": [a.value for a in ArchetypeId],
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def plan_academic_deck(
    source_text: str,
    target_slide_count: int = 10,
    palette_id: str = "lancet",
    scenario: str = "defense",
    is_proposal: bool = False,
    deck_title: Optional[str] = None,
) -> str:
    """Parse scientific text or outline into a validated DeckSpec v4.0 JSON with per-slide figure specs."""
    planner = PlannerAgent()
    deck = planner.plan_deck(
        source_text=source_text,
        deck_title=deck_title,
        scenario=ScenarioType(scenario),
        target_slide_count=target_slide_count,
        palette_id=palette_id,
        is_proposal=is_proposal,
    )
    return deck.model_dump_json(by_alias=True, indent=2)


@mcp.tool()
def generate_scientific_figure(
    archetype: str = "A01_cutaway_reactor_zoom",
    palette_id: str = "lancet",
    slide_no: int = 1,
    smiles: Optional[str] = None,
    origin_preset: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """Generate and QA-score (Best-of-N + Alpha matting + OCR zero-text) a single slide scientific figure."""
    settings = get_settings(ensure_dirs=True)
    out = Path(output_dir) if output_dir else settings.artifacts_root / "mcp_figures" / f"slide_{slide_no:02d}"
    fspec = build_default_figure_spec(
        archetype=ArchetypeId(archetype),
        slide_no=slide_no,
        palette_id=palette_id,
        smiles=smiles,
        origin_preset=origin_preset,
    )
    factory = ScientificFigureFactory(settings=settings)
    rendered = factory.render_figure_spec(fspec, out, palette_id=palette_id, best_of_n=2)
    return rendered.model_dump_json(indent=2)


@mcp.tool()
def build_and_audit_pptx(deck_spec_json: str, output_dir: Optional[str] = None) -> str:
    """Render all DeckSpec v4.0 figures, compile native editable .pptx, generate previews, and run audit_pptx."""
    settings = get_settings(ensure_dirs=True)
    deck = DeckSpec.model_validate_json(deck_spec_json)
    out = Path(output_dir) if output_dir else settings.decks_root / deck.meta.deck_id
    qa_agent = SlideVisualQAAgent(factory=ScientificFigureFactory(settings=settings))
    pptx_p, report, previews = qa_agent.build_and_verify(deck, out)
    return json.dumps(
        {
            "pptx_path": str(pptx_p),
            "preview_count": len(previews),
            "audit_report": report.model_dump(),
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def audit_existing_pptx(pptx_path: str, deck_spec_json: Optional[str] = None) -> str:
    """Audit an existing .pptx against zero-fill frameless, >=18pt, XML font, and figure quality gates."""
    deck = DeckSpec.model_validate_json(deck_spec_json) if deck_spec_json else None
    report = audit_pptx(pptx_path, deck_spec=deck)
    return report.model_dump_json(indent=2)


@mcp.tool()
def sync_word_to_pptx(docx_path: str, input_pptx: str, output_pptx: str) -> str:
    """Sync updated Word (.docx) prose into an existing .pptx at XML run level, preserving styles."""
    res = sync_word_into_pptx(docx_path, input_pptx, output_pptx)
    return json.dumps(res, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
