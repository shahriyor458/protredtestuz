"""Pro Tred — Yangiliklar (news) xizmati.

Ikki manba:
  1. ForexFactory kalendar (faireconomy.media) — tashqi API (429/403 bo'lsa skip)
  2. Narx harakatidan xabar (volatility spike) — ichki detektor: tez narz o'zgarish
     = yangilik chiqqanini anglatadi. Tashqi API shart emas.

Strategiya — "news momentum scalp":
  Yuqori volatilite yoki yangilik chiqqandan so'ng M5 narx kuchli bir yo'nalishda
  ketsa — o'sha yo'nalishda qisqa (scalp) pozitsiya.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
import numpy as np

# Currency map for symbols
SYMBOL_CURRENCY = {
    "XAUUSD": "USD",
    "XAGUSD": "USD",
}

# External calendar cache
_CACHE: dict[str, object] = {"ts": 0.0, "items": []}
_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_CACHE_TTL = 1800.0  # 30 daqiqa cache (API 429 oldini olish)

_MOCK_HIGH_IMPACT: list[dict] = [
    # Odatiy yuqori ta'sirli vaqtlar (UTC) — Python weekday: 0=Mon..6=Sun
    {"title": "US Non-Farm Payrolls", "currency": "United States", "impact": "High", "hour_utc": 12, "dow": 4},
    {"title": "US CPI (YoY)", "currency": "United States", "impact": "High", "hour_utc": 12, "dow": 1},
    {"title": "US FOMC Statement", "currency": "United States", "impact": "High", "hour_utc": 18, "dow": 2},
    {"title": "US Unemployment Rate", "currency": "United States", "impact": "Medium", "hour_utc": 12, "dow": 4},
    {"title": "US GDP (QoQ)", "currency": "United States", "impact": "High", "hour_utc": 12, "dow": 3},
    {"title": "US PPI (MoM)", "currency": "United States", "impact": "Medium", "hour_utc": 12, "dow": 2},
    {"title": "US Core Retail Sales", "currency": "United States", "impact": "High", "hour_utc": 12, "dow": 3},
]


def _fetch_calendar_external() -> list[dict]:
    try:
        req = urllib.request.Request(
            _CALENDAR_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, */*",
            })
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _fetch_calendar_mock() -> list[dict]:
    """API ishlamasligi mumkin — mock calendar asosidagi odatiy yuqori ta'sirli vaqtlar."""
    now = datetime.now(timezone.utc)
    result = []
    for item in _MOCK_HIGH_IMPACT:
        dow = item["dow"]  # 1=Mon..7=Sun
        hour = item["hour_utc"]
        days_ahead = (dow - now.weekday()) % 7
        if days_ahead == 0 and hour <= now.hour:
            days_ahead = 7
        target = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=0, second=0, microsecond=0)
        result.append({
            "title": item["title"],
            "country": item["currency"],
            "currency": "USD",
            "impact": item["impact"],
            "date_ms": int(target.timestamp() * 1000),
            "time_utc": target.strftime("%H:%M"),
        })
    result.sort(key=lambda x: x["date_ms"])
    return result


def get_calendar(force: bool = False) -> list[dict]:
    now = time.time()
    if force or (now - float(_CACHE["ts"])) > _CACHE_TTL:
        # External API dan urinib ko'ramiz
        raw = _fetch_calendar_external()
        used_external = bool(raw)
        if not raw:
            raw = _fetch_calendar_mock()

        cleaned = []
        for it in raw:
            ts = it.get("date") or it.get("date_ms")
            if not ts:
                continue
            try:
                ts = int(ts)
            except (TypeError, ValueError):
                continue
            currency = str(it.get("currency") or "").strip()
            if not currency:
                c = str(it.get("country") or "").strip()
                if "United States" in c or "USD" in c.upper():
                    currency = "USD"
                else:
                    currency = c
            cleaned.append({
                "title": str(it.get("title") or "").strip(),
                "country": str(it.get("country") or "").strip(),
                "currency": currency,
                "impact": str(it.get("impact") or "").strip(),
                "date_ms": ts,
                "time_utc": datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%H:%M"),
            })
        # External API ma'lumot bermasa yoki bo'sh bo'lsa — mock fallback
        if (not cleaned) and used_external:
            cleaned = []
            for it in _fetch_calendar_mock():
                ts = it.get("date") or it.get("date_ms")
                if not ts:
                    continue
                currency = str(it.get("currency") or "").strip() or "USD"
                cleaned.append({
                    "title": str(it.get("title") or "").strip(),
                    "country": str(it.get("country") or "").strip(),
                    "currency": currency,
                    "impact": str(it.get("impact") or "").strip(),
                    "date_ms": int(ts),
                    "time_utc": datetime.fromtimestamp(int(ts) / 1000, timezone.utc).strftime("%H:%M"),
                })
        cleaned.sort(key=lambda x: x["date_ms"])
        _CACHE["items"] = cleaned
        _CACHE["ts"] = now
    return list(_CACHE["items"])


def upcoming(currency: str = "USD", window_min: int = 120) -> list[dict]:
    events = get_calendar()
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    return [
        e for e in events
        if e["currency"].upper() == currency.upper()
        and e["impact"] in ("High", "Medium")
        and 0 <= (e["date_ms"] - now_ms) <= window_min * 60_000
    ]


