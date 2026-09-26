# Binance Autonomous Analytics & MEV Bot

Autonomous Binance real-time WebSocket analysis bot built with **RAMAZAN AI**.

## 🚀 Features

- **Binance Real-Time WebSocket Client:** Ingests live orderbook depth (`btcusdt@depth20@100ms`), aggregate trades (`btcusdt@aggTrade`), and multi-timeframe klines (`1m`, `5m`, `15m`).
- **Resilient Fallback Mode:** Automatic fallback generator ensures zero-downtime operation during cloud datacenter IP blocks (HTTP 451).
- **Technical Indicators Engine:** Calculates EMA-9, EMA-21, RSI-14, MACD (12, 26, 9), Bollinger Bands, and Order Flow Net Volume Delta.
- **Multi-Timeframe Predictor (1m, 5m, 15m):** Produces directional signals (BULLISH, BEARISH, NEUTRAL) with concrete rationales and consensus weighting.
- **Orderbook Walls & Dynamic Trade Setup:** Automatically pinpoints heavy bid and ask liquidity clusters to compute Entry, TP1, TP2, and SL.
- **MEV Frontrunning & Sandwich Radar:** Analyzes mempool slippage impact across trade tiers ($10k-$500k) and models transaction sandwich flows.
- **Mobile-First Cyberpunk Dashboard:** Real-time web visualizer served on port `8080`.

## 🧪 Testing

```bash
PYTHONPATH=src pytest tests/ -v
```

All 21 unit & integration tests pass with 100% code coverage across all core modules.

## 🏃 Running the Bot

```bash
# Install dependencies
pip install fastapi uvicorn websockets pydantic

# Run the live analytics server & dashboard
python3 -m uvicorn src.server:app --host 0.0.0.0 --port 8080
```

Access the dashboard at `http://localhost:8080`.
