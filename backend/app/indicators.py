"""Pro Tred — Technical indicators (pure numpy, TA-Lib kerak emas).

Bu modul professional treder foydalanadigan asosiy indikatorlar to'plami:
EMA/SMA, RSI, MACD, ATR, Bollinger, Stochastic, ADX, OBV, VWAP,
Support/Resistance va Fibonacchi retracement.
"""
from __future__ import annotations

import numpy as np


def sma(values, period: int):
    v = np.asarray(values, dtype=float)
    if len(v) < period:
        return np.full(len(v), np.nan)
    out = np.full(len(v), np.nan)
    c = np.cumsum(np.insert(v, 0, 0.0))
    out[period - 1:] = (c[period:] - c[:-period]) / period
    return out


def ema(values, period: int):
    v = np.asarray(values, dtype=float)
    out = np.full(len(v), np.nan)
    if len(v) < period:
        return out
    k = 2.0 / (period + 1.0)
    seed = np.mean(v[:period])
    out[period - 1] = seed
    e = seed
    for i in range(period, len(v)):
        e = v[i] * k + e * (1 - k)
        out[i] = e
    return out


def rsi(values, period: int = 14):
    v = np.asarray(values, dtype=float)
    out = np.full(len(v), np.nan)
    if len(v) <= period:
        return out
    delta = np.diff(v)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = sma(gain, period)
    avg_loss = sma(loss, period)
    for i in range(period, len(v)):
        g = avg_gain[i - 1]
        l = avg_loss[i - 1]
        if l == 0:
            out[i] = 100.0
            continue
        out[i] = 100.0 - 100.0 / (1.0 + g / l)
    return out


def macd(values, fast=12, slow=26, signal=9):
    v = np.asarray(values, dtype=float)
    ef = ema(v, fast)
    es = ema(v, slow)
    line = ef - es
    # signal: line'ning ema'si — NaN qatorlarni chetlab
    clean_line = line[~np.isnan(line)]
    sig_full = np.full(len(v), np.nan)
    if len(clean_line) >= signal:
        sig_clean = ema(clean_line, signal)
        idx = np.where(~np.isnan(line))[0]
        for j in range(signal - 1, len(clean_line)):
            sig_full[idx[j]] = sig_clean[j]
    hist = line - sig_full
    return line, sig_full, hist


def atr(high, low, close, period: int = 14):
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    return _atr_fill(tr, period, len(c))


def _atr_fill(tr, period, out):
    """Wilder RMA — asosiy _atr_fill: NaN qatorli natija qaytaradi."""
    out_len = out
    vals = np.full(out_len, np.nan)
    if len(tr) >= period:
        r = np.mean(tr[:period])
        vals[period] = r
        for i in range(period + 1, out_len):
            r = (r * (period - 1) + tr[i - 1]) / period
            vals[i] = r
    return vals


def bollinger(values, period=20, mult=2.0):
    v = np.asarray(values, dtype=float)
    mid = sma(v, period)
    sd = np.full(len(v), np.nan)
    for i in range(period - 1, len(v)):
        sd[i] = np.std(v[i - period + 1:i + 1])
    up = mid + mult * sd
    low = mid - mult * sd
    return up, mid, low


def stochastic(high, low, close, k_period=14, d_period=3):
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    k = np.full(len(c), np.nan)
    for i in range(k_period - 1, len(c)):
        hh = np.max(h[i - k_period + 1:i + 1])
        ll = np.min(l[i - k_period + 1:i + 1])
        if hh == ll:
            k[i] = 50.0
        else:
            k[i] = 100.0 * (c[i] - ll) / (hh - ll)
    d = np.full(len(c), np.nan)
    for i in range(k_period + d_period - 2, len(c)):
        d[i] = np.nanmean(k[i - d_period + 1:i + 1])
    return k, d


def adx(high, low, close, period=14):
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    n = len(c)
    adx_out = np.full(n, np.nan)
    if n <= period * 2:
        return adx_out
    up = np.diff(h)
    down = -np.diff(l)
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    atr_r = np.full(n - 1, np.nan)
    if len(tr) >= period:
        atr_r[period - 1] = np.mean(tr[:period])
        for i in range(period, len(tr)):
            atr_r[i] = (atr_r[i - 1] * (period - 1) + tr[i]) / period
    plus_di = np.full(n - 1, np.nan)
    minus_di = np.full(n - 1, np.nan)
    for i in range(period - 1, len(tr)):
        if atr_r[i]:
            plus_di[i] = 100.0 * np.mean(plus_dm[i - period + 1:i + 1]) / atr_r[i]
            minus_di[i] = 100.0 * np.mean(minus_dm[i - period + 1:i + 1]) / atr_r[i]
    dx = np.full(n - 1, np.nan)
    for i in range(period - 1, len(tr)):
        s = plus_di[i] + minus_di[i]
        if s:
            dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / s
    # ADX = sma of DX
    valid_idx = np.where(~np.isnan(dx))[0]
    valid = dx[valid_idx]
    adx_vals = np.full(n, np.nan)
    if len(valid_idx) >= period:
        avg = sma(valid, period)
        for k in range(period - 1, len(valid_idx)):
            adx_vals[valid_idx[k] + 1] = avg[k]
        return adx_vals
    return adx_out


def obv(close, volume):
    c = np.asarray(close, dtype=float)
    v = np.asarray(volume, dtype=float)
    out = np.zeros(len(c))
    for i in range(1, len(c)):
        if c[i] > c[i - 1]:
            out[i] = out[i - 1] + v[i]
        elif c[i] < c[i - 1]:
            out[i] = out[i - 1] - v[i]
        else:
            out[i] = out[i - 1]
    return out


def vwap(high, low, close, volume):
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    v = np.asarray(volume, dtype=float)
    tp = (h + l + c) / 3.0
    cum_v = np.cumsum(v)
    cum_pv = np.cumsum(tp * v)
    return np.where(cum_v > 0, cum_pv / np.where(cum_v > 0, cum_v, 1.0), np.nan)


def support_resistance(high, low, close, lookback=120):
    """Oddiy swing-based support/resistance."""
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    n = len(close)
    start = max(0, n - lookback)
    pivots_high, pivots_low = [], []
    # lokal ekstremumlar
    for i in range(start + 2, n - 2):
        if h[i] == max(h[i - 2:i + 3]):
            pivots_high.append(h[i])
        if l[i] == min(l[i - 2:i + 3]):
            pivots_low.append(l[i])
    if not pivots_low:
        pivots_low = [np.min(l[start:])]
    if not pivots_high:
        pivots_high = [np.max(h[start:])]
    resistance = float(np.mean(sorted(pivots_high)[-3:])) if len(pivots_high) >= 3 else float(np.max(pivots_high))
    support = float(np.mean(sorted(pivots_low)[:3])) if len(pivots_low) >= 3 else float(np.min(pivots_low))
    return round(support, 2), round(resistance, 2)


def fib_retracement(swing_low, swing_high, levels=(0.236, 0.382, 0.5, 0.618, 0.786)):
    rng = swing_high - swing_low
    return {lvl: swing_high - rng * lvl for lvl in levels}


def last_valid(arr_or_scalar):
    if np.isscalar(arr_or_scalar):
        return float(arr_or_scalar)
    a = np.asarray(arr_or_scalar, dtype=float)
    if a.size == 0:
        return None
    for v in a[::-1]:
        if not np.isnan(v):
            return float(v)
    return None