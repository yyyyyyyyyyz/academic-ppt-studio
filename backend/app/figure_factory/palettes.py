"""15 Publication-Grade Scientific Color Palettes & 3D Material Prompt Mappings.

All HEX codes match Spec Section 4.2 verbatim, with unified global semantic tokens
(s1..s6, ink, muted, line, alert) driving python-pptx frames and all 5 figure engines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ScientificPalette:
    id: str
    name: str
    category: str
    description: str
    series: List[str]
    s1: str
    s2: str
    s3: str
    s4: str
    s5: str
    s6: str
    ink: str = "#162032"
    muted: str = "#475569"
    line: str = "#D8E2EC"
    alert: str = "#AD002A"
    material_prompt_terms: str = ""

    def token(self, name: str) -> str:
        mapping = {
            "s1": self.s1,
            "s2": self.s2,
            "s3": self.s3,
            "s4": self.s4,
            "s5": self.s5,
            "s6": self.s6,
            "ink": self.ink,
            "muted": self.muted,
            "line": self.line,
            "alert": self.alert,
        }
        return mapping.get(name, self.s1)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "series": self.series,
            "tokens": {
                "s1": self.s1,
                "s2": self.s2,
                "s3": self.s3,
                "s4": self.s4,
                "s5": self.s5,
                "s6": self.s6,
                "ink": self.ink,
                "muted": self.muted,
                "line": self.line,
                "alert": self.alert,
            },
            "material_prompt_terms": self.material_prompt_terms,
        }


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (0, 70, 139)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def hex_to_rgb_norm(hex_color: str) -> Tuple[float, float, float]:
    r, g, b = hex_to_rgb(hex_color)
    return (r / 255.0, g / 255.0, b / 255.0)


def blend_with_white(hex_color: str, factor: float) -> str:
    """Blend hex_color toward #FFFFFF (factor=0 -> original, factor=1 -> white)."""
    r, g, b = hex_to_rgb(hex_color)
    nr = int(round(r + (255 - r) * factor))
    ng = int(round(g + (255 - g) * factor))
    nb = int(round(b + (255 - b) * factor))
    return f"#{nr:02X}{ng:02X}{nb:02X}"


def darken_hex(hex_color: str, factor: float) -> str:
    """Blend hex_color toward #000000 (factor=0 -> original, factor=1 -> black)."""
    r, g, b = hex_to_rgb(hex_color)
    nr = max(0, int(round(r * (1.0 - factor))))
    ng = max(0, int(round(g * (1.0 - factor))))
    nb = max(0, int(round(b * (1.0 - factor))))
    return f"#{nr:02X}{ng:02X}{nb:02X}"


