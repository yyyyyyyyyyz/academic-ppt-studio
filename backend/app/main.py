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

from dataclasses import replace
import hmac
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .agents.art_director_agent import build_default_figure_spec
from .agents.doc_parser import ParsedDocument, parse_document_file
from .agents.outline_agent import OutlineAgent, load_word_outline_skill
from .agents.planner_agent import PlannerAgent
from .agents.qa_agent import SlideVisualQAAgent
from .billing import BillingError, BillingStore, default_billing_db_path
from .builder.word_sync import sync_word_into_pptx
from .config import Settings, get_settings
from .figure_factory.chem_grounding import resolve_compound_smiles
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
billing_store = BillingStore(default_billing_db_path(settings.repo_root))
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
    {"id": ArchetypeId.A05.value, "name": "ChemDraw 2D · 高清分子结构式（6 种画风 + .cdxml）", "engines": ["chemdraw_rdkit"]},
    {"id": ArchetypeId.A04.value, "name": "PyMOL / CYLview 3D · 球棍构象（+ .sdf）", "engines": ["cylview_3d"]},
    {"id": ArchetypeId.A06.value, "name": "OriginPro / Nature · 600 DPI 统计与谱学图（+ .csv）", "engines": ["origin_plot"]},
    {"id": ArchetypeId.A10.value, "name": "专业机理与路线 · 3D球棍机理 / 催化循环 / 技术路线", "engines": ["vector_mech"]},
    {"id": ArchetypeId.A09.value, "name": "综述分类图 · 同心圆环 Sunburst", "engines": ["vector_mech"]},
    {"id": ArchetypeId.A01.value, "name": "AI 3D 概念图 · 反应装置剖切与微界面（接生图模型更佳）", "engines": ["sci3d_art", "vector_mech"]},
    {"id": ArchetypeId.A02.value, "name": "AI 3D 概念图 · 团聚 vs 限域分散对比（接生图模型更佳）", "engines": ["sci3d_art"]},
    {"id": ArchetypeId.A03.value, "name": "AI 2D 概念图 · 物理场激活编辑插画（接生图模型更佳）", "engines": ["sci3d_art"]},
    {"id": ArchetypeId.A07.value, "name": "AI 晶体界面图 · VESTA 多面体双色分屏（接生图模型更佳）", "engines": ["sci3d_art"]},
    {"id": ArchetypeId.A08.value, "name": "AI 多尺度线稿 · 宏观-介观-微观三联（接生图模型更佳）", "engines": ["sci3d_art"]},
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


class RedeemCheckRequest(BaseModel):
    code: str = ""


class AdminGenerateCodesRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=100)
    credits: int = Field(default=5, ge=1, le=10000)
    prefix: str = Field(default="PRO", max_length=12)
    label: str = Field(default="", max_length=80)
    valid_days: Optional[int] = Field(default=None, ge=1, le=3650)


class AdminRevokeCodeRequest(BaseModel):
    code: str
    active: bool = False


def _admin_secret() -> str:
    return os.environ.get("ADMIN_SECRET", "").strip()


def _require_code_for_hosted() -> bool:
    return os.environ.get("REQUIRE_CODE_FOR_HOSTED", "true").strip().lower() not in {"0", "false", "no"}


def _official_plan_cost() -> int:
    try:
        return max(1, int(os.environ.get("OFFICIAL_PLAN_COST", "1")))
    except ValueError:
        return 1


def _official_model_label() -> str:
    custom = os.environ.get("OFFICIAL_MODEL_LABEL", "").strip()
    if custom:
        return custom
    backend = ModelProvider(settings).active_text_backend()
    if backend == "gemini":
        return f"官方 Pro · {settings.gemini_text_model}"
    if backend == "openai":
        return f"官方 Pro · {settings.openai_text_model}"
    return "官方 Pro 学术精读模型"


def _official_purchase_note() -> str:
    return os.environ.get(
        "OFFICIAL_PURCHASE_NOTE",
        "联系站长获取官方 AI 次数兑换码；也可免费使用本地确定性引擎或自带 API Key。",
    ).strip()


def _verify_admin(request: Request) -> None:
    configured = _admin_secret()
    if not configured:
        raise HTTPException(
            status_code=503,
            detail="管理员密钥未配置：请在服务器 .env 中设置 ADMIN_SECRET 后再使用发码管理。",
        )
    supplied = request.headers.get("x-admin-secret", "").strip()
    if not supplied or not hmac.compare_digest(supplied, configured):
        raise HTTPException(status_code=403, detail="管理员密钥错误，无权操作卡密。")


