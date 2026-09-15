# Pro Tred — AI Metal Trader

Metallar indeksi (Oltin — XAU/USD, Kumush — XAG/USD) bo'yicha MT5 broker
hisobida avtomatik savdo qiladigan AI robot. 20-30+ yillik professional
treyder kabi ko'p-timeframe tahlil, indikator konfluensiyasi va risk
nazorati bilan ishlaydi. Telegram bot orqali ulash + kunlik hisobot,
admin panelda real-vaqt kuzatuv.

## Arxivtektura

```
Pro Tred/
├── backend/                 # Python (FastAPI + MT5 + Telegram)
│   ├── main.py              # FastAPI kirish nuqtasi
│   ├── config.py            # .env sozlamalari
│   ├── .env.example         # sozlamalar namuna
│   ├── requirements.txt
│   ├── app/
│   │   ├── mt5_broker.py    # MetaTrader 5 ulagich (login, order, pozitsiya)
│   │   ├── indicators.py    # EMA/RSI/MACD/ATR/ADX/Stoch/Bollinger/S-R/Fib
│   │   ├── signal_engine.py # AI signal dvigateli (ko'p-TF ning konfluensiya)
│   │   ├── risk_manager.py  # Risk darajalari, drawdown, lot hisobi
│   │   ├── pnl_service.py   # Unrealized va Realized P&L
│   │   ├── account_manager.py  # 5 xonali link kodlar + user bog'lash
│   │   ├── auth.py          # Web ro'yxatdan o'tish/kirish (token)
│   │   ├── store.py         # SQLite saqlash (Users, Broadcast, trades ...)
│   │   ├── trader_engine.py # Asosiy savdo sikl (scan + execute + risk)
│   │   ├── telegram_bot.py  # Telegram bot (link, hisobot, buyruqlar)
│   │   └── api.py           # REST + WebSocket + admin/analitika
│   └── data/trader.db       # (avtomatik yaratiladi) — YAGONA BAZA
├── frontend/                # Vite + React admin panel
│   ├── public/join.html     # Web foydalanuvchi ro'yxatdan o'tish sahifasi
│   └── dist/                # build natijasi (backend /panel/ orqali xizmat qiladi)
├── setup.bat                # 1-marta o'rnatish
└── start.bat                # ishga tushirish
```

## Talablar (Windows)

- **MetaTrader 5** terminali kompyuterda o'rnatilgan va broker hisobingizga
  kira oladigan bo'lishi kerak (istalgan broker: Exness, IC Markets, XM...).
- **Python 3.10+** (`setup.bat` tekshiradi).
- **Node.js** (admin panel build uchun, `npm` kerak).

> Eslatma: MT5 Python API faqat MT5 terminali bilan bir kompyuterda
> ishlaydi — robot o'sha kompyuterda ishga tushiriladi.

## O'rnatish (1-marta)

1. `setup.bat` ni ishga tushiring (venv + paketlar + panel build).
2. `backend\.env` faylini oching va to'ldiring:
   ```ini
   MT5_LOGIN=12345678
   MT5_PASSWORD=parolingiz
   MT5_SERVER=Broker-Server-Here
   TELEGRAM_BOT_TOKEN=BotFather-dan olingan token
   PAPER_TRADING=true      # birinchi sinovda true (demo). Real savdo uchun false.
   ADMIN_TOKEN=kuchli-token
   ```
3. `start.bat` — robot ishga tushadi, brauzerda admin panel ochiladi.

> **Xavfsizlik:** `MT5_PASSWORD` va `TELEGRAM_BOT_TOKEN` ochiq faylda saqlanadi.
> Faqat o'z kompyuteringizda ishlating.

## Telegram bot bilan ulash (5 xonali ID)

1. `start.bat` ishlayotgan paytida admin panelga o'ting → **Sozlamalar**.
2. "Yangi akkaunt yaratish" tugmasi → sizga **5 xonali kod** beriladi
   (masalan `56321`).
3. Telegram'da botingizni oching va yuboring:
   ```
   /link 56321
   ```
4. Akkaunt Telegram chat'ingizga ulanadi. Endi sizga **kunlik hisobot**,
   yangi bitim xabarlari, risk ogohlantirishlari keladi.

**Web orqali ro'yxatdan o'tish:** `http://SERVIS:8120/panel/join.html`
— web foydalanuvchi o'z loginini yaratadi, avtomatik 5 xonali kod oladi va
Telegram botga `/link <kod>` orqali ulanadi. Web va Telegram a'zolar **bitta
bazada**, markaziy admin paneldan ko'rinadi.

Buyruqlar:

| Buyruq | Vazifasi |
|---|---|
| `/link <kod>` | Akkauntni shu chatga ulash |
| `/status` | Balans, marja, P&L |
| `/positions` | Ochiq pozitsiyalar |
| `/signals` | So'nggi AI signallar |
| `/risk` | Xavf limitlari |
| `/close <ticket>` | Pozitsiyani yopish (admin) |
| `/help` | Yordam |
| `Bot orqali reklama` | Admin panel **Bot Sahifasi** → reklama matni → yuborish |

## Admin panel bo'limlari

1. **Bosh Panel** — platforma ko'rsatkichlari: jami a'zolar (Web/Telegram),
   qancha odam robot orqali savdo ochgan, umumiy hajm (lot), bugungi faol va
   yangi a'zolar; **qaysi instrumentlarda qancha aylanma** (XAU/USD, XAG/USD),
   ro'yxatdan o'tish grafigi va DAU (kunlik faol) analitikasi.