PALETTES: Dict[str, ScientificPalette] = {
    "lancet": ScientificPalette(
        id="lancet",
        name="Lancet · 深海蓝（默认）",
        category="High-Impact Journal",
        description="柳叶刀权威深海蓝单色系梯度，适合医药合成、反应工程与答辩汇报主视觉",
        series=["#00468B", "#1A5F9E", "#3F80BC", "#72A6D5", "#B2D0EB", "#EAF2FA"],
        s1="#00468B",
        s2="#1A5F9E",
        s3="#3F80BC",
        s4="#72A6D5",
        s5="#B2D0EB",
        s6="#EAF2FA",
        alert="#AD002A",
        material_prompt_terms=(
            "deep cobalt sapphire metallic catalyst spheres (#00468B), translucent ice-blue borosilicate glass "
            "and porous zeolite framework (#72A6D5 / #B2D0EB), soft frosted sky-tint accents (#EAF2FA)"
        ),
    ),
    "cell": ScientificPalette(
        id="cell",
        name="Cell · 清透蓝",
        category="High-Impact Journal",
        description="Cell Press 清透科研发蓝渐变，适合化学生物学、分子识别与微流控界面",
        series=["#1F77B4", "#3D8CC2", "#62A4D1", "#8BBDE0", "#B7D7EE", "#E8F3FB"],
        s1="#1F77B4",
        s2="#3D8CC2",
        s3="#62A4D1",
        s4="#8BBDE0",
        s5="#B7D7EE",
        s6="#E8F3FB",
        alert="#D62728",
        material_prompt_terms=(
            "crisp cerulean blue satin catalyst particles (#1F77B4), clear aquatic blue glass shell (#62A4D1), "
            "pale mist translucent porous matrix (#B7D7EE / #E8F3FB)"
        ),
    ),
    "nature": ScientificPalette(
        id="nature",
        name="Nature · 朱红橙",
        category="High-Impact Journal",
        description="Nature 朱红暖橙主阶配中性灰炭黑，适合光热/能量转换、靶向递送与机制突破",
        series=["#C83E2B", "#E64B35", "#F07B63", "#F5A38C", "#F7CBB9", "#B8B8B8", "#262626"],
        s1="#C83E2B",
        s2="#E64B35",
        s3="#F07B63",
        s4="#F5A38C",
        s5="#F7CBB9",
        s6="#FDEEE9",
        alert="#00468B",
        material_prompt_terms=(
            "terracotta vermilion satin nanoparticles (#C83E2B / #E64B35), warm coral ceramic substrate (#F07B63), "
            "matte graphite spheres (#262626) and cool neutral light-gray support (#B8B8B8)"
        ),
    ),
    "science": ScientificPalette(
        id="science",
        name="Science · 典雅紫",
        category="High-Impact Journal",
        description="Science 典雅紫罗兰色阶，适合配位化学、超分子组装与计算化学/ML",
        series=["#332288", "#594A9E", "#8274B8", "#B1A6D4", "#DDD8EE", "#B8B8B8", "#262626"],
        s1="#332288",
        s2="#594A9E",
        s3="#8274B8",
        s4="#B1A6D4",
        s5="#DDD8EE",
        s6="#F2EFF9",
        alert="#C83E2B",
        material_prompt_terms=(
            "royal indigo-violet metallic core (#332288 / #594A9E), lavender translucent crystal cage (#8274B8 / #B1A6D4), "
            "soft lilac frosted highlights (#DDD8EE) with matte dark charcoal anchors (#262626)"
        ),
    ),
    "nejm": ScientificPalette(
        id="nejm",
        name="NEJM · 赤陶红",
        category="High-Impact Journal",
        description="新英格兰医学杂志醇厚赤陶红阶，适合临床前药理、药代动力学与生物医药转化",
        series=["#9E2F1E", "#BC3C29", "#CE5742", "#DD7864", "#EA9C8B", "#F4C2B6"],
        s1="#9E2F1E",
        s2="#BC3C29",
        s3="#CE5742",
        s4="#DD7864",
        s5="#EA9C8B",
        s6="#FBECE8",
        alert="#1F4E78",
        material_prompt_terms=(
            "crimson garnet satin spheres (#9E2F1E / #BC3C29), salmon pastel ceramic capsules (#DD7864), "
            "translucent rose quartz porous scaffold (#F4C2B6)"
        ),
    ),
    "wong": ScientificPalette(
        id="wong",
        name="Wong · 琥珀橙",
        category="High-Impact Journal",
        description="Nature Methods Wong 色盲安全琥珀明橙阶，适合压电/光催化与对比度要求高的现场答辩",
        series=["#B07300", "#E69F00", "#EBAD24", "#F0BC4A", "#F5CC73", "#F9DDA0"],
        s1="#B07300",
        s2="#E69F00",
        s3="#EBAD24",
        s4="#F0BC4A",
        s5="#F5CC73",
        s6="#FDF4DE",
        alert="#0072B2",
        material_prompt_terms=(
            "amber gold metallic nanoparticles (#B07300 / #E69F00), warm honey translucent crystal cube (#F0BC4A), "
            "pale champagne frosted glass (#F9DDA0) paired with cool slate-blue accents"
        ),
    ),
    "viridis": ScientificPalette(
        id="viridis",
        name="Viridis · 紫青绿",
        category="High-Impact Journal",
        description="感知均匀紫-青-翠绿连续色谱，适合热图、DFT 电子密度与机器学习预测分布",
        series=["#440154", "#3B528B", "#21918C", "#5EC962", "#FDE725"],
        s1="#3B528B",
        s2="#21918C",
        s3="#440154",
        s4="#5EC962",
        s5="#BEEAD0",
        s6="#EAF7F5",
        alert="#C83E2B",
        material_prompt_terms=(
            "deep indigo (#440154) and oceanic teal (#21918C) satin nanospheres, emerald gradient highlights (#5EC962), "
            "subtle luminous warm-gold active center (#FDE725)"
        ),
    ),
    "diverging": ScientificPalette(
        id="diverging",
        name="RdBu · 红白蓝",
        category="High-Impact Journal",
        description="ColorBrewer RdBu 双极发散带，适合正负对照、结合能升降与机理前后对比",
        series=["#67001F", "#B2182B", "#F4A582", "#F7F7F7", "#92C5DE", "#2166AC", "#053061"],
        s1="#053061",
        s2="#2166AC",
        s3="#92C5DE",
        s4="#F4A582",
        s5="#D6E8F5",
        s6="#EEF5FB",
        alert="#B2182B",
        material_prompt_terms=(
            "polar navy blue (#053061 / #2166AC) innovative catalyst side contrasting against warm coral-red (#B2182B / #F4A582) "
            "conventional side on pure crisp frosted glass (#F7F7F7)"
        ),
    ),
    "medical_gray": ScientificPalette(
        id="medical_gray",
        name="Editorial · 中性灰",
        category="High-Impact Journal",
        description="极简黑白灰高定出版风，适合电镜图衬托、理论公式与极端克制的数据对比",
        series=["#262626", "#4D4D4D", "#737373", "#999999", "#BDBDBD", "#D9D9D9"],
        s1="#262626",
        s2="#4D4D4D",
        s3="#737373",
        s4="#999999",
        s5="#D9D9D9",
        s6="#F1F3F5",
        alert="#AD002A",
        material_prompt_terms=(
            "monochrome platinum and brushed graphite spheres (#262626 / #737373), smoked crystal glass (#BDBDBD), "
            "ultra-clean matte alabaster ceramic (#D9D9D9)"
        ),
    ),
    "immunology": ScientificPalette(
        id="immunology",
        name="Immunology · 翠绿紫",
        category="High-Impact Journal",
        description="Nature Immunology 翠绿-薰衣草紫对冲平衡带，适合绿色化学减废与生物医学双通路",
        series=["#1B7837", "#4D9221", "#A1D76A", "#F7F7F7", "#AF8DC3", "#542788"],
        s1="#1B7837",
        s2="#542788",
        s3="#4D9221",
        s4="#AF8DC3",
        s5="#DDF2CA",
        s6="#EEF8E6",
        alert="#9E2F1E",
        material_prompt_terms=(
            "forest emerald green (#1B7837 / #4D9221) sustainable spheres paired with royal amethyst purple (#542788 / #AF8DC3) "
            "and fresh mint frosted glass (#A1D76A)"
        ),
    ),
    "sci_morandi_catalysis": ScientificPalette(
        id="sci_morandi_catalysis",
        name="催化 · 莫兰迪青",
        category="SCI Measured",
        description="高引表面催化多组对照柔雅莫兰迪 9 色，耐看不刺眼且多系列区分度极高",
        series=["#81C9D3", "#B8D09E", "#EC7576", "#D3D3D3", "#BDA4D1", "#BCBC7F", "#89B687", "#E7CB8D", "#F0904D"],
        s1="#2E7D8B",  # darkened anchor derived from #81C9D3 for >=4.5:1 slide heading legibility
        s2="#81C9D3",
        s3="#89B687",
        s4="#BDA4D1",
        s5="#D3E8EC",
        s6="#EEF7F9",
        alert="#EC7576",
        material_prompt_terms=(
            "Morandi soft teal-cyan porous framework (#81C9D3), sage green ceramic spheres (#B8D09E / #89B687), "
            "dusty coral (#EC7576) and muted lavender (#BDA4D1) substrate capsules"
        ),
    ),
    "sci_angew_blue_orange": ScientificPalette(
        id="sci_angew_blue_orange",
        name="Angew · 冰蓝珊瑚",
        category="SCI Measured",
        description="Angew. Chem. 经典冰蓝 vs 珊瑚橙双通路对照，适合正负反应机制与对照组实验组硬切分屏",
        series=["#3A80DA", "#ADDFFF", "#F1673D", "#FBD9DA", "#BBBCBC"],
        s1="#3A80DA",
        s2="#F1673D",
        s3="#5C9CE6",
        s4="#ADDFFF",
        s5="#DCEEFF",
        s6="#EEF6FF",
        alert="#F1673D",
        material_prompt_terms=(
            "bright sapphire blue (#3A80DA) active sites and icy sky-blue translucent cage (#ADDFFF) "
            "contrasting with vivid coral-orange (#F1673D) and soft blush tint (#FBD9DA)"
        ),
    ),
    "sci_high_entropy_echem": ScientificPalette(
        id="sci_high_entropy_echem",
        name="电化学 · 碧青粉",
        category="SCI Measured",
        description="高熵合金/电催化多联图专用清爽 9 色，LSV/Tafel/稳定性 6 联排零视觉疲劳",
        series=["#6AB4DC", "#42B8B1", "#E78489", "#9ED6E2", "#D8CA77", "#E1A8BC", "#D9BDBD", "#D96E7F", "#B1DDF4"],
        s1="#287BA8",  # high-contrast anchor harmonized with #6AB4DC
        s2="#42B8B1",
        s3="#6AB4DC",
        s4="#9ED6E2",
        s5="#D5EFF6",
        s6="#EEF8FC",
        alert="#D96E7F",
        material_prompt_terms=(
            "crystalline turquoise-cyan (#42B8B1 / #6AB4DC) high-entropy alloy facets, soft ice-aqua glass (#9ED6E2 / #B1DDF4), "
            "rose-pink (#E78489) and warm gold (#D8CA77) doped atomic spheres"
        ),
    ),
    "sci_nanoconfined_xps": ScientificPalette(
        id="sci_nanoconfined_xps",
        name="XPS · 钴蓝薄荷",
        category="SCI Measured",
        description="纳米限域催化剂与 XPS 多价态半透明分峰专用 10 色",
        series=["#F1AB78", "#80C7A7", "#CBCFE9", "#C884B6", "#3D73B9", "#F3A8A8", "#C7E3F6", "#E1C4A6", "#BCCEA8", "#5EB0A2"],
        s1="#3D73B9",
        s2="#5EB0A2",
        s3="#C884B6",
        s4="#80C7A7",
        s5="#C7E3F6",
        s6="#EDF6FD",
        alert="#D9625C",
        material_prompt_terms=(
            "cobalt-blue metallic nanoclusters (#3D73B9), mint-jade (#80C7A7 / #5EB0A2) and warm peach (#F1AB78) "
            "encapsulated in frosted periwinkle porous cages (#CBCFE9 / #C7E3F6)"
        ),
    ),
    "sci_sunburst_pastel": ScientificPalette(
        id="sci_sunburst_pastel",
        name="综述 · 矢车菊柔色",
        category="SCI Measured",
        description="同心圆环综述（Sunburst）与 BioRender 通路专用高雅柔色 9 色",
        series=["#EDF4FC", "#FDEDED", "#88ADDF", "#85DD84", "#F0D29A", "#DEABCC", "#F5F7F1", "#FDF0DE", "#EFE2FA"],
        s1="#36629D",
        s2="#88ADDF",
        s3="#57AD56",
        s4="#DEABCC",
        s5="#D6E5F7",
        s6="#EDF4FC",
        alert="#C95353",
        material_prompt_terms=(
            "soft cornflower blue (#88ADDF), mint pistachio (#85DD84), champagne cream (#F0D29A), "
            "and rose-orchid pastel shells (#DEABCC) in airy white studio lighting"
        ),
    ),
}


