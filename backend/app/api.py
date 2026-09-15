"""Pro Tred — FastAPI + WebSocket real-vaqt API."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.app.account_manager import account_manager
from backend.app.mt5_broker import broker
from backend.app.pnl_service import pnl
from backend.app.risk_manager import risk, risk_summary
from backend.app.store import store
from backend.app.telegram_bot import tg
from backend.app.trader_engine import trader
from backend.app.auth import register as register_user, login as login_user
from backend.config import config

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------- auth
def require_admin():
    pass


def _check_token(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    if config.ADMIN_TOKEN:
        if x_admin_token != config.ADMIN_TOKEN:
            raise HTTPException(403, "Ruxsat yo'q: ADMIN_TOKEN noto'g'ri")
    return True


# ---------------------------------------------------------------- models
class RiskSettings(BaseModel):
    risk_level: Optional[str] = None
    max_risk_per_trade: Optional[float] = None
    max_daily_drawdown: Optional[float] = None
    daily_profit_target: Optional[float] = None
    max_open_positions: Optional[int] = None
    min_confidence: Optional[float] = None
    max_daily_trades: Optional[int] = None
    paper_trading: Optional[bool] = None
    scalping: Optional[bool] = None
    news_trading: Optional[bool] = None


class AccountCreate(BaseModel):
    name: str = ""


class BrokerSwitch(BaseModel):
    login: str
    password: str
    server: str


class RegisterBody(BaseModel):
    username: str
    name: str = ""
    phone: str = ""
    password: str = ""


class LoginBody(BaseModel):
    username: str
    password: str


class BroadcastBody(BaseModel):
    text: str


class AdminLoginBody(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------- GET
@router.get("/mt5/accounts")
def mt5_accounts(x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    """MT5 terminaldagi mavjud akkauntlar ro'yxati (ero akkaunt tanlash uchun)."""
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            try:
                from backend.config import config as cfg
                if cfg.MT5_PATH:
                    mt5.initialize(path=cfg.MT5_PATH)
            except Exception:
                pass
        infos = mt5.accounts_get()
    except Exception:
        return {"accounts": [], "error": "MetaTrader5 o'rnatilmagan yoki terminal ochilmagan"}
    accs = []
    seen = set()
    for a in (infos or []):
        key = (a.login, a.server)
        if key in seen:
            continue
        seen.add(key)
        accs.append({
            "login": a.login,
            "server": a.server,
            "leverage": a.leverage,
            "currency": a.currency,
            "company": getattr(a, "company", "") or "",
            "name": getattr(a, "name", "") or "",
        })
    return {"accounts": accs}


@router.get("/news/events")
def news_events(limit: int = 20):
    """Kelgusi va yaqinda chiqqan kuchli yangiliklar."""
    from backend.app.news_service import get_calendar
    import time as _t
    now_ms = _t.time() * 1000
    items = get_calendar()
    items = [e for e in items if e["impact"] in ("High", "Medium")]
    upcoming_ = [e for e in items if e["date_ms"] >= now_ms - 60_000][:limit]
    return {"events": upcoming_, "now_ms": int(now_ms)}


@router.get("/status")
def status():
    return trader.account_snapshot()


@router.get("/symbols")
def symbols():
    return {"symbols": config.trade_symbols, "resolved": broker.symbol_map if hasattr(broker, 'symbol_map') else {}}


@router.get("/positions")
def positions():
    return {"positions": broker.positions(),
            "unrealized": pnl.unrealized()}


@router.get("/signals")
def signals(limit: int = 100):
    return {"signals": [{
        "id": s.id,
        "symbol": s.symbol,
        "direction": s.direction,
        "entry": s.entry,
        "stop_loss": s.stop_loss,
        "take_profit": s.take_profit,
        "confidence": s.confidence,
        "timeframe": s.timeframe,
        "reasons": __import__("json").loads(s.reasons or "[]"),
        "regime": s.regime,
        "applied": s.applied,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    } for s in store.recent_signals(limit)]}


