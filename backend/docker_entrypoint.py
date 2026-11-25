"""Cloud Container Entrypoint & Showcase Bootstrapper for Academic PPT Design Studio.

Ensures the curated Nature Editorial showcase plates exist locally (built in-process from
skill/scripts/build_nature_editorial_showcase.py when missing after a clean Git checkout),
then starts the single-port FastAPI server on 0.0.0.0:$PORT.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.agents.qa_agent import SlideVisualQAAgent
from app.config import Settings, get_settings
from app.figure_factory.factory import ScientificFigureFactory


def ensure_showcase_artifacts(artifacts_root: Path | None = None) -> bool:
    """Build curated Nature Editorial showcase plates in-process if not already present."""
    base_settings = get_settings(ensure_dirs=False)
    root = Path(artifacts_root) if artifacts_root is not None else base_settings.artifacts_root
    target_dir = root / "decks" / "nature_editorial_showcase"
    previews_dir = target_dir / "previews"

    expected = [previews_dir / f"slide_{i:02d}.png" for i in range(1, 5)]
    if all(p.is_file() and p.stat().st_size > 10_000 for p in expected) and (target_dir / "nature_editorial_showcase.pptx").is_file():
        return False

    from build_nature_editorial_showcase import build_spec

    deck = build_spec()
    run_settings = Settings(
        repo_root=REPO_ROOT,
        artifacts_root=root,
        decks_root=root / "decks",
        gallery_root=root / "archetype_gallery",
        demo_deck_root=root / "demo_deck",
        skill_root=REPO_ROOT / "skill",
        figure_provider_mode="local",
        llm_provider_mode="local",
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    qa_agent = SlideVisualQAAgent(factory=ScientificFigureFactory(settings=run_settings))
    pptx_path, report, _ = qa_agent.build_and_verify(deck, target_dir, max_rounds=2)
    (target_dir / "deck_spec.json").write_text(deck.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
    if not report.passed or not pptx_path.exists():
        raise RuntimeError(f"Failed to bootstrap showcase deck: {report.violations}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Academic Studio showcase & launch Uvicorn.")
    parser.add_argument("--init-only", action="store_true", help="Pre-build showcase artifacts and exit.")
    args = parser.parse_args()

    ensure_showcase_artifacts()
    if args.init_only:
        return 0

    import uvicorn

    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
