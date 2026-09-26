"""
Tests for Binance WebSocket Client and Synthetic Fallback Generator.
"""

import pytest
import asyncio
from src.websocket_client import BinanceWebSocketClient


@pytest.mark.asyncio
async def test_websocket_client_initialization():
    client = BinanceWebSocketClient(symbol="btcusdt", force_fallback=True)
    assert client.symbol == "btcusdt"
    assert "btcusdt@aggTrade" in client.get_stream_url()
    assert len(client.history_candles["1m"]) > 0
    assert len(client.history_candles["5m"]) > 0
    assert len(client.history_candles["15m"]) > 0


@pytest.mark.asyncio
async def test_synthetic_fallback_generator():
    trades = []
    depths = []

    client = BinanceWebSocketClient(
        symbol="btcusdt",
        on_trade=lambda t: trades.append(t),
        on_depth=lambda d: depths.append(d),
        force_fallback=True,
    )

    await client._run_synthetic_step(duration_seconds=0.5)

    assert len(trades) > 0
    assert "price" in trades[0]
    assert trades[0]["side"] in ["BUY", "SELL"]

    assert len(depths) > 0
    assert len(depths[0]["bids"]) == 20
    assert len(depths[0]["asks"]) == 20
    # Bids should be strictly descending
    assert depths[0]["bids"][0][0] > depths[0]["bids"][1][0]
    # Asks should be strictly ascending
    assert depths[0]["asks"][0][0] < depths[0]["asks"][1][0]


def test_message_parser():
    trades = []
    client = BinanceWebSocketClient(on_trade=lambda t: trades.append(t))

    mock_trade_msg = '{"e": "aggTrade", "E": 1672531199000, "s": "BTCUSDT", "p": "68500.50", "q": "1.25", "m": false}'
    client._handle_raw_message(mock_trade_msg)

    assert len(trades) == 1
    assert trades[0]["price"] == 68500.50
    assert trades[0]["quantity"] == 1.25
    assert trades[0]["side"] == "BUY"
