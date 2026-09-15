"""Pro Tred — SQLite storage layer (SQLAlchemy ORM)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import config

DB_DIR = Path(config.DB_PATH).parent
DB_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, index=True, nullable=True)
    name = Column(String(128), default="")
    phone = Column(String(32), default="")
    password_hash = Column(String(128), nullable=True)
    source = Column(String(16), default="web")  # web | telegram
    tg_chat_id = Column(String(32), nullable=True, index=True)
    tg_username = Column(String(64), nullable=True)
    plan = Column(String(16), default="free")
    active = Column(Boolean, default=True)
    token = Column(String(64), index=True, nullable=True)
    # Broker / trading config per user
    broker_login = Column(String(32), nullable=True)
    broker_password = Column(String(128), nullable=True)
    broker_server = Column(String(64), nullable=True)
    trading_enabled = Column(Boolean, default=False)
    paper_trading = Column(Boolean, default=True)
    risk_level = Column(String(16), default="moderate")
    max_risk_pct = Column(Float, default=3.0)
    login_count = Column(Integer, default=0)
    visits = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow, index=True)
    last_active_at = Column(DateTime, default=utcnow)


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True)
    text = Column(Text, default="")
    recipients = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True, index=True)  # User'ga bog'langan
    link_code = Column(String(5), unique=True, index=True)  # 5 xonali tasodifiy ID
    name = Column(String(64), default="")
    tg_chat_id = Column(String(32), nullable=True, index=True)
    tg_username = Column(String(64), nullable=True)
    linked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    meta = Column(Text, default="{}")  # broker nomi, server va b.


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True, index=True)
    symbol = Column(String(16), index=True)
    direction = Column(String(8))  # BUY | SELL
    entry = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    confidence = Column(Float)
    timeframe = Column(String(8))
    reasons = Column(Text, default="[]")  # JSON: indikator asoslari
    regime = Column(String(16), default="")
    applied = Column(Boolean, default=False)
    executed_ticket = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True, index=True)
    ticket = Column(Integer, unique=True, index=True)
    symbol = Column(String(16), index=True)
    direction = Column(String(8))  # BUY | SELL
    volume = Column(Float)
    entry = Column(Float)
    tp = Column(Float, nullable=True)
    sl = Column(Float, nullable=True)
    current = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)  # fiat
    pnl_pct = Column(Float, nullable=True)
    status = Column(String(16), default="open")  # open | closed
    magic = Column(Integer, nullable=True)
    opened_at = Column(DateTime, default=utcnow)
    closed_at = Column(DateTime, nullable=True)
    close_reason = Column(String(32), nullable=True)  # tp | sl | manual | risk | other


class DailySummary(Base):
    __tablename__ = "daily_summary"

    id = Column(Integer, primary_key=True)
    day = Column(String(10), index=True)  # YYYY-MM-DD
    realized_pnl = Column(Float, default=0.0)
    peak_equity = Column(Float, default=0.0)
    worst_drawdown = Column(Float, default=0.0)
    trade_count = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    signals = Column(Integer, default=0)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(48), primary_key=True)
    value = Column(String(255), default="")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=utcnow, index=True)
    level = Column(String(8), default="info")
    source = Column(String(24), default="engine")
    message = Column(Text, default="")


Base.metadata.create_all(engine)


def migrate():
    """Eski bazalarga yangi maydonlarni qo'shadi (SQLite ALTER)."""
    with engine.connect() as conn:
        tables = {r[0] for r in conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        additions = {
            "accounts": {"user_id": "INTEGER"},
            "trades": {"user_id": "INTEGER"},
            "signals": {"user_id": "INTEGER"},
            "users": {
                "broker_login": "VARCHAR(32)",
                "broker_password": "VARCHAR(128)",
                "broker_server": "VARCHAR(64)",
                "trading_enabled": "BOOLEAN DEFAULT 0",
                "paper_trading": "BOOLEAN DEFAULT 1",
                "risk_level": "VARCHAR(16) DEFAULT 'moderate'",
                "max_risk_pct": "REAL DEFAULT 3.0",
                "login_count": "INTEGER DEFAULT 0",
                "visits": "INTEGER DEFAULT 0",
            },
        }
        for tbl, fields in additions.items():
            if tbl not in tables:
                continue
            have = {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({tbl})").fetchall()}
            for col, typ in fields.items():
                if col not in have:
                    conn.exec_driver_sql(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
        conn.commit()


migrate()


# ----------------------------------------------------------------- helpers
class Store:
    def __init__(self):
        self.session_factory = SessionLocal

    def session(self):
        return self.session_factory()

    # account
    def find_account_by_code(self, code: str):
        with self.session() as s:
            return s.query(Account).filter(Account.link_code == code).first()

    def find_account_by_chat(self, chat_id):
        with self.session() as s:
            return s.query(Account).filter(Account.tg_chat_id == str(chat_id)).first()

    def find_account_by_user(self, user_id: int):
        with self.session() as s:
            return s.query(Account).filter(Account.user_id == user_id).first()

    def set_account_user(self, account_id: int, user_id: int):
        with self.session() as s:
            acc = s.get(Account, account_id)
            if acc:
                acc.user_id = user_id
                s.commit()
            return acc

    # ------------------------------------------------------------ users
    def create_user(self, username="", password_hash=None, name="", phone="",
                    source="web", tg_chat_id=None, tg_username="", plan="free"):
        with self.session() as s:
            u = User(
                username=username or None,
                name=name, phone=phone, password_hash=password_hash,
                source=source,
                tg_chat_id=str(tg_chat_id) if tg_chat_id else None,
                tg_username=tg_username, plan=plan, active=True,
            )
            s.add(u)
            s.commit()
            s.refresh(u)
            return u

    def find_user_by_username(self, username):
        if not username:
            return None
        with self.session() as s:
            return s.query(User).filter(User.username == username).first()

    def find_user_by_chat(self, chat_id):
        with self.session() as s:
            return s.query(User).filter(User.tg_chat_id == str(chat_id)).first()

    def find_user_by_token(self, token):
        if not token:
            return None
        with self.session() as s:
            return s.query(User).filter(User.token == token).first()

    def find_user(self, user_id: int):
        with self.session() as s:
            return s.get(User, user_id)

    def find_user_by_token(self, token):
        if not token:
            return None
        with self.session() as s:
            return s.query(User).filter(User.token == token).first()

    def find_user_by_chat(self, chat_id):
        with self.session() as s:
            return s.query(User).filter(User.tg_chat_id == str(chat_id)).first()

    def find_user_by_username(self, username):
        if not username:
            return None
        with self.session() as s:
            return s.query(User).filter(User.username == username).first()

    def active_trading_users(self) -> list:
        with self.session() as s:
            return s.query(User).filter(
                User.active == True,  # noqa: E712
                User.trading_enabled == True,  # noqa: E712
                User.broker_login.isnot(None),
                User.broker_server.isnot(None),
            ).all()

    def set_user_broker(self, user_id: int, login: str, password: str, server: str):
        with self.session() as s:
            u = s.get(User, user_id)
            if not u:
                return None
            u.broker_login = login
            u.broker_password = password
            u.broker_server = server
            s.commit()
            return True

    def set_user_trading(self, user_id: int, enabled: bool):
        with self.session() as s:
            u = s.get(User, user_id)
            if not u:
                return None
            u.trading_enabled = enabled
            s.commit()
            return True

    def set_user_risk(self, user_id: int, risk_level: str, paper: bool = True, max_risk_pct: float = 3.0):
        with self.session() as s:
            u = s.get(User, user_id)
            if not u:
                return None
            u.risk_level = risk_level
            u.paper_trading = paper
            u.max_risk_pct = max_risk_pct
            s.commit()
            return True

    def set_user_token(self, user_id: int, token: str):
        with self.session() as s:
            u = s.get(User, user_id)
            if u:
                u.token = token
                s.commit()

    def touch_user(self, user_id: int):
        with self.session() as s:
            u = s.get(User, user_id)
            if u:
                u.last_active_at = utcnow()
                u.visits = (u.visits or 0) + 1
                s.commit()

    def bump_login_count(self, user_id: int):
        with self.session() as s:
            u = s.get(User, user_id)
            if u:
                u.login_count = (u.login_count or 0) + 1
                s.commit()

    def most_active_users(self, limit: int = 10) -> list[dict]:
        """Eng faol foydalanuvchilar (loginlar soni va faolligi bo'yicha)."""
        with self.session() as s:
            rows = (
                s.query(User)
                .order_by(User.login_count.desc(), User.visits.desc(),
                          User.last_active_at.desc())
                .limit(limit)
                .all()
            )
        return [{
            "id": u.id,
            "username": u.username,
            "name": u.name,
            "source": u.source,
            "plan": u.plan,
            "login_count": u.login_count or 0,
            "visits": u.visits or 0,
            "last_active_at": u.last_active_at.isoformat() if u.last_active_at else "",
            "created_at": u.created_at.isoformat() if u.created_at else "",
        } for u in rows]

    def pnl_history(self, days: int = 14) -> list[dict]:
        """Kunlik realizatsiya qilingan P&L (oxirgi `days` kun)."""
        start = utcnow() - timedelta(days=days - 1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        with self.session() as s:
            from sqlalchemy import func
            rows = (
                s.query(func.strftime("%Y-%m-%d", Trade.closed_at),
                        func.sum(Trade.pnl), func.count(Trade.id))
                .filter(Trade.status == "closed",
                        Trade.closed_at >= start,
                        Trade.pnl.isnot(None))
                .group_by(func.strftime("%Y-%m-%d", Trade.closed_at))
                .all()
            )
        buckets = {}
        for d in range(days):
            day = (start + timedelta(days=d)).strftime("%Y-%m-%d")
            buckets[day] = {"date": day, "pnl": 0.0, "trades": 0}
        for day, pnl_sum, cnt in rows:
            if day in buckets:
                buckets[day]["pnl"] = round(float(pnl_sum or 0.0), 2)
                buckets[day]["trades"] = int(cnt or 0)
        return [buckets[d] for d in sorted(buckets)]

    def trade_stats(self) -> dict:
        """Platforma umumiy bitim statistikasi."""
        from sqlalchemy import func
        with self.session() as s:
            realized = s.query(func.sum(Trade.pnl)).filter(
                Trade.status == "closed").scalar() or 0.0
            total_trades = s.query(Trade).count()
            open_count = s.query(Trade).filter(Trade.status == "open").count()
            wins = s.query(Trade).filter(
                Trade.status == "closed", Trade.pnl > 0).count()
            losses = s.query(Trade).filter(
                Trade.status == "closed", Trade.pnl <= 0).count()
            open_pnl = s.query(func.sum(Trade.pnl)).filter(
                Trade.status == "open").scalar() or 0.0
        closed = wins + losses
        return {
            "realized": round(realized, 2),
            "unrealized": round(open_pnl, 2),
            "total_trades": total_trades,
            "open_count": open_count,
            "wins": wins,
            "losses": losses,
            "winrate": round(wins / closed * 100, 1) if closed > 0 else 0,
        }

    def find_open_trade(self, ticket: int):
        with self.session() as s:
            return (
                s.query(Trade)
                .filter(Trade.ticket == ticket, Trade.status == "open")
                .first()
            )

    def list_users(self, source=None):
        with self.session() as s:
            q = s.query(User)
            if source:
                q = q.filter(User.source == source)
            return q.order_by(User.id.desc()).all()

    def user_counts(self) -> dict:
        now = utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        with self.session() as s:
            total = s.query(User).count()
            web = s.query(User).filter(User.source == "web").count()
            tgc = s.query(User).filter(User.source == "telegram").count()
            active_today = s.query(User).filter(User.last_active_at >= day_start).count()
            new_today = s.query(User).filter(User.created_at >= day_start).count()
            active_all = s.query(User).filter(User.active == True).count()  # noqa: E712
        return {
            "total": total, "web": web, "telegram": tgc,
            "active_today": active_today, "new_today": new_today,
            "active": active_all,
        }

    def registrations_by_day(self, days: int = 14) -> list[dict]:
        start = utcnow() - timedelta(days=days - 1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        with self.session() as s:
            rows = (
                s.query(User.created_at, User.source)
                .filter(User.created_at >= start)
                .all()
            )
        buckets = {}
        for d in range(days):
            day = (start + timedelta(days=d)).strftime("%Y-%m-%d")
            buckets[day] = {"web": 0, "telegram": 0}
        for created, src in rows:
            day = created.strftime("%Y-%m-%d")
            if day in buckets:
                buckets[day][src if src in buckets[day] else "web"] += 1
        return [
            {"date": day, "web": v["web"], "telegram": v["telegram"],
             "total": v["web"] + v["telegram"]}
            for day, v in sorted(buckets.items())
        ]

    def dau_by_day(self, days: int = 14) -> list[dict]:
        start = utcnow() - timedelta(days=days - 1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        with self.session() as s:
            rows = (
                s.query(User.last_active_at)
                .filter(User.last_active_at >= start)
                .all()
            )
        buckets = {}
        for d in range(days):
            day = (start + timedelta(days=d)).strftime("%Y-%m-%d")
            buckets[day] = 0
        for (ts,) in rows:
            day = ts.strftime("%Y-%m-%d")
            if day in buckets:
                buckets[day] += 1
        return [{"date": d, "active": buckets[d]} for d in sorted(buckets)]

    # -------------------------------------------------------- broadcasts
    def add_broadcast(self, text: str, recipients: int):
        with self.session() as s:
            b = Broadcast(text=text, recipients=recipients)
            s.add(b)
            s.commit()
            s.refresh(b)
            return b

    def list_broadcasts(self, limit: int = 50):
        with self.session() as s:
            return (
                s.query(Broadcast)
                .order_by(Broadcast.id.desc())
                .limit(limit)
                .all()
            )

    # ------------------------------------------------------- instrument stats
    def instrument_stats(self):
        """Barcha bitimlar bo'yicha instrumentlar yig'indisi (hajm, P&L)."""
        from collections import defaultdict
        with self.session() as s:
            traders = (
                s.query(Trade.symbol,
                        Trade.direction,
                        Trade.volume,
                        Trade.pnl)
                .all()
            )
            users_w_trades = (
                s.query(Trade.user_id).filter(Trade.user_id.isnot(None)).distinct().count()
            )
        agg = defaultdict(lambda: {"count": 0, "volume": 0.0, "pnl": 0.0, "buys": 0, "sells": 0})
        for symbol, direction, volume, pnlv in traders:
            a = agg[symbol]
            a["count"] += 1
            a["volume"] += volume or 0.0
            a["pnl"] += pnlv or 0.0
            if direction == "BUY":
                a["buys"] += 1
            else:
                a["sells"] += 1
        return {
            "users_with_trades": users_w_trades,
            "total_volume": sum(a["volume"] for a in agg.values()),
            "total_trades": sum(a["count"] for a in agg.values()),
            "by_symbol": [
                {"symbol": sym, **a} for sym, a in sorted(agg.items())
            ],
        }

    def create_account(self, link_code: str):
        with self.session() as s:
            acc = Account(link_code=link_code)
            s.add(acc)
            s.commit()
            s.refresh(acc)
            return acc

    def list_accounts(self):
        with self.session() as s:
            return s.query(Account).order_by(Account.id).all()

    def bind_chat(self, account_id: int, chat_id, username=""):
        with self.session() as s:
            acc = s.get(Account, account_id)
            if acc:
                acc.tg_chat_id = str(chat_id)
                acc.tg_username = username
                acc.linked_at = utcnow()
                s.commit()
            return acc

    # settings
    def get_setting(self, key: str, default=None):
        with self.session() as s:
            row = s.get(Setting, key)
            return row.value if row else default

    def set_setting(self, key: str, value):
        with self.session() as s:
            row = s.get(Setting, key)
            if row:
                row.value = str(value)
            else:
                s.add(Setting(key=key, value=str(value)))
            s.commit()

    def all_settings(self, as_float: set[str] | None = None, as_bool: set[str] | None = None):
        as_float = as_float or {"MAX_RISK_PER_TRADE", "MAX_DAILY_DRAWDOWN", "DAILY_PROFIT_TARGET"}
        as_bool = as_bool or {"PAPER_TRADING"}
        with self.session() as s:
            rows = s.query(Setting).all()
        out = {}
        for r in rows:
            key = r.key
            if key in as_float:
                try:
                    out[key] = float(r.value)
                except ValueError:
                    out[key] = 0.0
            elif key in as_bool:
                out[key] = r.value.lower() in {"1", "true", "yes", "on"}
            else:
                out[key] = r.value
        return out

    # events
    def log(self, level: str, source: str, message: str):
        with self.session() as s:
            s.add(Event(level=level, source=source, message=message))
            s.commit()

    def recent_events(self, limit: int = 100):
        with self.session() as s:
            return (
                s.query(Event)
                .order_by(Event.id.desc())
                .limit(limit)
                .all()
            )

    # signals
    def add_signal(self, symbol, direction, entry, sl, tp, confidence, timeframe,
                   reasons, regime, user_id=None):
        with self.session() as s:
            sig = Signal(
                symbol=symbol, direction=direction, entry=entry, stop_loss=sl,
                take_profit=tp, confidence=confidence, timeframe=timeframe,
                reasons=json.dumps(reasons, ensure_ascii=False),
                regime=regime, user_id=user_id,
            )
            s.add(sig)
            s.commit()
            s.refresh(sig)
            return sig

    def recent_signals(self, limit: int = 100):
        with self.session() as s:
            return (
                s.query(Signal)
                .order_by(Signal.id.desc())
                .limit(limit)
                .all()
            )

    def mark_signal_applied(self, signal_id: int, ticket: int | None = None):
        with self.session() as s:
            sig = s.get(Signal, signal_id)
            if sig:
                sig.applied = True
                sig.executed_ticket = ticket
                s.commit()

    def tick_count_for_day(self, day: str, applied=None):
        with self.session() as s:
            q = s.query(Signal)
            return q.count()

    # trades
    def upsert_open_trade(self, ticket, symbol, direction, volume, entry, tp, sl,
                          magic, user_id=None):
        with self.session() as s:
            t = (
                s.query(Trade)
                .filter(Trade.ticket == ticket)
                .first()
            )
            if not t:
                t = Trade(
                    ticket=ticket, symbol=symbol, direction=direction,
                    volume=volume, entry=entry, tp=tp, sl=sl, magic=magic,
                    status="open", user_id=user_id,
                )
                s.add(t)
            else:
                t.symbol, t.direction = symbol, direction
                t.volume, t.entry, t.tp, t.sl, t.magic = volume, entry, tp, sl, magic
                t.status = "open"
                if user_id is not None:
                    t.user_id = user_id
            s.commit()
            return t

    def update_open_trade_px(self, ticket, current, pnl, pnl_pct):
        with self.session() as s:
            t = s.query(Trade).filter(Trade.ticket == ticket).first()
            if t:
                t.current = current
                t.pnl = pnl
                t.pnl_pct = pnl_pct
                s.commit()

    def close_trade(self, ticket, closed_at=None, reason=None):
        with self.session() as s:
            t = s.query(Trade).filter(Trade.ticket == ticket).first()
            if t:
                t.status = "closed"
                t.closed_at = closed_at or utcnow()
                t.close_reason = reason
                s.commit()
                return t

    def open_trades(self):
        with self.session() as s:
            return (
                s.query(Trade)
                .filter(Trade.status == "open")
                .order_by(Trade.id.desc())
                .all()
            )

    def closed_trades(self, since=None, until=None):
        with self.session() as s:
            q = s.query(Trade).filter(Trade.status == "closed")
            if since is not None:
                q = q.filter(Trade.closed_at >= since)
            if until is not None:
                q = q.filter(Trade.closed_at <= until)
            return q.order_by(Trade.closed_at.desc()).all()

    def count_open_trades(self) -> int:
        return len(self.open_trades())

    def today_closed_trades(self, day_prefix: str):
        with self.session() as s:
            return (
                s.query(Trade)
                .filter(Trade.status == "closed")
                .filter(Trade.closed_at >= datetime.fromisoformat(day_prefix))
                .all()
            )

    # daily summary
    def get_daily(self, day: str):
        with self.session() as s:
            return s.query(DailySummary).filter(DailySummary.day == day).first()

    def upsert_daily(self, day: str, realized: float):
        with self.session() as s:
            row = s.query(DailySummary).filter(DailySummary.day == day).first()
            if row:
                row.realized_pnl = realized
            else:
                s.add(DailySummary(day=day, realized_pnl=realized))
            s.commit()
            return row or s.query(DailySummary).filter(DailySummary.day == day).first()


store = Store()