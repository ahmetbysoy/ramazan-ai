"""
Unit tests for Orderbook Wall Detection and Trade Setup Calculator.
"""

from src.orderbook_walls import OrderbookWallDetector


def test_orderbook_walls_analysis():
    detector = OrderbookWallDetector(wall_threshold_btc=10.0)

    # 20 bids, with a massive wall at price 64000
    bids = [[65000 - i * 10, 1.0] for i in range(20)]
    bids[5] = [64950.0, 55.0]  # Huge wall

    # 20 asks, with a massive wall at price 65200
    asks = [[65010 + i * 10, 1.0] for i in range(20)]
    asks[6] = [65070.0, 48.0]  # Huge wall

    res = detector.analyze_orderbook(bids, asks, mark_price=65005.0, bias_direction="BULLISH")

    assert "bidWalls" in res
    assert len(res["bidWalls"]) > 0
    assert res["bidWalls"][0]["price"] == 64950.0

    assert "askWalls" in res
    assert len(res["askWalls"]) > 0
    assert res["askWalls"][0]["price"] == 65070.0

    setup = res["tradeSetup"]
    assert setup["direction"] == "LONG"
    assert setup["entry"] == 65000.0
    # TP1 should target the first ask wall
    assert setup["tp1"] == 65070.0
    # SL should be protected below the bid wall
    assert setup["sl"] < 64950.0


def test_orderbook_fallback_empty():
    detector = OrderbookWallDetector()
    res = detector.analyze_orderbook([], [], mark_price=60000.0, bias_direction="SHORT")
    assert res["tradeSetup"]["direction"] == "SHORT"
    assert res["tradeSetup"]["sl"] > res["tradeSetup"]["entry"]
    assert res["tradeSetup"]["tp1"] < res["tradeSetup"]["entry"]
