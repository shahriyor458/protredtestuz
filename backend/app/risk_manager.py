"""Pro Tred — Risk & Balance boshqaruvi.

Risk darajalari:
  - Conservative (Past): har bir bitimga balansning 1–2%
  - Moderate (O'rta): 3–5%
  - Aggressive (Yuqori): 5%+

Admin panel orqali MAX_RISK_PER_TRADE va MAX_DAILY_DRAWDOWN o'zgartiriladi,
o'sha qiymatlar this modul tomonidan ishlatiladi.
"""
from __future__ import annotations

from datetime import date

from backend.app.mt5_broker import broker
from backend.app.store import store, utcnow

RISK_BANDS = {
    "conservative": (1.0, 2.0),
    "moderate": (3.0, 5.0),
    "aggressive": (5.0, 8.0),
}

KEY_RISK_LEVEL = "RISK_LEVEL"
KEY_MAX_RISK = "MAX_RISK_PER_TRADE"
KEY_MAX_DD = "MAX_DAILY_DRAWDOWN"
KEY_DAILY_TARGET = "DAILY_PROFIT_TARGET"
KEY_MAX_OPEN = "MAX_OPEN_POSITIONS"
KEY_PAPER = "PAPER_TRADING"
KEY_MIN_CONF = "MIN_SIGNAL_CONFIDENCE"
KEY_MAX_DAILY_TRADES = "MAX_DAILY_TRADES"
KEY_SCALPING = "SCALPING_ENABLED"
KEY_NEWS = "NEWS_TRADING"


