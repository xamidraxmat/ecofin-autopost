"""Gemini API (bepul tarif) bilan ishlash: matn yozish, tadqiqot, sifat nazorati."""
from __future__ import annotations

import json
import re
import time

import requests

from .config import common, env, log

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(RuntimeError):
    pass


def _call(model: str, body: dict, key: str) -> dict:
    r = requests.post(API.format(model=model), params={"key": key}, json=body, timeout=180)
    if r.status_code != 200:
        raise LLMError(f"{model}: HTTP {r.status_code} {r.text[:300]}")
    return r.json()


def _text(resp: dict) -> str:
    try:
        parts = resp["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise LLMError(f"Bo'sh javob: {json.dumps(resp)[:300]}")
    return "".join(p.get("text", "") for p in parts).strip()


def generate(prompt: str, *, system: str | None = None, json_mode: bool = False,
             search: bool = False, temperature: float | None = None) -> str:
    cfg = common()["gemini"]
    key = env("GEMINI_API_KEY")
    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature if temperature is not None else cfg.get("temperature", 0.7)},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    if search and cfg.get("use_search", True):
        body["tools"] = [{"google_search": {}}]

    errors = []
    for model in cfg["models"]:
        for attempt in range(3):
            try:
                return _text(_call(model, body, key))
            except LLMError as e:
                msg = str(e)
                errors.append(msg)
                if "429" in msg or "503" in msg or "500" in msg:
                    time.sleep(15 * (attempt + 1))   # limit — kutib qayta urinish
                    continue
                if search and "tools" in body and ("400" in msg or "403" in msg):
                    log("Google qidiruv mavjud emas — qidiruvsiz davom etyapman.")
                    body.pop("tools")
                    continue
                break  # boshqa model sinab ko'riladi
    raise LLMError("Gemini ishlamadi:\n" + "\n".join(errors[-4:]))


def generate_json(prompt: str, **kw) -> dict:
    raw = generate(prompt, json_mode=True, **kw)
    return parse_json(raw)


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    if m:
        raw = m.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1:
        raise LLMError(f"JSON topilmadi: {raw[:200]}")
    return json.loads(raw[start:end + 1])
