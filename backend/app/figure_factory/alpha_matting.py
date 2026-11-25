"""True Alpha Matting & White-Halo Edge Decontamination for Scientific Studio Figures.

Removes solid white studio backgrounds from AI-generated or rendered artwork while
preserving internal white specular highlights, glass reflections, and smooth anti-aliased edges.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image


def _border_connected_background_mask(rgb: np.ndarray, threshold: float = 242.0) -> np.ndarray:
    """Flood-fill from image borders across near-white low-chroma pixels.

    This strictly preserves interior white specular highlights (e.g., on glass flasks
    or shiny spheres) that are enclosed by darker contours or shading.
    """
    h, w, _ = rgb.shape
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)

    min_c = np.minimum(np.minimum(r, g), b)
    max_c = np.maximum(np.maximum(r, g), b)
    chroma = max_c - min_c
    is_bg_candidate = (min_c >= threshold) & (chroma <= 18.0)

    visited = np.zeros((h, w), dtype=bool)
    q: deque[Tuple[int, int]] = deque()

    for x in range(w):
        if is_bg_candidate[0, x]:
            visited[0, x] = True
            q.append((0, x))
        if is_bg_candidate[h - 1, x] and not visited[h - 1, x]:
            visited[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(h):
        if is_bg_candidate[y, 0] and not visited[y, 0]:
            visited[y, 0] = True
            q.append((y, 0))
        if is_bg_candidate[y, w - 1] and not visited[y, w - 1]:
            visited[y, w - 1] = True
            q.append((y, w - 1))

    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and is_bg_candidate[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    return visited


def _dilate_mask(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Pure-NumPy morphological binary dilation."""
    out = mask.copy()
    for _ in range(radius):
        padded = np.pad(out, 1, mode="constant", constant_values=False)
        out = (
            padded[:-2, 1:-1]
            | padded[2:, 1:-1]
            | padded[1:-1, :-2]
            | padded[1:-1, 2:]
            | padded[:-2, :-2]
            | padded[:-2, 2:]
            | padded[2:, :-2]
            | padded[2:, 2:]
            | out
        )
    return out


def matte_white_background(
    image: Image.Image | Path | str,
    output_path: Path | str | None = None,
    white_threshold: float = 242.0,
    crop_padding: int = 12,
    dpi: int = 600,
) -> Image.Image:
    """Convert a white-studio image into a true-alpha decontaminated transparent RGBA PNG.

    Steps:
    1. If image already has meaningful alpha (e.g., >5% transparent pixels), refine edges and tight-crop.
    2. Otherwise run border-seeded flood-fill background detection (keeping enclosed highlights).
    3. Estimate soft fractional alpha along the 2-pixel transition rim and unmix white fringe:
       C_fg = clamp((C_obs - (1 - a) * 255) / max(a, eps), 0, 255).
    4. Tight-crop to alpha > 4 bounding box with clean padding.
    """
    img = Image.open(image) if isinstance(image, (Path, str)) else image
    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.float32)

    alpha_existing = arr[:, :, 3]
    has_existing_alpha = float(np.mean(alpha_existing < 250)) > 0.03

    if has_existing_alpha:
        alpha = alpha_existing / 255.0
        rgb = arr[:, :, :3]
        # Decontaminate slightly semi-transparent border pixels against white
        rim = (alpha > 0.02) & (alpha < 0.96)
        for c in range(3):
            unmixed = (rgb[:, :, c] - (1.0 - alpha) * 255.0) / np.maximum(alpha, 0.08)
            rgb[:, :, c] = np.where(rim, np.clip(unmixed, 0.0, 255.0), rgb[:, :, c])
        out_arr = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255.0, 0, 255)]).astype(np.uint8)
    else:
        rgb = arr[:, :, :3]
        bg_mask = _border_connected_background_mask(rgb, threshold=white_threshold)
        transition_zone = _dilate_mask(bg_mask, radius=2) & (~bg_mask)

        alpha = np.where(bg_mask, 0.0, 1.0).astype(np.float32)

        # Soft feather & color unmixing on the immediate foreground rim touching background
        min_c = np.minimum(np.minimum(rgb[:, :, 0], rgb[:, :, 1]), rgb[:, :, 2])
        max_c = np.maximum(np.maximum(rgb[:, :, 0], rgb[:, :, 1]), rgb[:, :, 2])
        chroma = max_c - min_c
        # Near-white pixels in the 2px rim get smooth fractional alpha
        soft_factor = np.clip((255.0 - min_c) / max(255.0 - 205.0, 1.0), 0.0, 1.0)
        soft_factor = np.where(chroma > 28.0, np.maximum(soft_factor, 0.85), soft_factor)
        alpha = np.where(transition_zone, soft_factor, alpha)

        rim = (alpha > 0.02) & (alpha < 0.98)
        for c in range(3):
            unmixed = (rgb[:, :, c] - (1.0 - alpha) * 255.0) / np.maximum(alpha, 0.10)
            rgb[:, :, c] = np.where(rim, np.clip(unmixed, 0.0, 255.0), rgb[:, :, c])

        # Zero RGB under fully transparent background
        rgb[alpha < 0.02] = 0.0
        out_arr = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255.0, 0, 255)]).astype(np.uint8)

    # Tight bounding-box crop
    ys, xs = np.where(out_arr[:, :, 3] > 6)
    if len(ys) > 0 and len(xs) > 0:
        h, w = out_arr.shape[:2]
        y0 = max(0, int(ys.min()) - crop_padding)
        y1 = min(h, int(ys.max()) + 1 + crop_padding)
        x0 = max(0, int(xs.min()) - crop_padding)
        x1 = min(w, int(xs.max()) + 1 + crop_padding)
        out_arr = out_arr[y0:y1, x0:x1]

    result = Image.fromarray(out_arr, mode="RGBA")
    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        result.save(str(out_p), format="PNG", dpi=(dpi, dpi))
    return result


def compute_alpha_edge_cleanliness(png_path: Path | str) -> float:
    """Score 0..10 for true transparency and absence of hard white rectangular edges."""
    img = Image.open(png_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    alpha = arr[:, :, 3]
    h, w = alpha.shape
    if h == 0 or w == 0:
        return 0.0

    # Check border pixels are transparent (no solid white frame box)
    border_alpha = np.concatenate([alpha[0, :], alpha[-1, :], alpha[:, 0], alpha[:, -1]])
    transparent_border_ratio = float(np.mean(border_alpha < 15))
    transparent_area_ratio = float(np.mean(alpha < 15))

    # Detect white halo on semi-transparent boundary pixels
    rim = (alpha > 15) & (alpha < 240)
    if np.any(rim):
        brightness = np.mean(arr[:, :, :3], axis=2)
        white_halo_fraction = float(np.mean(brightness[rim] > 246))
    else:
        white_halo_fraction = 0.0

    score = 6.5 + 2.2 * transparent_border_ratio + 1.3 * min(transparent_area_ratio / 0.15, 1.0) - 2.0 * white_halo_fraction
    return float(np.clip(round(score, 2), 0.0, 10.0))
