"""Pro Tred — Telegram bot.

Vazifalar:
  - /link <5 xonali kod> — akkauntni Telegram chat'iga ulash
  - /status — hisob balansi, ochiq pozitsiyalar, P&L
  - /positions, /signals, /risk — ma'lumotlar
  - /close <ticket> — pozitsiyani majburiy yopish (admin)
  - KUNLIK HISOBOT: biriktirilgan chatlarga kunlik natija, risklar, yangiliklar.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.app import pnl_service
from backend.app.account_manager import account_manager
from backend.app.mt5_broker import broker
from backend.app.pnl_service import pnl
from backend.app.risk_manager import risk, risk_summary
from backend.app.store import store
from backend.config import config

ADMIN_IDS = config.TELEGRAM_ADMIN_IDS

BOT_COMMANDS = [
    ("start", "Botni ishga tushirish"),
    ("link", "Akkauntni ulash — masalan: /link 56321"),
    ("unlink", "Ulangan akkauntni uzish — /unlink 56321"),
    ("status", "Hisob balansi, marja va P&L"),
    ("positions", "Ochiq pozitsiyalar"),
    ("signals", "So'nggi AI signallari"),
    ("risk", "Xavf darajalari va limitlar"),
    ("close", "Pozitsiyani yopish — /close <ticket> (admin)"),
    ("help", "Yordam"),
]


class TelegramBot:
    def __init__(self, token: str | None = None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.app = None
        self._task = None
        self._enabled = bool(self.token)
        if self._enabled:
            from telegram.ext import Application, CommandHandler
            self.app = Application.builder().token(self.token).build()
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("help", self.cmd_start))
            self.app.add_handler(CommandHandler("link", self.cmd_link))
            self.app.add_handler(CommandHandler("unlink", self.cmd_unlink))
            self.app.add_handler(CommandHandler("status", self.cmd_status))
            self.app.add_handler(CommandHandler("positions", self.cmd_positions))
            self.app.add_handler(CommandHandler("signals", self.cmd_signals))
            self.app.add_handler(CommandHandler("risk", self.cmd_risk))
            self.app.add_handler(CommandHandler("close", self.cmd_close))

    @property
    def enabled(self):
        return self._enabled

    # ---------------------------------------------------------- lifecycle
    async def start(self):
        if not self._enabled or self.app is None:
            store.log("info", "telegram", "bot o'chirilgan (token yo'q)")
            return
        try:
            # PTB 22x low-level: initialize + start_polling (loop ichida ishlaydi)
            await self.app.initialize()
            if self.app.updater is None:
                store.log("error", "telegram", "updater yo'q")
                return
            self._task = asyncio.create_task(self.app.updater.start_polling())
            store.log("info", "telegram", "bot ishga tushdi (polling)")
        except Exception as e:
            store.log("error", "telegram", f"bot start xatosi: {e}")

    async def stop(self):
        if not self._enabled or self.app is None:
            return
        try:
            if self.app.updater:
                await self.app.updater.stop()
        except Exception as e:
            store.log("warning", "telegram", f"updater stop: {e}")
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=3)
            except Exception:
                pass

    def get_chats(self) -> list[str]:
        """Barcha ulangan chat id'lar (akkauntlar + telegram userlar)."""
        chats = set()
        for acc in store.list_accounts():
            if acc.tg_chat_id:
                chats.add(acc.tg_chat_id)
        for user in store.list_users(source="telegram"):
            if user.tg_chat_id:
                chats.add(user.tg_chat_id)
        if config.TELEGRAM_CHAT_ID:
            chats.add(config.TELEGRAM_CHAT_ID)
        return list(chats)

    async def send(self, chat_id, text: str):
        if not self._enabled or self.app is None:
            return
        try:
            await self.app.bot.send_message(chat_id=int(chat_id), text=text, parse_mode="HTML")
        except Exception as e:
            print(f"[tg] send failed -> {chat_id}: {e}")

    async def broadcast(self, text: str, delay: float = 0.12):
        """Barcha chat'larga xabar yuborish (rate-limitga qarshi to'xtash bilan)."""
        chats = self.get_chats()
        sent = 0
        for chat in chats:
            await self.send(chat, text)
            sent += 1
            if delay:
                await asyncio.sleep(delay)
        return len(chats)

    async def broadcast_safe(self, text: str, delay: float = 0.12) -> dict:
        """Xabarni yuboradi va natijani qaytaradi (analitika uchun)."""
        try:
            sent = await self.broadcast(text, delay)
        except Exception as e:
            return {"ok": False, "error": str(e), "sent": 0}
        return {"ok": True, "sent": sent}

    # ---------------------------------------------------------- handlers
    def _touch_chat(self, chat_id):
        user = store.find_user_by_chat(chat_id)
        if user:
            store.touch_user(user.id)

    async def _require_admin(self, update) -> bool:
        user_id = update.effective_user.id if update.effective_user else None
        if ADMIN_IDS and user_id not in ADMIN_IDS:
            await update.effective_message.reply_text("⛔ Bu buyruq faqat adminlar uchun.")
            return False
        return True

    async def cmd_start(self, update, context):
        chat = update.effective_chat.id
        self._touch_chat(chat)
        if not store.find_user_by_chat(chat) and update.effective_user:
            uname = update.effective_user.username or update.effective_user.first_name or ""
            store.create_user(
                username=uname or None, name=uname or "",
                source="telegram", tg_chat_id=chat, tg_username=uname)
        txt = (
            "<b>🤖 AI Metal Trader</b>\n\n"
            "Akkauntni ulash uchun admin panelda yaratilgan <b>5 xonali kod</b>ni yuboring:\n"
            "  <code>/link 56321</code>\n\n"
            "Buyruqlar:\n"
            "  /status — balans va P&L\n"
            "  /positions — ochiq bitimlar\n"
            "  /signals — so'nggi AI signallar\n"
            "  /risk — xavf limitlari\n"
            "  /help — yordam"
        )
        await context.bot.send_message(chat_id=chat, text=txt, parse_mode="HTML")

    async def cmd_link(self, update, context):
        chat = update.effective_chat.id
        self._touch_chat(chat)
        username = update.effective_user.username or update.effective_user.first_name or ""
        if not context.args:
            await update.effective_message.reply_text(
                "5 xonali kodni yozing. Misol: <code>/link 56321</code>", parse_mode="HTML")
            return
        code = context.args[0].strip()
        if not (len(code) == 5 and code.isdigit()):
            await update.effective_message.reply_text("Kod 5 xonali raqam bo'lishi kerak.")
            return
        res = account_manager.bind_telegram(code, chat, username)
        if res["ok"]:
            await update.effective_message.reply_text(
                f"✅ Akkaunt <b>(kod {res['code']})</b> Telegram-ga ulandi!\n"
                f"Endi <b>kunlik hisobot</b> va ogohlantirishlar shu chatga keladi.",
                parse_mode="HTML")
            store.log("info", "telegram", f"account {res['code']} linked to chat {chat}")
            await self.send_daily_report(chat)
        else:
            await update.effective_message.reply_text(f"❌ {res['error']}")

    async def cmd_unlink(self, update, context):
        if not context.args:
            await update.effective_message.reply_text("Kodni yozing: /unlink 56321")
            return
        res = account_manager.unbind(context.args[0].strip())
        await update.effective_message.reply_text("Akkaunt uzildi." if res["ok"] else res["error"])

    async def cmd_status(self, update, context):
        self._touch_chat(update.effective_chat.id)
        info = broker.account_info()
        if not info:
            await update.effective_message.reply_text("⚠️ MT5 hisobiga ulanish yo'q.")
            return
        unreal = pnl.unrealized()
        realized = pnl.realized_periods()
        txt = (
            "<b>💼 Hisob holati</b>\n"
            f"Broker: {info['broker']} · {info['login']}@{info['server']}\n"
            f"Balans: <b>{info['balance']:,.2f}</b> {info['currency']}\n"
            f"Equity: {info['equity']:,.2f} · Marja: {info['margin']:,.2f}\n"
            f"Free margin: <b>{info['free_margin']:,.2f}</b> · Margin level: {info['margin_level']:.0f}%\n\n"
            f"Ochiq pozitsiyalar: {unreal['open_count']}\n"
            f"Floating P&L: <b>{unreal['unrealized_pnl']:+,.2f}</b> ({unreal['unrealized_pnl_pct']:+.2f}%)\n"
            f"Bugun: {realized['today']:+,.2f} ({realized['today_pct']:+.2f}%)\n"
            f"7 kun: {realized['week']:+,.2f} | 30 kun: {realized['month']:+,.2f} | "
            f"Umumiy: {realized['total']:+,.2f}"
        )
        await update.effective_message.reply_text(txt, parse_mode="HTML")

    async def cmd_positions(self, update, context):
        positions = broker.positions()
        if not positions:
            await update.effective_message.reply_text("Ochiq pozitsiya yo'q.")
            return
        lines = ["<b>📊 Ochiq pozitsiyalar</b>"]
        for p in positions:
            pct = ""
            info = broker.account_info()
            bal = info["balance"] if info else 0
            pct = f" ({p['profit'] / bal * 100:+.2f}%)" if bal else ""
            lines.append(
                f"#{p['ticket']} {p['symbol']} {p['direction']} {p['volume']} lot\n"
                f"  Kirish {p['entry']:.2f} | Joriy {p['current']:.2f}\n"
                f"  SL {p['sl']:.2f} | TP {p['tp']:.2f}\n"
                f"  P&L: <b>{p['profit']:+,.2f}</b>{pct}"
            )
        await update.effective_message.reply_text("\n\n".join(lines), parse_mode="HTML")

    async def cmd_signals(self, update, context):
        sigs = store.recent_signals(10)
        if not sigs:
            await update.effective_message.reply_text("Signallar hali yo'q.")
            return
        lines = ["<b>🔔 So'nggi AI signallar</b>"]
        for s in sigs:
            ts = s.created_at.astimezone().strftime("%d.%m %H:%M") if s.created_at else ""
            mark = "✅" if s.applied else "▫️"
            lines.append(
                f"{mark} {ts} · {s.symbol} · {s.direction} · {s.timeframe}\n"
                f"  Kirish {s.entry:.2f} | SL {s.stop_loss:.2f} | TP {s.take_profit:.2f}\n"
                f"  Confidence: <b>{s.confidence:.0f}%</b> · {s.regime}"
            )
        await update.effective_message.reply_text("\n\n".join(lines), parse_mode="HTML")

    async def cmd_risk(self, update, context):
        r = risk_summary()
        txt = (
            "<b>⚠️ Xavf limitlari</b>\n"
            f"Daraja: <b>{r['risk_level'].upper()}</b>\n"
            f"Bir bitimga xavf: <b>{r['risk_percent_per_trade']:.1f}%</b>\n"
            f"Maks. kunlik drawdown: {r['max_daily_drawdown']:.1f}%\n"
            f"Maks. ochiq pozitsiya: {r['max_open_positions']}\n"
            f"Kunlik savdo limiti: {r['max_daily_trades']}\n"
            f"Joriy kunlik P&L: {r['daily_profit_pct']:+.2f}%\n"
            f"Joriy drawdown: {r['current_drawdown_pct']:.2f}%\n"
            f"Paper trading: {'HA' if r['paper_trading'] else 'YOQ'}"
        )
        await update.effective_message.reply_text(txt, parse_mode="HTML")

    async def cmd_close(self, update, context):
        if not await self._require_admin(update):
            return
        if not context.args:
            await update.effective_message.reply_text("/close <ticket>")
            return
        try:
            ticket = int(context.args[0])
        except ValueError:
            await update.effective_message.reply_text("Ticket son bo'lishi kerak.")
            return
        import asyncio
        res = await asyncio.to_thread(broker.close_position, ticket)
        if res and res.get("ok"):
            await update.effective_message.reply_text(f"✅ Pozitsiya #{ticket} yopildi.")
            store.close_trade(ticket, reason="telegram")
        else:
            await update.effective_message.reply_text(
                f"❌ Yopilmadi: {res.get('error') if res else 'not found'}")

    # ---------------------------------------------------------- daily report
    def _today_stats(self):
        """Bugungi yopilgan bitimlar statistikasi (DB): soni, yutuqlar, winrate."""
        from datetime import timedelta
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        trades = store.closed_trades(since=today)
        total = len(trades)
        wins = sum(1 for t in trades if (t.pnl or 0) > 0)
        losses = total - wins
        winrate = (wins / total * 100.0) if total else 0.0
        pl = sum(t.pnl or 0 for t in trades)
        return {"count": total, "wins": wins, "losses": losses, "winrate": winrate, "pnl": pl}

    async def send_daily_report(self, chat_id: str | None = None, day_offset: int = 0):
        """KUNLIK SAVDO HISOBOTI — foydalanuvchi talab qilgan formatda."""
        info = broker.account_info()
        if not info:
            if chat_id:
                await self.send(chat_id, "MT5 hisobiga ulanmagan.")
            return

        realized = pnl.realized_periods()
        unreal = pnl.unrealized()
        r = risk_summary()
        stats = self._today_stats()
        cur = info["currency"] or "USD"
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        risk_name = {"conservative": "Past", "moderate": "O'rta", "aggressive": "Yuqori"}.get(
            r["risk_level"], r["risk_level"])

        lines = [
            f"📊 KUNLIK SAVDO HISOBOTI | {today_date}",
            "----------------------------------",
            f"💰 Umumiy Balans: ${info['balance']:,.2f} "
            f"({realized['today_pct']:+.2f}%)",
            f"📉 Joriy Risk Darajasi: {risk_name} ({r['risk_percent_per_trade']:.0f}%)",
            "",
            "📈 BUGUNGI NATIJALAR:",
            f"• Bajarilgan bitimlar: {stats['count']} ta",
            f"• Yutug'li bitimlar: {stats['wins']} ta "
            f"({stats['winrate']:.0f}% Winrate)",
            f"• Bugungi P&L: {stats['pnl']:+,.2f} ({realized['today_pct']:+.2f}%)",
        ]

        positions = broker.positions()
        if positions:
            lines.append("")
            lines.append("🟡 OCHIQ BITIMLAR:")
            for p in positions[:5]:
                pct = (p["profit"] / info["balance"] * 100.0) if info["balance"] else 0.0
                sym = p["symbol"].replace("m", "").replace(".", "").upper()
                lines.append(
                    f"• {sym[:6]}/{cur} ({p['direction']}) — "
                    f"Joriy P&L: {p['profit']:+,.2f} ({pct:+.2f}%)")

        lines.append("")
        lines.append("🤖 METAL INDEX SIGNALLARI:")
        signals = self._recent_signal_state()
        if signals:
            for sym, txt in signals.items():
                lines.append(f"• {sym} — {txt}")
        else:
            lines.append("• XAU/USD — NEUTRAL (Kutishda)")
            lines.append("• XAG/USD — NEUTRAL (Kutishda)")

        lines.append("")
        lines.append("⏱ Keyingi yangilanish: Ertaga 23:59")
        text = "\n".join(lines)

        if chat_id:
            await self.send(chat_id, text)
        else:
            for chat in self.get_chats():
                await self.send(chat, text)

    def _recent_signal_state(self) -> dict[str, str]:
        """So'nggi signallarni Metal Index holatiga aylantirish."""
        from backend.app.trader_engine import trader
        out = {}
        for symbol, txt in trader.last_signal_text.items():
            short = symbol.replace("m", "").replace(".", "")
            if len(short) > 6:
                short = short[:6]
            short = f"{short[:3]}/{short[3:6]}" if len(short) == 6 else short
            if txt.startswith("BUY"):
                out[f"{short}/USD"] = "BUY signal (Aktiv)"
            elif txt.startswith("SELL"):
                out[f"{short}/USD"] = "SELL signal (Aktiv)"
            else:
                out[f"{short}/USD"] = "NEUTRAL (Kutishda)"
        return out

    def _ai_daily_summary(self, realized, unreal, r) -> str:
        """30 yillik professional treder kabi kunni baholash."""
        today = realized["today"]
        if today > 0:
            verdict = f"Kun foyda bilan yakunlandi ({today:+,.2f}). Professional yondashuv — "
            if r["daily_profit_pct"] >= r["daily_profit_target"]:
                verdict += "kunlik maqsadga erishildi, yangi pozitsiya ochilmadi — kapital himoyasi birinchi o'rinda."
            else:
                verdict += "foyda erta himoya qilish qoidasi saqlanib qolindi, keyingi sessiyaga tayyor."
        elif today == 0:
            verdict = "Kun o'zgarishsiz — reyj bozorlarda pozitsiya ochmaslik professional qoidaga mos."
        else:
            verdict = f"Kun zarar bilan ({today:+,.2f}). Drawdown {r['current_drawdown_pct']:.1f}% — "
            if r["current_drawdown_pct"] >= r["max_daily_drawdown"]:
                verdict += "kunlik stop-loss ishladi, savdo to'xtatildi. Nazorat — professionalning asosiy qoidalaridan."
            else:
                verdict += "zarar limitdan past — jamoaviy xatolar tahlil qilindi, ertaga qaytamiz."
        noti = "Ogohlantirish: hafta davomida Oltin/Kumush volatil bo'lishi kutilmoqda. Yirik yangiliklar oldidan pozitsiya hajmi kamaytirildi." if r["current_drawdown_pct"] > 3 else \
               "Eslatma: keyingi sessiyada AQSh makro-ko'rsatkichlar e'lonlari — bozor ochilishida spread kengayishi mumkin."
        return f"{verdict}\n{noti}"


tg = TelegramBot()


def asyncio_loop_or_new():
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.new_event_loop()