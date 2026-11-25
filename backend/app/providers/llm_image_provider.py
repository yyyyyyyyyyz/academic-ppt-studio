"""Pluggable Provider Architecture for LLM Planning, Image Generation & VLM Critique.

Supports:
1. Gemini REST API (`GEMINI_API_KEY`)
2. OpenAI-Compatible REST API (`OPENAI_API_KEY` + `OPENAI_BASE_URL`)
3. Deterministic Local Studio Fallback (`local` or automatic fallback on any failure)
"""

from __future__ import annotations

import base64
from dataclasses import replace
import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlparse

import httpx

from ..config import Settings, get_settings


def _clean_http_url(raw: str) -> Optional[str]:
    val = (raw or "").strip().rstrip("/")
    if not val:
        return None
    parsed = urlparse(val)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return val
    return None


def settings_from_request_headers(base: Settings, headers: Mapping[str, str]) -> Settings:
    """Create an isolated per-request Settings copy from BYOK HTTP headers without mutating global config."""
    lowered = {str(k).lower(): str(v).strip() for k, v in headers.items()}
    hdr_provider = lowered.get("x-llm-provider", "").lower()
    hdr_key = lowered.get("x-llm-api-key", "")
    hdr_base = lowered.get("x-llm-base-url", "")
    hdr_model = lowered.get("x-llm-model", "")
    hdr_fig = lowered.get("x-figure-provider", "").lower()

    if not hdr_provider and not hdr_key and not hdr_fig:
        return base

    allowed_modes = {"local", "openai", "gemini", "auto"}
    if hdr_provider in allowed_modes:
        provider_mode = hdr_provider
    elif hdr_key:
        provider_mode = "openai"
    else:
        provider_mode = base.llm_provider_mode

    fig_mode = hdr_fig if hdr_fig in allowed_modes else "local"
    updates: Dict[str, Any] = {
        "llm_provider_mode": provider_mode,
        "figure_provider_mode": fig_mode,
    }

    if provider_mode == "gemini":
        if hdr_key:
            updates["gemini_api_key"] = hdr_key
        if hdr_model:
            updates["gemini_text_model"] = hdr_model
    elif provider_mode in {"openai", "auto"}:
        if hdr_key:
            updates["openai_api_key"] = hdr_key
        safe_url = _clean_http_url(hdr_base)
        if safe_url:
            updates["openai_base_url"] = safe_url
        if hdr_model:
            updates["openai_text_model"] = hdr_model

    return replace(base, **updates)