DEFAULT_PALETTE_ID = "lancet"
_HEX6_PAT = re.compile(r"^[0-9A-Fa-f]{6}$")


def build_custom_palette(hex_primary: str, hex_alert: Optional[str] = None) -> ScientificPalette:
    """Build a harmonious 6-step academic tonal palette from any user-chosen HEX color."""
    clean = (hex_primary or "").strip().lstrip("#")
    h1 = clean.upper() if _HEX6_PAT.match(clean) else "00468B"
    raw_hex = f"#{h1}"
    r, g, b = hex_to_rgb(raw_hex)
    luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    s1 = darken_hex(raw_hex, 0.25) if luma > 0.72 else raw_hex
    s2 = blend_with_white(s1, 0.18)
    s3 = blend_with_white(s1, 0.38)
    s4 = blend_with_white(s1, 0.60)
    s5 = blend_with_white(s1, 0.80)
    s6 = blend_with_white(s1, 0.92)

    clean_alert = (hex_alert or "").strip().lstrip("#")
    if clean_alert and _HEX6_PAT.match(clean_alert):
        h2 = clean_alert.upper()
        alert = f"#{h2}"
        pid = f"custom_{h1}_{h2}"
    else:
        alert = "#00468B" if (r > 160 and r > b + 40) else "#B91C1C"
        pid = f"custom_{h1}"

    return ScientificPalette(
        id=pid,
        name=f"自定义 · #{h1}",
        category="Custom",
        description=f"基于主色 #{h1} 自动生成的 6 阶单色学术渐变配色方案",
        series=[s1, s2, s3, s4, s5, s6],
        s1=s1,
        s2=s2,
        s3=s3,
        s4=s4,
        s5=s5,
        s6=s6,
        alert=alert,
        material_prompt_terms=f"satin primary catalyst spheres ({s1} / {s2}), translucent frosted accents ({s4} / {s6})",
    )


