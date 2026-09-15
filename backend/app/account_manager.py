"""Pro Tred — Account manager.

Har bir foydalanuvchi akkaunti 5 xonali tasodifiy ID (link_code) oladi.
Admin panelda akkaunt yaratilib, uning 5 xonali kodi Telegram botga
yuborilsa — akkaunt Telegram chat'iga ulanadi va kunlik hisobot yetkaziladi.
Har qanday broker akkauntini ulash mumkin: MT5 terminalida broker
hisoblarini qo'shish orqali yoki bu yerdan login/parol saqlash orqali.
"""
from __future__ import annotations

import json
import random

from backend.app.mt5_broker import broker
from backend.app.store import store, utcnow

MAX_ATTEMPTS = 20


def generate_link_code() -> str:
    """Unikal 5 xonali raqamli kod."""
    for _ in range(MAX_ATTEMPTS):
        code = f"{random.randint(10000, 99999)}"
        if store.find_account_by_code(code) is None:
            return code
    raise RuntimeError("5 xonali unikal kod topilmadi (ko'p urinish)")


class AccountManager:
    def __init__(self):
        self.active_id: int | None = None

    def active_user_id(self):
        """Hozir faol broker akkauntiga tegishli user ID (yoki None)."""
        if self.active_id is not None:
            with store.session() as s:
                from backend.app.store import Account
                row = s.get(Account, self.active_id)
                if row:
                    return row.user_id
        # faol maydon bo'lmasa — broker login bo'yicha qidirish
        if broker.is_connected():
            info = broker.account_info()
            if info:
                for acc in store.list_accounts():
                    meta = json.loads(acc.meta or "{}")
                    if str(meta.get("mt5_login", "")) == str(info["login"]):
                        return acc.user_id
        return None

    def create_account(self, name: str = "", user_id: int | None = None) -> dict:
        code = generate_link_code()
        acc = store.create_account(code)
        if name or user_id is not None:
            with store.session() as s:
                from backend.app.store import Account
                row = s.get(Account, acc.id)
                if name:
                    row.name = name
                if user_id is not None:
                    row.user_id = user_id
                s.commit()
            acc = store.find_account_by_code(code)
        return {
            "id": acc.id,
            "name": acc.name,
            "link_code": acc.link_code,
            "linked": bool(acc.tg_chat_id),
            "tg_username": acc.tg_username,
            "user_id": acc.user_id,
            "meta": json.loads(acc.meta or "{}"),
        }

    def bind_telegram(self, code: str, chat_id: int | str, username: str = "") -> dict:
        """Telegram bot'dan 5 xonali kod orqali ulash.

        Akkaunt egasi bo'lmasa — Telegram user yaratiladi (source=telegram)
        va akkaunt o'sha user'ga bog'lanadi.
        """
        acc = store.find_account_by_code(code)
        if acc is None:
            return {"ok": False, "error": "Kod topilmadi. Kod 5 xonali raqam bo'lishi shart."}
        if acc.tg_chat_id:
            return {"ok": False, "error": "Bu akkaunt allaqachon boshqa Telegram chat'ga ulangan."}

        # Telegram user'ni topish yoki yaratish
        user = store.find_user_by_chat(chat_id)
        if user is None:
            user = store.create_user(
                username=username or None, name=username or "",
                source="telegram", tg_chat_id=chat_id, tg_username=username)
        store.touch_user(user.id)
        if acc.user_id is None:
            store.set_account_user(acc.id, user.id)

        acc = store.bind_chat(acc.id, chat_id, username)
        return {
            "ok": True,
            "code": acc.link_code,
            "name": acc.name,
            "tg_chat_id": acc.tg_chat_id,
            "user_id": user.id,
        }

    def unbind(self, code: str) -> dict:
        acc = store.find_account_by_code(code)
        if acc is None:
            return {"ok": False, "error": "Kod topilmadi"}
        with store.session() as s:
            a = s.get(type(acc), acc.id)
            a.tg_chat_id = None
            a.tg_username = None
            a.linked_at = None
            s.commit()
        return {"ok": True}

    def list_accounts(self) -> list[dict]:
        out = []
        for acc in store.list_accounts():
            out.append({
                "id": acc.id,
                "user_id": acc.user_id,
                "name": acc.name,
                "link_code": acc.link_code,
                "linked": bool(acc.tg_chat_id),
                "tg_username": acc.tg_username,
                "created_at": acc.created_at.isoformat() if acc.created_at else "",
                "linked_at": acc.linked_at.isoformat() if acc.linked_at else "",
                "meta": json.loads(acc.meta or "{}"),
            })
        return out

    def set_meta(self, code: str, **kv) -> dict:
        acc = store.find_account_by_code(code)
        if acc is None:
            return {"ok": False, "error": "Kod topilmadi"}
        with store.session() as s:
            a = s.get(type(acc), acc.id)
            meta = json.loads(a.meta or "{}")
            meta.update(kv)
            a.meta = json.dumps(meta)
            s.commit()
        return {"ok": True}

    def switch_broker(self, code: str, login: str, password: str, server: str) -> dict:
        """Boshqa broker akkauntiga o'tish (MT5 login)."""
        acc = store.find_account_by_code(code)
        if acc is None:
            return {"ok": False, "error": "Kod topilmadi"}
        ok = broker.connect(login=login, password=password, server=server)
        if not ok:
            return {"ok": False, "error": f"MT5 login muvaffaqiyatsiz: {login}@{server}"}
        self.set_meta(code, mt5_login=login, mt5_server=server)
        self.active_id = acc.id
        return {"ok": True, "login": login, "server": server}

    def accounts_for_telegram(self, chat_id) -> list[dict]:
        out = []
        for acc in store.list_accounts():
            if acc.tg_chat_id == str(chat_id):
                out.append(self._serialize(acc))
        return out

    @staticmethod
    def _serialize(acc) -> dict:
        return {
            "id": acc.id,
            "name": acc.name,
            "link_code": acc.link_code,
            "linked": bool(acc.tg_chat_id),
            "tg_username": acc.tg_username,
        }


account_manager = AccountManager()