def _resolve_request_provider(
    request: Request,
    *,
    consume_for_plan: bool = False,
    validate_hosted_code: bool = False,
) -> Tuple[Settings, ModelProvider, Optional[Dict[str, Any]]]:
    hdr_provider = request.headers.get("x-llm-provider", "").strip().lower()
    hdr_key = request.headers.get("x-llm-api-key", "").strip()
    hdr_code = request.headers.get("x-access-code", "").strip()

    if hdr_provider == "hosted":
        server_backend = ModelProvider(settings).active_text_backend()
        if server_backend == "local":
            raise HTTPException(
                status_code=503,
                detail="站长尚未在服务器配置官方大模型 API，请先切回「本地确定性引擎」或使用自带 API Key。",
            )
        cost = _official_plan_cost()
        try:
            if consume_for_plan:
                info = billing_store.consume(hdr_code, amount=cost, action="plan_deck")
            elif validate_hosted_code:
                info = billing_store.validate_for_use(hdr_code, amount=cost)
            else:
                info = billing_store.validate_for_use(hdr_code, amount=1)
        except BillingError as exc:
            raise HTTPException(status_code=402, detail=exc.message) from exc

        hosted_settings = replace(settings, figure_provider_mode="local")
        receipt = {
            "mode": "hosted",
            "code": info["code"],
            "cost": cost if consume_for_plan else 0,
            "credits_left": info["credits_left"],
            "credits_total": info["credits_total"],
        }
        return hosted_settings, ModelProvider(hosted_settings), receipt

    if hdr_key and hdr_provider in {"openai", "gemini", "auto", ""}:
        req_settings = settings_from_request_headers(settings, request.headers)
        return req_settings, ModelProvider(req_settings), None

    if _require_code_for_hosted():
        local_only = replace(settings, llm_provider_mode="local", figure_provider_mode="local")
        return local_only, ModelProvider(local_only), None

    req_settings = settings_from_request_headers(settings, request.headers)
    return req_settings, ModelProvider(req_settings), None


def _request_provider(request: Request) -> Tuple[Settings, ModelProvider]:
    req_settings, provider, _ = _resolve_request_provider(request, consume_for_plan=False)
    return req_settings, provider


@app.get("/api/health")
def health() -> Dict[str, object]:
    server_backend = ModelProvider(settings).active_text_backend()
    return {
        "status": "ok",
        "version": "4.0.0",
        "artifacts_root": str(settings.artifacts_root),
        "server_llm_backend": server_backend,
        "hosted_ai_enabled": server_backend != "local",
        "frontend_bundled": (_frontend_dist_dir() / "index.html").exists(),
    }


@app.get("/api/billing/status")
def api_billing_status() -> Dict[str, object]:
    server_backend = ModelProvider(settings).active_text_backend()
    return {
        "hosted_ai_enabled": server_backend != "local",
        "hosted_backend": server_backend,
        "model_label": _official_model_label(),
        "purchase_note": _official_purchase_note(),
        "plan_cost": _official_plan_cost(),
        "require_code_for_hosted": _require_code_for_hosted(),
    }


@app.post("/api/billing/redeem-check")
def api_billing_redeem_check(req: RedeemCheckRequest) -> Dict[str, object]:
    info = billing_store.get_code(req.code)
    if info is None:
        return {
            "valid": False,
            "code": req.code.strip().upper(),
            "credits_left": 0,
            "credits_total": 0,
            "active": False,
            "expired": False,
            "label": "",
            "expires_at": None,
            "message": "兑换码不存在，请核对输入是否完整。",
        }
    msg = "兑换码有效"
    if not info["active"]:
        msg = "该兑换码已被停用"
    elif info["expired"]:
        msg = "该兑换码已过期"
    elif info["credits_left"] <= 0:
        msg = "该兑换码次数已用完"
    else:
        msg = f"兑换码有效，剩余 {info['credits_left']} / {info['credits_total']} 次"
    return {**info, "message": msg}


@app.post("/api/admin/codes/generate")
def api_admin_generate_codes(req: AdminGenerateCodesRequest, request: Request) -> Dict[str, object]:
    _verify_admin(request)
    created = billing_store.create_codes(
        count=req.count,
        credits=req.credits,
        prefix=req.prefix,
        label=req.label,
        valid_days=req.valid_days,
    )
    return {"codes": created}


@app.get("/api/admin/codes")
def api_admin_list_codes(request: Request, limit: int = 100) -> Dict[str, object]:
    _verify_admin(request)
    codes = billing_store.list_codes(limit=limit)
    return {"codes": codes, "total": len(codes)}