def get_palette(palette_id: str | None = None) -> ScientificPalette:
    raw = (palette_id or DEFAULT_PALETTE_ID).strip()
    pid = raw.lower()
    if pid in PALETTES:
        return PALETTES[pid]
    if pid.startswith("custom_"):
        parts = [p for p in raw[7:].split("_") if p]
        if parts and _HEX6_PAT.match(parts[0]):
            alert_part = parts[1] if len(parts) >= 2 and _HEX6_PAT.match(parts[1]) else None
            return build_custom_palette(parts[0], alert_part)
    stripped = raw.lstrip("#")
    if _HEX6_PAT.match(stripped):
        return build_custom_palette(stripped)
    return PALETTES[DEFAULT_PALETTE_ID]


def list_palettes() -> List[Dict[str, object]]:
    return [p.to_dict() for p in PALETTES.values()]


def generate_palette_reference_card(output_path: Path | str) -> Path:
    """Render all 15 palettes into a clean 300 DPI reference card JPG."""
    from ..config import bootstrap_matplotlib_env

    bootstrap_matplotlib_env()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "Arial", "Liberation Sans", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    items = list(PALETTES.values())
    fig, ax = plt.subplots(figsize=(14, 10.5), dpi=220)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, len(items) * 6.4 + 6)
    ax.axis("off")

    ax.text(
        2, len(items) * 6.4 + 2.5,
        "Academic PPT Design Studio v4.0 — 15 Publication-Grade Scientific Color Palettes",
        fontsize=15, fontweight="bold", color="#162032", family="Arial"
    )

    top_y = len(items) * 6.4 - 1.5
    for idx, pal in enumerate(items):
        y = top_y - idx * 6.2
        ax.text(2, y + 1.8, f"{idx + 1:02d}. {pal.name} [{pal.id}]", fontsize=10.5, fontweight="bold", color=pal.s1)
        ax.text(2, y + 0.1, pal.description, fontsize=8.2, color="#475569")

        start_x = 46.0
        swatch_w = 4.6
        gap = 0.7
        for s_idx, hx in enumerate(pal.series[:10]):
            x = start_x + s_idx * (swatch_w + gap)
            rect = patches.FancyBboxPatch(
                (x, y + 0.2), swatch_w, 3.0,
                boxstyle="round,pad=0.1,rounding_size=0.35",
                facecolor=hx, edgecolor="#CBD5E1", linewidth=0.7
            )
            ax.add_patch(rect)
            ax.text(x + swatch_w / 2, y - 0.85, hx, ha="center", va="top", fontsize=6.5, color="#334155", family="Arial")

    plt.tight_layout(pad=0.8)
    fig.savefig(str(out), dpi=220, facecolor="#FFFFFF", format="jpeg")
    plt.close(fig)
    return out