class RiskManager:
    def __init__(self):
        self.day = ""
        self.day_open_equity: float | None = None
        self.day_peak_equity: float | None = None
        self.day_trades: int = 0
        self._load_settings()

    def _load_settings(self):
        from backend.config import config
        # agar DB da sozlama yo'q bo'lsa .env dan olinadi
        stored = store.all_settings()
        self.level = stored.get(KEY_RISK_LEVEL) or config.RISK_LEVEL
        self.max_risk_per_trade = float(stored.get(KEY_MAX_RISK, config.MAX_RISK_PER_TRADE))
        self.max_daily_drawdown = float(stored.get(KEY_MAX_DD, config.MAX_DAILY_DRAWDOWN))
        self.daily_profit_target = float(stored.get(KEY_DAILY_TARGET, config.DAILY_PROFIT_TARGET))
        self.max_open_positions = int(stored.get(KEY_MAX_OPEN, config.MAX_OPEN_POSITIONS) or 4)
        self.paper = bool(stored.get(KEY_PAPER, config.is_paper))
        self.min_confidence = float(stored.get(KEY_MIN_CONF, config.MIN_SIGNAL_CONFIDENCE))
        self.max_daily_trades = int(stored.get(KEY_MAX_DAILY_TRADES, config.MAX_DAILY_TRADES) or 6)
        self.scalping = bool(stored.get(KEY_SCALPING, config.SCALPING_ENABLED))
        self.news_trading = bool(stored.get(KEY_NEWS, config.NEWS_TRADING))

    def set_setting(self, key: str, value) -> None:
        store.set_setting(key, value)
        self._load_settings()

    # -----------------------------------------------------------------
    def reset_daily(self, now=None) -> None:
        """Yangi sessiya (kun) boshlanishi: kunlik byudjet qayta to'ldiriladi."""
        from datetime import timezone
        now = now or utcnow()
        day = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
        if day != self.day:
            self.day = day
            info = broker.account_info()
            eq = info["equity"] if info else 0.0
            self.day_open_equity = eq
            self.day_peak_equity = eq
            self.day_trades = 0

    def current_drawdown(self, equity: float | None = None) -> tuple[float, float]:
        """(drawdown_pct, drawdown_abs) — kundan boshlab."""
        info = broker.account_info()
        equity = equity if equity is not None else (info["equity"] if info else 0.0)
        if not self.day_peak_equity:
            return 0.0, 0.0
        peak = max(self.day_peak_equity, equity)
        self.day_peak_equity = peak
        dd = peak - equity
        dd_pct = (dd / peak * 100.0) if peak else 0.0
        return dd_pct, dd

    def daily_profit_pct(self, equity: float | None = None) -> float:
        info = broker.account_info()
        equity = equity if equity is not None else (info["equity"] if info else 0.0)
        if not self.day_open_equity:
            return 0.0
        return (equity - self.day_open_equity) / self.day_open_equity * 100.0

    def is_drawdown_hit(self, equity: float | None = None) -> bool:
        dd, _ = self.current_drawdown(equity)
        return dd >= self.max_daily_drawdown

    def is_profit_target_hit(self, equity: float | None = None) -> bool:
        return self.daily_profit_pct(equity) >= self.daily_profit_target

    def can_open(self, open_positions: int, confidence: float | None = None) -> tuple[bool, str]:
        """Yangi pozitsiya ochish uchun ruxsat."""
        if self.day_trades >= self.max_daily_trades:
            return False, f"Kunlik savdo limiti ({self.max_daily_trades}) tugadi"
        if open_positions >= self.max_open_positions:
            return False, f"Maksimal ochiq pozitsiya ({self.max_open_positions}) to'ldi"
        if self.is_drawdown_hit():
            return False, f"Kunlik drawdown limiti ({self.max_daily_drawdown}%) kesib o'tildi"
        if self.is_profit_target_hit():
            return False, f"Kunlik foyda maqsadi ({self.daily_profit_target}%) erishildi"
        if confidence is not None and confidence < self.min_confidence:
            return False, f"Signal confidence ({confidence:.0f}) chegaradan ({self.min_confidence:.0f}) past"
        return True, "OK"

    # -----------------------------------------------------------------
    def risk_percent(self) -> float:
        """Amaldagi risk darajasi bo'ycha bitimga xavf foizi."""
        lo, hi = RISK_BANDS.get(self.level, RISK_BANDS["moderate"])
        return min(max(self.max_risk_per_trade, lo), hi)

    def position_size(self, symbol_info: dict, tick, sl_distance: float,
                      balance: float) -> tuple[float, str]:
        """Balans va xavf foizi asosida lot hisobi."""
        risk_amount = balance * self.risk_percent() / 100.0
        if sl_distance <= 0:
            return 0.0, "SL masofasi noto'g'ri"
        tval = symbol_info.get("tick_value", 0)
        tsize = symbol_info.get("tick_size", 0)
        if tval <= 0 or tsize <= 0:
            return 0.0, "tick ma'lumotlari yo'q"
        # usd per 1.0 lot per 1.0 price move
        usd_per_unit = tval / tsize
        if usd_per_unit <= 0:
            return 0.0, "lot qiymati 0"
        volume = risk_amount / (sl_distance * usd_per_unit)
        step = symbol_info.get("volume_step", 0.01)
        if step <= 0:
            step = 0.01
        # step ga bo'lamiz
        volume = math_floor(volume, step)
        min_v = symbol_info.get("min_volume", 0.01)
        max_v = symbol_info.get("max_volume", 100.0)
        if volume < min_v:
            return 0.0, f"Hisoblangan hajm ({volume:.2f}) minimal ({min_v}) dan kichik"
        volume = min(volume, max_v)
        return round(volume, 2), "OK"

    def on_trade_opened(self):
        self.day_trades += 1
        store.set_setting("_day_trades", self.day_trades)


def math_floor(value: float, step: float) -> float:
    import math
    if step <= 0:
        return value
    return math.floor(value / step) * step


risk = RiskManager()


def risk_summary() -> dict:
    """Admin panel uchun risk holati."""
    rules = RISK_BANDS.get(risk.level, RISK_BANDS["moderate"])
    dd_pct, dd_abs = risk.current_drawdown()
    return {
        "risk_level": risk.level,
        "risk_band": rules,
        "risk_percent_per_trade": risk.risk_percent(),
        "max_risk_per_trade": round(risk.max_risk_per_trade, 2),
        "max_daily_drawdown": round(risk.max_daily_drawdown, 1),
        "daily_profit_target": round(risk.daily_profit_target, 1),
        "max_open_positions": risk.max_open_positions,
        "max_daily_trades": risk.max_daily_trades,
        "min_confidence": risk.min_confidence,
        "paper_trading": risk.paper,
        "scalping": risk.scalping,
        "news_trading": risk.news_trading,
        "current_drawdown_pct": round(dd_pct, 2),
        "current_drawdown_abs": round(dd_abs, 2),
        "daily_profit_pct": round(risk.daily_profit_pct(), 2),
        "trades_today": risk.day_trades,
    }