@app.post("/api/admin/codes/revoke")
def api_admin_revoke_code(req: AdminRevokeCodeRequest, request: Request) -> Dict[str, object]:
    _verify_admin(request)
    ok = billing_store.set_active(req.code, req.active)
    if not ok:
        raise HTTPException(status_code=404, detail="兑换码不存在")
    return {"ok": True, "code": req.code.strip().upper(), "active": req.active}


@app.post("/api/llm/test")
def api_llm_test(request: Request) -> Dict[str, object]:
    hdr_provider = request.headers.get("x-llm-provider", "").strip().lower()
    if hdr_provider == "hosted":
        _, provider, billing_info = _resolve_request_provider(request, validate_hosted_code=True)
        res = provider.test_connection()
        if billing_info:
            res["credits_left"] = billing_info["credits_left"]
            res["credits_total"] = billing_info["credits_total"]
            if res.get("ok"):
                res["message"] = f"{_official_model_label()} 连通成功，兑换码剩余 {billing_info['credits_left']} 次"
        return res
    _, provider, _ = _resolve_request_provider(request)
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


@app.get("/api/skills/word-outline")
def api_get_word_outline_skill() -> Dict[str, object]:
    return {
        "name": "word-to-ppt-outline",
        "version": "1.0",
        "content": load_word_outline_skill(),
    }


@app.post("/api/outline/from-file")
async def api_outline_from_file(
    request: Request,
    file: UploadFile = File(...),
    target_slide_count: int = Form(default=8),
    scenario: ScenarioType = Form(default=ScenarioType.defense),
    is_proposal: bool = Form(default=False),
) -> Dict[str, object]:
    outline_dir = _deck_dir(f"outline_{uuid.uuid4().hex[:8]}")
    upload_p = outline_dir / f"source_{Path(file.filename or 'input.docx').name}"
    _save_upload_limited(file, upload_p)
    fallback_title = Path(file.filename or "学术研究工作汇报").stem
    parsed_doc = parse_document_file(
        upload_p,
        image_output_dir=outline_dir / "word_images",
        default_title=fallback_title,
    )

    try:
        _, provider, _ = _resolve_request_provider(request, consume_for_plan=False)
    except HTTPException:
        local_cfg = replace(settings, llm_provider_mode="local", figure_provider_mode="local")
        provider = ModelProvider(local_cfg)

    agent = OutlineAgent(provider=provider)
    return agent.summarize_document_to_outline(
        parsed_doc,
        target_slide_count=target_slide_count,
        scenario=scenario,
        is_proposal=is_proposal,
    )


def _run_plan(
    req: PlanRequest,
    request: Request,
    *,
    parsed_doc: Optional[ParsedDocument] = None,
    deck_id: Optional[str] = None,
) -> Dict[str, object]:
    active_deck_id = deck_id or f"deck_{uuid.uuid4().hex[:8]}"
    d_dir = _deck_dir(active_deck_id)
    req_settings, provider, billing_info = _resolve_request_provider(request, consume_for_plan=True)
    try:
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
            deck_id=active_deck_id,
            design_style=req.design_style,
            cover_template=req.cover_template,
            advisor=req.advisor,
            date_str=req.date_str,
            parsed_doc=parsed_doc,
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
    except Exception as exc:
        if billing_info and billing_info.get("cost", 0) > 0:
            billing_store.refund(
                billing_info["code"],
                amount=int(billing_info["cost"]),
                detail=f"error:{type(exc).__name__}",
            )
        raise

    return {
        "deck_spec": deck.model_dump(by_alias=True),
        "artifact_urls": {
            f"slide_{sl.slide_no:02d}": _to_artifact_url(str(d_dir / "previews" / f"slide_{sl.slide_no:02d}.png"))
            for sl in deck.slides
        },
        "asset_urls": _collect_asset_urls(deck),
        "billing": billing_info,
    }


@app.post("/api/plan")
def api_plan(req: PlanRequest, request: Request) -> Dict[str, object]:
    return _run_plan(req, request)


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
    fallback_title = (deck_title or "").strip() or Path(file.filename or "学术研究工作汇报").stem
    parsed_doc = parse_document_file(
        upload_p,
        image_output_dir=d_dir / "word_images",
        default_title=fallback_title,
    )

    req = PlanRequest(
        source_text=parsed_doc.raw_text,
        deck_title=deck_title or parsed_doc.title,
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
    return _run_plan(req, request, parsed_doc=parsed_doc, deck_id=deck_id)


def _with_cache_bust(url: Optional[str], tag: str) -> Optional[str]:
    if not url:
        return None
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}v={tag}"


