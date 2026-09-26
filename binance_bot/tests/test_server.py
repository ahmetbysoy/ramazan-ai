"""
Integration tests for FastAPI Server and REST Analytics Endpoints.
"""

from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)


def test_api_status_endpoint():
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()

    assert data["symbol"] == "BTCUSDT"
    assert "markPrice" in data
    assert "predictions" in data
    assert "1m" in data["predictions"]["timeframes"]
    assert "5m" in data["predictions"]["timeframes"]
    assert "15m" in data["predictions"]["timeframes"]

    # Check reasons
    assert len(data["predictions"]["timeframes"]["1m"]["reasons"]) > 0

    # Check setup (Entry, TP1, TP2, SL)
    setup = data["orderbook"]["tradeSetup"]
    assert "entry" in setup
    assert "tp1" in setup
    assert "tp2" in setup
    assert "sl" in setup
    assert "riskRewardRatio" in setup

    # Check MEV metrics
    mev = data["mevAnalytics"]
    assert "frontrunRiskScore" in mev
    assert "slippageMatrix" in mev
    assert "sandwichSimulation" in mev


def test_dashboard_html_served():
    res = client.get("/")
    assert res.status_code == 200
    assert "BINANCE WSS" in res.text
    assert "SANDWICH" in res.text
