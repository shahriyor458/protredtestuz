"""Pro Tred — config loading from .env / environment variables."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# .env har doim project rootda qidiriladi, keyin backend/ papkasida
for candidate in (BASE_DIR / ".env", BASE_DIR / "backend" / ".env"):
    if candidate.exists():
        load_dotenv(candidate)


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _float(v: str | None, default: float) -> float:
    if v is None or v.strip() == "":
        return default
    return float(v)


def _int(v: str | None, default: int) -> int:
    if v is None or v.strip() == "":
        return default
    return int(v)


def _list(v: str | None, default: list[str] | None = None) -> list[str]:
    if v is None or v.strip() == "":
        return default or []
    return [x.strip() for x in v.replace(";", ",").split(",") if x.strip()]


class Config:
    # MT5
    MT5_LOGIN: str = os.getenv("MT5_LOGIN", "").strip()
    MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "").strip()
    MT5_SERVER: str = os.getenv("MT5_SERVER", "").strip()
    MT5_PATH: str = os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")

    TRADE_SYMBOLS: list[str] = _list(os.getenv("TRADE_SYMBOLS"), ["XAUUSD", "XAGUSD"])
    TRADE_TIMEFRAMES: list[str] = _list(os.getenv("TRADE_TIMEFRAMES"), ["M15", "H1", "H4", "D1"])
    SCALP_TIMEFRAMES: list[str] = _list(os.getenv("SCALP_TIMEFRAMES"), ["M1", "M5"])
    POLL_INTERVAL: int = _int(os.getenv("POLL_INTERVAL"), 3)
    SIGNAL_SCAN_INTERVAL: int = _int(os.getenv("SIGNAL_SCAN_INTERVAL"), 60)
    SCALP_SCAN_INTERVAL: int = _int(os.getenv("SCALP_SCAN_INTERVAL"), 15)
    MAX_SPREAD_MULT: float = _float(os.getenv("MAX_SPREAD_MULT"), 3.0)
    NEW_SESSION_UTC: int = _int(os.getenv("NEW_SESSION_UTC"), 0)
    REPORT_CURRENCY: str = os.getenv("REPORT_CURRENCY", "USD")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    DAILY_REPORT_TIME: str = os.getenv("DAILY_REPORT_TIME", "19:00").strip()
    TELEGRAM_ADMIN_IDS: list[int] = [
        int(x) for x in _list(os.getenv("TELEGRAM_ADMIN_IDS")) if x.isdigit()
    ]

    # Engine / trade policy
    TRADE_MODE: str = os.getenv("TRADE_MODE", "SERVER")  # SERVER | PAPER
    PAPER_TRADING: bool = _bool(os.getenv("PAPER_TRADING"), True)
    MAGIC_BASE: int = _int(os.getenv("MAGIC_BASE"), 774410)
    TRADE_ALLOW_MULTIPLE: bool = _bool(os.getenv("TRADE_ALLOW_MULTIPLE"), True)
    MIN_SIGNAL_CONFIDENCE: int = _int(os.getenv("MIN_SIGNAL_CONFIDENCE"), 40)
    MAX_DAILY_TRADES: int = _int(os.getenv("MAX_DAILY_TRADES"), 150)
    SCALPING_ENABLED: bool = _bool(os.getenv("SCALPING_ENABLED"), True)
    NEWS_TRADING: bool = _bool(os.getenv("NEWS_TRADING"), True)
    NEWS_MINUTES_AFTER: int = _int(os.getenv("NEWS_MINUTES_AFTER"), 15)

    # Risk defaults (admin panel tomonidan runtime'da o'zgartiriladi)
    RISK_LEVEL: str = os.getenv("RISK_LEVEL", "aggressive")
    MAX_RISK_PER_TRADE: float = _float(os.getenv("MAX_RISK_PER_TRADE"), 8.0)
    MAX_DAILY_DRAWDOWN: float = _float(os.getenv("MAX_DAILY_DRAWDOWN"), 12.0)
    DAILY_PROFIT_TARGET: float = _float(os.getenv("DAILY_PROFIT_TARGET"), 30.0)
    MAX_OPEN_POSITIONS: int = _int(os.getenv("MAX_OPEN_POSITIONS"), 12)

    # API / Admin
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = _int(os.getenv("API_PORT"), 8120)
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "change-me-strong-token")
    ADMIN_USER: str = os.getenv("ADMIN_USER", "shaxriyor")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "shaxriyor")

    DB_PATH: str = os.getenv("DB_PATH", "backend/data/trader.db")

    @property
    def is_paper(self) -> bool:
        return self.PAPER_TRADING or self.TRADE_MODE.upper() == "PAPER"

    @property
    def trade_symbols(self) -> list[str]:
        return self.TRADE_SYMBOLS


config = Config()