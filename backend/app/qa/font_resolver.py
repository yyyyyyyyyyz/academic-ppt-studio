"""Cross-platform PIL & Matplotlib font resolution (Windows Fonts + Linux Noto CJK / Liberation)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from PIL import ImageFont

MATPLOTLIB_CJK_SANS: List[str] = [
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "WenQuanYi Zen Hei",
    "SimHei",
    "Arial",
    "Liberation Sans",
    "DejaVu Sans",
]

_FONT_SEARCH_DIRS: List[Path] = [
    Path(r"C:\Windows\Fonts"),
    Path("/usr/share/fonts/opentype/noto"),
    Path("/usr/share/fonts/truetype/noto"),
    Path("/usr/share/fonts/truetype/wqy"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts"),
]


@lru_cache(maxsize=64)
def _find_font_file(filename: str) -> str | None:
    for root in _FONT_SEARCH_DIRS:
        if not root.exists():
            continue
        direct = root / filename
        if direct.is_file():
            return str(direct)
    for root in _FONT_SEARCH_DIRS:
        if not root.exists():
            continue
        try:
            for hit in root.rglob(filename):
                if hit.is_file():
                    return str(hit)
        except OSError:
            continue
    return None


@lru_cache(maxsize=256)
def _load_cached_font(path_str: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path_str, size=size_px)


def resolve_pil_font(
    size_px: int,
    *,
    is_cjk: bool,
    bold: bool = False,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
) -> ImageFont.FreeTypeFont:
    """Resolve a TrueType font cleanly on both Windows and Linux Docker environments."""
    px = max(10, int(size_px))
    if is_cjk:
        if "宋" in ea_font or "SimSun" in ea_font:
            cands = [
                "simsun.ttc",
                "NotoSerifCJK-Regular.ttc",
                "NotoSansCJK-Regular.ttc",
                "NotoSansSC-Regular.otf",
                "wqy-zenhei.ttc",
                "msyh.ttc",
            ]
        elif bold:
            cands = [
                "msyhbd.ttc",
                "msyh.ttc",
                "NotoSansCJK-Bold.ttc",
                "NotoSansSC-Bold.otf",
                "NotoSansCJK-Regular.ttc",
                "wqy-zenhei.ttc",
                "wqy-microhei.ttc",
            ]
        else:
            cands = [
                "msyh.ttc",
                "msyhbd.ttc",
                "NotoSansCJK-Regular.ttc",
                "NotoSansSC-Regular.otf",
                "wqy-zenhei.ttc",
                "wqy-microhei.ttc",
            ]
    else:
        if "Times" in latin_font:
            cands = (
                ["timesbd.ttf", "times.ttf", "LiberationSerif-Bold.ttf", "DejaVuSerif-Bold.ttf", "arialbd.ttf"]
                if bold
                else ["times.ttf", "arial.ttf", "LiberationSerif-Regular.ttf", "DejaVuSerif.ttf"]
            )
        else:
            cands = (
                ["arialbd.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", "msyhbd.ttc", "NotoSansCJK-Bold.ttc"]
                if bold
                else ["arial.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf", "msyh.ttc", "NotoSansCJK-Regular.ttc"]
            )

    for fn in cands:
        found = _find_font_file(fn)
        if found:
            try:
                return _load_cached_font(found, px)
            except Exception:
                continue
    return ImageFont.load_default()
