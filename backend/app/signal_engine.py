"""Pro Tred — AI Signal Engine.

Robot 20-30 yillik professional treder kabi fikrlaydi:
  1. Ko'p timeframe tahlil (D1/H4 trend, H1/M15 kirish trigger).
  2. Konfluent indikatorlar (EMA, MACD, RSI, Stochastic, ADX, Bollinger,
     S/R, OBV, ATR) — bir yo'nalishda bo'lsagina signal beradi.
  3. Bozor rejimi (trend/reyj) aniqlash — reyjda yangi pozitsiya ochmaydi.
  4. Kirish, Stop-Loss (ATR), Take-Profit (kamida 1.5R) professional qoida.
  5. Confidence 0-100 — konfluensiya kuchiga qarab.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from backend.app import indicators as ind
from backend.app.mt5_broker import broker

TF_ORDER = ["M15", "H1", "H4", "D1"]
TREND_TF = ["H4", "D1"]
ENTRY_TF = ["M15", "H1"]

BARS = 400


@dataclass
class TFAnalysis:
    timeframe: str
    trend: str = "neutral"          # up | down | neutral
    regime: str = "range"           # trend_up | trend_down | range | volatile
    adx: float = 0.0
    rsi: float = 50.0
    macd_hist: float = 0.0
    macd_bull: bool = False
    price_vs_ema20: float = 0.0      # (-1..1) price position vs ema20
    price_vs_ema50: float = 0.0
    price_vs_ema200: float = 0.0
    closed_above_ema20: int = 0      # nechta bar ketma-ket ema20 ostida/ustida
    atr: float = 0.0
    stoch_k: float = 50.0
    stoch_d: float = 50.0
    bb_pos: float = 0.0              # -1 (pastki) .. 1 (yuqori)
    last_candle: dict = field(default_factory=dict)
    pattern: str = ""


@dataclass
class Signal:
    symbol: str = ""
    direction: str = "NONE"          # BUY | SELL
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    confidence: float = 0.0
    timeframe: str = ""
    regime: str = ""
    reasons: list[str] = field(default_factory=list)
    breakout: bool = False


class SignalEngine:
    def __init__(self):
        self.broker = broker
        self._cache: dict[str, dict] = {}

    # -----------------------------------------------------------------
    def get_rates(self, symbol: str, tf: str):
        return self.broker.rates(symbol, tf, BARS)

    def analyze_symbol(self, symbol: str, tick=None, symbol_info=None) -> Signal | None:
        """Bitta simbol uchun to'liq AI tahlil."""
        if not (tick and symbol_info):
            tick = self.broker.tick(symbol)
            symbol_info = self.broker.symbol_info(symbol) or {}
        if not tick:
            return None

        tfs = self._load_all_tfs(symbol)
        if not tfs:
            return None

        tfm: dict[str, TFAnalysis] = {}
        for tf, bars in tfs.items():
            tfm[tf] = self._analyze_tf(tf, bars)

        # 1) Trend + rejim
        trend_votes = {"up": 0, "down": 0}
        for tf in TREND_TF:
            a = tfm.get(tf)
            if not a:
                continue
            if a.trend == "up":
                trend_votes["up"] += 1
            elif a.trend == "down":
                trend_votes["down"] += 1

        net_trend = trend_votes["up"] - trend_votes["down"]
        regime = "trend_up" if net_trend > 0 else "trend_down" if net_trend < 0 else "range"

        # D1 trend liniyasi
        d1 = tfm.get("D1")
        h4 = tfm.get("H4")
        h1 = tfm.get("H1")
        m15 = tfm.get("M15")

        reasons: list[str] = []
        if d1:
            reasons.append(f"D1: {self._regime_text(d1)} (ADX {d1.adx:.0f}, RSI {d1.rsi:.0f})")
        if h4:
            reasons.append(f"H4: {self._regime_text(h4)} (EMA20 poz. {self._pct(h4.price_vs_ema50)})")
        if h1:
            reasons.append(f"H1: {self._regime_text(h1)} (Stoch {h1.stoch_k:.0f}/{h1.stoch_d:.0f}, MACD hist {h1.macd_hist:.2f})")

        # 2) Kirish yo'nalishi — konfluensiya hisobi (professional skoring)
        score = 0.0
        reasons_in: list[str] = []
        entry_a = tfm.get(ENTRY_TF[1]) or h1 or m15   # H1
        entry_b = tfm.get(ENTRY_TF[0]) or m15 or h1   # M15

        if net_trend == 0:
            reasons.append(f"Yuqori TF trend aniq emas ({trend_votes}) — professional qoida: "
                           f"trendsiz bozorda oldindan pozitsiya ochilmaydi")
            return None

        # Yetakchi yo'nalish signali yuqori TF'lardan keladi
        direction = "BUY" if net_trend > 0 else "SELL"
        bullish = direction == "BUY"

        # --- Yuqori TF (H4, D1) konfluensiya: 40 ball
        higher_agree = 0
        for tf in TREND_TF:
            a = tfm.get(tf)
            if not a:
                continue
            if (a.trend == "up" and bullish) or (a.trend == "down" and not bullish):
                higher_agree += 1
            else:
                higher_agree -= 1
        if higher_agree >= 1:
            score += 28
            reasons_in.append(f"Yuqori TF konfluensiya ({higher_agree}/{len(TREND_TF)} yo'nalishda)")
        elif higher_agree == 0:
            score += 6  # qisman mos
        else:
            reasons_in.append("Yuqori TF'lar bir-biriga qarshi — xavf yuqori")
            # qarshi kelgan kuchli xavf — kirishga yo'l bermaymiz
            return None

        # D1 struktura — narx EMA50 ustida/ostida
        if d1:
            if bullish and d1.price_vs_ema50 > 0:
                score += 8
                reasons_in.append("D1 narx EMA50 ustida (uzoq trend struktura)")
            elif not bullish and d1.price_vs_ema50 < 0:
                score += 8
                reasons_in.append("D1 narx EMA50 ostida (uzoq trend struktura)")
            # trend kuchini ADX tasdiqlaydi
            if d1.adx >= 25 and ((bullish and d1.regime == "trend_up") or
                                 (not bullish and d1.regime == "trend_down")):
                score += 6
                reasons_in.append(f"D1 ADX {d1.adx:.0f} — trend kuchli")

        # --- Kirish TF (H1/M15) trigger: 35 ball
        if entry_a:
            if (entry_a.trend == "up" and bullish) or (entry_a.trend == "down" and not bullish):
                score += 12
                reasons_in.append(f"{entry_a.timeframe}: kirish TF trendga mos")
            else:
                reasons_in.append(f"{entry_a.timeframe}: kirish TF trendga qarshi — trigersiz")
                score -= 12

            if entry_b:
                if (entry_b.trend == "up" and bullish) or (entry_b.trend == "down" and not bullish):
                    score += 7
                    reasons_in.append(f"{entry_b.timeframe}: kirish TF qo'llab-quvvatlamoqda")

            # MACD kesishish trigger
            if entry_a.macd_bull == bullish:
                score += 8
                reasons_in.append(f"{entry_a.timeframe}: MACD {'bullish' if bullish else 'bearish'}")

            # RSI — trend yo'nalishida, lekin ekstremal emas
            if bullish and 45 <= entry_a.rsi <= 66:
                score += 4
            elif not bullish and 34 <= entry_a.rsi <= 55:
                score += 4
            if (bullish and entry_a.rsi > 80) or (not bullish and entry_a.rsi < 20):
                score -= 10
                reasons_in.append("RSI ekstremal — ta'qib qilish xavfi (hind-side)")

            # Stochastic kesishish
            if (bullish and entry_a.stoch_k > entry_a.stoch_d and entry_a.stoch_k < 70) or \
               (not bullish and entry_a.stoch_k < entry_a.stoch_d and entry_a.stoch_k > 30):
                score += 4
                reasons_in.append(f"{entry_a.timeframe}: Stochastic kesishish")

            # Kirish TF kuchli trendli (ADX) bo'lsa
            if entry_a.adx >= 22 and entry_a.adx < 60:
                score += 3

            # Kuchli yo'nalishli candle trigger
            body = entry_a.last_candle.get("body", 0)
            rng = entry_a.last_candle.get("range", 1)
            if (bullish and body > 0 and body > rng * 0.5) or \
               (not bullish and body < 0 and abs(body) > rng * 0.5):
                score += 6
                reasons_in.append(f"Kuchli {'yashil' if bullish else 'qizil'} {entry_a.timeframe} candle")

        # Pattern bonus (har bir TF uchun)
        for tf in (h1, m15):
            if tf and tf.pattern:
                ok = (tf.pattern in ("bullish_engulf", "hammer") and bullish) or \
                     (tf.pattern in ("bearish_engulf", "shooting_star") and not bullish)
                if ok:
                    score += 8
                    reasons_in.append(f"{tf.timeframe}: {tf.pattern} pattern")

        # VB shelf: OBV yo'nalishni tasdiqlasa
        try:
            if d1 and self._obv_align(symbol, d1) == bullish:
                score += 3
        except Exception:
            pass

        score = max(0.0, min(100.0, score))

        # 3) ATR-based SL/TP
        atr_h1 = h1.atr if h1 and h1.atr > 0 else (m15.atr if m15 else 0)
        atr_h4 = h4.atr if h4 and h4.atr > 0 else atr_h1
        atr_d1 = d1.atr if d1 and d1.atr > 0 else atr_h4
        base_atr = max(atr_h4, atr_d1 * 0.6, 1e-9)
        spread = symbol_info.get("spread", 0)
        spread_pts = spread * (symbol_info.get("point", 0.01) or 0.01)
        digits = symbol_info.get("digits", 2)

        # SL: structure ostida/ustida (so'nggi swing) va ATR qopqog'i
        closes = self._last_closes(tfs["D1"]) if "D1" in tfs else None
        lows = self._last_lows(tfs["D1"]) if "D1" in tfs else None
        highs = self._last_highs(tfs["D1"]) if "D1" in tfs else None
        swing_low = float(np.min(lows[-12:])) if lows is not None else 0
        swing_high = float(np.max(highs[-12:])) if highs is not None else 0

        price = tick["ask"] if direction == "BUY" else tick["bid"]
        if direction == "BUY":
            sl = min(swing_low if swing_low else price - 3 * base_atr,
                     price - 2.5 * base_atr)
            sl = round(sl - spread_pts * 0.5, digits)
            # TP: qarshilik yoki 1.8R
            sup, res = ind.support_resistance(
                self._last_highs(tfs["H4"]) if "H4" in tfs else highs,
                self._last_lows(tfs["H4"]) if "H4" in tfs else lows,
                closes if closes is not None else [], 90)
            if res and res > price:
                tp = res
            else:
                tp = price + (price - sl) * 1.8
            tp = round(tp, digits)
        else:
            sl = max(swing_high if swing_high else price + 3 * base_atr,
                     price + 2.5 * base_atr)
            sl = round(sl + spread_pts * 0.5, digits)
            sup, res = ind.support_resistance(
                self._last_highs(tfs["H4"]) if "H4" in tfs else highs,
                self._last_lows(tfs["H4"]) if "H4" in tfs else lows,
                closes if closes is not None else [], 90)
            if sup and 0 < sup < price:
                tp = sup
            else:
                tp = price - (sl - price) * 1.8
            tp = round(tp, digits)

        # 4) Confidence (professional yaxlit baholash)
        confidence = round(max(0.0, min(100.0, score)), 1)

        sig_time = entry_a.timeframe if entry_a and entry_a.pattern else h4.timeframe if h4 else "H1"
        signal = Signal(
            symbol=symbol,
            direction=direction,
            entry=round(price + (spread_pts if direction == "BUY" else 0), digits),
            stop_loss=sl,
            take_profit=tp,
            confidence=confidence,
            timeframe=sig_time,
            regime=regime,
            reasons=reasons + reasons_in,
        )
        return signal

    # -----------------------------------------------------------------
    def _load_all_tfs(self, symbol: str) -> dict[str, list[dict]]:
        out = {}
        for tf in TF_ORDER:
            r = self.get_rates(symbol, tf)
            if r and len(r) >= 60:
                out[tf] = r
        return out

    def _obv_align(self, symbol: str, d1: TFAnalysis) -> bool | None:
        """OBV trend yo'nalishini tasdiqlaydimi (True=bullish, False=bearish, None=aniq emas)."""
        rates = self.get_rates(symbol, "D1")
        if not rates or len(rates) < 40:
            return None
        obv = ind.obv(
            np.array([r["close"] for r in rates], float),
            np.array([r["volume"] for r in rates], float))
        seg = obv[-20:]
        slope = (seg[-1] - seg[0]) / max(abs(seg[0]), 1e-9)
        if slope > 0.02:
            return True
        if slope < -0.02:
            return False
        return None

    def _analyze_tf(self, tf: str, bars: list[dict]) -> TFAnalysis:
        close = np.array([b["close"] for b in bars], dtype=float)
        high = np.array([b["high"] for b in bars], dtype=float)
        low = np.array([b["low"] for b in bars], dtype=float)
        vol = np.array([b["volume"] for b in bars], dtype=float)
        n = len(close)

        a = TFAnalysis(timeframe=tf)
        a.atr = ind.last_valid(ind.atr(high, low, close, 14)) or 0.0

        e20 = ind.ema(close, 20)
        e50 = ind.ema(close, 50)
        e200 = ind.ema(close, 200) if n >= 200 else ind.ema(close, max(20, n // 2))
        e20v, e50v, e200v = (ind.last_valid(x) for x in (e20, e50, e200))

        if e20v and e50v:
            a.price_vs_ema20 = (close[-1] - e20v) / e20v
            a.price_vs_ema50 = (close[-1] - e50v) / e50v
            a.price_vs_ema200 = ((close[-1] - e200v) / e200v) if e200v else 0.0

            if close[-1] > e20v and e20v > e50v and ind.last_valid(ind.ema(close, 50)) is not None:
                a.trend = "up"
            elif close[-1] < e20v and e20v < e50v:
                a.trend = "down"
            else:
                a.trend = "neutral"

        # ketma-ket ema20 ustida/ostida
        above = close > e20
        cnt = 0
        for x in above[::-1]:
            if not isinstance(x, (bool, np.bool_)):
                break
            if x:
                cnt += 1
                continue
            break
        a.closed_above_ema20 = cnt if a.trend == "up" else -cnt

        # ADX / rejim
        adx_arr = ind.adx(high, low, close, 14)
        a.adx = ind.last_valid(adx_arr) or 0.0
        plus_di = None
        # DI+ DI- hisoblash (adx uchun)
        di_plus, di_minus = self._compute_di(high, low, close, 14)
        di_p, di_m = (ind.last_valid(x) or 0.0 for x in (di_plus, di_minus))
        if a.adx >= 25 and di_p > di_m:
            a.regime = "trend_up"
        elif a.adx >= 25 and di_m > di_p:
            a.regime = "trend_down"
        elif a.adx < 20:
            a.regime = "range"
        else:
            a.regime = "volatile"
        # RSI
        rsi_arr = ind.rsi(close, 14)
        a.rsi = ind.last_valid(rsi_arr) or 50.0
        # MACD
        m_line, m_sig, m_hist = ind.macd(close)
        a.macd_hist = ind.last_valid(m_hist) or 0.0
        h_pre = ind.last_valid(m_hist[:-3]) if m_hist is not None and len(m_hist) > 5 else 0.0
        a.macd_bull = a.macd_hist > 0 and a.macd_hist > h_pre
        # Stochastic
        k, d = ind.stochastic(high, low, close)
        a.stoch_k = ind.last_valid(k) or 50.0
        a.stoch_d = ind.last_valid(d) or 50.0
        # Bollinger pozitsiya
        up, mid, lowb = ind.bollinger(close, 20, 2.0)
        upv, midv, lowv = (ind.last_valid(x) for x in (up, mid, lowb))
        if upv and lowv and upv != lowv:
            a.bb_pos = (close[-1] - lowv) / (upv - lowv) * 2 - 1
        # candle pattern (engulfing / hammer / shooting star)
        a.last_candle = self._candle_shape(bars[-1])
        a.pattern = self._detect_pattern(bars[-3:])
        return a

    @staticmethod
    def _compute_di(high, low, close, period=14):
        h, l, c = np.asarray(high, float), np.asarray(low, float), np.asarray(close, float)
        up = np.diff(h)
        down = -np.diff(l)
        plus = np.where((up > down) & (up > 0), up, 0.0)
        minus = np.where((down > up) & (down > 0), down, 0.0)
        tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
        atr_r = ind._atr_fill(tr, period, len(c))[1:]
        plus_di = np.where(atr_r > 0, 100.0 * ind.sma(plus, period) / atr_r, np.nan)
        minus_di = np.where(atr_r > 0, 100.0 * ind.sma(minus, period) / atr_r, np.nan)
        return plus_di, minus_di

    def _candle_shape(self, bar: dict) -> dict:
        o, h, l, cl = bar["open"], bar["high"], bar["low"], bar["close"]
        rng = max(h - l, 1e-9)
        body = cl - o
        return {"open": o, "high": h, "low": l, "close": cl,
                "body": round(body, 5), "range": round(rng, 5),
                "signed": "up" if body > 0 else "down"}

    def _detect_pattern(self, bars: list[dict]) -> str:
        if len(bars) < 3:
            return ""
        prev1, prev2, cur = bars[-2], bars[-3], bars[-1]
        o1, c1 = prev1["open"], prev1["close"]
        o2, c2 = prev2["open"], prev2["close"]
        o3, c3 = cur["open"], cur["close"]
        body1 = c1 - o1
        body3 = c3 - o3
        rng3 = max(cur["high"] - cur["low"], 1e-9)
        # Engulfing
        if body1 != 0 and c3 != o3:
            if body1 > 0 and body3 < 0 and c3 < o1 and o3 > c1 and abs(body3) > abs(body1) * 1.1:
                return "bearish_engulf"
            if body1 < 0 and body3 > 0 and c3 > o1 and o3 < c1 and abs(body3) > abs(body1) * 1.1:
                return "bullish_engulf"
        # Hammer / Shooting star
        lower_wick = min(o3, c3) - cur["low"]
        upper_wick = cur["high"] - max(o3, c3)
        if abs(body3) < rng3 * 0.35:
            if lower_wick > rng3 * 0.55 and upper_wick < rng3 * 0.15:
                return "hammer"
            if upper_wick > rng3 * 0.55 and lower_wick < rng3 * 0.15:
                return "shooting_star"
        return ""

    # ---------- utils ----------
    @staticmethod
    def _last_closes(bars): return np.array([b["close"] for b in bars], float)
    @staticmethod
    def _last_lows(bars): return np.array([b["low"] for b in bars], float)
    @staticmethod
    def _last_highs(bars): return np.array([b["high"] for b in bars], float)

    @staticmethod
    def _pct(x):
        if x is None:
            return "n/a"
        return f"{x * 100:+0.1f}%"

    @staticmethod
    def _regime_text(a: TFAnalysis) -> str:
        t = {"up": "TREND UP", "down": "TREND DOWN", "neutral": "NEUTRAL"}.get(a.trend, a.trend)
        r = {"trend_up": "trend", "trend_down": "trend", "range": "reyj", "volatile": "tebranuvchi"}.get(a.regime, a.regime)
        return f"{t} ({r})"


engine = SignalEngine()