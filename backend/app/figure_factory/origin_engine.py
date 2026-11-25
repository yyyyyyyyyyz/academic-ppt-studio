"""Engine 3: OriginPlotEngine — 600 DPI 1:1 Physical-Size Publication Plots.

Implements 8 OriginPro-grade scientific figure presets with:
- Exact 1:1 physical figsize matching Slide box_in (600 DPI)
- Closed 4-sided axis spines, inward major + minor ticks on all 4 sides, zero gridlines
- Minimum 14 pt Arial typography + Mathtext ($...$) sub/superscripts
- Zero-overlap direct inline curve labeling or above-frame borderless legends
- Pure-NumPy spline & KDE routines (no mandatory SciPy dependency)
"""

from __future__ import annotations

from ..config import bootstrap_matplotlib_env

bootstrap_matplotlib_env()

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .palettes import ScientificPalette, blend_with_white, get_palette


def _configure_origin_rcparams(latin_font: str = "Arial", ea_font: str = "微软雅黑") -> None:
    plt.rcParams.update({
        "font.family": "sans-serif" if "Times" not in latin_font else "serif",
        "font.sans-serif": [ea_font, "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", latin_font, "Arial", "Liberation Sans", "DejaVu Sans"],
        "font.serif": [latin_font, ea_font, "Times New Roman", "Liberation Serif", "SimSun", "Noto Serif CJK SC", "DejaVu Serif"],
        "mathtext.fontset": "custom",
        "mathtext.rm": latin_font,
        "mathtext.it": f"{latin_font}:italic",
        "mathtext.bf": f"{latin_font}:bold",
        "axes.unicode_minus": False,
        "font.size": 14.0,
        "axes.titlesize": 15.0,
        "axes.labelsize": 14.0,
        "xtick.labelsize": 14.0,
        "ytick.labelsize": 14.0,
        "legend.fontsize": 14.0,
        "axes.linewidth": 0.95,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
        "xtick.minor.visible": True,
        "ytick.minor.visible": True,
        "xtick.major.size": 5.0,
        "ytick.major.size": 5.0,
        "xtick.minor.size": 2.6,
        "ytick.minor.size": 2.6,
        "xtick.major.width": 0.9,
        "ytick.major.width": 0.9,
        "xtick.minor.width": 0.65,
        "ytick.minor.width": 0.65,
        "axes.grid": False,
        "savefig.transparent": True,
    })


def _style_origin_axes(ax: plt.Axes, border_color: str = "#162032") -> None:
    ax.set_facecolor("#FFFFFF")
    ax.grid(False)
    for spine in ("top", "bottom", "left", "right"):
        ax.spines[spine].set_visible(True)
        ax.spines[spine].set_linewidth(0.95)
        ax.spines[spine].set_color(border_color)
    ax.tick_params(
        axis="both",
        which="both",
        direction="in",
        top=True,
        right=True,
        bottom=True,
        left=True,
        colors=border_color,
        labelsize=14.0,
    )


def _catmull_rom_spline(x: Sequence[float], y: Sequence[float], samples_per_seg: int = 32) -> Tuple[np.ndarray, np.ndarray]:
    """Pure-NumPy smooth shape-preserving Catmull-Rom spline interpolation."""
    xa = np.asarray(x, dtype=np.float64)
    ya = np.asarray(y, dtype=np.float64)
    if len(xa) < 3:
        return xa, ya

    x_pad = np.concatenate([[2 * xa[0] - xa[1]], xa, [2 * xa[-1] - xa[-2]]])
    y_pad = np.concatenate([[2 * ya[0] - ya[1]], ya, [2 * ya[-1] - ya[-2]]])

    xs_out: List[np.ndarray] = []
    ys_out: List[np.ndarray] = []
    t = np.linspace(0.0, 1.0, samples_per_seg, endpoint=False)
    t2 = t * t
    t3 = t2 * t

    for i in range(1, len(x_pad) - 2):
        p0x, p1x, p2x, p3x = x_pad[i - 1], x_pad[i], x_pad[i + 1], x_pad[i + 2]
        p0y, p1y, p2y, p3y = y_pad[i - 1], y_pad[i], y_pad[i + 1], y_pad[i + 2]
        qx = 0.5 * ((2 * p1x) + (-p0x + p2x) * t + (2 * p0x - 5 * p1x + 4 * p2x - p3x) * t2 + (-p0x + 3 * p1x - 3 * p2x + p3x) * t3)
        qy = 0.5 * ((2 * p1y) + (-p0y + p2y) * t + (2 * p0y - 5 * p1y + 4 * p2y - p3y) * t2 + (-p0y + 3 * p1y - 3 * p2y + p3y) * t3)
        xs_out.append(qx)
        ys_out.append(qy)

    xs_out.append(np.array([xa[-1]]))
    ys_out.append(np.array([ya[-1]]))
    return np.concatenate(xs_out), np.concatenate(ys_out)


def _gaussian_kde_1d(samples: np.ndarray, grid: np.ndarray) -> np.ndarray:
    n = len(samples)
    if n < 2:
        return np.zeros_like(grid)
    std = float(np.std(samples))
    bw = max(1.06 * std * (n ** -0.2), 1e-3)
    diffs = (grid[:, None] - samples[None, :]) / bw
    density = np.mean(np.exp(-0.5 * diffs * diffs), axis=1) / (bw * np.sqrt(2.0 * np.pi))
    return density


def _gaussian_peak(x: np.ndarray, center: float, height: float, fwhm: float) -> np.ndarray:
    sigma = max(fwhm / 2.35482, 1e-3)
    return height * np.exp(-0.5 * ((x - center) / sigma) ** 2)


