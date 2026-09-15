"""Pro Tred — Savdo dvigateli (yagona server hisobi).

AI Robot serverdagi yagona MT5 akkauntda 24/7 agressiv savdo qiladi:
  - SCALP_SCAN_INTERVAL sekundda AI signal skan + yangilik momentum
  - POLL_INTERVAL sekundda pozitsiya sync + risk nazorati

Xulosa: MT5 akkaunt almashtirilmaydi (user cycling olib tashlandi),
shuning uchun terminalda ulangan akkaunt savdo vaqtida chiqarib tashlanmaydi.
"""
from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime, timezone

from backend.app.mt5_broker import broker
from backend.app.pnl_service import pnl, sync_positions
from backend.app.risk_manager import risk, risk_summary
from backend.app.signal_engine import engine as signal_engine
from backend.app.store import store, utcnow
from backend.app.telegram_bot import tg
from backend.config import config

PAPER_MAGIC = 999001
_next_paper_ticket = [random.randint(90_000_000, 99_000_000)]


def paper_ticket():
    _next_paper_ticket[0] += 1
    return _next_paper_ticket[0]


def _sig_from_news(symbol: str, nm: dict) -> object | None:
    """News momentum dict'ni Signal ko'rinishiga aylantiradi."""
    from backend.app.signal_engine import Signal

    sig = Signal(
        symbol=symbol,
        direction=nm["direction"],
        entry=nm["entry"],
        stop_loss=nm["stop_loss"],
        take_profit=nm["take_profit"],
        confidence=nm["confidence"],
        timeframe=nm.get("timeframe", "M5"),
        regime=nm.get("regime", "news_momentum"),
        reasons=nm.get("reasons", []),
        breakout=True,
    )
    row = store.add_signal(
        symbol=symbol, direction=sig.direction, entry=sig.entry,
        sl=sig.stop_loss, tp=sig.take_profit, confidence=sig.confidence,
        timeframe=sig.timeframe, reasons=sig.reasons, regime=sig.regime)
    sig.uid = None
    sig.signal_id = row.id
    store.log("info", "news",
              f"[NEWS] {symbol}: {sig.direction} (conf {sig.confidence:.0f}%) "
              f"@ {sig.entry:.2f}")
    return sig


def _serial_trade(t) -> dict:
    return {
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
        "opened_at": t.opened_at.isoformat() if t.opened_at else t.opened_at,
        "closed_at": t.closed_at.isoformat() if t.closed_at else t.closed_at,
        "close_reason": t.close_reason,
    }


