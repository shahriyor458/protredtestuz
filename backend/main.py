"""Pro Tred — AI Trading Robot (main entry).

Ishga tushirish:  uvicorn backend.main:app --host 127.0.0.1 --port 8120
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import router as api_router
from backend.app.store import store
from backend.app.telegram_bot import tg
from backend.app.trader_engine import trader
from backend.config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("protred")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


async def run_trader():
    await trader.start_async()


async def daily_report_loop():
    """Har kuni DAILY_REPORT_TIME da Telegram'ga kunlik hisobot."""
    hh, mm = config.DAILY_REPORT_TIME.split(":")
    target = int(hh) * 3600 + int(mm) * 60
    while True:
        now = datetime.now(timezone.utc)
        secs = now.hour * 3600 + now.minute * 60 + now.second
        if secs >= target:
            await tg.send_daily_report()
            # ertaga
            await asyncio.sleep(86400 - secs + target + 10)
            continue
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Pro Tred boshlanmoqda...")
    store.log("info", "system", "AI Trader ishga tushmoqda")
    tg_task = None
    report_task = None
    if tg.enabled:
        tg_task = asyncio.create_task(tg.start())
    trader_task = asyncio.create_task(run_trader())
    report_task = asyncio.create_task(daily_report_loop())
    yield
    await trader.stop()
    if tg_task:
        tg_task.cancel()
    if report_task:
        report_task.cancel()
    log.info("Pro Tred to'xtatildi.")


app = FastAPI(title="Pro Tred — AI Metal Trader", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
def health():
    return {"ok": True,
            "mt5": "ok" if trader.connected else "disconnected",
            "paper": config.is_paper,
            "time": datetime.now(timezone.utc).isoformat()}


# static frontend (agar build qilingan bo'lsa)
if FRONTEND_DIR.exists():
    app.mount("/panel", StaticFiles(directory=FRONTEND_DIR, html=True), name="panel")

    @app.get("/")
    def index():
        return {"service": "pro-tred-ai", "docs": "/docs", "admin": "/panel"}