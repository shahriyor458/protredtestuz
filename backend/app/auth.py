"""Pro Tred — Web foydalanuvchilar uchun ro'yxatdan o'tish va kirish."""
from __future__ import annotations

import hashlib
import secrets

from backend.app.account_manager import account_manager
from backend.app.store import store


def hash_password(password: str) -> str:
    salt = hashlib.sha256(password.encode()).hexdigest()[:16]
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    salt = hashlib.sha256(password.encode()).hexdigest()[:16]
    return hashlib.sha256((salt + password).encode()).hexdigest() == hashed


def register(username: str, name: str = "", phone: str = "",
             password: str = "") -> dict:
    username = (username or "").strip()
    if len(username) < 3:
        return {"ok": False, "error": "Login kamida 3 ta belgi bo'lishi kerak."}
    if store.find_user_by_username(username) is not None:
        return {"ok": False, "error": "Bu login allaqachon band."}
    if password and len(password) < 4:
        return {"ok": False, "error": "Parol kamida 4 ta belgi bo'lishi kerak."}

    user = store.create_user(
        username=username, name=(name or username),
        phone=phone,
        password_hash=hash_password(password) if password else None,
        source="web",
    )
    token = secrets.token_hex(16)
    store.set_user_token(user.id, token)
    # Har bir web user o'z akkaunti (5 xonali kod) oladi
    account_manager.create_account(name=f"{username} (#{user.id})", user_id=user.id)
    return {
        "ok": True,
        "user": {"id": user.id, "username": user.username, "name": user.name,
                 "source": user.source, "token": token},
    }


def login(username: str, password: str) -> dict:
    from backend.config import config
    user = store.find_user_by_username((username or "").strip())
    # Admin login
    if username == config.ADMIN_USER and password == config.ADMIN_PASSWORD:
        if user is None:
            user = store.create_user(
                username=username, name="Admin",
                password_hash=hash_password(password), source="web")
            token = secrets.token_hex(16)
            store.set_user_token(user.id, token)
        elif not verify_password(password, user.password_hash or ""):
            token = secrets.token_hex(16)
            store.set_user_token(user.id, token)
        else:
            token = user.token or secrets.token_hex(16)
            store.set_user_token(user.id, token)
        store.touch_user(user.id)
        store.bump_login_count(user.id)
        return {
            "ok": True,
            "role": "admin",
            "user": {"id": user.id, "username": user.username, "name": user.name,
                     "token": token, "role": "admin"},
        }
    # Oddiy foydalanuvchi
    if user is None:
        return {"ok": False, "error": "Foydalanuvchi topilmadi."}
    if not user.password_hash:
        return {"ok": False, "error": "Bu akkaunt paroli yo'q (Telegram orqali)."}
    if not verify_password(password, user.password_hash):
        return {"ok": False, "error": "Parol noto'g'ri."}
    if user.token is None:
        user.token = secrets.token_hex(16)
        store.set_user_token(user.id, user.token)
    store.touch_user(user.id)
    store.bump_login_count(user.id)
    return {
        "ok": True,
        "role": "user",
        "user": {"id": user.id, "username": user.username, "name": user.name,
                 "phone": user.phone, "source": user.source, "token": user.token,
                 "plan": user.plan, "active": user.active, "role": "user",
                 "broker_connected": bool(user.broker_login),
                 "trading_enabled": bool(user.trading_enabled)},
    }


def get_user_by_token(token: str):
    if not token:
        return None
    return store.find_user_by_token(token)