"""
models.py — Registry cac model LLM mien phi (OpenRouter :free + Gemini free tier).

Vai tro ② trong pipeline RAG: sinh cau tra loi (khong tao vector). OpenRouter
la lua chon chinh, Gemini la du phong — xem default_selection().

Muc dich:
  - Tu dong lay danh sach model mien phi moi nhat tu API cong khai cua
    OpenRouter (khong can API key), cache 1 gio -> luon co model moi ma
    khong phai sua code.
  - Kem danh sach du phong (DEFAULT_OPENROUTER_MODELS) de van chay duoc
    khi khong goi duoc API (mat mang, chan firewall...).

Model spec dung chung toan bo du an:
    { "provider": "openrouter" | "gemini", "model": <model_id>, "label": str }
"""
from __future__ import annotations

import logging
import os
import time
import urllib.request
import json

logger = logging.getLogger(__name__)

# Cache trong RAM — 1 gio goi lai API 1 lan
_CACHE_TTL_SEC = 3600
_cache: dict = {"ts": 0.0, "models": None}

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Danh sach du phong: cac model :free on dinh, duoc chon thu cong.
# CHI dung khi khong goi duoc API OpenRouter (mat mang, chan firewall...) —
# binh thuong lay danh sach truc tiep tu API de tranh model da het mien phi.
# Gan OPENROUTER_MODELS=oai/model1:free,org/model2:free trong .env de tu dinh nghia.
DEFAULT_OPENROUTER_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",   # mac dinh trong .env
    "nvidia/nemotron-3.5-lightning:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free",
]

# Model co :free nhung khong phai chatbot (phan loai, kiem duyet noi dung...)
_EXCLUDE_KEYWORDS = ("content-safety",)

GEMINI_DEFAULT_MODEL = "gemini-3.6-flash"


def _parse_env_model_list() -> list[str]:
    """Doc OPENROUTER_MODELS tu .env (cach nhau boi dau phay), neu co."""
    raw = os.getenv("OPENROUTER_MODELS", "")
    return [m.strip() for m in raw.split(",") if m.strip()]


def _fetch_free_models(limit: int = 25) -> list[str]:
    """Goi API cong khai cua OpenRouter, tra ve id cac model :free (chat tro chuyen duoc).

    Loc:
      - id tan cung bang :free (duong dan dinh gia 0 dong)
      - chi giu model nhan text va tra ve text (loai image/audio generation)
    Sap xep: uu tien cac ho model manh ve chat tieng Viet / pho bien truoc.
    """
    req = urllib.request.Request(
        OPENROUTER_MODELS_URL,
        headers={"User-Agent": "chatbot-quyche/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    ids: list[str] = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        if not mid.endswith(":free"):
            continue
        if any(kw in mid for kw in _EXCLUDE_KEYWORDS):
            continue
        arch = (m.get("architecture") or {})
        ins = arch.get("input_modalities") or []
        outs = arch.get("output_modalities") or []
        # Chatbot can: dau vao co text, dau ra la text (chat hoac text)
        if "text" not in ins or not (set(outs) & {"text", "chat"}):
            continue
        ids.append(mid)

    # Ho duoc uu tien (chat tot, pho bien, ho tro nhieu ngon ngu ke ca tieng Viet)
    preferred = ("openai/", "nvidia/", "deepseek/", "anthropic/",
                 "meta-llama/", "qwen/", "google/", "mistralai/", "z-ai/")

    def _rank(mid: str) -> tuple:
        for i, pref in enumerate(preferred):
            if mid.startswith(pref):
                return (0, i, mid)
        return (1, 0, mid)

    ids.sort(key=_rank)
    return ids[:limit]


def get_openrouter_free_models(refresh: bool = False) -> list[str]:
    """Danh sach model :free cua OpenRouter (cache 1h; loi mang -> list du phong)."""
    if not refresh and _cache["models"] and \
            time.monotonic() - _cache["ts"] < _CACHE_TTL_SEC:
        return _cache["models"]

    ids = _parse_env_model_list()
    if not ids:
        try:
            ids = _fetch_free_models()
            logger.info("Lay duoc %d model :free tu OpenRouter API", len(ids))
        except Exception as e:
            logger.warning("Khong lay duoc danh sach model OpenRouter (%s: %s) "
                           "-> dung danh sach du phong",
                           type(e).__name__, str(e)[:120])
            ids = list(DEFAULT_OPENROUTER_MODELS)

    # Model cau hinh trong .env luon co mat (dat dau — do la lua chon cua user)
    env_model = os.getenv("OPENROUTER_MODEL", "")
    if env_model and env_model not in ids:
        ids.insert(0, env_model)

    _cache["models"], _cache["ts"] = ids, time.monotonic()
    return ids


def gemini_available() -> bool:
    # Uu tien GOOGLE_API_KEY (ten chuan cua SDK Google); GEMINI_API_KEY la
    # ten cu cua du an — chap nhan ca hai de .env dat ten nao cung chay duoc.
    key = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    return bool(key) and "PASTE" not in key


def openrouter_available() -> bool:
    key = os.getenv("OPENROUTER_API_KEY", "")
    return bool(key) and "PASTE" not in key


def gemini_model_id() -> str:
    return os.getenv("GEMINI_MODEL", GEMINI_DEFAULT_MODEL)


def list_available_models() -> list[dict]:
    """Danh sach {provider, model, label} kha dung de hien thi tren web.

    Gom: toan bo model OpenRouter :free (model chinh — chi khi co key) +
    Gemini (du phong — chi khi co key).
    """
    models: list[dict] = []
    if openrouter_available():
        for mid in get_openrouter_free_models():
            models.append({"provider": "openrouter", "model": mid,
                           "label": f"⚡ {mid}"})
    if gemini_available():
        gid = gemini_model_id()
        models.append({"provider": "gemini", "model": gid,
                       "label": f"✨ {gid} (Google — dự phòng)"})
    return models


def default_selection() -> dict:
    """Model mac dinh (cau hinh trong .env hoac dau danh sach kha dung).

    OpenRouter la lua chon chinh (model tra loi cau hinh trong OPENROUTER_MODEL
    — doi tu do, ke ca model :free); Gemini chi la du phong khi OpenRouter loi
    hoac khong co key.
    """
    if openrouter_available():
        env_model = os.getenv("OPENROUTER_MODEL", "")
        if env_model:
            return {"provider": "openrouter", "model": env_model,
                    "label": f"⚡ {env_model}"}
        free = get_openrouter_free_models()
        if free:
            return {"provider": "openrouter", "model": free[0],
                    "label": f"⚡ {free[0]}"}
    if gemini_available():
        gid = gemini_model_id()
        return {"provider": "gemini", "model": gid, "label": f"✨ {gid}"}
    return {}

