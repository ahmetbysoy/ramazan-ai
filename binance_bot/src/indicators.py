"""
Technical Indicators Calculation Engine for Multi-Timeframe Crypto Analysis.
Computes EMA, RSI, MACD, Bollinger Bands, and Order Flow Volume Delta.
"""

from typing import List, Dict, Any, Tuple, Optional
import math


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculates Exponential Moving Average (EMA) for a price series."""
    if not prices or len(prices) < period or period <= 0:
        return [prices[-1]] if prices else []

    k = 2.0 / (period + 1)
    # Start with SMA of the first `period` prices
    ema = [sum(prices[:period]) / period]
    for p in prices[period:]:
        new_val = (p * k) + (ema[-1] * (1.0 - k))
        ema.append(round(new_val, 2))
    return ema


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """Calculates Relative Strength Index (RSI) for a price series."""
    if len(prices) < period + 1:
        return 50.0

    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 2)


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Dict[str, float]:
    """Calculates MACD line, Signal line, and Histogram."""
    if len(prices) < slow_period + signal_period:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)

    # Align lengths
    offset = len(ema_fast) - len(ema_slow)
    aligned_fast = ema_fast[offset:]

    macd_line = [f - s for f, s in zip(aligned_fast, ema_slow)]
    signal_line = calculate_ema(macd_line, signal_period)

    last_macd = macd_line[-1]
    last_signal = signal_line[-1]
    hist = last_macd - last_signal

    return {
        "macd": round(last_macd, 2),
        "signal": round(last_signal, 2),
        "histogram": round(hist, 2),
    }


def calculate_bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2.0) -> Dict[str, float]:
    """Calculates upper, middle, and lower Bollinger Bands."""
    if len(prices) < period:
        p = prices[-1] if prices else 0.0
        return {"upper": p, "middle": p, "lower": p}

    subset = prices[-period:]
    mean = sum(subset) / period
    variance = sum((x - mean) ** 2 for x in subset) / period
    std_dev = math.sqrt(variance)

    return {
        "upper": round(mean + (num_std * std_dev), 2),
        "middle": round(mean, 2),
        "lower": round(mean - (num_std * std_dev), 2),
    }


def calculate_volume_delta(trades: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculates buy volume, sell volume, and net volume delta from trade stream."""
    buy_vol = 0.0
    sell_vol = 0.0

    for t in trades:
        side = t.get("side", "BUY")
        q = float(t.get("quantity", 0.0))
        if side == "BUY":
            buy_vol += q
        else:
            sell_vol += q

    delta = buy_vol - sell_vol
    ratio = (buy_vol / (buy_vol + sell_vol)) * 100.0 if (buy_vol + sell_vol) > 0 else 50.0

    return {
        "buyVolume": round(buy_vol, 4),
        "sellVolume": round(sell_vol, 4),
        "netDelta": round(delta, 4),
        "buyRatio": round(ratio, 1),
    }
