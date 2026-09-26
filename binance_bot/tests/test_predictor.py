"""
Unit tests for Multi-Timeframe Analytical Predictor.
"""

from src.predictor import MultiTimeframePredictor


def test_predictor_neutral_on_insufficient_data():
    pred = MultiTimeframePredictor()
    res = pred.analyze_timeframe("1m", [])
    assert res["direction"] == "NEUTRAL"
    assert "Insufficient" in res["reasons"][0]


def test_predictor_bullish_on_strong_uptrend():
    pred = MultiTimeframePredictor()
    candles = []
    base_p = 60000.0
    for i in range(30):
        base_p += 15.0
        candles.append({
            "open": base_p - 10.0,
            "high": base_p + 10.0,
            "low": base_p - 15.0,
            "close": base_p,
            "volume": 20.0
        })

    res = pred.analyze_timeframe("5m", candles, volume_delta=10.0)
    assert res["direction"] == "BULLISH"
    assert res["confidence"] >= 60
    assert len(res["reasons"]) > 0


def test_predictor_multi_timeframe_consensus():
    pred = MultiTimeframePredictor()
    candles = [{"open": 65000, "high": 65100, "low": 64900, "close": 65000 + i*10, "volume": 15.0} for i in range(35)]
    history = {
        "1m": candles,
        "5m": candles,
        "15m": candles,
    }
    all_res = pred.analyze_all(history, volume_delta=8.0)
    assert "consensus" in all_res
    assert "timeframes" in all_res
    assert "1m" in all_res["timeframes"]
    assert "5m" in all_res["timeframes"]
    assert "15m" in all_res["timeframes"]