def _asset_url_entry(asset: FigureAsset, cache_tag: Optional[str] = None) -> Dict[str, object]:
    png_u = _to_artifact_url(asset.png_path)
    if cache_tag and png_u:
        png_u = _with_cache_bust(png_u, cache_tag)
    return {
        "png_url": png_u,
        "svg_url": _to_artifact_url(asset.svg_path),
        "cdxml_url": _to_artifact_url(asset.cdxml_path),
        "sdf_url": _to_artifact_url(asset.sdf_path),
        "csv_url": _to_artifact_url(asset.csv_path),
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "png_url": _with_cache_bust(_to_artifact_url(c.png_path), cache_tag) if cache_tag else _to_artifact_url(c.png_path),
                "ocr_text_count": c.ocr_text_count,
                "vlm_aesthetic_score": c.vlm_aesthetic_score,
                "passed": c.passed,
            }
            for c in asset.candidates
        ],
    }


def _collect_asset_urls(deck: DeckSpec, cache_tag: Optional[str] = None) -> Dict[str, object]:
    urls: Dict[str, object] = {}
    for sl in deck.slides:
        if not sl.figure_spec:
            continue
        for asset in sl.figure_spec.assets:
            urls[asset.asset_id] = _asset_url_entry(asset, cache_tag=cache_tag)
    return urls


@app.post("/api/figures/generate")
def api_figures_generate(req: GenerateFigureRequest, request: Request) -> Dict[str, object]:
    d_dir = _deck_dir(req.deck_id)
    bust = uuid.uuid4().hex[:6]
    out_dir = d_dir / "figures" / f"slide_{req.slide_no:02d}_{bust}"
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
        "asset_urls": {a.asset_id: _asset_url_entry(a, cache_tag=bust) for a in res_spec.assets},
    }


@app.post("/api/figures/select-or-refine")
def api_figures_select_or_refine(req: SelectOrRefineFigureRequest, request: Request) -> Dict[str, object]:
    fspec = req.figure_spec
    resolved_smiles = (
        resolve_compound_smiles(req.smiles_override, allow_pubchem=True) or req.smiles_override
        if req.smiles_override
        else None
    )
    if req.archetype_override and req.archetype_override != fspec.archetype:
        base_smiles = resolved_smiles or next((a.smiles for a in fspec.assets if a.smiles), None)
        fspec = build_default_figure_spec(
            archetype=req.archetype_override,
            slide_no=req.slide_no,
            palette_id=req.palette_id,
            box_in=fspec.box_in,
            smiles=base_smiles,
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
                "asset_urls": {asset.asset_id: _asset_url_entry(asset)},
            }

        if resolved_smiles:
            asset.smiles = resolved_smiles
        if req.fixed_bond_length_px is not None:
            asset.fixed_bond_length_px = req.fixed_bond_length_px
        if req.highlight_atoms is not None:
            asset.highlight_atoms = req.highlight_atoms
        if req.chem_style_override:
            asset.chem_style = req.chem_style_override
            asset.drug_burgundy = req.chem_style_override == "nature_burgundy"
        if req.style_3d_override:
            asset.style_3d = req.style_3d_override
        if req.rotation_deg_override is not None:
            asset.rotation_deg = [float(x) for x in req.rotation_deg_override[:3]]
        if req.show_nonpolar_h_override is not None:
            asset.show_nonpolar_h = req.show_nonpolar_h_override
        if req.origin_preset:
            asset.preset = req.origin_preset
        if req.render_mode:
            asset.render_mode = req.render_mode
        if req.mech_mode_override:
            asset.mech_mode = req.mech_mode_override
        if req.refinement_instruction:
            asset.refinement_note = req.refinement_instruction

    d_dir = _deck_dir(req.deck_id)
    req_settings, provider = _request_provider(request)
    factory = ScientificFigureFactory(settings=req_settings, provider=provider)
    bust = uuid.uuid4().hex[:6]
    updated = factory.render_figure_spec(
        fspec,
        output_dir=d_dir / "figures" / f"slide_{req.slide_no:02d}_refine_{bust}",
        palette_id=req.palette_id,
    )
    return {
        "figure_spec": updated.model_dump(),
        "asset_urls": {a.asset_id: _asset_url_entry(a, cache_tag=bust) for a in updated.assets},
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
    bust = f"{req.palette_id}_{uuid.uuid4().hex[:6]}"

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
            f"slide_{sl.slide_no:02d}": _with_cache_bust(
                _to_artifact_url(str(d_dir / "previews" / f"slide_{sl.slide_no:02d}.png")),
                bust,
            )
            for sl in deck.slides
        },
        "asset_urls": _collect_asset_urls(deck, cache_tag=bust),
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
    return {"preview_url": _with_cache_bust(_to_artifact_url(str(out_p)), uuid.uuid4().hex[:6])}


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