class ModelProvider:
    """Unified pluggable text / vision / image generation provider."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def active_text_backend(self) -> str:
        mode = self.settings.llm_provider_mode
        if mode == "local":
            return "local"
        if mode == "gemini" and self.settings.gemini_api_key:
            return "gemini"
        if mode == "openai" and self.settings.openai_api_key:
            return "openai"
        if mode == "auto":
            if self.settings.gemini_api_key:
                return "gemini"
            if self.settings.openai_api_key:
                return "openai"
        return "local"

    def active_image_backend(self) -> str:
        mode = self.settings.figure_provider_mode
        if mode == "local":
            return "local"
        if mode == "gemini" and self.settings.gemini_api_key:
            return "gemini"
        if mode == "openai" and self.settings.openai_api_key:
            return "openai"
        if mode == "auto":
            if self.settings.gemini_api_key:
                return "gemini"
            if self.settings.openai_api_key:
                return "openai"
        return "local"

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: float = 45.0) -> Optional[Dict[str, Any]]:
        """Attempt structured JSON generation via Gemini or OpenAI; returns None on fallback."""
        backend = self.active_text_backend()
        if backend == "local":
            return None

        try:
            if backend == "gemini":
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.settings.gemini_text_model}:generateContent?key={self.settings.gemini_api_key}"
                )
                payload = {
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
                }
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    txt = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(txt)

            if backend == "openai":
                url = f"{self.settings.openai_base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
                payload = {
                    "model": self.settings.openai_text_model,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                }
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    txt = data["choices"][0]["message"]["content"]
                    return json.loads(txt)
        except Exception:
            return None

        return None

    def generate_image(self, prompt: str, output_png: Path, timeout: float = 60.0) -> bool:
        """Generate a raw studio-white scientific illustration via configured cloud backend.

        Returns True if cloud image written cleanly to output_png; False signals caller to use
        the high-craft local studio renderer fallback.
        """
        backend = self.active_image_backend()
        if backend == "local":
            return False

        output_png.parent.mkdir(parents=True, exist_ok=True)

        try:
            if backend == "gemini":
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.settings.gemini_image_model}:generateContent?key={self.settings.gemini_api_key}"
                )
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                }
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    for cand in data.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            inline = part.get("inlineData") or part.get("inline_data")
                            if inline and inline.get("data"):
                                output_png.write_bytes(base64.b64decode(inline["data"]))
                                return True

            if backend == "openai":
                url = f"{self.settings.openai_base_url}/images/generations"
                headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
                payload = {
                    "model": self.settings.openai_image_model,
                    "prompt": prompt,
                    "n": 1,
                    "size": "1536x1024",
                }
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    item = data["data"][0]
                    if "b64_json" in item:
                        output_png.write_bytes(base64.b64decode(item["b64_json"]))
                        return True
                    if "url" in item:
                        img_resp = client.get(item["url"])
                        img_resp.raise_for_status()
                        output_png.write_bytes(img_resp.content)
                        return True
        except Exception:
            return False

        return False

    def critique_image(self, image_path: Path, rubric_prompt: str, timeout: float = 35.0) -> Optional[Dict[str, Any]]:
        """Evaluate an image with VLM (OCR zero-text & aesthetic score). Returns None if offline/fallback."""
        backend = self.active_text_backend()
        if backend == "local" or not image_path.exists():
            return None

        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        try:
            if backend == "gemini":
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.settings.gemini_text_model}:generateContent?key={self.settings.gemini_api_key}"
                )
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": rubric_prompt},
                                {"inlineData": {"mimeType": "image/png", "data": b64}},
                            ]
                        }
                    ],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
                }
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    txt = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(txt)

            if backend == "openai":
                url = f"{self.settings.openai_base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
                payload = {
                    "model": self.settings.openai_text_model,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": rubric_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            ],
                        }
                    ],
                }
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return json.loads(data["choices"][0]["message"]["content"])
        except Exception:
            return None

        return None

    def _scrub_secrets(self, text: str) -> str:
        cleaned = text
        for secret in (self.settings.gemini_api_key, self.settings.openai_api_key):
            if secret:
                cleaned = cleaned.replace(secret, "***")
        return cleaned

    def test_connection(self, timeout: float = 15.0) -> Dict[str, Any]:
        """Verify LLM connectivity for current settings (local deterministic or BYOK cloud API)."""
        t0 = time.perf_counter()
        backend = self.active_text_backend()
        if backend == "local":
            return {
                "ok": True,
                "backend": "local",
                "model": "deterministic-local",
                "latency_ms": 0,
                "message": "本地确定性引擎已就绪（RDKit 2D / 3D / 矢量机理与原生 PPTX 编译无需 API Key）",
            }

        active_model = (
            self.settings.gemini_text_model if backend == "gemini" else self.settings.openai_text_model
        )
        try:
            if backend == "gemini":
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.settings.gemini_text_model}:generateContent?key={self.settings.gemini_api_key}"
                )
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": 'Return JSON: {"pong": true}'}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0},
                }
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    _ = data["candidates"][0]["content"]["parts"][0]["text"]
            elif backend == "openai":
                url = f"{self.settings.openai_base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
                payload = {
                    "model": self.settings.openai_text_model,
                    "temperature": 0.0,
                    "max_tokens": 32,
                    "messages": [
                        {"role": "system", "content": "Reply concisely."},
                        {"role": "user", "content": 'Reply with {"pong": true}'},
                    ],
                }
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    _ = data["choices"][0]["message"]["content"]
            latency_ms = int(round((time.perf_counter() - t0) * 1000))
            return {
                "ok": True,
                "backend": backend,
                "model": active_model,
                "latency_ms": latency_ms,
                "message": f"{active_model} 连通成功，可进行 AI 文献解析与大纲规划",
            }
        except Exception as exc:
            latency_ms = int(round((time.perf_counter() - t0) * 1000))
            safe_err = self._scrub_secrets(str(exc))
            return {
                "ok": False,
                "backend": backend,
                "model": active_model,
                "latency_ms": latency_ms,
                "message": f"连接失败：{safe_err[:180]}",
            }
