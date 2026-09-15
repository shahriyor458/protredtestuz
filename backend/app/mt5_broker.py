"""Pro Tred — MT5 broker ulagichi (MetaTrader5 Python API).

MetaTrader5 paketi faqat Windows'da, o'sha kompyuterda MT5 terminali
ishlab turganida ishlaydi. Terminal ochiq bo'lmasa ham bu modul
initialize() orqali terminalni o'zi ochishga harakat qiladi.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except Exception:  # pragma: no cover
    mt5 = None
    HAS_MT5 = False

from backend.config import config

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1 if HAS_MT5 else 1,
    "M5": mt5.TIMEFRAME_M5 if HAS_MT5 else 5,
    "M15": mt5.TIMEFRAME_M15 if HAS_MT5 else 15,
    "M30": mt5.TIMEFRAME_M30 if HAS_MT5 else 30,
    "H1": mt5.TIMEFRAME_H1 if HAS_MT5 else 60,
    "H4": mt5.TIMEFRAME_H4 if HAS_MT5 else 240,
    "D1": mt5.TIMEFRAME_D1 if HAS_MT5 else 1440,
}


def _clean_symbol(name: str) -> str:
    """XAUUSD vs XAUUSDm / XAUUSD.a / #XAUUSD.b — yadro nomni ajratish."""
    s = name.strip().replace(".", "").replace("#", "").replace("-", "").upper()
    # broker suffix'larni olib tashlash (masalan XAUUSDm -> XAUUSD)
    for suf in ("M", "A", "B", "H", "Z", "LONG", "MINI", "MICRO"):
        if s.endswith(suf) and len(s) > 6:
            s = s[: -len(suf)]
    return s


