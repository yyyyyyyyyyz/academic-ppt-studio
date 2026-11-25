"""Engine 5: VectorMechanismEngine — Exact Bitangents, Sunburst Reviews, Dual Cycles & Roadmaps.

Produces both structured vector instructions (for native editable python-pptx AutoShapes)
and crisp 600 DPI preview PNGs with unified dark-navy geometric scientific icons.
"""

from __future__ import annotations

from ..config import bootstrap_matplotlib_env

bootstrap_matplotlib_env()

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from PIL import Image, ImageDraw

from .icon_library import render_icon
from .palettes import ScientificPalette, blend_with_white, get_palette, hex_to_rgb


def compute_external_bitangents(
    c1: Tuple[float, float, float],
    c2: Tuple[float, float, float],
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Compute the two exact external tangent line segments between circle 1 and circle 2.

    Each circle is (cx, cy, radius). Returns [(p1_a, p2_a), (p1_b, p2_b)].
    """
    x1, y1, r1 = float(c1[0]), float(c1[1]), float(c1[2])
    x2, y2, r2 = float(c2[0]), float(c2[1]), float(c2[2])
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    if d <= abs(r1 - r2) + 1e-6:
        # Degenerate overlapping circles: fallback horizontal projections
        return [((x1, y1 - r1), (x2, y2 - r2)), ((x1, y1 + r1), (x2, y2 + r2))]

    base_angle = math.atan2(dy, dx)
    cos_a = max(-1.0, min(1.0, (r1 - r2) / d))
    alpha = math.acos(cos_a)

    tangents: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    for sign in (+1.0, -1.0):
        theta = base_angle + sign * alpha
        nx, ny = math.cos(theta), math.sin(theta)
        p1 = (x1 + r1 * nx, y1 + r1 * ny)
        p2 = (x2 + r2 * nx, y2 + r2 * ny)
        tangents.append((p1, p2))
    return tangents


def _render_sunburst_preview(
    output_png: Path,
    pal: ScientificPalette,
    data: Dict[str, Any],
    box_w_in: float,
    box_h_in: float,
    dpi: int = 300,
) -> Path:
    """A09: Concentric Sunburst or auto-switched 4-branch Pathway Hub when labels are long."""
    plt.rcParams.update({"font.sans-serif": ["Arial", "Liberation Sans", "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False})
    categories = data.get("categories", [
        {"title": "Photocatalysis", "sub": "Visible light", "icon": "light_wave"},
        {"title": "Mechanochemistry", "sub": "Solvent-free", "icon": "ball_mill"},
        {"title": "Porous Confinement", "sub": "Zeolite / MOF", "icon": "porous_hex"},
        {"title": "NMR & Operando", "sub": "Real-time probe", "icon": "nmr_spectrum"},
    ])
    center_title = data.get("center_title", "Green\nSynthesis")
    long_text = any(len(c["title"]) > 10 for c in categories)

    fig, ax = plt.subplots(figsize=(box_w_in, box_h_in), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("#FFFFFF")
    ax.set_aspect("equal")
    ax.axis("off")

    ring_cols = [
        pal.s5,
        blend_with_white(pal.series[min(1, len(pal.series) - 1)], 0.35),
        blend_with_white(pal.series[min(2, len(pal.series) - 1)], 0.35),
        blend_with_white(pal.series[min(3, len(pal.series) - 1)], 0.35),
    ]
    if pal.id == "sci_sunburst_pastel":
        ring_cols = ["#88ADDF", "#85DD84", "#F0D29A", "#DEABCC"]

    if not long_text:
        ax.set_xlim(-1.45, 1.45)
        ax.set_ylim(-1.12, 1.12)
        n = len(categories)
        step = 360.0 / max(n, 1)
        for idx, cat in enumerate(categories):
            a0 = 90.0 - idx * step
            a1 = a0 - step
            col = ring_cols[idx % len(ring_cols)]
            col_outer = blend_with_white(col, 0.42)

            # Outer ring (r 0.72 -> 1.05)
            w_out = patches.Wedge((0, 0), 1.04, a1, a0, width=0.33, facecolor=col_outer, edgecolor="#FFFFFF", linewidth=3.5)
            ax.add_patch(w_out)
            # Middle ring (r 0.36 -> 0.72)
            w_mid = patches.Wedge((0, 0), 0.71, a1, a0, width=0.34, facecolor=col, edgecolor="#FFFFFF", linewidth=3.5)
            ax.add_patch(w_mid)

            mid_ang = math.radians(0.5 * (a0 + a1))
            tx_m, ty_m = 0.53 * math.cos(mid_ang), 0.53 * math.sin(mid_ang)
            tx_o, ty_o = 0.88 * math.cos(mid_ang), 0.88 * math.sin(mid_ang)
            ax.text(tx_m, ty_m, cat["title"], ha="center", va="center", fontsize=14.0, fontweight="bold", color=pal.ink)
            ax.text(tx_o, ty_o, cat.get("sub", ""), ha="center", va="center", fontsize=14.0, color=pal.ink)

        # Crisp white core
        core = patches.Circle((0, 0), 0.36, facecolor="#FFFFFF", edgecolor=pal.s1, linewidth=2.6, zorder=6)
        ax.add_patch(core)
        ax.text(0, 0, center_title, ha="center", va="center", fontsize=15.0, fontweight="bold", color=pal.s1, zorder=7)
    else:
        # Auto-switched Center Circle + 4 Arc Ribbons + 4 Rounded Pathway Nodes
        ax.set_xlim(-2.25, 2.25)
        ax.set_ylim(-1.24, 1.24)
        positions = [(-1.38, 0.62), (1.38, 0.62), (-1.38, -0.62), (1.38, -0.62)]
        for idx, (cat, (px, py)) in enumerate(zip(categories[:4], positions)):
            col = ring_cols[idx % len(ring_cols)]
            ax.annotate("", xy=(px * 0.56, py * 0.66), xytext=(0, 0), arrowprops=dict(arrowstyle="->", lw=2.8, color=col, connectionstyle="arc3,rad=0.18"))
            card = patches.FancyBboxPatch((px - 0.78, py - 0.34), 1.56, 0.68, boxstyle="round,pad=0.05,rounding_size=0.12", facecolor=blend_with_white(col, 0.55), edgecolor=pal.s1, lw=1.6)
            ax.add_patch(card)
            ax.text(px, py + 0.10, cat["title"], ha="center", va="center", fontsize=14.0, fontweight="bold", color=pal.ink)
            ax.text(px, py - 0.16, cat.get("sub", ""), ha="center", va="center", fontsize=14.0, color=pal.muted)
        core = patches.Circle((0, 0), 0.42, facecolor="#FFFFFF", edgecolor=pal.s1, linewidth=3.0, zorder=6)
        ax.add_patch(core)
        ax.text(0, 0, center_title, ha="center", va="center", fontsize=15.0, fontweight="bold", color=pal.s1, zorder=7)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_png), dpi=dpi, transparent=True)
    plt.close(fig)
    return output_png


def _render_dual_cycle_preview(
    output_png: Path,
    pal: ScientificPalette,
    data: Dict[str, Any],
    box_w_in: float,
    box_h_in: float,
    dpi: int = 300,
) -> Path:
    """A10 dual_cycle: Coupled Dual Catalytic Loops with HOMO/LUMO & intermediate hub."""
    plt.rcParams.update({"font.sans-serif": ["Arial", "Liberation Sans", "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(box_w_in, box_h_in), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(-2.75, 2.75)
    ax.set_ylim(-1.35, 1.35)
    ax.set_aspect("equal")
    ax.axis("off")

    # Left cycle (Cycle I) & Right cycle (Cycle II) cleanly separated from center hub and outer entry/exit
    c_left, c_right, r = (-1.12, 0.0), (1.12, 0.0), 0.78
    for (cx, cy), col, title in ((c_left, pal.s2, "Cycle I\nActivation"), (c_right, pal.s1, "Cycle II\nC-N Coupling")):
        circ = patches.Circle((cx, cy), r, facecolor="none", edgecolor=col, linewidth=3.0, linestyle="-")
        ax.add_patch(circ)
        # Directional arrow tips on top and bottom arcs
        ax.annotate("", xy=(cx + 0.12, cy + r), xytext=(cx - 0.12, cy + r), arrowprops=dict(arrowstyle="->", lw=2.6, color=col))
        ax.annotate("", xy=(cx - 0.12, cy - r), xytext=(cx + 0.12, cy - r), arrowprops=dict(arrowstyle="->", lw=2.6, color=col))
        lbl_x = cx - 0.14 if cx < 0 else cx + 0.14
        ax.text(lbl_x, cy, title, ha="center", va="center", fontsize=14.0, fontweight="bold", color=col)

    # Shared center intermediate hub
    hub = patches.FancyBboxPatch((-0.48, -0.25), 0.96, 0.50, boxstyle="round,pad=0.04,rounding_size=0.14", facecolor=pal.s6, edgecolor=pal.s1, lw=2.2, zorder=5)
    ax.add_patch(hub)
    ax.text(0.0, 0.0, data.get("center_species", "[M-L$_n$] Int."), ha="center", va="center", fontsize=14.0, fontweight="bold", color=pal.s1, zorder=6)

    # External entry/exit arrows so labels never collide with ring interior text
    ax.annotate("", xy=(-1.90, 0.0), xytext=(-2.25, 0.0), arrowprops=dict(arrowstyle="->", lw=2.2, color=pal.ink))
    ax.annotate("", xy=(2.25, 0.0), xytext=(1.90, 0.0), arrowprops=dict(arrowstyle="->", lw=2.2, color=pal.alert))

    nodes = [
        (-2.28, 0.24, data.get("left_entry", "Substrate + hν"), pal.ink, "center"),
        (-1.12, 1.04, data.get("top_left", "SET / HAA"), pal.s2, "center"),
        (1.12, 1.04, data.get("top_right", "Red. Elim."), pal.s1, "center"),
        (2.30, 0.24, data.get("right_exit", "Target API"), pal.alert, "center"),
        (-1.12, -1.06, data.get("bot_left", "HOMO → LUMO"), pal.muted, "center"),
        (1.12, -1.06, data.get("bot_right", "Regeneration"), pal.muted, "center"),
    ]
    for nx, ny, lbl, col, ha_val in nodes:
        ax.text(nx, ny, lbl, ha=ha_val, va="center", fontsize=14.0, fontweight="bold", color=col,
                bbox=dict(boxstyle="round,pad=0.18", facecolor="#FFFFFF", edgecolor="none"))

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_png), dpi=dpi, transparent=True)
    plt.close(fig)
    return output_png


def _render_roadmap_4stage_preview(
    output_png: Path,
    pal: ScientificPalette,
    data: Dict[str, Any],
    box_w_in: float,
    box_h_in: float,
    dpi: int = 300,
) -> Path:
    """A10 roadmap_4stage: 4-Stage Closed-Loop Technical Roadmap with unified icons."""
    plt.rcParams.update({"font.sans-serif": ["Arial", "Liberation Sans", "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False})
    stages = data.get("stages", [
        {"num": "01", "title": "Pain Point", "sub": "Solvent-free goal", "icon": "prohibited_flask"},
        {"num": "02", "title": "Mechanochem.", "sub": "High-energy shear", "icon": "ball_mill"},
        {"num": "03", "title": "Confinement", "sub": "Porous synergy", "icon": "porous_hex"},
        {"num": "04", "title": "Validation", "sub": "NMR & kinetics", "icon": "nmr_spectrum"},
    ])
    tmp_icons_dir = output_png.parent / "_icons"
    fig, ax = plt.subplots(figsize=(box_w_in, box_h_in), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 12.0)
    ax.set_ylim(0, 4.6)
    ax.axis("off")

    xs = [1.5, 4.5, 7.5, 10.5]
    for idx, (st, x) in enumerate(zip(stages[:4], xs)):
        icon_path = render_icon(st.get("icon", "flask"), tmp_icons_dir / f"{st.get('icon', 'flask')}_{pal.id}.png", palette_id=pal.id, size_px=140)
        icon_arr = np.array(Image.open(icon_path))

        # Top badge
        badge = patches.FancyBboxPatch((x - 0.36, 3.65), 0.72, 0.42, boxstyle="round,pad=0.04,rounding_size=0.14", facecolor=pal.s1, edgecolor="none")
        ax.add_patch(badge)
        ax.text(x, 3.86, st["num"], ha="center", va="center", fontsize=14.0, fontweight="bold", color="#FFFFFF")

        # Icon image inset
        ax.imshow(icon_arr, extent=(x - 0.78, x + 0.78, 1.95, 3.51), zorder=4)

        # Native underline + minimal text (NO filled box!)
        ax.plot([x - 0.95, x + 0.95], [1.72, 1.72], color=pal.s1, lw=2.0)
        ax.text(x, 1.32, st["title"], ha="center", va="center", fontsize=14.5, fontweight="bold", color=pal.ink)
        ax.text(x, 0.86, st.get("sub", ""), ha="center", va="center", fontsize=14.0, color=pal.muted)

        if idx < 3:
            ax.annotate("", xy=(xs[idx + 1] - 1.0, 2.75), xytext=(x + 1.0, 2.75),
                        arrowprops=dict(arrowstyle="->", lw=2.4, color=pal.s2))

    # Closed-loop feedback arc underneath
    ax.annotate(
        "", xy=(1.5, 0.42), xytext=(10.5, 0.42),
        arrowprops=dict(arrowstyle="->", lw=1.8, linestyle="--", color=pal.s3, connectionstyle="arc3,rad=0.10"),
    )
    ax.text(6.0, 0.14, "Closed-Loop Iteration & Scale-Up", ha="center", va="center", fontsize=14.0, fontweight="bold", color=pal.s2)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_png), dpi=dpi, transparent=True)
    plt.close(fig)
    return output_png


def _render_gap_quadrant_preview(
    output_png: Path,
    pal: ScientificPalette,
    data: Dict[str, Any],
    box_w_in: float,
    box_h_in: float,
    dpi: int = 300,
) -> Path:
    """A10 gap_quadrant: 2D Research Gap Quadrant + Target Innovation Bullseye."""
    plt.rcParams.update({"font.sans-serif": ["Arial", "Liberation Sans", "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(box_w_in, box_h_in), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axhline(5.0, color=pal.line, lw=1.4, ls="--")
    ax.axvline(5.0, color=pal.line, lw=1.4, ls="--")

    # Top-right innovation advantage zone
    zone = patches.FancyBboxPatch((5.2, 5.2), 4.5, 4.4, boxstyle="round,pad=0.1,rounding_size=0.4", facecolor=pal.s6, edgecolor=pal.s3, lw=1.5, ls="--", alpha=0.65)
    ax.add_patch(zone)

    # Prior literature clusters
    for lx, ly, lbl in ((2.3, 2.6, "Thermal\nBatch"), (3.1, 7.2, "High-Dilution\nSolvent"), (7.1, 2.8, "Unstable\nNanocatalyst")):
        ax.scatter([lx], [ly], s=260, facecolor="#E2E8F0", edgecolor=pal.muted, lw=1.6, zorder=3)
        ax.text(lx, ly - 1.15, lbl, ha="center", va="top", fontsize=14.0, color=pal.muted)

    # Bullseye Target
    tx, ty = 7.6, 7.6
    for rad, alpha in ((0.95, 0.25), (0.60, 0.45), (0.30, 0.95)):
        ax.add_patch(patches.Circle((tx, ty), rad, facecolor=pal.s1, edgecolor="none", alpha=alpha, zorder=4))
    ax.text(tx, ty - 1.3, data.get("target_label", "This Work\n(Target Zone)"), ha="center", va="top", fontsize=14.5, fontweight="bold", color=pal.s1)

    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("bottom", "left"):
        ax.spines[sp].set_linewidth(1.5)
        ax.spines[sp].set_color(pal.ink)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel(data.get("xlabel", "Process Greenness & Atom Economy →"), fontsize=14.5, fontweight="bold", color=pal.ink, labelpad=8)
    ax.set_ylabel(data.get("ylabel", "Catalytic Activity & Stability →"), fontsize=14.5, fontweight="bold", color=pal.ink, labelpad=8)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_png), dpi=dpi, transparent=True)
    plt.close(fig)
    return output_png


def _render_delta_g_concept_preview(
    output_png: Path,
    pal: ScientificPalette,
    data: Dict[str, Any],
    box_w_in: float,
    box_h_in: float,
    dpi: int = 300,
) -> Path:
    """A10 delta_g_concept: Conceptual Free-Energy Barrier Reduction (Unassisted vs Tri-synergy)."""
    plt.rcParams.update({"font.sans-serif": ["Arial", "Liberation Sans", "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(box_w_in, box_h_in), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("#FFFFFF")

    x = np.linspace(0.0, 1.0, 240)
    y_unassisted = 0.28 + 0.65 * np.exp(-((x - 0.48) / 0.19) ** 2) - 0.14 * x
    y_synergy = 0.28 + 0.24 * np.exp(-((x - 0.48) / 0.24) ** 2) - 0.22 * x

    ax.plot(x, y_unassisted, color=pal.muted, lw=2.5, ls="--")
    ax.plot(x, y_synergy, color=pal.s1, lw=3.5)
    ax.fill_between(x, y_synergy, y_unassisted, color=pal.s5, alpha=0.38)

    p_un = float(y_unassisted.max())
    p_sy = float(y_synergy.max())
    ax.annotate("", xy=(0.48, p_sy), xytext=(0.48, p_un), arrowprops=dict(arrowstyle="<->", color=pal.alert, lw=2.2))
    ax.text(0.51, 0.5 * (p_un + p_sy), r"$\Delta\Delta G^\ddagger$ Lowered", fontsize=14.5, fontweight="bold", color=pal.alert, va="center")
    ax.text(0.24, p_un + 0.03, "Unassisted", fontsize=14.0, color=pal.muted, ha="center")
    ax.text(0.75, y_synergy[180] + 0.09, "Tri-Synergy", fontsize=14.5, fontweight="bold", color=pal.s1, ha="center")

    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("bottom", "left"):
        ax.spines[sp].set_linewidth(1.5)
        ax.spines[sp].set_color(pal.ink)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_ylim(0.0, 1.08)
    ax.set_xlabel("Reaction Coordinate →", fontsize=14.5, fontweight="bold", color=pal.ink, labelpad=8)
    ax.set_ylabel("Free Energy ($G$) →", fontsize=14.5, fontweight="bold", color=pal.ink, labelpad=8)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_png), dpi=dpi, transparent=True)
    plt.close(fig)
    return output_png


def _render_pd_coupling_cycle_preview(
    output_png: Path,
    pal: ScientificPalette,
    data: Dict[str, Any],
    box_w_in: float,
    box_h_in: float,
    dpi: int = 300,
) -> Path:
    """Publication-grade Pd(0)/Pd(II) Buchwald-Hartwig C-N Catalytic Coupling Cycle."""
    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "SimHei", "Arial", "Liberation Sans", "DejaVu Sans"], "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(box_w_in, box_h_in), dpi=dpi)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(-2.45, 2.45)
    ax.set_ylim(-1.60, 1.52)
    ax.set_aspect("equal")
    ax.axis("off")

    # Central circular catalytic cycle segments (clockwise arcs)
    r = 0.88
    for deg_s, deg_e, col in ((62, -14, pal.s1), (-50, -130, pal.alert), (-166, -242, pal.s1)):
        t_arr = np.linspace(math.radians(deg_s), math.radians(deg_e), 48)
        ax.plot(r * np.cos(t_arr), r * np.sin(t_arr), color=col, lw=2.6, solid_capstyle="round", zorder=2)
        end_a = math.radians(deg_e)
        prev_a = math.radians(deg_e + 6)
        ax.annotate(
            "",
            xy=(r * math.cos(end_a), r * math.sin(end_a)),
            xytext=(r * math.cos(prev_a), r * math.sin(prev_a)),
            arrowprops=dict(arrowstyle="-|>,head_width=0.32,head_length=0.45", lw=2.4, color=col),
            zorder=3,
        )

    # 3 pure-white intermediate cards around the ring
    nodes = [
        (0.0, 0.94, data.get("top_species", "Pd(0)L$_n$"), pal.s1, 1.24, 0.40),
        (1.06, -0.48, data.get("right_species", "Ar–Pd(II)–X"), pal.alert, 1.56, 0.40),
        (-1.06, -0.48, data.get("left_species", "Ar–Pd(II)–NHR"), pal.s1, 1.66, 0.40),
    ]
    for nx, ny, lbl, bcol, bw, bh in nodes:
        card = patches.FancyBboxPatch(
            (nx - bw * 0.5, ny - bh * 0.5), bw, bh,
            boxstyle="round,pad=0.03,rounding_size=0.10",
            facecolor="#FFFFFF", edgecolor=bcol, lw=1.8, zorder=5,
        )
        ax.add_patch(card)
        ax.text(nx, ny, lbl, ha="center", va="center", fontsize=12.5, fontweight="bold", color=pal.ink, zorder=6)

    # Center catalytic hub label
    ax.text(0.0, 0.14, "Pd(0) / Pd(II)", ha="center", va="center", fontsize=13.0, fontweight="bold", color=pal.s1)
    ax.text(0.0, -0.08, "C–N 催化循环", ha="center", va="center", fontsize=12.0, color=pal.muted)

    # External reaction arrows & step annotations
    # 1) Top-right entry: Ar-X (Oxidative Addition)
    ax.annotate("", xy=(0.82, 0.44), xytext=(1.46, 0.88), arrowprops=dict(arrowstyle="-|>", lw=2.0, color=pal.alert, connectionstyle="arc3,rad=-0.18"), zorder=4)
    ax.text(1.58, 1.00, "Ar–X", ha="center", va="center", fontsize=12.5, fontweight="bold", color=pal.alert, bbox=dict(boxstyle="round,pad=0.14", facecolor="#FFFFFF", edgecolor="none"))
    ax.text(1.72, 0.40, "1. 氧化加成", ha="center", va="center", fontsize=12.0, fontweight="bold", color=pal.s1)

    # 2) Bottom: R-NH2 + Base -> Base*HX
    ax.annotate("", xy=(-0.08, -0.88), xytext=(0.14, -1.28), arrowprops=dict(arrowstyle="-|>", lw=1.8, color=pal.muted, connectionstyle="arc3,rad=0.18"), zorder=4)
    ax.text(0.0, -1.40, "R–NH$_2$ + Base  →  Base·HX", ha="center", va="center", fontsize=12.0, fontweight="bold", color=pal.ink, bbox=dict(boxstyle="round,pad=0.14", facecolor="#FFFFFF", edgecolor="none"))
    ax.text(0.0, -0.96, "2. 胺配位 / 脱质子", ha="center", va="center", fontsize=11.5, color=pal.muted)

    # 3) Top-left exit: Ar-NHR (Reductive Elimination)
    ax.annotate("", xy=(-1.46, 0.88), xytext=(-0.82, 0.44), arrowprops=dict(arrowstyle="-|>", lw=2.2, color=pal.s1, connectionstyle="arc3,rad=0.18"), zorder=4)
    ax.text(-1.58, 1.00, "Ar–NHR", ha="center", va="center", fontsize=12.5, fontweight="bold", color=pal.s1, bbox=dict(boxstyle="round,pad=0.16", facecolor="#FFFFFF", edgecolor=pal.s1, lw=1.1))
    ax.text(-1.72, 0.40, "3. 还原消除", ha="center", va="center", fontsize=12.0, fontweight="bold", color=pal.s1)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_png), dpi=dpi, transparent=True)
    plt.close(fig)
    return output_png


def _render_molecular_3d_pathway_preview(
    output_png: Path,
    pal: ScientificPalette,
    data: Dict[str, Any],
    w_in: float,
    h_in: float,
    dpi: int,
) -> Path:
    """Image-3 style 3D ball-and-stick + vector reaction pathway with dashed zoom enclosure & CPK atom legend."""
    from matplotlib.offsetbox import AnnotationBbox, OffsetImage
    from .cylview3d_engine import render_cylview3d
    from .chem_grounding import resolve_compound_smiles

    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "SimHei", "Arial", "Liberation Sans", "DejaVu Sans"], "axes.unicode_minus": False})
    fig = plt.figure(figsize=(max(w_in, 7.2), max(h_in, 4.4)), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
    ax.set_xlim(0.0, 10.0)
    ax.set_ylim(0.0, 6.2)
    ax.axis("off")

    nodes = list(data.get("nodes") or [])
    if len(nodes) < 3:
        fallback_smi = resolve_compound_smiles(str(data.get("smiles") or "Osimertinib")) or "COc1cc(N(C)CCN(C)C)c(NC(=O)C=C)cc1Nc2nccc(n2)c3cn(C)c4ccccc34"
        nodes = [
            {"smiles": "CC(=O)OO", "label": str(data.get("reactant_label") or "Reactant / Ligand")},
            {"smiles": "O=S([O-])(=O)O", "label": str(data.get("intermediate_label") or "IM1 Complex")},
            {"smiles": fallback_smi, "label": str(data.get("product_label") or "Target Active State")},
        ]
    step_labels = list(data.get("step_labels") or ["Nucleophilic / Binding", "Intermediate State", "Product Activation"])
    top_title = str(data.get("title_top") or "Primary Pathway vs. Inhibited Route").strip()
    blocked_label = str(data.get("blocked_label") or "High-Barrier Route").strip()
    sub_box_label = str(data.get("sub_box_label") or "Concerted Reaction Microenvironment").strip()

    # Render up to 3 genuine 3D ball-and-stick conformer PNGs into temp dir next to output
    mol_tmp = output_png.parent / "_pathway_3d"
    mol_tmp.mkdir(parents=True, exist_ok=True)
    rendered_imgs: List[Tuple[Image.Image, str]] = []
    for idx, nd in enumerate(nodes[:3]):
        smi = resolve_compound_smiles(str(nd.get("smiles") or "")) or "CC(=O)O"
        res_3d = render_cylview3d(
            smiles=smi,
            output_png=mol_tmp / f"node_{idx}.png",
            palette_id=pal.id,
            target_width_px=420,
            dpi=200,
        )
        im = Image.open(res_3d.png_path).convert("RGBA")
        rendered_imgs.append((im, str(nd.get("label") or f"Species {idx + 1}")[:22]))

    # Top overview bar
    ax.text(5.0, 5.88, top_title[:42], ha="center", va="center", fontsize=12.5, fontweight="bold", color=pal.ink)
    top_l = rendered_imgs[0]
    top_r = rendered_imgs[-1]
    for xpos, (im, lbl) in [(2.1, top_l), (7.9, top_r)]:
        oi = OffsetImage(np.asarray(im), zoom=0.14)
        ax.add_artist(AnnotationBbox(oi, (xpos, 5.25), frameon=False, zorder=5))
        ax.text(xpos, 4.62, lbl, ha="center", va="center", fontsize=11.0, fontweight="bold", color=pal.ink)

    # Blocked upper route + orange cross, lower active route
    ax.annotate("", xy=(6.35, 5.38), xytext=(3.65, 5.38),
                arrowprops=dict(arrowstyle="-|>,head_width=0.28,head_length=0.4", lw=2.2, color=pal.s1, connectionstyle="arc3,rad=-0.22"), zorder=4)
    ax.text(5.0, 5.56, "×", ha="center", va="center", fontsize=18.0, fontweight="bold", color=pal.alert, zorder=6)
    ax.text(5.0, 5.14, blocked_label[:24], ha="center", va="center", fontsize=10.5, color=pal.muted)
    ax.annotate("", xy=(6.35, 4.92), xytext=(3.65, 4.92),
                arrowprops=dict(arrowstyle="-|>,head_width=0.28,head_length=0.4", lw=2.2, color=pal.s1, connectionstyle="arc3,rad=0.20"), zorder=4)

    # Zoom-in dashed crimson connectors from main arrow to large bottom dashed enclosure
    ax.plot([4.3, 0.65], [4.75, 4.02], "--", color=pal.alert, lw=1.4, zorder=2)
    ax.plot([5.7, 9.35], [4.75, 4.02], "--", color=pal.alert, lw=1.4, zorder=2)

    enclosure = patches.FancyBboxPatch(
        (0.35, 0.35), 9.30, 3.68,
        boxstyle="round,pad=0.05,rounding_size=0.22",
        facecolor=blend_with_white("#FFFFFF", 0.0), edgecolor=pal.alert, lw=1.6, linestyle="--", zorder=1,
    )
    ax.add_patch(enclosure)
    ax.text(5.0, 4.18, sub_box_label[:38], ha="center", va="center", fontsize=12.0, fontweight="bold", color=pal.ink)

    # Place 3 detailed 3D ball-and-stick nodes inside the dashed mechanism box
    xs_pos = [1.85, 5.00, 8.15]
    for idx, (xpos, (im, lbl)) in enumerate(zip(xs_pos, rendered_imgs)):
        if idx == 1:
            sub_box = patches.FancyBboxPatch(
                (xpos - 1.38, 1.05), 2.76, 2.55,
                boxstyle="round,pad=0.03,rounding_size=0.14",
                facecolor=blend_with_white(pal.s5, 0.55), edgecolor=pal.s2, lw=1.3, linestyle="--", zorder=2,
            )
            ax.add_patch(sub_box)
        oi = OffsetImage(np.asarray(im), zoom=0.22)
        ax.add_artist(AnnotationBbox(oi, (xpos, 2.45), frameon=False, zorder=5))
        ax.text(xpos, 1.28, lbl, ha="center", va="center", fontsize=11.5, fontweight="bold", color=pal.ink, zorder=6)

    # Curved blue mechanistic step arrows between 3D intermediates
    for idx in range(len(rendered_imgs) - 1):
        x0, x1 = xs_pos[idx] + 0.95, xs_pos[idx + 1] - 0.95
        ax.annotate("", xy=(x1, 2.45), xytext=(x0, 2.45),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.32,head_length=0.45", lw=2.5, color=pal.s1, connectionstyle="arc3,rad=-0.12"), zorder=6)
        stxt = str(step_labels[idx] if idx < len(step_labels) else f"Step {idx + 1}")[:20]
        ax.text(0.5 * (x0 + x1), 2.95, stxt, ha="center", va="center", fontsize=11.0, fontweight="bold", color=pal.alert, zorder=7)

    # Bottom-left CPK atom legend (H, C, N, O, S) matching Image 3
    cpk_items = [("#E5E7EB", "H"), ("#6B7280", "C"), (pal.s1, "N"), ("#DC2626", "O"), ("#D97706", "S")]
    for l_idx, (col_hex, sym) in enumerate(cpk_items):
        lx = 0.78 + l_idx * 0.92
        circ = patches.Circle((lx, 0.68), 0.14, facecolor=col_hex, edgecolor=pal.ink, lw=0.8, zorder=6)
        ax.add_patch(circ)
        ax.text(lx + 0.24, 0.68, sym, ha="left", va="center", fontsize=11.0, fontweight="bold", color=pal.ink, zorder=6)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_png), dpi=dpi, transparent=True)
    plt.close(fig)
    return output_png


def render_vector_mechanism(
    mech_mode: str,
    output_png: Path | str,
    palette_id: str = "lancet",
    mech_data: Optional[Dict[str, Any]] = None,
    box_width_in: float = 7.75,
    box_height_in: float = 4.42,
    dpi: int = 300,
) -> Path:
    """Render any VectorMechanismEngine mode (A09 sunburst / A10 cycles, roadmap_4stage, gap_quadrant, delta_g_concept, molecular_3d_pathway)."""
    pal = get_palette(palette_id)
    out_p = Path(output_png)
    data = mech_data or {}

    mode = (mech_mode or "dual_cycle").strip().lower()
    if mode == "molecular_3d_pathway":
        return _render_molecular_3d_pathway_preview(out_p, pal, data, box_width_in, box_height_in, dpi)
    if mode == "sunburst_pathway":
        return _render_sunburst_preview(out_p, pal, data, box_width_in, box_height_in, dpi)
    if mode == "roadmap_4stage":
        return _render_roadmap_4stage_preview(out_p, pal, data, box_width_in, box_height_in, dpi)
    if mode == "gap_quadrant":
        return _render_gap_quadrant_preview(out_p, pal, data, box_width_in, box_height_in, dpi)
    if mode == "delta_g_concept":
        return _render_delta_g_concept_preview(out_p, pal, data, box_width_in, box_height_in, dpi)
    if mode == "pd_coupling_cycle":
        return _render_pd_coupling_cycle_preview(out_p, pal, data, box_width_in, box_height_in, dpi)
    return _render_dual_cycle_preview(out_p, pal, data, box_width_in, box_height_in, dpi)
