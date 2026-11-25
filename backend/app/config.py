"""Centralized configuration and Matplotlib/Temp bootstrap for Academic PPT Design Studio."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


def bootstrap_matplotlib_env() -> Path:
    """Ensure Matplotlib has a writable cache directory before pyplot import."""
    mpl_dir = Path(tempfile.gettempdir()) / "mpl_academic_ppt"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))
    return mpl_dir


bootstrap_matplotlib_env()


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
SKILL_ROOT = REPO_ROOT / "skill"
ARTIFACTS_ROOT = Path(os.environ.get("ACADEMIC_PPT_ARTIFACTS_DIR", str(REPO_ROOT / "artifacts")))
DECKS_ROOT = ARTIFACTS_ROOT / "decks"
GALLERY_ROOT = ARTIFACTS_ROOT / "archetype_gallery"
DEMO_DECK_ROOT = ARTIFACTS_ROOT / "demo_deck"


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    repo_root: Path = REPO_ROOT
    artifacts_root: Path = ARTIFACTS_ROOT
    decks_root: Path = DECKS_ROOT
    gallery_root: Path = GALLERY_ROOT
    demo_deck_root: Path = DEMO_DECK_ROOT
    skill_root: Path = SKILL_ROOT

    # Provider configuration: auto | gemini | openai | local
    figure_provider_mode: str = os.environ.get("FIGURE_PROVIDER_MODE", "auto").strip().lower()
    llm_provider_mode: str = os.environ.get("LLM_PROVIDER_MODE", "auto").strip().lower()

    # Gemini
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    gemini_text_model: str = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
    gemini_image_model: str = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp-image-generation")

    # OpenAI-compatible
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    openai_base_url: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    openai_text_model: str = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    openai_image_model: str = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")

    # Local Windows fonts
    windows_fonts_dir: Path = Path(r"C:\Windows\Fonts")


def get_settings(ensure_dirs: bool = False) -> Settings:
    """Return active runtime settings; optionally create artifact directories."""
    settings = Settings()
    if ensure_dirs:
        for p in (settings.artifacts_root, settings.decks_root, settings.gallery_root, settings.demo_deck_root):
            p.mkdir(parents=True, exist_ok=True)
    return settings