class TraderEngine:
    def __init__(self):
        self.running = False
        self._task: asyncio.Task | None = None
        self.last_prices: dict[str, dict] = {}
        self.opened_today: set[str] = set()
        self.last_signal_text: dict[str, str] = {}
        self._syncing = False

    @property
    def connected(self) -> bool:
        return broker.is_connected()

    def account_snapshot(self) -> dict:
        info = broker.account_info() or {
            "login": 0, "server": "", "broker": "", "currency": config.REPORT_CURRENCY,
            "balance": 0, "equity": 0, "margin": 0, "free_margin": 0,
            "margin_level": 0, "leverage": 0, "profit": 0, "drawdown": 0}
        unreal = pnl.unrealized()
        realized = pnl.realized_periods()
        open_trades = store.open_trades()
        return {
            "connected": self.connected,
            "account": info,
            "risk": risk_summary(),
            "unrealized": unreal,
            "realized": realized,
            "signals": self.last_signal_text,
            "trades": [_serial_trade(t) for t in open_trades],
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    async def _guard_connect(self) -> bool:
        if not broker.available:
            return False
        if not broker.is_connected():
            _ok = await asyncio.to_thread(broker.connect)
            if not _ok:
                return False
        return True

    # ---------------------------------------------------------------- main loop
    async def run(self):
        self.running = True
        risk.reset_daily()
        store.log("info", "engine", "AI Trader ishga tushdi (yagona akkaunt 24/7 agressiv)")

        last_scan = 0.0
        last_sync = 0.0
        while self.running:
            now = time.monotonic()
            try:
                if not await self._guard_connect():
                    await asyncio.sleep(5)
                    continue

                risk.reset_daily()

                # 1) sync + risk nazorati
                if now - last_sync >= config.POLL_INTERVAL:
                    last_sync = now
                    positions = broker.positions()
                    await asyncio.to_thread(sync_positions)

                    dd_pct, _ = risk.current_drawdown()
                    if risk.is_drawdown_hit() and positions:
                        store.log("warning", "risk",
                                  f"Kunlik drawdown {dd_pct:.2f}% → barcha pozitsiyalar yopilmoqda")
                        await self.close_all("kunlik drawdown limiti")
                        await tg.broadcast(
                            f"🛑 <b>Kunlik drawdown limiti</b> ({risk.max_daily_drawdown:.0f}%) "
                            f"kesib o'tildi ({dd_pct:.2f}%). Barcha pozitsiyalar yopildi.")
                        positions = []

                    _, closed = sync_positions()
                    for c in closed:
                        await tg.broadcast(
                            f"🔚 Pozitsiya #{c['ticket']} {c['symbol']} yopildi "
                            f"(P&L {c['pnl']:+,.2f}, sabab: {c['reason']})")

                    await self._update_paper()

                # 2) AI signal skan (agressiv — tez-suratli)
                if now - last_scan >= config.SCALP_SCAN_INTERVAL:
                    last_scan = now
                    await self.scan_and_trade()

            except Exception as e:
                store.log("error", "engine", f"loop xato: {e}")
                await asyncio.sleep(3)
            await asyncio.sleep(0.5)

    # ---------------------------------------------------------------- scan
    async def scan_and_trade(self):
        """AI tahlil va savdo qarorlari — yagona server akkauntida."""
        results = []

        for symbol in config.trade_symbols:
            tick = await asyncio.to_thread(broker.tick, symbol)
            sym_info = await asyncio.to_thread(broker.symbol_info, symbol)
            sig = await asyncio.to_thread(signal_engine.analyze_symbol, symbol, tick, sym_info)
            if sig is None:
                continue
            # MT5 ulanmagan bo'lsa tick yo'q → narx 0 bo'ladi — bunday signal tashlanadi
            if not tick or sig.entry <= 0:
                store.log("info", "risk",
                          f"{symbol}: MT5 ulanmagan yoki narx yo'q — signal o'tkazib yuborildi")
                continue
            self.last_signal_text[symbol] = (
                f"{sig.direction} {sig.confidence:.0f}% @ {sig.entry:.2f} "
                f"SL {sig.stop_loss:.2f} TP {sig.take_profit:.2f} ({sig.regime})")
            sig_row = store.add_signal(
                symbol=symbol, direction=sig.direction, entry=sig.entry,
                sl=sig.stop_loss, tp=sig.take_profit, confidence=sig.confidence,
                timeframe=sig.timeframe, reasons=sig.reasons, regime=sig.regime)
            sig.uid = None
            store.log("info", "signals",
                      f"{symbol}: {sig.direction} (conf {sig.confidence:.0f}%) "
                      f"@ {sig.entry:.2f}, rejim={sig.regime}")
            sig.signal_id = sig_row.id
            results.append(sig)

        # Yangilik momentum scalp (tezkor yangiliklar asosida savdo)
        if risk.scalping and risk.news_trading:
            for symbol in config.trade_symbols:
                from backend.app.news_service import news_momentum
                nm = await asyncio.to_thread(news_momentum, symbol, broker)
                if not nm:
                    continue
                # Tashqi API uchun encoding xatolarini oldini olamiz
                for k in ("reasons",):
                    if k in nm:
                        nm[k] = [str(r).encode("ascii", "replace").decode("ascii") for r in nm[k]]
                nm_sig = _sig_from_news(symbol, nm)
                if nm_sig:
                    results.append(nm_sig)

        open_pos = broker.positions()
        open_symbols = {p["symbol"] for p in open_pos}
        maxt = risk.max_open_positions

        for sig in sorted(results, key=lambda s: s.confidence, reverse=True):
            if len(open_pos) >= maxt:
                break
            if not config.TRADE_ALLOW_MULTIPLE and sig.symbol in open_symbols:
                continue
            ok, why = risk.can_open(len(open_pos), sig.confidence)
            if not ok:
                store.log("info", "risk", f"{sig.symbol}: savdo ochilmadi ({why})")
                continue

            info = await asyncio.to_thread(broker.symbol_info, sig.symbol)
            if info:
                rates_h1 = await asyncio.to_thread(broker.rates, sig.symbol, "H1", 100)
                atr_h1 = 0.0
                if rates_h1:
                    from backend.app.indicators import atr as _atr, last_valid
                    hs = [r["high"] for r in rates_h1]
                    ls = [r["low"] for r in rates_h1]
                    cs = [r["close"] for r in rates_h1]
                    atr_h1 = last_valid(_atr(hs, ls, cs, 14)) or 0.0
                spread_pts = info["spread"] * info["point"]
                if atr_h1 > 0 and spread_pts > atr_h1 * config.MAX_SPREAD_MULT:
                    store.log("warning", "risk",
                              f"{sig.symbol}: spread {spread_pts:.3f} juda keng — ochilmaydi")
                    continue

            executed = await self._execute_signal(sig)
            if executed:
                open_pos = broker.positions()
                open_symbols = {p["symbol"] for p in open_pos}

    # ---------------------------------------------------------------- execute
    async def _execute_signal(self, sig) -> bool:
        info = broker.account_info()
        if not info:
            return False
        balance = info["balance"]
        sym_info = broker.symbol_info(sig.symbol)
        if not sym_info:
            return False
        tick = broker.tick(sig.symbol)
        if not tick:
            return False

        price = tick["ask"] if sig.direction == "BUY" else tick["bid"]
        sl_dist = abs(price - sig.stop_loss)
        if sl_dist <= 0:
            return False

        volume, err = risk.position_size(sym_info, tick, sl_dist, balance)
        if volume <= 0 and risk.level == "aggressive" and sym_info.get("min_volume"):
            # Agressiv rejim: hisoblangan hajm yuqoriga yaxlitlanadi (min lotda ochiladi)
            volume = sym_info["min_volume"]
            store.log("info", "risk",
                      f"{sig.symbol}: hajm {volume:.2f} ga yaxlitlandi ({err})")
        if volume <= 0:
            store.log("warning", "risk", f"{sig.symbol}: hajm hisoblab bo'lmadi — {err}")
            return False

        store.log("info", "engine",
                  f"{sig.direction} {sig.symbol} {volume} lot @ ~{sig.entry:.2f} "
                  f"(SL {sig.stop_loss:.2f} TP {sig.take_profit:.2f}) conf={sig.confidence:.0f}%")

        if risk.paper:
            return await self._paper_execute(sig, volume)

        result = await asyncio.to_thread(
            broker.market_order, sig.symbol, sig.direction, volume,
            sig.stop_loss, sig.take_profit,
            magic=config.MAGIC_BASE + sum(ord(c) for c in sig.symbol) % 20,
            comment="AI Trade",
        )
        if result and result.get("ok"):
            risk.on_trade_opened()
            store.mark_signal_applied(getattr(sig, "signal_id", None) or 0,
                                      result.get("position", result.get("order", 0)))
            msg = (f"✅ <b>Yangi bitim ochildi</b>\n"
                   f"{sig.symbol} {sig.direction} {volume} lot\n"
                   f"Kirish: {result.get('price', 0):.2f}\n"
                   f"SL: {sig.stop_loss:.2f} | TP: {sig.take_profit:.2f}\n"
                   f"Confidence: {sig.confidence:.0f}%\n"
                   f"{('[NEWS] ' if getattr(sig, 'regime', '') == 'news_momentum' else 'AI strategiya')}")
            await self._notify(None, msg)
            return True
        store.log("error", "engine", f"{sig.symbol}: buyurtma xato — {result}")
        return False

    async def _notify(self, user_id, msg: str):
        """Bitim xabari: barcha chatlarga tarqatiladi."""
        try:
            await tg.broadcast(msg)
        except Exception as e:
            store.log("warning", "telegram", f"broadcast xato: {e}")

    async def _paper_execute(self, sig, volume: float) -> bool:
        ticket = paper_ticket()
        store.upsert_open_trade(
            ticket=ticket, symbol=sig.symbol, direction=sig.direction,
            volume=volume, entry=sig.entry, tp=sig.take_profit, sl=sig.stop_loss,
            magic=PAPER_MAGIC, user_id=None)
        store.mark_signal_applied(getattr(sig, "signal_id", None) or 0, ticket)
        risk.on_trade_opened()
        store.log("info", "paper", f"PAPER: {sig.direction} {sig.symbol} {volume} lot <{ticket}>")
        msg = (
            f"🧪 <b>PAPER bitim</b>\n"
            f"{sig.symbol} {sig.direction} {volume} lot\n"
            f"Kirish: {sig.entry:.2f} | SL {sig.stop_loss:.2f} | TP {sig.take_profit:.2f}\n"
            f"Confidence: {sig.confidence:.0f}%\n"
            f"{('[NEWS] ' if getattr(sig, 'regime', '') == 'news_momentum' else 'AI strategiya')}")
        await self._notify(None, msg)
        return True

    async def _update_paper(self):
        trades = store.open_trades()
        for t in trades:
            if t.magic != PAPER_MAGIC:
                continue
            tick = await asyncio.to_thread(broker.tick, t.symbol)
            if not tick:
                continue
            px = tick["bid"] if t.direction == "BUY" else tick["ask"]
            info = broker.account_info()
            bal = info["balance"] if info else 0.0
            sym = broker.symbol_info(t.symbol)
            tval = sym["tick_value"] if sym else 0
            tsize = sym["tick_size"] if sym else 0
            usd_unit = (tval / tsize) if tsize else 0
            diff = (px - t.entry) if t.direction == "BUY" else (t.entry - px)
            pnl_amt = diff * t.volume * usd_unit if usd_unit else 0.0
            pnl_pct = (pnl_amt / bal * 100.0) if bal else 0.0
            store.update_open_trade_px(t.ticket, px, pnl_amt, pnl_pct)

            hit = False
            reason = ""
            if t.direction == "BUY":
                if t.tp and px >= t.tp:
                    hit, reason = True, "TP (paper)"
                elif t.sl and px <= t.sl:
                    hit, reason = True, "SL (paper)"
            else:
                if t.tp and px <= t.tp:
                    hit, reason = True, "TP (paper)"
                elif t.sl and px >= t.sl:
                    hit, reason = True, "SL (paper)"
            if hit:
                store.close_trade(t.ticket, reason="tp_sl")
                await tg.broadcast(
                    f"🧪 Paper #{t.ticket} {t.symbol} {reason} · P&L {pnl_amt:+,.2f}")

    # ---------------------------------------------------------------- close
    async def close_all(self, reason: str = "manual"):
        positions = broker.positions()
        if not positions:
            return
        for p in positions:
            if p["magic"] == PAPER_MAGIC:
                continue
            if p["magic"] not in broker.magic_range:
                store.log("info", "risk",
                          f"#{p['ticket']} {p['symbol']} qo'lda ochilgan — robot yopmaydi")
                continue
            res = await asyncio.to_thread(broker.close_position, p["ticket"])
            if res and res.get("ok"):
                store.close_trade(p["ticket"], reason=reason)
            else:
                store.log("error", "engine", f"yopish xato #{p['ticket']}: {res}")

    async def close_ticket(self, ticket: int) -> dict:
        t = store.find_open_trade(ticket)
        if t and t.magic == PAPER_MAGIC:
            # PAPER bitim — DB ichida yopamiz (joriy narxda P&L bilan)
            tick = await asyncio.to_thread(broker.tick, t.symbol)
            if not tick:
                return {"ok": False, "error": "joriy narx yo'q"}
            px = tick["bid"] if t.direction == "BUY" else tick["ask"]
            sym = broker.symbol_info(t.symbol)
            tval = sym["tick_value"] if sym else 0
            tsize = sym["tick_size"] if sym else 0
            usd_unit = (tval / tsize) if tsize else 0
            diff = (px - t.entry) if t.direction == "BUY" else (t.entry - px)
            pnl_amt = diff * t.volume * usd_unit if usd_unit else 0.0
            store.update_open_trade_px(t.ticket, px, pnl_amt, pnl_amt / (t.entry * t.volume) * 100 if t.entry else 0.0)
            store.close_trade(t.ticket, reason="manual")
            await tg.broadcast(f"🧪 Paper #{ticket} {t.symbol} panel orqali yopildi · P&L {pnl_amt:+,.2f}")
            return {"ok": True, "pnl": round(pnl_amt, 2)}

        res = await asyncio.to_thread(broker.close_position, ticket)
        if res and res.get("ok"):
            store.close_trade(ticket, reason="manual")
            await tg.broadcast(f"✋ Pozitsiya #{ticket} panel orqali yopildi.")
            return {"ok": True}
        return {"ok": False, "error": (res or {}).get("error")}

    # ---------------------------------------------------------------- lifecycle
    async def start_async(self):
        self._task = asyncio.create_task(self.run())

    async def stop(self):
        self.running = False
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except Exception:
                pass


trader = TraderEngine()
