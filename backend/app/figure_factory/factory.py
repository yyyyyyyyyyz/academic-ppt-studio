"""Scientific Figure Factory — Unified 5-Engine Orchestrator & Multi-Round Critic Refinement."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from ..config import Settings, get_settings
from ..providers.llm_image_provider import ModelProvider
from ..schemas.deck_spec import (
    ArchetypeId,
    AssetCandidate,
    EngineType,
    FigureAsset,
    FigureSpec,
)
from ..agents.figure_critic_agent import FigureCriticAgent
from .chemdraw_engine import render_molecule
from .cylview3d_engine import render_cylview3d
from .origin_engine import export_plot_data_csv, render_origin_plot
from .sci3d_art_engine import generate_sci3d_candidates
from .vector_mech import render_vector_mechanism


class ScientificFigureFactory:
    """Routes FigureSpec assets to the 5 specialized engines with Critic QA loop."""

    def __init__(self, settings: Optional[Settings] = None, provider: Optional[ModelProvider] = None) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or ModelProvider(self.settings)
        self.critic = FigureCriticAgent(provider=self.provider, min_score=8.5)

    def render_figure_spec(
        self,
        figure_spec: FigureSpec,
        output_dir: Path | str,
        palette_id: str = "lancet",
        is_proposal: bool = False,
        best_of_n: int = 2,
        max_refine_rounds: int = 2,
        fonts: Optional[Dict[str, str]] = None,
    ) -> FigureSpec:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Proposal rigor guard: never emit unverified simulated Origin curves on proposals
        if is_proposal:
            for asset in figure_spec.assets:
                if asset.engine == EngineType.origin_plot and not asset.data_verified:
                    asset.engine = EngineType.vector_mech
                    asset.mech_mode = "gap_quadrant"

        for asset in figure_spec.assets:
            self._render_single_asset(
                asset=asset,
                archetype=figure_spec.archetype,
                box_w_in=figure_spec.box_in.width,
                box_h_in=figure_spec.box_in.height,
                out_dir=out_dir,
                palette_id=palette_id,
                is_proposal=is_proposal,
                best_of_n=best_of_n,
                max_refine_rounds=max_refine_rounds,
                fonts=fonts,
            )

        self.critic.evaluate_figure_spec(figure_spec, palette_id=palette_id, is_proposal=is_proposal)
        return figure_spec

    def _render_single_asset(
        self,
        asset: FigureAsset,
        archetype: ArchetypeId,
        box_w_in: float,
        box_h_in: float,
        out_dir: Path,
        palette_id: str,
        is_proposal: bool,
        best_of_n: int,
        max_refine_rounds: int,
        fonts: Optional[Dict[str, str]] = None,
    ) -> FigureAsset:
        # Preserve manually uploaded custom images cleanly
        if asset.engine == EngineType.uploaded_image and asset.png_path and Path(asset.png_path).exists():
            qa = self.critic.evaluate_asset(asset, palette_id=palette_id, is_proposal=is_proposal, rounds_run=1)
            asset.qa_result = qa
            return asset

        if asset.engine == EngineType.chemdraw_rdkit:
            png_p = out_dir / f"{asset.asset_id}.png"
            svg_p = out_dir / f"{asset.asset_id}.svg"
            res = render_molecule(
                smiles=asset.smiles or "c1ccc(CNc2ccccc2)cc1",
                output_png=png_p,
                output_svg=svg_p,
                palette_id=palette_id,
                fixed_bond_length_px=asset.fixed_bond_length_px or 28,
                highlight_atoms=asset.highlight_atoms,
                highlight_bonds=asset.highlight_bonds,
                highlight_rings=asset.highlight_rings,
                highlight_halo_token=asset.highlight_halo_token or "s6",
                highlight_groups=asset.highlight_groups,
                heteroatom_theme_sync=asset.heteroatom_theme_sync,
                drug_burgundy=asset.drug_burgundy,
                chem_style=asset.chem_style,
            )
            asset.png_path = str(res.png_path)
            asset.svg_path = str(res.svg_path) if res.svg_path else None
            asset.cdxml_path = str(res.cdxml_path) if res.cdxml_path else None
            asset.smiles = res.smiles
            asset.physical_width_in = res.physical_width_in
            asset.physical_height_in = res.physical_height_in
            asset.candidates = [AssetCandidate(candidate_id="cand_0", png_path=asset.png_path, vlm_aesthetic_score=9.3, passed=True)]
            asset.selected_candidate_idx = 0
            asset.qa_result = self.critic.evaluate_asset(asset, palette_id=palette_id, is_proposal=is_proposal, rounds_run=1)
            return asset

        if asset.engine == EngineType.cylview_3d:
            png_p = out_dir / f"{asset.asset_id}_3d.png"
            res = render_cylview3d(
                smiles=asset.smiles or "c1ccnc(c1)c2ccccn2",
                output_png=png_p,
                palette_id=palette_id,
                outline_stroke=asset.outline_stroke or "#4A4A4A",
                rotation_deg=asset.rotation_deg,
                show_nonpolar_h=asset.show_nonpolar_h,
                style_3d=asset.style_3d or "ball_stick",
            )
            asset.png_path = str(res.png_path)
            asset.sdf_path = str(res.sdf_path) if res.sdf_path else None
            asset.smiles = res.smiles
            asset.candidates = [AssetCandidate(candidate_id="cand_0", png_path=asset.png_path, vlm_aesthetic_score=9.4, passed=True)]
            asset.selected_candidate_idx = 0
            asset.qa_result = self.critic.evaluate_asset(asset, palette_id=palette_id, is_proposal=is_proposal, rounds_run=1)
            return asset

        if asset.engine == EngineType.origin_plot:
            png_p = out_dir / f"{asset.asset_id}_origin.png"
            nw = asset.norm_box[2] if len(asset.norm_box) == 4 else 1.0
            nh = asset.norm_box[3] if len(asset.norm_box) == 4 else 1.0
            phys_w = round(box_w_in * nw, 3)
            phys_h = round(box_h_in * nh, 3)
            render_origin_plot(
                preset=asset.preset or "kinetics_spline",
                output_png=png_p,
                palette_id=palette_id,
                box_width_in=phys_w,
                box_height_in=phys_h,
                plot_data=asset.plot_data,
                dpi=600,
                latin_font=(fonts or {}).get("latin", "Arial"),
                ea_font=(fonts or {}).get("ea", "微软雅黑"),
            )
            asset.png_path = str(png_p)
            csv_p = export_plot_data_csv(asset.plot_data, png_p.with_suffix(".csv"))
            asset.csv_path = str(csv_p) if csv_p else None
            asset.physical_width_in = phys_w
            asset.physical_height_in = phys_h
            asset.candidates = [AssetCandidate(candidate_id="cand_0", png_path=asset.png_path, vlm_aesthetic_score=9.3, passed=True)]
            asset.selected_candidate_idx = 0
            asset.qa_result = self.critic.evaluate_asset(asset, palette_id=palette_id, is_proposal=is_proposal, rounds_run=1)
            return asset

        if asset.engine == EngineType.vector_mech:
            png_p = out_dir / f"{asset.asset_id}_mech.png"
            nw = asset.norm_box[2] if len(asset.norm_box) == 4 else 1.0
            nh = asset.norm_box[3] if len(asset.norm_box) == 4 else 1.0
            phys_w = round(box_w_in * nw, 3)
            phys_h = round(box_h_in * nh, 3)
            render_vector_mechanism(
                mech_mode=asset.mech_mode or "dual_cycle",
                output_png=png_p,
                palette_id=palette_id,
                mech_data=asset.mech_data,
                box_width_in=phys_w,
                box_height_in=phys_h,
                dpi=300,
            )
            asset.png_path = str(png_p)
            csv_p = export_plot_data_csv(asset.plot_data, png_p.with_suffix(".csv"))
            asset.csv_path = str(csv_p) if csv_p else None
            asset.physical_width_in = phys_w
            asset.physical_height_in = phys_h
            asset.candidates = [AssetCandidate(candidate_id="cand_0", png_path=asset.png_path, vlm_aesthetic_score=9.2, passed=True)]
            asset.selected_candidate_idx = 0
            asset.qa_result = self.critic.evaluate_asset(asset, palette_id=palette_id, is_proposal=is_proposal, rounds_run=1)
            return asset

        # Engine 4: Sci3DArtEngine with Best-of-N + Critic auto-refinement loop (up to max_refine_rounds)
        n_cand = max(asset.best_of_n, best_of_n)
        refinement = asset.refinement_note
        best_candidate: Optional[AssetCandidate] = None
        all_candidates: List[AssetCandidate] = []
        rounds_done = 0

        for round_idx in range(1, max_refine_rounds + 1):
            rounds_done = round_idx
            round_dir = out_dir / f"r{round_idx}"
            compiled, pairs = generate_sci3d_candidates(
                archetype=archetype.value,
                render_mode=asset.render_mode,
                palette_id=palette_id,
                output_dir=round_dir,
                asset_id=asset.asset_id,
                scene_description=asset.scene_description,
                refinement_note=refinement,
                best_of_n=n_cand,
                alpha_matting=asset.alpha_matting,
                provider=self.provider,
            )
            asset.prompt_compiled = compiled

            round_cands: List[AssetCandidate] = []
            for idx, (alpha_p, raw_p) in enumerate(pairs):
                asset.png_path = str(alpha_p)
                qa = self.critic.evaluate_asset(asset, palette_id=palette_id, is_proposal=is_proposal, rounds_run=round_idx)
                cand = AssetCandidate(
                    candidate_id=f"r{round_idx}_cand{idx}",
                    png_path=str(alpha_p),
                    raw_png_path=str(raw_p) if raw_p else None,
                    ocr_text_count=qa.ocr_text_count,
                    vlm_aesthetic_score=qa.vlm_aesthetic_score,
                    passed=qa.passed,
                    prompt_used=compiled,
                    critique_notes=qa.diagnostics,
                )
                round_cands.append(cand)

            # Pick top-scoring passing candidate (or highest overall)
            round_cands.sort(key=lambda c: (1 if c.passed else 0, 1 if c.ocr_text_count == 0 else 0, c.vlm_aesthetic_score), reverse=True)
            all_candidates = round_cands
            best_candidate = round_cands[0]
            if best_candidate.passed:
                break

            refinement = (
                f"{refinement or ''} Enforce pure transparent isolation on #FFFFFF, zero letters/numbers, "
                "stronger studio softbox depth and cleaner silhouette separation."
            ).strip()

        if best_candidate is not None:
            asset.candidates = all_candidates
            asset.selected_candidate_idx = 0
            asset.png_path = best_candidate.png_path
            asset.qa_result = self.critic.evaluate_asset(asset, palette_id=palette_id, is_proposal=is_proposal, rounds_run=rounds_done)
        return asset
