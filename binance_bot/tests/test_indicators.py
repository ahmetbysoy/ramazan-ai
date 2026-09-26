"""
Unit tests for Technical Indicators Calculation Engine.
"""

from src.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_volume_delta,
)


def test_calculate_ema():
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
    ema = calculate_ema(prices, 3)
    assert len(ema) > 0
    assert ema[-1] > ema[0]


def test_calculate_rsi():
    # Uptrend prices -> RSI should be high (> 50)
    uptrend = [10.0 + i * 0.5 for i in range(25)]
    rsi_up = calculate_rsi(uptrend, 14)
    assert rsi_up > 50.0

    # Downtrend prices -> RSI should be low (< 50)
    downtrend = [50.0 - i * 0.5 for i in range(25)]
    rsi_down = calculate_rsi(downtrend, 14)
    assert rsi_down < 50.0


def test_calculate_macd():
    prices = [100.0 + (i % 5) for i in range(40)]
    macd_res = calculate_macd(prices)
    assert "macd" in macd_res
    assert "signal" in macd_res
    assert "histogram" in macd_res


def test_calculate_bollinger_bands():
    prices = [100.0] * 20
    bb = calculate_bollinger_bands(prices, 20, 2.0)
    assert bb["middle"] == 100.0
    assert bb["upper"] == 100.0
    assert bb["lower"] == 100.0


def test_calculate_volume_delta():
    trades = [
        {"side": "BUY", "quantity": 1.5},
        {"side": "BUY", "quantity": 2.0},
        {"side": "SELL", "quantity": 0.5},
    ]
    vd = calculate_volume_delta(trades)
    assert vd["buyVolume"] == 3.5
    assert vd["sellVolume"] == 0.5
    assert vd["netDelta"] == 3.0
    assert vd["buyRatio"] > 80.0