class Mt5Broker:
    def __init__(self):
        self.initialized = False
        self.account_no: int | None = None
        self.server = ""
        self.broker_name = ""
        self.symbols: list[str] = []
        self._symbol_map: dict[str, str] = {}

    # ---------------------------------------------------------- connect
    @property
    def available(self) -> bool:
        return HAS_MT5

    def connect(self, login: str = "", password: str = "", server: str = "") -> bool:
        if not HAS_MT5:
            return False
        login = login or config.MT5_LOGIN
        password = password or config.MT5_PASSWORD
        server = server or config.MT5_SERVER

        if not self.initialized:
            if not mt5.initialize():
                # terminal o'z-o'zidan ochilishi uchun urinib ko'ramiz
                path = config.MT5_PATH
                if path and not mt5.initialize(path=path):
                    print(f"[MT5] initialize failed: {mt5.last_error()}")
                    return False
            self.initialized = True

        if login:
            if not mt5.login(login, password=password or None, server=server or None):
                print(f"[MT5] login failed: {mt5.last_error()}")
                return False

        info = mt5.account_info()
        if info is None:
            print(f"[MT5] no account_info: {mt5.last_error()}")
            return False
        self.account_no = info.login
        self.server = info.server or ""
        self.broker_name = info.company or ""
        self._refresh_symbols(config.trade_symbols)
        return True

    def _refresh_symbols(self, wanted: list[str]) -> None:
        self.symbol_map = {}
        all_names = [s.name for s in (mt5.symbols_get() or [])]
        wanted_norm = {_clean_symbol(w): w for w in wanted}
        for name in all_names:
            key = _clean_symbol(name)
            if key in wanted_norm:
                self.symbol_map[wanted_norm[key]] = name
        self.symbols = list(self.symbol_map.keys())

    def resolved_symbol(self, symbol: str) -> str | None:
        return self.symbol_map.get(symbol, symbol if symbol in self.symbols else None)

    def is_connected(self) -> bool:
        if not HAS_MT5:
            return False
        try:
            return mt5.terminal_info() is not None
        except Exception:
            return False

    def shutdown(self):
        if HAS_MT5:
            try:
                mt5.shutdown()
            except Exception:
                pass
        self.initialized = False

    # ---------------------------------------------------------- data
    def account_info(self) -> dict[str, Any] | None:
        if not self.ensure():
            return None
        try:
            info = mt5.account_info()
        except Exception:
            return None
        if info is None:
            return None
        return {
            "login": info.login,
            "server": info.server,
            "broker": info.company,
            "currency": info.currency,
            "balance": float(info.balance),
            "equity": float(info.equity),
            "margin": float(info.margin),
            "free_margin": float(info.margin_free),
            "margin_level": float(info.margin_level or 0.0),
            "leverage": float(info.leverage),
            "profit": float(info.profit),
            "drawdown": float(getattr(info, "storage", 0.0) or 0.0),
        }

    def symbol_info(self, symbol: str) -> dict[str, Any] | None:
        if not self.ensure():
            return None
        name = self.resolved_symbol(symbol)
        if not name:
            return None
        info = mt5.symbol_info(name)
        if info is None:
            return None
        return {
            "symbol": symbol,
            "digits": int(info.digits),
            "point": float(info.point),
            "spread": float(info.spread),
            "min_volume": float(info.volume_min),
            "max_volume": float(info.volume_max),
            "volume_step": float(info.volume_step),
            "tick_value": float(info.trade_tick_value or 0.0),
            "tick_size": float(info.trade_tick_size or 0.0),
            "trade_mode": int(info.trade_mode),
            "session_state": bool(info.trade_mode > 0),
        }

    def tick(self, symbol: str) -> dict[str, Any] | None:
        if not self.ensure():
            return None
        name = self.resolved_symbol(symbol)
        if not name:
            return None
        t = mt5.symbol_info_tick(name)
        if t is None:
            return None
        return {
            "symbol": symbol,
            "bid": float(t.bid),
            "ask": float(t.ask),
            "last": float(t.last),
            "time": t.time,
        }

    def rates(self, symbol: str, timeframe: str = "M15", count: int = 500
              ) -> list[dict[str, Any]] | None:
        if not self.ensure():
            return None
        name = self.resolved_symbol(symbol)
        if not name:
            return None
        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            return None
        rates = mt5.copy_rates_from_pos(name, tf, 0, count)
        if rates is None or len(rates) == 0:
            return None
        return [
            {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["tick_volume"]),
            }
            for r in rates
        ]

    def server_time(self) -> datetime:
        try:
            si = mt5.symbol_info_tick(self.symbols[0]) if self.symbols else None
            if si:
                return datetime.fromtimestamp(si.time, tz=timezone.utc)
        except Exception:
            pass
        return datetime.now(tz=timezone.utc)

    # ---------------------------------------------------------- trading
    def is_trading_allowed(self, symbol: str) -> bool:
        if not self.ensure():
            return False
        name = self.resolved_symbol(symbol)
        if not name:
            return False
        info = mt5.symbol_info(name)
        if info is None:
            return False
        # 0 - santrali yopiq; 2 - spreadli; 1 - eksik.
        return getattr(info, "trade_mode", 0) in (0, 1, 2) and info.visible

    def market_order(self, symbol: str, direction: str, volume: float,
                     sl: float | None = None, tp: float | None = None,
                     magic: int = 0, comment: str = "AI") -> dict[str, Any] | None:
        if not self.ensure():
            return None
        name = self.resolved_symbol(symbol)
        if not name:
            return None
        tick = mt5.symbol_info_tick(name)
        if tick is None:
            return None

        order_type = (
            mt5.ORDER_TYPE_BUY if direction.upper() == "BUY"
            else mt5.ORDER_TYPE_SELL
        )
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        if sl is not None:
            sl = round(sl, self.symbol_info(symbol)["digits"]) if self.symbol_info(symbol) else sl
        if tp is not None:
            tp = round(tp, self.symbol_info(symbol)["digits"]) if self.symbol_info(symbol) else tp

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": name,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(sl) if sl is not None else 0.0,
            "tp": float(tp) if tp is not None else 0.0,
            "deviation": 50,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        try:
            result = mt5.order_send(request)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if result is None:
            return {"ok": False, "error": str(mt5.last_error())}
        d = result._asdict()
        d["ok"] = bool(result.retcode == mt5.TRADE_RETCODE_DONE)
        d["error"] = (
            "OK" if result.retcode == mt5.TRADE_RETCODE_DONE
            else f"{result.retcode} {result.comment}"
        )
        return d

    def modify_trade(self, ticket: int, sl: float | None = None,
                     tp: float | None = None) -> dict[str, Any] | None:
        if not self.ensure():
            return None
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return {"ok": False, "error": "position not found"}
        pos = pos[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": pos.ticket,
            "sl": float(sl) if sl is not None else pos.sl,
            "tp": float(tp) if tp is not None else pos.tp,
        }
        try:
            result = mt5.order_send(request)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if result is None:
            return {"ok": False, "error": str(mt5.last_error())}
        return {"ok": bool(result.retcode == mt5.TRADE_RETCODE_DONE),
                "error": str(result.comment)}

    def close_position(self, ticket: int) -> dict[str, Any] | None:
        if not self.ensure():
            return None
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return {"ok": False, "error": "position not found"}
        pos = pos[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return {"ok": False, "error": "no tick"}
        order_type = (
            mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY
            else mt5.ORDER_TYPE_BUY
        )
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": float(pos.volume),
            "type": order_type,
            "position": pos.ticket,
            "price": float(price),
            "deviation": 50,
            "magic": pos.magic,
            "comment": "AI close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        try:
            result = mt5.order_send(request)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if result is None:
            return {"ok": False, "error": str(mt5.last_error())}
        return {"ok": bool(result.retcode == mt5.TRADE_RETCODE_DONE),
                "error": str(result.comment)}

    def positions(self) -> list[dict[str, Any]]:
        if not self.ensure():
            return []
        try:
            pos = mt5.positions_get()
        except Exception:
            return []
        if not pos:
            return []
        out = []
        for p in pos:
            if p.magic and not (self.magic_range and p.magic in self.magic_range):
                continue
            out.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "direction": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume": float(p.volume),
                "entry": float(p.price_open),
                "sl": float(p.sl or 0.0),
                "tp": float(p.tp or 0.0),
                "current": float(p.price_current),
                "profit": float(p.profit),
                "magic": p.magic,
                "time": p.time,
            })
        return sorted(out, key=lambda x: x["ticket"])

    def history_deals(self, since_unix: int) -> list[dict[str, Any]]:
        if not self.ensure():
            return []
        deals = mt5.history_deals_get(since_unix, datetime.now().timestamp() + 60)
        if not deals:
            return []
        out = []
        for d in deals:
            out.append({
                "ticket": d.ticket,
                "position_id": d.position_id,
                "symbol": d.symbol,
                "type": int(d.type),
                "volume": float(d.volume),
                "price": float(d.price),
                "profit": float(d.profit),
                "fee": float(d.fee or 0.0),
                "commission": float(d.commission or 0.0),
                "time": int(d.time),
                "magic": d.magic,
                "comment": d.comment,
            })
        return out

    def ensure(self) -> bool:
        if not HAS_MT5:
            return False
        return self.initialized or self.connect()

    @property
    def magic_range(self):
        return [config.MAGIC_BASE + i for i in range(20)]


broker = Mt5Broker()