2. **A'zolar** — to'liq ro'yxat: manba (Web / Telegram), login, profil, telefon,
   ro'yxatdan o'tgan sana, so'nggi faollik, savdolar soni, hajm va realized P&L.
   Filter: hammasi / web / telegram + qidiruv.
3. **Bot Sahifasi** — Telegram reklama: matn (HTML) yozish, shablonlar,
   barcha ulangan chatlarga yuborish (tasdiqlash bilan) va yuborish tarixi.
4. **Risk va Balans** — balans, marja, free margin; margin level.
5. **P&L Panel** — Unrealized (real-vaqt, $ va %), Realized (bugun/7/30/umumiy).
6. **Ochiq Bitimlar** — live jadval (aktiv, tur, kirish, joriy, TP, SL, floating
   P&L) + **Close** tugmasi orqali majburiy yopish. Bitimlar tarixi ham bor.
7. **AI Signallar** — metallar indeksidagi o'zgarishlar jurnali: indikator
   asoslari, rejim, confidence, TP/SL.
8. **Sozlamalar** — manual risk setter: daraja (Conservative 1–2% / Moderate
   3–5% / Aggressive 5%+), max risk/bitim, max kunlik drawdown, kunlik foyda
   maqsadi, maks ochiq pozitsiya, confidence filtri, PAPER/REAL rejim, akkaunt
   yaratish + Telegram test.
9. **Jurnallar** — sistema va AI hodisalari.

## Xavf boshqaruvi (AI robot qoidalari)

- **Risk darajalari:** Conservative 1–2% / Moderate 3–5% / Aggressive 5%+.
- **Manual Risk Setter:** admin panel orqali maksimal risk % va maksimal
  kunlik drawdown (kunlik stop-loss) o'zgartiriladi.
- **Kunlik drawdown hit** → barcha AI pozitsiyalari yopiladi.
- **Kunlik foyda maqsadi** erishilsa → yangi pozitsiya ochilmaydi (foydani
  himoya qilish printsipi).
- **Reyj bozor** → professional qoida: pozitsiya ochilmaydi, faqat trend
  yo'nalishida konfluensiya yetarli bo'lsa.
- **PAPER rejim** — sinov uchun tavsiya etiladi; real savdo uchun
  `PAPER_TRADING=false` qiling.

## AI signal dvigateli

Har bir simbol uchun D1/H4/H1/M15 tahlil qilinadi:

- **Trend qatlami (D1, H4):** EMA20/50/200 strukturasi, ADX (trend kuchi),
  narx pozitsiyasi, RSI, OBV hajm konfirmatsiyasi.
- **Kirish qatlami (H1, M15):** MACD kesishish, Stochastic, kuchli candle,
  candle pattern (engulfing, hammer, shooting star), S/R.
- **Konfluensiya skoring:** yuqori TF mos kelmasa signal chiqmaydi; qarshi
  keladigan TF'lar borida pozitsiya ochilmaydi.
- **TP/SL:** ATR va struktura (swing/S/R) asosida, minimal 1.8R.
- **Confidence 0–100** — admin panelda filtr sifatida ishlaydi.

## API

- `GET  /api/status` — to'liq live holat
- `GET  /api/signals` — signal jurnali
- `GET  /api/trades?only_open=true` — bitimlar
- `GET  /api/events` — jurnallar
- `POST /api/positions/{ticket}/close` — pozitsiyani yopish
- `POST /api/settings` — risk sozlamalari (X-Admin-Token kerak)
- `POST /api/accounts` — yangi akkaunt / link kod
- `GET  /api/accounts` — akkauntlar (X-Admin-Token kerak)
- `WS   /api/ws` — real-vaqt status stream (panel sahifasi shunda yashaydi)
- `POST /api/report` — kunlik hisobotni hozir yuborish
- `POST /api/telegram/test` — Telegram test xabar
- `GET  /api/admin/stats` — platforma statistikasi (a'zolar, hajm, instrumentlar)
- `GET  /api/admin/users` — a'zolar ro'yxati (`?source=web|telegram`, `?q=`)
- `GET  /api/admin/registrations?days=14` — kunlik ro'yxatdan o'tish grafigi
- `GET  /api/admin/dau?days=14` — kunlik faol foydalanuvchilar
- `GET  /api/admin/broadcasts` — reklama tarixi
- `POST /api/admin/broadcast` — barcha Telegram chatlarga reklama
- `POST /api/register` — web ro'yxatdan o'tish
- `POST /api/login` — web kirish
- `GET  /api/me` — o'z profil va link kodi (X-User-Token)

Token `/api/status`, `/api/signals` kabi o'qish endpointlarida majburiy emas;
o'zgartirishlar `X-Admin-Token` header orqali `ADMIN_TOKEN` bilan himoyalangan
(panel sahifa token ni brauzer storage'da saqlaydi). Admin bo'limlar (users,
stats, broadcast) faqat `X-Admin-Token` bilan ochiladi.

## Ish rejimi

- `POLL_INTERVAL=3` — narxlar/pozitsiyalar har 3 sekundda yangilanadi.
- `SIGNAL_SCAN_INTERVAL=60` — AI skan har 60 sekundda.
- Kunlik sessiya TZ UTC 00:00 da yangilanadi (drawdown byudjeti).
- Kunlik Telegram hisoboti `DAILY_REPORT_TIME` da (masalan 19:00).