@router.get("/trades")
def trades(only_open: bool = False):
    if only_open:
        rows = store.open_trades()
    else:
        rows = open_list = store.open_trades()
        closed = store.closed_trades()
        rows = open_list + closed
    return {"trades": [{
        "ticket": t.ticket,
        "symbol": t.symbol,
        "direction": t.direction,
        "volume": t.volume,
        "entry": t.entry,
        "sl": t.sl,
        "tp": t.tp,
        "current": t.current,
        "pnl": t.pnl,
        "pnl_pct": t.pnl_pct,
        "status": t.status,
        "opened_at": t.opened_at.isoformat() if t.opened_at else "",
        "closed_at": t.closed_at.isoformat() if t.closed_at else "",
        "close_reason": t.close_reason,
    } for t in rows]}


@router.get("/events")
def events(limit: int = 100):
    return {"events": [{
        "ts": e.ts.isoformat() if e.ts else "",
        "level": e.level,
        "source": e.source,
        "message": e.message,
    } for e in store.recent_events(limit)]}


@router.get("/settings")
def get_settings(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    return risk_summary()


@router.get("/accounts")
def get_accounts(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    return {"accounts": account_manager.list_accounts()}


# --------------------------------------------------------- admin: users & stats
def _serial_user(u, accounts=None):
    return {
        "id": u.id,
        "username": u.username,
        "name": u.name,
        "phone": u.phone,
        "source": u.source,
        "plan": u.plan,
        "active": u.active,
        "tg_username": u.tg_username,
        "broker_connected": bool(u.broker_login),
        "trading_enabled": bool(u.trading_enabled),
        "paper_trading": bool(u.paper_trading),
        "risk_level": u.risk_level or "moderate",
        "created_at": u.created_at.isoformat() if u.created_at else "",
        "last_active_at": u.last_active_at.isoformat() if u.last_active_at else "",
        "trade_count": _user_trade_count(u.id),
        "trade_volume": _user_trade_volume(u.id),
        "realized_pnl": _user_realized(u.id),
    }


def _user_trade_count(user_id):
    from backend.app.store import Trade
    with store.session() as s:
        return s.query(Trade).filter(Trade.user_id == user_id).count()


def _user_trade_volume(user_id):
    from backend.app.store import Trade
    from sqlalchemy import func
    with store.session() as s:
        row = s.query(func.sum(Trade.volume)).filter(Trade.user_id == user_id).scalar()
        return round(row or 0.0, 2)


def _user_realized(user_id):
    from backend.app.store import Trade
    from sqlalchemy import func
    with store.session() as s:
        row = s.query(func.sum(Trade.pnl)).filter(
            Trade.user_id == user_id, Trade.status == "closed").scalar()
        return round(row or 0.0, 2)


@router.get("/admin/stats")
def admin_stats(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    users = store.user_counts()
    instr = store.instrument_stats()
    live = trader.account_snapshot()
    return {
        "users": users,
        "instruments": instr,
        "accounts_total": len(account_manager.list_accounts()),
        "top_active": store.most_active_users(10),
        "pnl": store.trade_stats(),
        "pnl_history": store.pnl_history(14),
        "live": {
            "balance": live["account"]["balance"],
            "equity": live["account"]["equity"],
            "currency": live["account"]["currency"],
            "open_positions": live["unrealized"]["open_count"],
            "connected": live["connected"],
        },
    }


@router.get("/admin/users")
def admin_users(source: str = "", q: str = "",
                x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    rows = store.list_users(source or None)
    if q:
        q = q.lower()
        rows = [u for u in rows
                if q in (u.username or "").lower() or q in (u.name or "").lower()
                or q in (u.tg_username or "").lower()]
    return {"users": [_serial_user(u) for u in rows]}


@router.get("/admin/registrations")
def admin_registrations(days: int = 14,
                        x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    days = min(max(days, 1), 60)
    return {"series": store.registrations_by_day(days)}


@router.get("/admin/dau")
def admin_dau(days: int = 14,
              x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    days = min(max(days, 1), 60)
    return {"series": store.dau_by_day(days)}


@router.get("/admin/broadcasts")
def admin_broadcasts(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    return {"broadcasts": [{
        "id": b.id,
        "text": b.text,
        "recipients": b.recipients,
        "created_at": b.created_at.isoformat() if b.created_at else "",
    } for b in store.list_broadcasts()]}


@router.post("/admin/broadcast")
def admin_broadcast(body: BroadcastBody,
                    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    if not body.text.strip():
        raise HTTPException(400, "Xabar matni bo'sh bo'lmasligi kerak.")
    if not tg.enabled:
        raise HTTPException(400, "TELEGRAM_BOT_TOKEN .env'da to'ldirilmagan. Bot ishlamayapti.")
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(tg.broadcast_safe(body.text))
    finally:
        loop.close()
    if not result["ok"]:
        store.log("error", "broadcast", f"reklama yuborilmadi: {result.get('error')}")
        return {"ok": False, "error": result.get("error")}
    store.add_broadcast(body.text, result["sent"])
    store.log("info", "broadcast", f"reklama {result['sent']} chat'ga yuborildi")
    return {"ok": True, **result}


# ----------------------------------------------------------- public auth
@router.post("/admin/login")
def admin_login(body: AdminLoginBody):
    """Admin panelga username/parol bilan kirish -> admin token."""
    res = login_user(body.username, body.password)
    if not res["ok"]:
        raise HTTPException(401, res["error"])
    if res.get("role") != "admin":
        raise HTTPException(403, "Admin emas")
    return {
        "ok": True,
        "role": "admin",
        "token": config.ADMIN_TOKEN,
        "username": body.username,
    }


@router.post("/register")
def register(body: RegisterBody):
    res = register_user(body.username, body.name, body.phone, body.password)
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    store.log("info", "auth", f"yangi web user: {body.username}")
    return res


@router.post("/login")
def login(body: LoginBody):
    res = login_user(body.username, body.password)
    if not res["ok"]:
        raise HTTPException(401, res["error"])
    return res


@router.get("/me")
def me(x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    u = store.find_user_by_token(x_user_token)
    if not u:
        raise HTTPException(401, "Token yaroqsiz")
    store.touch_user(u.id)
    acc = store.find_account_by_user(u.id)
    return {
        "user": {
            "id": u.id, "username": u.username, "name": u.name,
            "phone": u.phone, "source": u.source, "plan": u.plan, "active": u.active,
            "role": "admin" if u.username == config.ADMIN_USER else "user",
            "broker_connected": bool(u.broker_login),
            "trading_enabled": bool(u.trading_enabled),
            "paper_trading": bool(u.paper_trading),
            "risk_level": u.risk_level or "moderate",
            "max_risk_pct": u.max_risk_pct or 3.0,
        },
        "account": {
            "link_code": acc.link_code if acc else None,
            "linked": bool(acc and acc.tg_chat_id),
            "name": acc.name if acc else "",
        } if acc else None,
    }


# -------------------------------------------------------- user broker & trading
class BrokerConnect(BaseModel):
    login: str
    password: str
    server: str


class TradingSettings(BaseModel):
    risk_level: Optional[str] = None
    paper_trading: Optional[bool] = None
    max_risk_pct: Optional[float] = None


def _require_user(x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    u = store.find_user_by_token(x_user_token)
    if not u:
        raise HTTPException(401, "Token yaroqsiz")
    return u


@router.post("/me/broker")
def connect_broker(body: BrokerConnect, x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    """Eskirgan: endi foydalanuvchilar o'z akkauntini ulamaydi — yagona server hisob ishlaydi."""
    _require_user(x_user_token)
    return {"ok": True, "message": "Robot yagona server akkauntida 24/7 ishlaydi."}


@router.get("/me/broker")
def get_broker(x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    """Serverdagi yagona MT5 akkaunt holati."""
    _require_user(x_user_token)
    snap = trader.account_snapshot()
    acc = snap["account"]
    return {
        "connected": snap["connected"],
        "login": acc.get("login"),
        "server": acc.get("server"),
        "trading_enabled": snap["connected"],
        "paper_trading": snap["risk"].get("paper_trading", True),
    }


@router.post("/me/trading")
def toggle_trading(x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    """Robot doim yagona akkauntda ishlaydi — holatni qaytaradi."""
    _require_user(x_user_token)
    snap = trader.account_snapshot()
    return {"ok": True, "trading_enabled": snap["connected"]}


@router.post("/me/settings")
def user_settings(body: TradingSettings, x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    u = _require_user(x_user_token)
    risk_level = body.risk_level or u.risk_level or "moderate"
    paper = body.paper_trading if body.paper_trading is not None else bool(u.paper_trading)
    max_risk = body.max_risk_pct or u.max_risk_pct or 3.0
    store.set_user_risk(u.id, risk_level, paper, max_risk)
    return {"ok": True, "risk_level": risk_level, "paper_trading": paper, "max_risk_pct": max_risk}


@router.get("/me/trades")
def my_trades(limit: int = 100, x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    """Platforma bitimlari (yagona server akkaunti — barcha foydalanuvchilar ko'radi)."""
    _require_user(x_user_token)
    from backend.app.trader_engine import _serial_trade
    open_rows = store.open_trades()
    closed_rows = store.closed_trades()
    rows = open_rows + closed_rows
    rows = rows[:limit]
    return {"trades": [_serial_trade(t) for t in rows]}


@router.get("/me/pnl")
def my_pnl(x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    """Platforma umumiy P&L (yagona akkaunt)."""
    _require_user(x_user_token)
    return store.trade_stats()


@router.post("/me/trades/{ticket}/close")
def user_close_trade(ticket: int,
                     x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    """Foydalanuvchi panelidan bitimni yopish."""
    _require_user(x_user_token)
    import threading
    out = {}

    def _do():
        out["res"] = asyncio.run(trader.close_ticket(ticket))

    t = threading.Thread(target=_do)
    t.start()
    t.join()
    return out.get("res") or {"ok": False, "error": "xato"}


@router.get("/me/pnl/history")
def my_pnl_history(days: int = 14,
                   x_user_token: Optional[str] = Header(None, alias="X-User-Token")):
    _require_user(x_user_token)
    days = min(max(days, 1), 90)
    return {"series": store.pnl_history(days)}


# --------------------------------------------------- admin: manage user trading
@router.post("/admin/users/{user_id}/trading")
def admin_toggle_user_trading(user_id: int, body: TradingSettings,
                              x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    u = store.find_user(user_id)
    if not u:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if body.paper_trading is not None:
        store.set_user_trading(user_id, body.paper_trading)
    if body.risk_level is not None:
        store.set_user_risk(user_id, body.risk_level, u.paper_trading, u.max_risk_pct)
    return {"ok": True}


@router.post("/admin/users/{user_id}/enable")
def admin_enable_user(user_id: int, x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    u = store.find_user(user_id)
    if not u:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    store.set_user_trading(user_id, True)
    store.log("info", "admin", f"trading yoqildi: {u.username}")
    return {"ok": True, "trading_enabled": True}


@router.post("/admin/users/{user_id}/disable")
def admin_disable_user(user_id: int, x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    u = store.find_user(user_id)
    if not u:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    store.set_user_trading(user_id, False)
    store.log("info", "admin", f"trading o'chirildi: {u.username}")
    return {"ok": True, "trading_enabled": False}


# ---------------------------------------------------------------- POST
@router.post("/accounts")
def create_account(body: AccountCreate, x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    acc = account_manager.create_account(body.name)
    return {"ok": True, "account": acc,
            "hint": "Bu 5 xonali kodni Telegram botga /link 53621 ko'rinishida yuboring."}


@router.post("/accounts/{code}/switch_broker")
def switch_broker(code: str, body: BrokerSwitch, x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    res = account_manager.switch_broker(code, body.login, body.password, body.server)
    return res


@router.post("/settings")
def update_settings(body: RiskSettings, x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    updates = {}
    if body.risk_level is not None:
        if body.risk_level not in ("conservative", "moderate", "aggressive"):
            raise HTTPException(400, "risk_level: conservative|moderate|aggressive")
        risk.set_setting("RISK_LEVEL", body.risk_level)
        updates["risk_level"] = body.risk_level
    if body.max_risk_per_trade is not None:
        risk.set_setting("MAX_RISK_PER_TRADE", body.max_risk_per_trade)
        updates["max_risk_per_trade"] = body.max_risk_per_trade
    if body.max_daily_drawdown is not None:
        risk.set_setting("MAX_DAILY_DRAWDOWN", body.max_daily_drawdown)
        updates["max_daily_drawdown"] = body.max_daily_drawdown
    if body.daily_profit_target is not None:
        risk.set_setting("DAILY_PROFIT_TARGET", body.daily_profit_target)
        updates["daily_profit_target"] = body.daily_profit_target
    if body.max_open_positions is not None:
        risk.set_setting("MAX_OPEN_POSITIONS", body.max_open_positions)
        updates["max_open_positions"] = body.max_open_positions
    if body.min_confidence is not None:
        risk.set_setting("MIN_SIGNAL_CONFIDENCE", body.min_confidence)
        updates["min_confidence"] = body.min_confidence
    if body.max_daily_trades is not None:
        risk.set_setting("MAX_DAILY_TRADES", body.max_daily_trades)
        updates["max_daily_trades"] = body.max_daily_trades
    if body.paper_trading is not None:
        risk.set_setting("PAPER_TRADING", "1" if body.paper_trading else "0")
        updates["paper_trading"] = body.paper_trading
    if body.scalping is not None:
        risk.set_setting("SCALPING_ENABLED", "1" if body.scalping else "0")
        updates["scalping"] = body.scalping
    if body.news_trading is not None:
        risk.set_setting("NEWS_TRADING", "1" if body.news_trading else "0")
        updates["news_trading"] = body.news_trading
    store.log("info", "admin", f"sozlamalar yangilandi: {updates}")
    return {"ok": True, "updated": updates, "settings": risk_summary()}


@router.post("/positions/{ticket}/close")
def close_position(ticket: int, x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    import threading
    out = {}

    def _do():
        out["res"] = asyncio.run(trader.close_ticket(ticket))

    t = threading.Thread(target=_do)
    t.start()
    t.join()
    return out.get("res") or {"ok": False, "error": "xato"}


@router.post("/close-all")
def close_all(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    return {"result": "started", "queued": True, "note": "close tezgina amalga oshiriladi"}


@router.post("/telegram/test")
def telegram_test(text: str = "✅ Test xabari — AI Traderning Telegram kanali ishlayapti.",
                  x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    if not tg.enabled:
        raise HTTPException(400, "TELEGRAM_BOT_TOKEN .env'da to'ldirilmagan")
    loop = asyncio.new_event_loop()

    async def _s():
        await tg.broadcast(text)

    loop.run_until_complete(_s())
    return {"ok": True, "sent_to": tg.get_chats()}


@router.post("/report")
def send_report_now(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _check_token(x_admin_token)
    loop = asyncio.new_event_loop()
    loop.run_until_complete(tg.send_daily_report())
    return {"ok": True}


# ---------------------------------------------------------------- WebSocket
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = trader.account_snapshot()
            try:
                await ws.send_json(data)
            except Exception:
                break
            await asyncio.sleep(config.POLL_INTERVAL)
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)