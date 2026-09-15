"""Pro Tred — P&L xizmati (real-vaqt va bajarilgan P&L)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.mt5_broker import broker
from backend.app.store import store

DEAL_TYPE_BUY = 0
DEAL_TYPE_SELL = 1
DEAL_TYPE_BUY_CANCELED = 2
DEAL_TYPE_SELL_CANCELED = 3
DEAL_ENTRY_OUT = 1  # position yopish (close)
DEAL_ENTRY_INOUT = 2  # tp/sl orqali berkitish


def today_start_utc() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


class PnlService:
    def __init__(self):
        self.broker = broker

    # -----------------------------------------------------------------
    def unrealized(self, positions=None) -> dict:
        """Ochiq pozitsiyalar bo'yicha suzuvchi P&L."""
        positions = positions if positions is not None else self.broker.positions()
        total = sum(p["profit"] for p in positions)
        info = self.broker.account_info()
        base_balance = info["balance"] if info else 0.0
        pct = (total / base_balance * 100.0) if base_balance else 0.0
        return {
            "unrealized_pnl": round(total, 2),
            "unrealized_pnl_pct": round(pct, 2),
            "open_count": len(positions),
            "positions": positions,
        }

    # -----------------------------------------------------------------
    def realized(self, since_days: int | None = None, to_dt=None) -> dict:
        """Bajarilgan P&L: hisobning butun tarixi (barcha yopilgan bitimlar)."""
        days = since_days if since_days is not None else 3650
        since_dt = to_dt - timedelta(days=days) if to_dt else (datetime.now(timezone.utc) - timedelta(days=days))
        deals = self.broker.history_deals(int(since_dt.timestamp()))
        profit = 0.0
        volume = 0.0
        for d in deals:
            if d["type"] not in (DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT):
                continue
            # balans/kredit (deposit, bonus va h.k.) operatsiyalari pozitsiya emas
            if d.get("position_id") == 0 or d.get("volume", 0) <= 0:
                continue
            profit += d["profit"]
            volume += d["volume"]
        return {"profit": round(profit, 2), "volume": round(volume, 2), "deals": len(deals)}

    def realized_periods(self) -> dict:
        """Bugun, 7 kun, 30 kun, umumiy."""
        now = datetime.now(timezone.utc)
        total = self.realized(since_days=3650)["profit"]
        d30 = self.realized(since_days=30)["profit"]
        d7 = self.realized(since_days=7)["profit"]
        d1 = self.realized(since_days=1)["profit"]

        info = self.broker.account_info()
        bal = info["balance"] if info else 0.0
        return {
            "currency": (info["currency"] if info else config_report_currency()),
            "today": round(d1, 2),
            "today_pct": round(d1 / bal * 100, 2) if bal else 0.0,
            "week": round(d7, 2),
            "week_pct": round(d7 / bal * 100, 2) if bal else 0.0,
            "month": round(d30, 2),
            "month_pct": round(d30 / bal * 100, 2) if bal else 0.0,
            "total": round(total, 2),
            "total_pct": round(total / bal * 100, 2) if bal else 0.0,
        }


def config_report_currency() -> str:
    from backend.config import config
    return config.REPORT_CURRENCY


pnl = PnlService()


def sync_positions(session_day: str = "") -> None:
    """MT5 position'larni DB'ga sinxronlaydi; yopilganlarini yopadi.

    return: (ochiq, yopilgan) sanalari.
    """
    from backend.app.store import utcnow
    open_pos = broker.positions()
    open_tickets = {p["ticket"] for p in open_pos}
    magic_ids = broker.magic_range

    # 1) ochiqlarni yangilash
    from backend.app.account_manager import account_manager
    uid = account_manager.active_user_id()
    for p in open_pos:
        t = store.upsert_open_trade(
            ticket=p["ticket"], symbol=p["symbol"], direction=p["direction"],
            volume=p["volume"], entry=p["entry"], tp=p["tp"] or None, sl=p["sl"] or None,
            magic=p["magic"], user_id=uid,
        )
        info = broker.account_info()
        bal = info["balance"] if info else 0.0
        pct = (p["profit"] / bal * 100.0) if bal else 0.0
        store.update_open_trade_px(p["ticket"], p["current"], p["profit"], pct)

    # 2) DB'da ochiq deb turgan, lekin MT5'da end yo'q → yopildi
    db_open = store.open_trades()
    closed = []
    for t in db_open:
        ticket = t.ticket
        if ticket not in open_tickets:
            # yopilish sababini history'dan topish
            history = broker.history_deals(int(datetime.now(timezone.utc).timestamp()) - 20 * 24 * 3600)
            reason = "other"
            for d in history:
                if d["position_id"] == ticket and d["profit"] != 0.0:
                    if d["comment"] and "AI close" in d["comment"]:
                        reason = "manual"
                    elif d["type"] in (DEAL_TYPE_BUY_CANCELED, DEAL_TYPE_SELL_CANCELED):
                        reason = "tp_sl"
                    break
            ct = store.close_trade(ticket, reason=reason)
            if ct:
                closed.append({"ticket": ct.ticket, "symbol": ct.symbol,
                               "pnl": t.pnl, "reason": reason})
    return open_pos, closed