def recently_released(currency: str = "USD", window_min: int = 20) -> list[dict]:
    events = get_calendar()
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    return [
        e for e in events
        if e["currency"].upper() == currency.upper()
        and e["impact"] in ("High", "Medium")
        and 0 <= (now_ms - e["date_ms"]) <= window_min * 60_000
    ]


def news_momentum(symbol: str, broker) -> dict | None:
    """Narz harakatidan (volatility spike) momentum scalping signali.

    Tashqi kalendarga bog'liq emas — narz o'zgarishini o'zi aniqlaydi:
    oxirgi 3-5 M5 candle'lar kuchli harakat qilsa + yaqinda yangilik bo'lsa
    → sentiment yo'nalishida momentum scalp.
    """
    cur = SYMBOL_CURRENCY.get(symbol.replace("m", "").replace(".", "").upper())
    if not cur:
        return None

    # M5 data
    rates = broker.rates(symbol, "M5", 30)
    if not rates or len(rates) < 20:
        return None

    closes = np.array([r["close"] for r in rates], dtype=float)
    highs = np.array([r["high"] for r in rates], dtype=float)
    lows = np.array([r["low"] for r in rates], dtype=float)
    opens = np.array([r["open"] for r in rates], dtype=float)

    sym_info = broker.symbol_info(symbol)
    if not sym_info:
        return None

    from backend.app.indicators import atr as _atr, last_valid
    atr_14 = last_valid(_atr(highs, lows, closes, 14)) or 0.0
    if atr_14 <= 0:
        return None

    # ─── Volatility spike detector ───
    # Oxirgi 3 M5 candle'dagi umumiy harakat (momentum)
    tail3_move = closes[-1] - closes[-4] if len(closes) >= 4 else 0.0
    # Oxirgi 5 candle
    tail5_move = closes[-1] - closes[-6] if len(closes) >= 6 else 0.0
    # Oxirgi 1 candle (tez)
    last_move = closes[-1] - closes[-2] if len(closes) >= 2 else 0.0
    # Oxirgi 1 candle body size (ko'rsatkich)
    last_body = abs(closes[-1] - opens[-1])
    # Oxirgi 3 ta candle'ning body'lari (kuchli impuls)
    last3_bodies = [abs(closes[-(i+1)] - opens[-(i+1)]) for i in range(3)]
    avg_last3_body = sum(last3_bodies) / 3.0

    # Signal uchun shartlar:
    # 1) Umumiy harakat 1.3+ ATR (kuchli momentum)
    # 2) Umumiy yo'nalish aniq (3 ta candle bir xil yo'nalishda)
    move_3 = tail3_move
    abs_move = abs(move_3)

    # 2) Yo'nalishlik: oxirgi 3 ta candle bir yo'nalishda?
    last3_dirs = []
    for i in range(3):
        idx = -(i+1)
        if idx >= -len(closes):
            last3_dirs.append(1 if closes[idx] > opens[idx] else -1)
    consistency = sum(last3_dirs) / len(last3_dirs) if last3_dirs else 0

    if abs_move < atr_14 * 1.3:
        return None
    if abs(consistency) < 0.66:
        return None  # 2/3 ta candle bir yo'nalishda bo'lishi kerak

    direction = "BUY" if move_3 > 0 else "SELL"
    spread = sym_info.get("spread", 0) * (sym_info.get("point", 0.01) or 0.01)
    digits = sym_info.get("digits", 2)
    price_now = float(closes[-1])

    # SL: 1.0 ATR (tez Scalp)  |  TP: 1.5R
    if direction == "BUY":
        entry = price_now
        sl = round(entry - atr_14 * 1.0, digits)
        tp = round(entry + atr_14 * 1.5, digits)
    else:
        entry = price_now
        sl = round(entry + atr_14 * 1.0, digits)
        tp = round(entry - atr_14 * 1.5, digits)

    # Confidence: harakat kuchiga qarab (1.3 → 70, 2.0 → 85, 3.0+ → 95)
    atr_ratio = abs_move / max(atr_14, 1e-9)
    confidence = 65.0 + min(30.0, (atr_ratio - 1.3) * 25.0)
    confidence = round(max(60.0, min(98.0, confidence)), 1)

    # Yangilik mavjudmi?
    released = recently_released(cur, window_min=20)
    news_info = ""
    if released:
        titles = ", ".join(e["title"] for e in released[:2])
        news_info = f" | [NEWS] {titles}"
        confidence = min(98.0, confidence + 8.0)

    return {
        "direction": direction,
        "entry": round(entry, digits),
        "stop_loss": round(sl, digits),
        "take_profit": round(tp, digits),
        "confidence": confidence,
        "regime": "news_momentum" if released else "volatility_scalp",
        "reasons": [
            f"[FAST] M5 {move_3:+.2f} ({atr_ratio:.1f} ATR)",
            f"Momentum: {abs_move:.1f} ATR, yo'nalishlik: {consistency:.0%}",
            f"SL {atr_14*1.0:.2f} / TP {atr_14*1.5:.2f} ({'yangilik' if released else 'volatilite'}){news_info}",
        ],
        "timeframe": "M5",
    }