"""Tests for Hosted Pro AI Redeem-Code Billing, Anti-Bypass Guard & Owner Admin API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FIGURE_PROVIDER_MODE"] = "local"
os.environ["LLM_PROVIDER_MODE"] = "local"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import app.main as main_mod
from app.billing import BillingStore
from app.config import Settings


def _setup_isolated_app(tmp_path: Path, monkeypatch, *, server_openai_key: str = "sk-server-test") -> TestClient:
    test_settings = Settings(
        artifacts_root=tmp_path / "artifacts",
        decks_root=tmp_path / "artifacts" / "decks",
        gallery_root=tmp_path / "artifacts" / "archetype_gallery",
        demo_deck_root=tmp_path / "artifacts" / "demo_deck",
        llm_provider_mode="auto",
        figure_provider_mode="local",
        gemini_api_key="",
        openai_api_key=server_openai_key,
        openai_base_url="https://api.deepseek.com/v1",
        openai_text_model="deepseek-chat",
    )
    store = BillingStore(tmp_path / "billing.db")
    monkeypatch.setattr(main_mod, "settings", test_settings)
    monkeypatch.setattr(main_mod, "billing_store", store)
    return TestClient(main_mod.app, raise_server_exceptions=False)


def test_admin_secret_and_code_lifecycle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    client = _setup_isolated_app(tmp_path, monkeypatch)

    # Admin endpoints fail closed with 503 when ADMIN_SECRET is unset
    r_unset = client.get("/api/admin/codes")
    assert r_unset.status_code == 503

    monkeypatch.setenv("ADMIN_SECRET", "super-secret-999")
    # Wrong secret -> 403
    r_wrong = client.post(
        "/api/admin/codes/generate",
        headers={"X-Admin-Secret": "wrong-pass"},
        json={"count": 2, "credits": 3},
    )
    assert r_wrong.status_code == 403

    # Valid secret -> generate 2 codes with 3 credits each
    r_gen = client.post(
        "/api/admin/codes/generate",
        headers={"X-Admin-Secret": "super-secret-999"},
        json={"count": 2, "credits": 3, "prefix": "PRO", "label": "体验卡3次"},
    )
    assert r_gen.status_code == 200
    codes = r_gen.json()["codes"]
    assert len(codes) == 2
    code1 = codes[0]["code"]
    assert code1.startswith("PRO-")
    assert codes[0]["credits_left"] == 3

    # Redeem check valid
    chk1 = client.post("/api/billing/redeem-check", json={"code": code1.lower()})
    assert chk1.status_code == 200
    assert chk1.json()["valid"] is True
    assert chk1.json()["credits_left"] == 3

    # Revoke code1 -> redeem check invalid
    r_rev = client.post(
        "/api/admin/codes/revoke",
        headers={"X-Admin-Secret": "super-secret-999"},
        json={"code": code1, "active": False},
    )
    assert r_rev.status_code == 200
    chk_rev = client.post("/api/billing/redeem-check", json={"code": code1})
    assert chk_rev.json()["valid"] is False
    assert chk_rev.json()["active"] is False

    # Re-enable code1
    r_en = client.post(
        "/api/admin/codes/revoke",
        headers={"X-Admin-Secret": "super-secret-999"},
        json={"code": code1, "active": True},
    )
    assert r_en.status_code == 200
    assert client.post("/api/billing/redeem-check", json={"code": code1}).json()["valid"] is True


def test_hosted_anti_bypass_consume_and_refund(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_SECRET", "admin-123")
    monkeypatch.setenv("REQUIRE_CODE_FOR_HOSTED", "true")
    client = _setup_isolated_app(tmp_path, monkeypatch, server_openai_key="sk-server-paid")

    status = client.get("/api/billing/status").json()
    assert status["hosted_ai_enabled"] is True
    assert status["hosted_backend"] == "openai"

    # Anti-bypass: Track backend seen by PlannerAgent for unauthenticated request
    seen_backends = []
    orig_plan_deck = main_mod.PlannerAgent.plan_deck

    def spy_plan_deck(self, *args, **kwargs):
        seen_backends.append(self.provider.active_text_backend())
        # Force deterministic fallback offline without real HTTP call to DeepSeek
        self.provider.settings = Settings(llm_provider_mode="local", figure_provider_mode="local")
        return orig_plan_deck(self, *args, **kwargs)

    monkeypatch.setattr(main_mod.PlannerAgent, "plan_deck", spy_plan_deck)

    # 1. Unauthenticated caller must be downgraded to 'local' even though server has sk-server-paid
    r_anon = client.post(
        "/api/plan",
        json={"source_text": "# 测试\n## 1. 背景\n内容", "target_slide_count": 4, "palette_id": "lancet"},
    )
    assert r_anon.status_code == 200
    assert r_anon.json()["billing"] is None
    assert seen_backends[-1] == "local"

    # 2. Hosted caller without valid code -> 402 Payment Required
    r_no_code = client.post(
        "/api/plan",
        headers={"X-LLM-Provider": "hosted", "X-Access-Code": "PRO-NONE-0000"},
        json={"source_text": "# 测试\n## 1. 背景\n内容", "target_slide_count": 4, "palette_id": "lancet"},
    )
    assert r_no_code.status_code == 402

    # 3. Generate a 1-credit code, consume it successfully -> credits_left == 0, backend == 'openai'
    gen = client.post(
        "/api/admin/codes/generate",
        headers={"X-Admin-Secret": "admin-123"},
        json={"count": 1, "credits": 1},
    ).json()["codes"][0]
    code = gen["code"]

    r_ok = client.post(
        "/api/plan",
        headers={"X-LLM-Provider": "hosted", "X-Access-Code": code},
        json={"source_text": "# 测试\n## 1. 背景\n内容", "target_slide_count": 4, "palette_id": "lancet"},
    )
    assert r_ok.status_code == 200
    assert seen_backends[-1] == "openai"
    assert r_ok.json()["billing"]["credits_left"] == 0

    # 4. Reuse exhausted code -> 402
    r_empty = client.post(
        "/api/plan",
        headers={"X-LLM-Provider": "hosted", "X-Access-Code": code},
        json={"source_text": "# 测试\n## 1. 背景\n内容", "target_slide_count": 4, "palette_id": "lancet"},
    )
    assert r_empty.status_code == 402

    # 5. Refund automatically when generation raises an exception
    code_err = client.post(
        "/api/admin/codes/generate",
        headers={"X-Admin-Secret": "admin-123"},
        json={"count": 1, "credits": 2},
    ).json()["codes"][0]["code"]

    def failing_plan_deck(self, *args, **kwargs):
        raise RuntimeError("Simulated pipeline failure")

    monkeypatch.setattr(main_mod.PlannerAgent, "plan_deck", failing_plan_deck)
    r_fail = client.post(
        "/api/plan",
        headers={"X-LLM-Provider": "hosted", "X-Access-Code": code_err},
        json={"source_text": "# 测试\n## 1. 背景\n内容", "target_slide_count": 4, "palette_id": "lancet"},
    )
    assert r_fail.status_code == 500
    # Credits must be refunded back to 2
    chk_after = client.post("/api/billing/redeem-check", json={"code": code_err}).json()
    assert chk_after["credits_left"] == 2
