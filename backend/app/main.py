"""FastAPI Backend Server — Academic PPT Design Studio (v4.0).

Implements all endpoints in Spec Section 6.4:
- GET  /api/health
- GET  /api/palettes
- GET  /api/archetypes
- POST /api/plan
- POST /api/plan/upload
- POST /api/figures/generate
- POST /api/figures/select-or-refine
- POST /api/figures/upload
- POST /api/palettes/apply
- POST /api/build/pptx
- POST /api/preview/slide
- POST /api/sync/word
- GET  /api/artifacts/{file_path:path}
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .agents.art_director_agent import build_default_figure_spec
from .agents.doc_parser import parse_file_to_text
from .agents.planner_agent import PlannerAgent
from .agents.qa_agent import SlideVisualQAAgent
from .builder.word_sync import sync_word_into_pptx
from .config import Settings, get_settings
from .figure_factory.factory import ScientificFigureFactory
from .figure_factory.palettes import list_palettes
from .providers.llm_image_provider import ModelProvider, settings_from_request_headers
from .qa.slide_renderer import render_slide_preview_png
from .schemas.deck_spec import (
    ArchetypeId,
    BuildPptxRequest,
    CoverTemplateId,
    DeckSpec,
    DesignStyle,
    EngineType,
    FigureAsset,
    GenerateFigureRequest,
    PaletteApplyRequest,
    PlanRequest,
    ScenarioType,
    SelectOrRefineFigureRequest,
)


settings = get_settings(ensure_dirs=False)
app = FastAPI(title="Academic PPT Design Studio API", version="4.0.0")

_RAW_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").strip()
_CORS_ORIGINS = ["*"] if not _RAW_ORIGINS or _RAW_ORIGINS == "*" else [o.strip() for o in _RAW_ORIGINS.split(",") if o.strip()]
MAX_UPLOAD_BYTES = max(1, int(os.environ.get("MAX_UPLOAD_MB", "20"))) * 1024 * 1024
DECK_TTL_HOURS = float(os.environ.get("DECK_TTL_HOURS", "24"))
_PROTECTED_DECK_IDS: Set[str] = {"nature_editorial_showcase", "science2021_nirmatrelvir"}
_last_cleanup_ts: float = 0.0

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=_CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


ARCHETYPE_CATALOG = [
    {"id": ArchetypeId.A01.value, "name": "A01 · 3D 剖切装置 + 放大镜微界面", "engines": ["sci3d_art", "vector_mech"]},
    {"id": ArchetypeId.A02.value, "name": "A02 · 3D 团聚失效 vs 多孔限域分散", "engines": ["sci3d_art"]},
    {"id": ArchetypeId.A03.value, "name": "A03 · 2D 扁平微立体编辑插画", "engines": ["sci3d_art"]},
    {"id": ArchetypeId.A04.value, "name": "A04 · CYLview 3D 球棍分子模型", "engines": ["cylview_3d"]},
    {"id": ArchetypeId.A05.value, "name": "A05 · ChemDraw ACS 1996 + 柔色光晕", "engines": ["chemdraw_rdkit"]},
    {"id": ArchetypeId.A06.value, "name": "A06 · OriginPro 600 DPI 1:1 定量谱学", "engines": ["origin_plot"]},
    {"id": ArchetypeId.A07.value, "name": "A07 · VESTA 晶体多面体 + 双色硬切分屏", "engines": ["sci3d_art"]},
    {"id": ArchetypeId.A08.value, "name": "A08 · Nature Reviews 黑线扁平多尺度三联", "engines": ["sci3d_art"]},
    {"id": ArchetypeId.A09.value, "name": "A09 · 同心圆环综述与 BioRender 通路", "engines": ["vector_mech"]},
    {"id": ArchetypeId.A10.value, "name": "A10 · 全矢量催化双循环 / 路线 / 象限", "engines": ["vector_mech"]},
]

COVER_TEMPLATE_CATALOG = [
    {"id": CoverTemplateId.hero_band_bottom_bar.value, "name": "01 · 经典横幅底栏式", "short_desc": "上部主题满幅底色+居中徽标标题，下部纯白三栏圆标元数据"},
    {"id": CoverTemplateId.top_bottom_bands_framed.value, "name": "02 · 上下双带纯白夹心式", "short_desc": "上下主题色带对称呼应，中段纯白留白配淡彩徽标底纹与胶囊铭牌"},
    {"id": CoverTemplateId.floating_rounded_hero_card.value, "name": "03 · 悬浮圆角主色卡式", "short_desc": "白边环绕大圆角主色浮卡，左上场景标签+右下透光几何底纹"},
    {"id": CoverTemplateId.left_aligned_rounded_panel.value, "name": "04 · 精致留白圆角大板式", "short_desc": "主色圆角版面左对齐重磅排版+右侧大校徽水纹，底部双栏机构信息"},
    {"id": CoverTemplateId.chevron_v_cut_banner.value, "name": "05 · 顶部 V 型尖角裁切式", "short_desc": "大 V 型几何切角主题头图配白色胶囊标签，底部居中纯白承托院徽"},
]


def _to_artifact_url(path_str: Optional[str]) -> Optional[str]:
    if not path_str:
        return None
    p = Path(path_str).resolve()
    root = settings.artifacts_root.resolve()
    try:
        rel = p.relative_to(root).as_posix()
        return f"/api/artifacts/{rel}"
    except Exception:
        return None


def _attach_preview_urls(deck: DeckSpec) -> DeckSpec:
    for sl in deck.slides:
        if sl.figure_spec:
            for a in sl.figure_spec.assets:
                for cand in a.candidates:
                    if not cand.png_path.startswith("/api/"):
                        url = _to_artifact_url(cand.png_path)
                        if url:
                            cand.raw_png_path = cand.raw_png_path or url
    return deck


def cleanup_old_decks(
    decks_root: Path,
    ttl_hours: float = 24.0,
    keep_ids: Optional[Set[str]] = None,
) -> int:
    """Remove expired temporary deck directories while keeping curated showcase decks intact."""
    if not decks_root.exists() or ttl_hours <= 0:
        return 0
    protected = set(_PROTECTED_DECK_IDS)
    if keep_ids:
        protected.update(keep_ids)
    cutoff = time.time() - ttl_hours * 3600.0
    removed = 0
    for item in decks_root.iterdir():
        if not item.is_dir() or item.name in protected:
            continue
        try:
            if item.stat().st_mtime < cutoff:
                shutil.rmtree(item, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


def _save_upload_limited(upload: UploadFile, target: Path, max_bytes: Optional[int] = None) -> None:
    limit = MAX_UPLOAD_BYTES if max_bytes is None else max_bytes
    written = 0
    try:
        upload.file.seek(0)
    except Exception:
        pass
    try:
        with target.open("wb") as f:
            while True:
                chunk = upload.file.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Uploaded file exceeds maximum allowed size ({limit // (1024 * 1024) or 1} MB).",
                    )
                f.write(chunk)
    except HTTPException:
        if target.exists():
            target.unlink(missing_ok=True)
        raise


def _deck_dir(deck_id: Optional[str]) -> Path:
    global _last_cleanup_ts
    now = time.time()
    if now - _last_cleanup_ts > 1800.0:
        _last_cleanup_ts = now
        cleanup_old_decks(settings.decks_root, ttl_hours=DECK_TTL_HOURS)
    did = deck_id or f"deck_{uuid.uuid4().hex[:8]}"
    d = settings.decks_root / did
    d.mkdir(parents=True, exist_ok=True)
    return d


def _frontend_dist_dir() -> Path:
    return settings.repo_root / "frontend" / "dist"


def _request_provider(request: Request) -> Tuple[Settings, ModelProvider]:
    req_settings = settings_from_request_headers(settings, request.headers)
    return req_settings, ModelProvider(req_settings)


@app.get("/api/health")
def health() -> Dict[str, object]:
    return {
        "status": "ok",
        "version": "4.0.0",
        "artifacts_root": str(settings.artifacts_root),
        "server_llm_backend": ModelProvider(settings).active_text_backend(),
        "frontend_bundled": (_frontend_dist_dir() / "index.html").exists(),
    }


@app.post("/api/llm/test")
def api_llm_test(request: Request) -> Dict[str, object]:
    _, provider = _request_provider(request)
    return provider.test_connection()


@app.get("/api/palettes")
def api_palettes() -> Dict[str, object]:
    return {"palettes": list_palettes()}


@app.get("/api/archetypes")
def api_archetypes() -> Dict[str, object]:
    return {"archetypes": ARCHETYPE_CATALOG}


@app.get("/api/cover-templates")
def api_cover_templates() -> Dict[str, object]:
    return {"cover_templates": COVER_TEMPLATE_CATALOG}


@app.post("/api/plan")
def api_plan(req: PlanRequest, request: Request) -> Dict[str, object]:
    deck_id = f"deck_{uuid.uuid4().hex[:8]}"
    d_dir = _deck_dir(deck_id)
    req_settings, provider = _request_provider(request)
    planner = PlannerAgent(provider=provider)
    deck = planner.plan_deck(
        source_text=req.source_text,
        deck_title=req.deck_title,
        author=req.author,
        affiliation=req.affiliation,
        scenario=req.scenario,
        target_slide_count=req.target_slide_count,
        palette_id=req.palette_id,
        is_proposal=req.is_proposal,
        deck_id=deck_id,
        design_style=req.design_style,
        cover_template=req.cover_template,
        advisor=req.advisor,
        date_str=req.date_str,
    )

    factory = ScientificFigureFactory(settings=req_settings, provider=provider)
    for sl in deck.slides:
        if sl.figure_spec:
            factory.render_figure_spec(
                sl.figure_spec,
                output_dir=d_dir / "figures" / f"slide_{sl.slide_no:02d}",
                palette_id=deck.meta.palette_id,
                is_proposal=deck.meta.is_proposal,
            )
        preview_p = d_dir / "previews" / f"slide_{sl.slide_no:02d}.png"
        render_slide_preview_png(sl, deck, preview_p)

    spec_path = d_dir / "deck_spec.json"
    spec_path.write_text(deck.model_dump_json(by_alias=True, indent=2), encoding="utf-8")

    return {
        "deck_spec": deck.model_dump(by_alias=True),
        "artifact_urls": {
            f"slide_{sl.slide_no:02d}": _to_artifact_url(str(d_dir / "previews" / f"slide_{sl.slide_no:02d}.png"))
            for sl in deck.slides
        },
        "asset_urls": _collect_asset_urls(deck),
    }


@app.post("/api/plan/upload")
async def api_plan_upload(
    request: Request,
    file: UploadFile = File(...),
    deck_title: Optional[str] = Form(default=None),
    author: str = Form(default="Researcher"),
    affiliation: str = Form(default="School of Pharmaceutical Sciences"),
    advisor: str = Form(default=""),
    date_str: str = Form(default=""),
    scenario: ScenarioType = Form(default=ScenarioType.defense),
    target_slide_count: int = Form(default=10),
    palette_id: str = Form(default="lancet"),
    is_proposal: bool = Form(default=False),
    design_style: DesignStyle = Form(default=DesignStyle.defense_modular),
    cover_template: CoverTemplateId = Form(default=CoverTemplateId.hero_band_bottom_bar),
) -> Dict[str, object]:
    deck_id = f"deck_{uuid.uuid4().hex[:8]}"
    d_dir = _deck_dir(deck_id)
    upload_p = d_dir / f"source_{Path(file.filename or 'input.txt').name}"
    _save_upload_limited(file, upload_p)
    text = parse_file_to_text(upload_p)

    req = PlanRequest(
        source_text=text,
        deck_title=deck_title,
        author=author,
        affiliation=affiliation,
        advisor=advisor,
        date_str=date_str,
        scenario=scenario,
        target_slide_count=target_slide_count,
        palette_id=palette_id,
        is_proposal=is_proposal,
        design_style=design_style,
        cover_template=cover_template,
    )
    return api_plan(req, request)


def _collect_asset_urls(deck: DeckSpec) -> Dict[str, object]:
    urls: Dict[str, object] = {}
    for sl in deck.slides:
        if not sl.figure_spec:
            continue
        for asset in sl.figure_spec.assets:
            urls[asset.asset_id] = {
                "png_url": _to_artifact_url(asset.png_path),
                "candidates": [
                    {
                        "candidate_id": c.candidate_id,
                        "png_url": _to_artifact_url(c.png_path),
                        "ocr_text_count": c.ocr_text_count,
                        "vlm_aesthetic_score": c.vlm_aesthetic_score,
                        "passed": c.passed,
                    }
                    for c in asset.candidates
                ],
            }
    return urls


@app.post("/api/figures/generate")
def api_figures_generate(req: GenerateFigureRequest, request: Request) -> Dict[str, object]:
    d_dir = _deck_dir(req.deck_id)
    out_dir = d_dir / "figures" / f"slide_{req.slide_no:02d}_{uuid.uuid4().hex[:4]}"
    req_settings, provider = _request_provider(request)
    factory = ScientificFigureFactory(settings=req_settings, provider=provider)
    res_spec = factory.render_figure_spec(
        req.figure_spec,
        output_dir=out_dir,
        palette_id=req.palette_id,
        is_proposal=req.is_proposal,
        best_of_n=req.best_of_n,
    )
    return {
        "figure_spec": res_spec.model_dump(),
        "asset_urls": {
            a.asset_id: {
                "png_url": _to_artifact_url(a.png_path),
                "candidates": [
                    {
                        "candidate_id": c.candidate_id,
                        "png_url": _to_artifact_url(c.png_path),
                        "ocr_text_count": c.ocr_text_count,
                        "vlm_aesthetic_score": c.vlm_aesthetic_score,
                        "passed": c.passed,
                    }
                    for c in a.candidates
                ],
            }
            for a in res_spec.assets
        },
    }


@app.post("/api/figures/select-or-refine")
def api_figures_select_or_refine(req: SelectOrRefineFigureRequest, request: Request) -> Dict[str, object]:
    fspec = req.figure_spec
    if req.archetype_override and req.archetype_override != fspec.archetype:
        fspec = build_default_figure_spec(
            archetype=req.archetype_override,
            slide_no=req.slide_no,
            palette_id=req.palette_id,
            box_in=fspec.box_in,
            smiles=req.smiles_override,
            origin_preset=req.origin_preset,
        )

    for asset in fspec.assets:
        if req.asset_id and asset.asset_id != req.asset_id:
            continue
        if req.selected_candidate_idx is not None and 0 <= req.selected_candidate_idx < len(asset.candidates):
            asset.selected_candidate_idx = req.selected_candidate_idx
            cand = asset.candidates[req.selected_candidate_idx]
            asset.png_path = cand.png_path
            return {
                "figure_spec": fspec.model_dump(),
                "asset_urls": {asset.asset_id: {"png_url": _to_artifact_url(asset.png_path)}},
            }

        if req.smiles_override:
            asset.smiles = req.smiles_override
        if req.fixed_bond_length_px is not None:
            asset.fixed_bond_length_px = req.fixed_bond_length_px
        if req.highlight_atoms is not None:
            asset.highlight_atoms = req.highlight_atoms
        if req.origin_preset:
            asset.preset = req.origin_preset
        if req.render_mode:
            asset.render_mode = req.render_mode
        if req.refinement_instruction:
            asset.refinement_note = req.refinement_instruction

    d_dir = _deck_dir(req.deck_id)
    req_settings, provider = _request_provider(request)
    factory = ScientificFigureFactory(settings=req_settings, provider=provider)
    updated = factory.render_figure_spec(
        fspec,
        output_dir=d_dir / "figures" / f"slide_{req.slide_no:02d}_refine_{uuid.uuid4().hex[:4]}",
        palette_id=req.palette_id,
    )
    return {
        "figure_spec": updated.model_dump(),
        "asset_urls": {
            a.asset_id: {
                "png_url": _to_artifact_url(a.png_path),
                "candidates": [
                    {
                        "candidate_id": c.candidate_id,
                        "png_url": _to_artifact_url(c.png_path),
                        "ocr_text_count": c.ocr_text_count,
                        "vlm_aesthetic_score": c.vlm_aesthetic_score,
                        "passed": c.passed,
                    }
                    for c in a.candidates
                ],
            }
            for a in updated.assets
        },
    }


@app.post("/api/figures/upload")
async def api_figures_upload(
    file: UploadFile = File(...),
    deck_id: str = Form(default="deck_custom"),
    slide_no: int = Form(default=1),
    asset_id: str = Form(default="custom_upload"),
) -> Dict[str, object]:
    d_dir = _deck_dir(deck_id)
    up_dir = d_dir / "uploads"
    up_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "figure.png").suffix or ".png"
    target = up_dir / f"slide_{slide_no:02d}_{asset_id}_{uuid.uuid4().hex[:6]}{suffix}"
    _save_upload_limited(file, target)

    asset = FigureAsset(
        asset_id=asset_id,
        engine=EngineType.uploaded_image,
        png_path=str(target),
    )
    return {
        "asset": asset.model_dump(),
        "png_url": _to_artifact_url(str(target)),
    }


@app.post("/api/palettes/apply")
def api_palettes_apply(req: PaletteApplyRequest) -> Dict[str, object]:
    deck = req.deck_spec
    deck.meta.palette_id = req.palette_id
    d_dir = _deck_dir(deck.meta.deck_id)
    factory = ScientificFigureFactory(settings=settings)

    for sl in deck.slides:
        if req.rerender_figures and sl.figure_spec:
            factory.render_figure_spec(
                sl.figure_spec,
                output_dir=d_dir / "figures" / f"slide_{sl.slide_no:02d}_{req.palette_id}",
                palette_id=req.palette_id,
                is_proposal=deck.meta.is_proposal,
            )
        render_slide_preview_png(sl, deck, d_dir / "previews" / f"slide_{sl.slide_no:02d}.png")

    return {
        "deck_spec": deck.model_dump(by_alias=True),
        "artifact_urls": {
            f"slide_{sl.slide_no:02d}": _to_artifact_url(str(d_dir / "previews" / f"slide_{sl.slide_no:02d}.png"))
            for sl in deck.slides
        },
        "asset_urls": _collect_asset_urls(deck),
    }


@app.post("/api/preview/slide")
def api_preview_slide(payload: Dict[str, object]) -> Dict[str, object]:
    deck = DeckSpec.model_validate(payload["deck_spec"])
    slide_no = int(payload.get("slide_no", 1))
    layers = payload.get("layers", ["L1", "L2", "L3"])
    sl = next((s for s in deck.slides if s.slide_no == slide_no), None)
    if sl is None:
        raise HTTPException(status_code=404, detail=f"Slide {slide_no} not found")
    d_dir = _deck_dir(deck.meta.deck_id)
    tag = "_".join(str(x) for x in layers)
    out_p = d_dir / "previews" / f"slide_{slide_no:02d}_{tag}.png"
    render_slide_preview_png(sl, deck, out_p, layers=list(layers))
    return {"preview_url": _to_artifact_url(str(out_p))}


@app.post("/api/build/pptx")
def api_build_pptx(req: BuildPptxRequest) -> Dict[str, object]:
    deck = req.deck_spec
    d_dir = _deck_dir(deck.meta.deck_id)
    qa_agent = SlideVisualQAAgent(factory=ScientificFigureFactory(settings=settings))
    pptx_path, report, previews = qa_agent.build_and_verify(deck, d_dir, max_rounds=2 if req.run_qa_loop else 1)

    spec_p = d_dir / "deck_spec.json"
    spec_p.write_text(deck.model_dump_json(by_alias=True, indent=2), encoding="utf-8")

    return {
        "pptx_url": _to_artifact_url(str(pptx_path)),
        "deck_spec_url": _to_artifact_url(str(spec_p)),
        "preview_urls": [_to_artifact_url(str(p)) for p in previews],
        "audit_report": report.model_dump(),
    }


@app.post("/api/sync/word")
async def api_sync_word(
    docx_file: UploadFile = File(...),
    deck_id: str = Form(...),
) -> Dict[str, object]:
    d_dir = _deck_dir(deck_id)
    input_pptx = d_dir / f"{deck_id}.pptx"
    if not input_pptx.exists():
        raise HTTPException(status_code=404, detail=f"Built PPTX not found for deck_id={deck_id}. Run /api/build/pptx first.")

    docx_p = d_dir / f"sync_{Path(docx_file.filename or 'updated.docx').name}"
    _save_upload_limited(docx_file, docx_p)

    out_pptx = d_dir / f"{deck_id}_synced.pptx"
    res = sync_word_into_pptx(docx_p, input_pptx, out_pptx)
    return {
        **res,
        "synced_pptx_url": _to_artifact_url(str(out_pptx)),
    }


@app.get("/api/artifacts/{file_path:path}")
def api_get_artifact(file_path: str):
    target = (settings.artifacts_root / file_path).resolve()
    root = settings.artifacts_root.resolve()
    if root not in target.parents and target != root:
        raise HTTPException(status_code=403, detail="Forbidden artifact path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(str(target))


@app.get("/{full_path:path}")
def serve_frontend_spa(full_path: str):
    """Serve bundled Vite production SPA on the same port when frontend/dist is built."""
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    dist = _frontend_dist_dir().resolve()
    index_file = dist / "index.html"
    if not index_file.exists():
        return {
            "status": "backend_only",
            "message": "Frontend not built yet. Run npm run build in frontend/.",
        }
    if full_path:
        candidate = (dist / full_path).resolve()
        if dist in candidate.parents and candidate.is_file():
            return FileResponse(str(candidate))
    return FileResponse(str(index_file))
