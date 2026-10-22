"""6-bosqich: Telegram admin bot orqali yuborish (Bot API, bepul)."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from .config import env

TIMEOUT = 300


class TG:
    def __init__(self, token: str | None = None):
        self.token = token or env("TELEGRAM_BOT_TOKEN")
        self.base = f"https://api.telegram.org/bot{self.token}"

    def call(self, method: str, files: dict | None = None, **params):
        data = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                for k, v in params.items() if v is not None}
        opened = {}
        try:
            for k, p in (files or {}).items():
                opened[k] = open(p, "rb")
            r = requests.post(f"{self.base}/{method}", data=data, files=opened or None, timeout=TIMEOUT)
        finally:
            for f in opened.values():
                f.close()
        res = r.json()
        if not res.get("ok"):
            raise RuntimeError(f"Telegram {method}: {res.get('description')}")
        return res["result"]

    # --- media: fayl yo'li (Path) yoki oldin yuklangan file_id (str) ---
    def _media(self, key: str, value):
        if isinstance(value, Path):
            return {key: value}, {}
        return {}, {key: value}

    def photo(self, chat, photo, caption=None, markup=None, silent=False):
        f, p = self._media("photo", photo)
        m = self.call("sendPhoto", files=f, chat_id=chat, caption=caption, parse_mode="HTML",
                      reply_markup=markup, disable_notification=silent, **p)
        return m, m["photo"][-1]["file_id"]

    def text(self, chat, text, markup=None, silent=False):
        return self.call("sendMessage", chat_id=chat, text=text, parse_mode="HTML",
                         reply_markup=markup, disable_notification=silent,
                         link_preview_options={"is_disabled": True})

    def audio(self, chat, audio, title, performer, caption=None, silent=False):
        f, p = self._media("audio", audio)
        m = self.call("sendAudio", files=f, chat_id=chat, title=title, performer=performer,
                      caption=caption, parse_mode="HTML", disable_notification=silent, **p)
        return m, m["audio"]["file_id"]

    def video(self, chat, video, caption=None, thumb: Path | None = None, w=1080, h=1920, silent=False):
        f, p = self._media("video", video)
        if thumb and isinstance(video, Path):
            f["thumbnail"] = thumb
        m = self.call("sendVideo", files=f, chat_id=chat, caption=caption, parse_mode="HTML",
                      width=w, height=h, supports_streaming=True, disable_notification=silent, **p)
        return m, m["video"]["file_id"]

    def updates(self, offset: int):
        return self.call("getUpdates", offset=offset, timeout=0,
                         allowed_updates=["callback_query", "message"])

    def answer(self, callback_id: str, text: str):
        try:
            self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)
        except RuntimeError:
            pass  # eski tugma — e'tibor bermaymiz

    def clear_buttons(self, chat, message_id):
        try:
            self.call("editMessageReplyMarkup", chat_id=chat, message_id=message_id,
                      reply_markup={"inline_keyboard": []})
        except RuntimeError:
            pass


def approval_buttons(draft_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Chiqarish", "callback_data": f"ok|{draft_id}"},
        {"text": "🔄 Qayta yozish", "callback_data": f"re|{draft_id}"},
        {"text": "❌ Bekor", "callback_data": f"no|{draft_id}"},
    ]]}