# ---------------------------------------------------------------------------
# 8 Publication Presets
# ---------------------------------------------------------------------------

def _plot_kinetics_spline(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    ax = fig.add_axes([0.13, 0.16, 0.72, 0.76])
    _style_origin_axes(ax, palette.ink)

    x = data.get("x", [0, 10, 20, 30, 45, 60, 90, 120])
    series_list = data.get("series", [
        {"name": "Catalyst A", "y": [0, 28, 56, 76, 89, 94, 96, 96], "marker": "o", "hollow": False, "color": palette.s1},
        {"name": "Bulk Control", "y": [0, 14, 29, 41, 52, 60, 66, 68], "marker": "s", "hollow": True, "color": palette.s3},
        {"name": "Blank", "y": [0, 4, 8, 12, 16, 19, 22, 24], "marker": "^", "hollow": True, "color": palette.muted},
    ])

    y_all: List[float] = []
    for idx, s in enumerate(series_list):
        col = s.get("color") or ([palette.s1, palette.s3, palette.muted, palette.alert][idx % 4])
        sy = s["y"]
        y_all.extend(sy)
        sx_smooth, sy_smooth = _catmull_rom_spline(x, sy)
        lw = 2.4 if idx == 0 else 1.8
        ls = "-" if idx == 0 else ("--" if idx == 1 else ":")
        ax.plot(sx_smooth, sy_smooth, color=col, linewidth=lw, linestyle=ls, zorder=3 - idx * 0.2)

        hollow = bool(s.get("hollow", idx > 0))
        ax.plot(
            x, sy,
            linestyle="none",
            marker=s.get("marker", "o"),
            markersize=7.5,
            markerfacecolor="#FFFFFF" if hollow else col,
            markeredgecolor=col,
            markeredgewidth=1.6,
            zorder=4,
        )
        # Direct curve-end inline label (zero legend box overlap)
        ax.text(
            x[-1] + (max(x) - min(x)) * 0.025,
            sy[-1],
            s["name"],
            color=col,
            fontsize=14.0,
            fontweight="bold" if idx == 0 else "normal",
            va="center",
            ha="left",
            clip_on=False,
        )

    # Peak / gain arrow annotation
    top_y = series_list[0]["y"]
    peak_idx = int(np.argmax(top_y))
    peak_x, peak_val = x[peak_idx], top_y[peak_idx]
    ax.annotate(
        data.get("peak_note", f"{peak_val:.0f}% in {x[4]} min"),
        xy=(x[min(4, len(x) - 1)], top_y[min(4, len(top_y) - 1)]),
        xytext=(x[min(2, len(x) - 1)], max(y_all) * 1.01 if max(y_all) < 92 else 101),
        fontsize=14.0,
        fontweight="bold",
        color=palette.s1,
        arrowprops=dict(arrowstyle="->", color=palette.s1, lw=1.4, shrinkA=2, shrinkB=4),
        ha="center",
    )

    ax.set_xlim(min(x) - 4, max(x) + 6)
    ax.set_ylim(-4, max(108, max(y_all) * 1.14))
    ax.set_xlabel(data.get("xlabel", "Reaction Time (min)"), fontsize=14.0, fontweight="bold", color=palette.ink)
    ax.set_ylabel(data.get("ylabel", "Yield (%)"), fontsize=14.0, fontweight="bold", color=palette.ink)


def _plot_paired_gain_bar(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    ax = fig.add_axes([0.13, 0.16, 0.83, 0.68])
    ax.set_facecolor("#FFFFFF")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_visible(True)
        ax.spines[sp].set_linewidth(1.1)
        ax.spines[sp].set_color("#334155")
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color="#E8EEF5", linewidth=0.75, zorder=0)
    ax.xaxis.grid(False)
    ax.tick_params(axis="both", which="major", direction="out", top=False, right=False, length=4.5, width=1.0, colors="#334155", labelsize=14.0)
    ax.tick_params(axis="both", which="minor", top=False, right=False, left=False, bottom=False)

    categories = data.get("categories", ["Aryl-Cl", "Aryl-Br", "Heteroaryl", "Alkyl"])
    fmt_cats = [str(c).replace("Fa×Fg", r"$\mathrm{F_a\times F_g}$") for c in categories]
    ctrl_vals = data.get("control", [42.0, 62.4, 48.5, 51.0])
    work_vals = data.get("this_work", [87.5, 91.2, 86.0, 84.5])
    ctrl_label = data.get("control_label", "Conventional")
    work_label = data.get("work_label", "This Work")

    x = np.arange(len(categories), dtype=np.float64)
    w = 0.32

    bars_c = ax.bar(
        x - w / 2 - 0.015, ctrl_vals, width=w,
        facecolor="#CFE0F5",
        edgecolor="#4A7BB0", linewidth=1.0, hatch="///",
        label=ctrl_label, zorder=3,
    )
    bars_w = ax.bar(
        x + w / 2 + 0.015, work_vals, width=w,
        facecolor=palette.s1, edgecolor="#002F61", linewidth=0.9,
        label=work_label, zorder=3,
    )

    max_v = max(max(ctrl_vals), max(work_vals), 1.0)
    deltas_in = data.get("deltas")
    for i, (bc, bw) in enumerate(zip(bars_c, bars_w)):
        vc, vw = ctrl_vals[i], work_vals[i]
        ax.text(bc.get_x() + w / 2, vc + max_v * 0.025, f"{vc:.1f}", ha="center", va="bottom", fontsize=14.0, color="#475569", zorder=4)
        ax.text(bw.get_x() + w / 2, vw + max_v * 0.025, f"{vw:.1f}", ha="center", va="bottom", fontsize=14.0, fontweight="bold", color=palette.s1, zorder=4)
        rel = vw - vc
        sign = "+" if rel >= 0 else ""
        delta_txt = (deltas_in[i] if deltas_in and i < len(deltas_in) else None) or f"{sign}{rel:.1f}%"
        ax.text(
            x[i], max(vc, vw) + max_v * 0.19,
            delta_txt, ha="center", va="bottom",
            fontsize=14.0, fontweight="bold",
            color=palette.alert if rel < 0 else palette.s1,
            bbox=dict(boxstyle="round,pad=0.20", facecolor="#FFFFFF", edgecolor=palette.alert if rel < 0 else palette.s1, linewidth=1.05),
            zorder=5,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(fmt_cats, fontsize=14.0, color=palette.ink)
    ax.set_ylim(0, max_v * 1.44)
    ax.set_ylabel(data.get("ylabel", "Isolated Yield (%)"), fontsize=14.0, fontweight="bold", color=palette.ink)
    ax.legend(
        loc="lower center", bbox_to_anchor=(0.5, 1.03),
        ncol=2, frameon=False, fontsize=14.0, handlelength=1.8, columnspacing=1.8
    )


def _plot_electrochem_suite(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    fig.subplots_adjust(left=0.13, right=0.96, top=0.91, bottom=0.13, wspace=0.36, hspace=0.58)
    axes = fig.subplots(2, 2)
    titles = ["(a) LSV Polarization", "(b) Overpotential", "(c) Tafel Kinetics", "(d) Stability"]

    for ax in axes.flat:
        _style_origin_axes(ax, palette.ink)

    # Panel a: LSV
    ax = axes[0, 0]
    v = np.linspace(1.20, 1.68, 80)
    j_cat = 1.5 * np.exp((v - 1.38) * 16.5)
    j_ref = 1.2 * np.exp((v - 1.48) * 12.0)
    j_cat = np.clip(j_cat, 0, 120)
    j_ref = np.clip(j_ref, 0, 120)
    ax.plot(v, j_cat, color=palette.s1, lw=2.3)
    ax.plot(v, j_ref, color=palette.muted, lw=1.8, ls="--")
    ax.text(1.52, 92, "Cat-1", color=palette.s1, fontsize=14.0, fontweight="bold", ha="right")
    ax.text(1.66, 26, "Ref", color=palette.muted, fontsize=14.0, ha="right")
    ax.set_xlabel("$E$ (V vs. RHE)", fontsize=14.0)
    ax.set_ylabel("$j$ (mA cm$^{-2}$)", fontsize=14.0)
    ax.set_title(titles[0], loc="left", fontsize=14.0, fontweight="bold", color=palette.ink, pad=6)

    # Panel b: Overpotential bar
    ax = axes[0, 1]
    names = ["Cat-1", "Ref", "Bare"]
    vals = [235, 318, 412]
    cols = [palette.s1, palette.s3, palette.muted]
    bars = ax.bar(names, vals, width=0.52, color=cols, edgecolor=palette.ink, linewidth=0.8)
    for b, val in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, val + 12, f"{val}", ha="center", va="bottom", fontsize=14.0, fontweight="bold", color=palette.ink)
    ax.set_ylim(0, 495)
    ax.set_ylabel(r"$\eta_{10}$ (mV)", fontsize=14.0)
    ax.set_title(titles[1], loc="left", fontsize=14.0, fontweight="bold", color=palette.ink, pad=6)

    # Panel c: Tafel
    ax = axes[1, 0]
    logj = np.linspace(0.2, 1.8, 20)
    eta_cat = 195 + 48 * logj
    eta_ref = 245 + 82 * logj
    ax.plot(logj, eta_cat, color=palette.s1, lw=2.2, marker="o", markersize=5.0, markevery=4)
    ax.plot(logj, eta_ref, color=palette.muted, lw=1.8, ls="--", marker="s", markersize=5.0, markerfacecolor="#FFFFFF", markevery=4)
    ax.text(0.95, 222, "48 mV dec$^{-1}$", color=palette.s1, fontsize=14.0, fontweight="bold")
    ax.text(0.45, 360, "82 mV dec$^{-1}$", color=palette.muted, fontsize=14.0)
    ax.set_ylim(175, 425)
    ax.set_xlabel("log $|j|$", fontsize=14.0)
    ax.set_ylabel(r"$\eta$ (mV)", fontsize=14.0)
    ax.set_title(titles[2], loc="left", fontsize=14.0, fontweight="bold", color=palette.ink, pad=6)

    # Panel d: Stability with 100% dashed line
    ax = axes[1, 1]
    hrs = np.linspace(0, 48, 25)
    ret_cat = 100.0 - 0.04 * hrs + 0.35 * np.sin(hrs * 0.5)
    ret_ref = 100.0 - 0.42 * hrs
    ax.axhline(100.0, color=palette.line, lw=1.3, ls="--")
    ax.plot(hrs, ret_cat, color=palette.s1, lw=2.3)
    ax.plot(hrs, ret_ref, color=palette.alert, lw=1.8, ls=":")
    ax.text(46, 94.5, "98.1%", color=palette.s1, fontsize=14.0, fontweight="bold", ha="right")
    ax.text(46, 85.2, "79.8%", color=palette.alert, fontsize=14.0, fontweight="bold", ha="right")
    ax.set_ylim(74, 106)
    ax.set_xlabel("Time (h)", fontsize=14.0)
    ax.set_ylabel("Retention (%)", fontsize=14.0)
    ax.set_title(titles[3], loc="left", fontsize=14.0, fontweight="bold", color=palette.ink, pad=6)


def _plot_xps_deconv(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    ax = fig.add_axes([0.13, 0.16, 0.82, 0.76])
    _style_origin_axes(ax, palette.ink)

    be = np.linspace(850.0, 868.0, 400)
    # Multi-peak XPS deconvolution (e.g., Ni 2p3/2)
    peaks = data.get("peaks", [
        {"name": "Ni$^0$", "center": 852.6, "height": 34.0, "fwhm": 1.35, "pct": "21.4%", "color": palette.series[0]},
        {"name": "Ni$^{2+}$", "center": 855.3, "height": 68.0, "fwhm": 1.85, "pct": "54.2%", "color": palette.series[min(1, len(palette.series)-1)]},
        {"name": "Ni$^{3+}$", "center": 857.4, "height": 29.0, "fwhm": 1.70, "pct": "16.1%", "color": palette.series[min(2, len(palette.series)-1)]},
        {"name": "Sat.", "center": 861.4, "height": 22.0, "fwhm": 2.90, "pct": "8.3%", "color": palette.muted},
    ])

    baseline = 12.0 + 0.15 * (be - 850.0)
    total = baseline.copy()
    sub_curves = []
    for pk in peaks:
        y_pk = _gaussian_peak(be, pk["center"], pk["height"], pk["fwhm"])
        sub_curves.append((pk, baseline + y_pk))
        total += y_pk

    rng = np.random.default_rng(7)
    raw = total + rng.normal(0.0, 1.3, size=be.shape)

    # Vertical alignment bands
    for pk, _ in sub_curves[:3]:
        ax.axvspan(pk["center"] - 0.35, pk["center"] + 0.35, color=palette.s6, alpha=0.85, zorder=0)
        ax.axvline(pk["center"], color=palette.s4, lw=0.9, ls="--", zorder=1)

    for pk, y_curve in sub_curves:
        ax.fill_between(be, baseline, y_curve, color=pk["color"], alpha=0.38, zorder=2)
        ax.plot(be, y_curve, color=pk["color"], lw=1.3, zorder=3)
        ax.text(pk["center"], y_curve.max() + 2.2, pk["name"], ha="center", va="bottom", fontsize=14.0, fontweight="bold", color=pk["color"])

    ax.scatter(be[::6], raw[::6], s=18, facecolors="none", edgecolors=palette.muted, linewidths=0.9, zorder=4)
    ax.plot(be, total, color=palette.ink, lw=2.0, zorder=5)

    # Top-left element badge
    badge = data.get("element_badge", "Ni 2p$_{3/2}$")
    ax.text(
        0.04, 0.90, badge, transform=ax.transAxes,
        fontsize=15.0, fontweight="bold", color="#FFFFFF",
        bbox=dict(boxstyle="round,pad=0.32", facecolor=palette.s1, edgecolor="none"),
    )

    # Inset clean three-line table of valence percentages (top-right inside frame)
    inset = ax.inset_axes([0.62, 0.54, 0.35, 0.40])
    inset.axis("off")
    inset.plot([0.02, 0.98], [0.96, 0.96], color=palette.ink, lw=1.4, transform=inset.transAxes)
    inset.plot([0.02, 0.98], [0.74, 0.74], color=palette.ink, lw=0.8, transform=inset.transAxes)
    inset.plot([0.02, 0.98], [0.04, 0.04], color=palette.ink, lw=1.4, transform=inset.transAxes)
    inset.text(0.08, 0.81, "Species", fontsize=14.0, fontweight="bold", color=palette.ink, transform=inset.transAxes)
    inset.text(0.92, 0.81, "Ratio", fontsize=14.0, fontweight="bold", color=palette.ink, ha="right", transform=inset.transAxes)
    for row_i, pk in enumerate(peaks[:3]):
        y_row = 0.54 - row_i * 0.21
        inset.text(0.08, y_row, pk["name"], fontsize=14.0, color=pk["color"], fontweight="bold", transform=inset.transAxes)
        inset.text(0.92, y_row, pk["pct"], fontsize=14.0, color=palette.ink, ha="right", transform=inset.transAxes)

    ax.set_xlim(868.0, 850.0)  # Decreasing binding energy
    ax.set_ylim(5, total.max() * 1.24)
    ax.set_yticks([])
    ax.set_xlabel("Binding Energy (eV)", fontsize=14.0, fontweight="bold", color=palette.ink)
    ax.set_ylabel("Intensity (a.u.)", fontsize=14.0, fontweight="bold", color=palette.ink)


def _plot_dft_energy_profile(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    ax = fig.add_axes([0.13, 0.17, 0.82, 0.74])
    _style_origin_axes(ax, palette.ink)

    states = data.get("states", ["IS", "IM1", "TS1", "IM2", "FS"])
    e_ctrl = data.get("control", [0.00, -0.22, 1.18, -0.35, -0.68])
    e_cat = data.get("this_work", [0.00, -0.34, 0.42, -0.58, -0.92])

    ax.axhline(0.0, color=palette.line, lw=1.1, ls=":")
    plat_w = 0.28

    for label, vals, col, ls, offset_y in (
        (data.get("control_label", "Unassisted"), e_ctrl, palette.muted, "--", 0.08),
        (data.get("work_label", "Catalyst Synergy"), e_cat, palette.s1, "-", -0.14),
    ):
        for i, val in enumerate(vals):
            x0, x1 = i - plat_w, i + plat_w
            ax.plot([x0, x1], [val, val], color=col, lw=3.2, solid_capstyle="butt", zorder=4)
            if i < len(vals) - 1:
                ax.plot([x1, (i + 1) - plat_w], [val, vals[i + 1]], color=col, lw=1.5, ls="--", zorder=3)
            # Direct label
            va = "bottom" if offset_y > 0 else "top"
            dy = 0.05 if offset_y > 0 else -0.06
            if col == palette.s1 and i == 2:
                va, dy = "bottom", 0.05
            ax.text(
                i, val + dy, f"{val:+.2f}",
                ha="center", va=va, fontsize=14.0,
                fontweight="bold" if col == palette.s1 else "normal",
                color=col,
            )

        # Inline end label
        ax.text(len(vals) - 1 + plat_w + 0.08, vals[-1], label, fontsize=14.0, fontweight="bold" if col == palette.s1 else "normal", color=col, va="center")

    # Barrier reduction annotation
    ax.annotate(
        "", xy=(2, e_cat[2]), xytext=(2, e_ctrl[2]),
        arrowprops=dict(arrowstyle="<->", color=palette.alert, lw=1.8),
    )
    ax.text(2.12, 0.5 * (e_cat[2] + e_ctrl[2]), r"$\Delta\Delta G^\ddagger = -0.76$ eV", fontsize=14.0, fontweight="bold", color=palette.alert, va="center")

    ax.set_xticks(range(len(states)))
    ax.set_xticklabels(states, fontsize=14.0, fontweight="bold", color=palette.ink)
    ax.set_xlim(-0.55, len(states) - 0.1 + 1.4)
    all_e = e_ctrl + e_cat
    ax.set_ylim(min(all_e) - 0.35, max(all_e) + 0.38)
    ax.set_ylabel(r"Relative Free Energy $\Delta G$ (eV)", fontsize=14.0, fontweight="bold", color=palette.ink)


def _plot_dft_slab_bader_link(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    gs = GridSpec(2, 1, height_ratios=[1.0, 1.65], hspace=0.12, left=0.14, right=0.95, top=0.92, bottom=0.15)
    ax_top = fig.add_subplot(gs[0])
    ax_bot = fig.add_subplot(gs[1], sharex=ax_top)

    sites = data.get("sites", ["Pristine", "M-N$_3$", "M-N$_4$", "Dual-Site"])
    e_ads = data.get("e_ads", [-0.62, -1.18, -1.46, -1.94])
    bader = data.get("bader", [0.18, 0.41, 0.56, 0.74])
    cols = [palette.muted, palette.s3, palette.s2, palette.s1]

    # Top panel: schematic crystal slab descriptors aligned to each column
    ax_top.set_facecolor("#FFFFFF")
    ax_top.set_ylim(0, 1.0)
    for sp in ("top", "left", "right", "bottom"):
        ax_top.spines[sp].set_color(palette.line)
        ax_top.spines[sp].set_linewidth(0.8)
    ax_top.set_yticks([])
    ax_top.tick_params(labelbottom=False, bottom=False)

    for i, col in enumerate(cols):
        # Draw minimalist slab grid + active center sphere + adsorbed molecule sphere
        rect = patches.FancyBboxPatch((i - 0.28, 0.16), 0.56, 0.24, boxstyle="round,pad=0.02", facecolor=palette.s5, edgecolor=palette.ink, lw=0.8)
        ax_top.add_patch(rect)
        ax_top.scatter([i], [0.44], s=260, color=col, edgecolor=palette.ink, linewidth=1.0, zorder=4)
        ax_top.scatter([i], [0.74], s=140, color=palette.alert, edgecolor=palette.ink, linewidth=0.9, zorder=5)
        ax_top.plot([i, i], [0.44, 0.74], color=palette.ink, lw=1.4, ls="--", zorder=3)
        ax_top.text(i, 0.88, f"+{bader[i]:.2f} |e|", ha="center", va="bottom", fontsize=14.0, fontweight="bold", color=col)

    ax_top.set_title("Active-Site Charge Transfer & Adsorption Linkage", fontsize=14.5, fontweight="bold", color=palette.ink, pad=6)

    # Bottom panel: color-linked E_ads bars
    _style_origin_axes(ax_bot, palette.ink)
    x = np.arange(len(sites))
    bars = ax_bot.bar(x, [abs(v) for v in e_ads], width=0.46, color=cols, edgecolor=palette.ink, linewidth=0.9)
    for b, val, col in zip(bars, e_ads, cols):
        ax_bot.text(b.get_x() + b.get_width() / 2, abs(val) + 0.06, f"{val:.2f} eV", ha="center", va="bottom", fontsize=14.0, fontweight="bold", color=col)

    ax_bot.set_xticks(x)
    ax_bot.set_xticklabels(sites, fontsize=14.0, fontweight="bold", color=palette.ink)
    ax_bot.set_xlim(-0.55, len(sites) - 0.45)
    ax_bot.set_ylim(0, max(abs(v) for v in e_ads) * 1.25)
    ax_bot.set_ylabel(r"$|E_{\mathrm{ads}}|$ (eV)", fontsize=14.0, fontweight="bold", color=palette.ink)


def _plot_ml_parity_kde(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    gs = GridSpec(2, 2, width_ratios=[4.2, 1.0], height_ratios=[1.0, 4.2], wspace=0.05, hspace=0.05, left=0.14, right=0.95, top=0.94, bottom=0.15)
    ax_main = fig.add_subplot(gs[1, 0])
    ax_top = fig.add_subplot(gs[0, 0], sharex=ax_main)
    ax_right = fig.add_subplot(gs[1, 1], sharey=ax_main)

    rng = np.random.default_rng(21)
    y_true = np.asarray(data.get("y_true", rng.uniform(15, 96, 85)), dtype=np.float64)
    y_pred = np.asarray(data.get("y_pred", np.clip(y_true + rng.normal(0, 4.1, size=len(y_true)), 8, 99)), dtype=np.float64)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 1.0 - ss_res / max(ss_tot, 1e-8)

    _style_origin_axes(ax_main, palette.ink)
    lo, hi = 5.0, 105.0
    ax_main.plot([lo, hi], [lo, hi], color=palette.ink, lw=1.4, ls="--", zorder=2)
    ax_main.fill_between([lo, hi], [lo - 6, hi - 6], [lo + 6, hi + 6], color=palette.s5, alpha=0.35, zorder=1)
    ax_main.scatter(y_true, y_pred, s=46, facecolor=palette.s1, edgecolor="#FFFFFF", linewidth=0.7, alpha=0.82, zorder=3)

    ax_main.text(0.06, 0.88, f"MAE = {mae:.2f}%\n$R^2$ = {r2:.3f}", transform=ax_main.transAxes, fontsize=14.0, fontweight="bold", color=palette.s1, va="top")
    ax_main.set_xlim(lo, hi)
    ax_main.set_ylim(lo, hi)
    ax_main.set_xlabel("Experimental Yield (%)", fontsize=14.0, fontweight="bold", color=palette.ink)
    ax_main.set_ylabel("ML Predicted Yield (%)", fontsize=14.0, fontweight="bold", color=palette.ink)

    # Marginal KDE top
    grid = np.linspace(lo, hi, 200)
    kde_x = _gaussian_kde_1d(y_true, grid)
    ax_top.fill_between(grid, 0, kde_x, color=palette.s2, alpha=0.45)
    ax_top.plot(grid, kde_x, color=palette.s1, lw=1.6)
    ax_top.axis("off")

    # Marginal KDE right
    kde_y = _gaussian_kde_1d(y_pred, grid)
    ax_right.fill_betweenx(grid, 0, kde_y, color=palette.s3, alpha=0.45)
    ax_right.plot(kde_y, grid, color=palette.s2, lw=1.6)
    ax_right.axis("off")


def _plot_benchmark_scatter(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    ax = fig.add_axes([0.14, 0.16, 0.81, 0.74])
    _style_origin_axes(ax, palette.ink)

    lit_x = data.get("lit_x", [110, 120, 95, 130, 85, 100, 75])
    lit_y = data.get("lit_y", [58, 66, 72, 79, 61, 82, 54])
    lit_labels = data.get("lit_labels", ["Ref. 1", "Ref. 2", "Ref. 3", "Ref. 4", "Ref. 5", "Ref. 6", "Ref. 7"])
    this_x = float(data.get("this_x", 45.0))
    this_y = float(data.get("this_y", 94.5))

    # Advantage zone ellipse in top-left (lower temp, higher yield)
    ellipse = patches.Ellipse(
        (this_x + 4, this_y - 2), width=36, height=18,
        facecolor=palette.s5, edgecolor=palette.s3, linestyle="--", linewidth=1.2, alpha=0.42, zorder=1
    )
    ax.add_patch(ellipse)

    markers = ["o", "s", "^", "D", "v", "P", "X"]
    for i, (lx, ly) in enumerate(zip(lit_x, lit_y)):
        ax.scatter([lx], [ly], s=78, marker=markers[i % len(markers)], facecolor=palette.s4 if i % 2 == 0 else "#FFFFFF", edgecolor=palette.muted, linewidth=1.3, zorder=3)
        if i in (0, 3, 5):
            ax.text(lx, ly - 4.5, lit_labels[i], ha="center", va="top", fontsize=14.0, color=palette.muted)

    ax.scatter([this_x], [this_y], s=320, marker="*", facecolor=palette.s1, edgecolor=palette.ink, linewidth=0.9, zorder=5)
    ax.text(this_x + 5.5, this_y + 0.5, "This Work (94.5%)", fontsize=14.0, fontweight="bold", color=palette.s1, va="center")

    ax.set_xlim(22, 148)
    ax.set_ylim(42, 106)
    ax.set_xlabel(data.get("xlabel", "Reaction Temperature (°C)"), fontsize=14.0, fontweight="bold", color=palette.ink)
    ax.set_ylabel(data.get("ylabel", "Target Yield (%)"), fontsize=14.0, fontweight="bold", color=palette.ink)


def _plot_nature_grouped_bar(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    """Image-1 Nature/Origin grouped bar chart: borderless top swatch legend, Tukey letters, italic P-value."""
    ax = fig.add_axes([0.14, 0.17, 0.81, 0.67])
    _style_origin_axes(ax, palette.ink)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(top=False, right=False)

    categories = list(data.get("categories") or ["Ctrl", "Low", "Mid", "High"])
    raw_series = data.get("series") or [
        {"name": "Wild-Type", "values": [1.8, 2.4, 3.1, 3.8], "errors": [0.2, 0.25, 0.3, 0.35]},
        {"name": "Mutant", "values": [2.2, 4.1, 6.4, 8.9], "errors": [0.25, 0.4, 0.5, 0.6]},
    ]
    n_cat = max(1, len(categories))
    n_ser = max(1, len(raw_series))
    x = np.arange(n_cat, dtype=float)
    total_w = min(0.76, 0.22 * n_ser + 0.18)
    bar_w = total_w / n_ser
    colors = [palette.s1, palette.s2, palette.s3, palette.alert, palette.s4, palette.s5]

    all_tops: List[float] = []
    letters = list(data.get("letters") or [])
    for s_idx, ser in enumerate(raw_series):
        vals = [float(v) for v in (ser.get("values") or [0] * n_cat)[:n_cat]]
        while len(vals) < n_cat:
            vals.append(0.0)
        errs = ser.get("errors")
        err_arr = [float(e) for e in errs[:n_cat]] if isinstance(errs, list) and len(errs) >= n_cat else None
        offset = (s_idx - (n_ser - 1) / 2.0) * bar_w
        col = colors[s_idx % len(colors)]
        bars = ax.bar(
            x + offset,
            vals,
            width=bar_w * 0.90,
            color=col,
            edgecolor=palette.ink,
            linewidth=0.85,
            label=str(ser.get("name", f"Series {s_idx + 1}")),
            zorder=3,
        )
        if err_arr:
            ax.errorbar(
                x + offset,
                vals,
                yerr=err_arr,
                fmt="none",
                ecolor=palette.ink,
                elinewidth=1.0,
                capsize=3.0,
                zorder=4,
            )
        for b_idx, bar in enumerate(bars):
            top = bar.get_height() + (err_arr[b_idx] if err_arr else 0.0)
            all_tops.append(top)
            if letters and n_ser == 1 and b_idx < len(letters):
                ax.text(bar.get_x() + bar.get_width() / 2.0, top, str(letters[b_idx]), ha="center", va="bottom", fontsize=14.0, fontweight="bold", color=palette.ink)
            elif n_cat <= 6 and n_ser <= 2:
                txt = f"{vals[b_idx]:.1f}" if abs(vals[b_idx]) >= 1 else f"{vals[b_idx]:.2f}"
                ax.text(bar.get_x() + bar.get_width() / 2.0, top, txt, ha="center", va="bottom", fontsize=13.5, color=palette.ink)

    ymax = max(all_tops) if all_tops else 1.0
    ax.set_ylim(0, ymax * 1.24 if not data.get("log_y") else ymax * 2.2)
    if data.get("log_y"):
        ax.set_yscale("log")
        ax.set_ylim(max(0.05, min([v for v in all_tops if v > 0] or [0.1]) * 0.5), ymax * 2.5)

    ax.set_xticks(x)
    ax.set_xticklabels([str(c)[:14] for c in categories], fontsize=14.0, color=palette.ink)
    ax.set_ylabel(str(data.get("ylabel", "Response / Activity")), fontsize=14.0, fontweight="bold", color=palette.ink)
    if data.get("xlabel"):
        ax.set_xlabel(str(data["xlabel"]), fontsize=14.0, fontweight="bold", color=palette.ink)

    p_val = str(data.get("p_value", "")).strip()
    if p_val:
        ax.text(0.5, 0.94, p_val, transform=ax.transAxes, ha="center", va="top", fontsize=14.0, style="italic", color=palette.ink)

    panel_lbl = str(data.get("panel_label", "a")).strip()
    if panel_lbl:
        ax.text(-0.10, 1.11, panel_lbl, transform=ax.transAxes, fontsize=16.0, fontweight="bold", color=palette.ink)

    if n_ser > 1:
        ax.legend(
            loc="lower center",
            bbox_to_anchor=(0.5, 1.01),
            ncol=min(5, n_ser),
            frameon=False,
            fontsize=14.0,
            handlelength=1.2,
            columnspacing=1.0,
        )


def _plot_nature_step_drop_zoom(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    """Image-1 Nature waterfall step-drop chart with dashed connector steps & zoomed inset panel."""
    ax = fig.add_axes([0.13, 0.16, 0.82, 0.74])
    _style_origin_axes(ax, palette.ink)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(top=False, right=False)

    categories = list(data.get("categories") or ["Baseline", "Step 1", "Step 2", "Step 3", "Final A", "Final B"])
    values = [float(v) for v in (data.get("values") or [41.0, 32.5, 13.7, 5.9, 0.50, 0.14])]
    errors = [float(e) for e in (data.get("errors") or [v * 0.10 for v in values])]
    drops = list(data.get("drop_labels") or ["-20.7%", "-57.8%", "-56.9%", "-91.5%", "-72.0%"])

    n = len(values)
    x = np.arange(n, dtype=float)
    bar_cols = [palette.s1, palette.s2, palette.s3, palette.alert, palette.s4, palette.s5]
    colors = [bar_cols[i % len(bar_cols)] for i in range(n)]

    ax.bar(x, values, width=0.52, color=colors, edgecolor=palette.ink, linewidth=0.9, zorder=3)
    ax.errorbar(x, values, yerr=errors, fmt="none", ecolor=palette.ink, elinewidth=1.0, capsize=3.0, zorder=4)

    for i in range(n - 1):
        ax.plot([x[i], x[i + 1]], [values[i], values[i]], "--", color=palette.ink, lw=1.1, zorder=4)
        if values[i] > values[i + 1] and i < len(drops):
            ax.annotate("", xy=(x[i + 1], values[i + 1] + errors[i + 1] + 0.5), xytext=(x[i + 1], values[i]),
                        arrowprops=dict(arrowstyle="-|>", color=palette.ink, lw=1.2), zorder=5)
            ax.text(x[i + 1] + 0.08, 0.5 * (values[i] + values[i + 1]), str(drops[i]), fontsize=14.0, fontweight="bold", color=palette.ink, va="center")

    ax.set_xticks(x)
    ax.set_xticklabels([str(c)[:12] for c in categories], fontsize=14.0, color=palette.ink)
    ax.set_ylim(0, max(values) * 1.24 if values else 50)
    ax.set_ylabel(str(data.get("ylabel", "Target Burden / Value")), fontsize=14.0, fontweight="bold", color=palette.ink)
    panel_lbl = str(data.get("panel_label", "a")).strip()
    if panel_lbl:
        ax.text(-0.10, 1.05, panel_lbl, transform=ax.transAxes, fontsize=16.0, fontweight="bold", color=palette.ink)

    # Inset zoom on last two small bars if dramatically smaller than max
    if n >= 5 and max(values[-2:]) < max(values) * 0.25:
        ax_in = fig.add_axes([0.56, 0.50, 0.36, 0.36])
        _style_origin_axes(ax_in, palette.ink)
        sub_x = np.arange(2, dtype=float)
        ax_in.bar(sub_x, values[-2:], width=0.45, color=colors[-2:], edgecolor=palette.ink, lw=0.85, zorder=3)
        ax_in.errorbar(sub_x, values[-2:], yerr=errors[-2:], fmt="none", ecolor=palette.ink, elinewidth=0.9, capsize=2.5, zorder=4)
        ax_in.set_xticks(sub_x)
        ax_in.set_xticklabels([str(c)[:10] for c in categories[-2:]], fontsize=14.0)
        ax_in.set_ylim(0, max(values[-2:]) * 1.6 + 0.05)


def _plot_nature_horizontal_ranked(fig: plt.Figure, palette: ScientificPalette, data: Dict[str, Any]) -> None:
    """Image-1 Nature horizontal ranked bar chart with significance stars (*..****)."""
    ax = fig.add_axes([0.30, 0.16, 0.64, 0.74])
    _style_origin_axes(ax, palette.ink)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(top=False, right=False)

    labels = list(data.get("labels") or ["Control", "Analog A", "Analog B", "Analog C", "YJ-402"])
    values = [float(v) for v in (data.get("values") or [12.0, 28.0, 46.0, 69.0, 92.0])]
    errors = [float(e) for e in (data.get("errors") or [v * 0.08 for v in values])]
    stars = list(data.get("stars") or ["ns", "*", "**", "***", "****"])

    y = np.arange(len(labels), dtype=float)
    bar_cols = [blend_with_white(palette.s1, 0.45)] * max(0, len(labels) - 1) + [palette.s1]
    ax.barh(y, values, height=0.60, color=bar_cols, edgecolor=palette.ink, linewidth=0.85, zorder=3)
    ax.errorbar(values, y, xerr=errors, fmt="none", ecolor=palette.ink, elinewidth=1.0, capsize=3.0, zorder=4)

    for idx, (val, err) in enumerate(zip(values, errors)):
        st = str(stars[idx]) if idx < len(stars) else ""
        if st:
            ax.text(val + err + max(values) * 0.02, y[idx], st, va="center", ha="left", fontsize=14.0, fontweight="bold", color=palette.alert if "*" in st else palette.muted)

    ax.set_yticks(y)
    ax.set_yticklabels([str(l)[:18] for l in labels], fontsize=14.0, color=palette.ink)
    ax.set_xlim(0, max(values) * 1.24 if values else 100)
    ax.set_xlabel(str(data.get("xlabel", "Activity / Inhibition (%)")), fontsize=14.0, fontweight="bold", color=palette.ink)
    panel_lbl = str(data.get("panel_label", "a")).strip()
    if panel_lbl:
        ax.text(-0.34, 1.04, panel_lbl, transform=ax.transAxes, fontsize=16.0, fontweight="bold", color=palette.ink)


def export_plot_data_csv(plot_data: Dict[str, Any], output_csv: Path | str) -> Optional[Path]:
    """Export real chart series/categories to UTF-8 CSV for downstream OriginPro refinement."""
    if not plot_data:
        return None
    import csv

    out_p = Path(output_csv)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    cats = plot_data.get("categories") or plot_data.get("labels")
    series = plot_data.get("series")
    values = plot_data.get("values")

    rows: List[List[Any]] = []
    if isinstance(cats, list) and isinstance(series, list) and series:
        header = ["Category"] + [str(s.get("name", f"Series_{i+1}")) for i, s in enumerate(series)]
        rows.append(header)
        for idx, cat in enumerate(cats):
            row = [cat]
            for ser in series:
                vals = ser.get("values") or []
                row.append(vals[idx] if idx < len(vals) else "")
            rows.append(row)
    elif isinstance(cats, list) and isinstance(values, list):
        rows.append(["Label", str(plot_data.get("ylabel") or plot_data.get("xlabel") or "Value")])
        for c, v in zip(cats, values):
            rows.append([c, v])
    else:
        return None

    with out_p.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return out_p


PRESET_DISPATCH = {
    "kinetics_spline": _plot_kinetics_spline,
    "paired_gain_bar": _plot_paired_gain_bar,
    "electrochem_suite": _plot_electrochem_suite,
    "xps_deconv": _plot_xps_deconv,
    "dft_energy_profile": _plot_dft_energy_profile,
    "dft_slab_bader_link": _plot_dft_slab_bader_link,
    "ml_parity_kde": _plot_ml_parity_kde,
    "benchmark_scatter": _plot_benchmark_scatter,
    "nature_grouped_bar": _plot_nature_grouped_bar,
    "nature_step_drop_zoom": _plot_nature_step_drop_zoom,
    "nature_horizontal_ranked": _plot_nature_horizontal_ranked,
}


def render_origin_plot(
    preset: str,
    output_png: Path | str,
    palette_id: str = "lancet",
    box_width_in: float = 7.75,
    box_height_in: float = 4.42,
    plot_data: Optional[Dict[str, Any]] = None,
    dpi: int = 600,
    latin_font: str = "Arial",
    ea_font: str = "微软雅黑",
) -> Path:
    """Render a 1:1 physical-size 600 DPI OriginPro-grade scientific chart."""
    _configure_origin_rcparams(latin_font=latin_font, ea_font=ea_font)
    palette = get_palette(palette_id)
    fn = PRESET_DISPATCH.get(preset or "kinetics_spline", _plot_kinetics_spline)

    fig = plt.figure(figsize=(max(box_width_in, 3.2), max(box_height_in, 2.4)), dpi=dpi)
    fig.patch.set_alpha(0.0)
    fn(fig, palette, plot_data or {})

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_p), dpi=dpi, transparent=True)
    plt.close(fig)
    return out_p
