# Binance Real-Time WebSocket Analytics & MEV Frontrunning Bot

## 1. Project Goal
Develop an autonomous, production-ready real-time crypto analytics bot and interactive mobile dashboard powered by live Binance WebSocket streams (`stream.binance.com`).

## 2. Core Functional Requirements

### 2.1 Binance WebSocket Data Collector
- Connect to Binance Public WebSocket Streams (`wss://stream.binance.com:9443/ws` or `wss://stream.binance.com:443/ws`):
  - Live trades: `btcusdt@aggTrade`
  - Live Orderbook depth: `btcusdt@depth20@100ms` or depth stream
  - Klines/Candlesticks: `btcusdt@kline_1m`, `btcusdt@kline_5m`, `btcusdt@kline_15m`
- Robust reconnect with exponential backoff and synthetic realistic fallback generator when network/firewall blocks direct Binance connection.

### 2.2 Multi-Timeframe Analytical Predictor (1m, 5m, 15m)
- Compute technical indicators across 1m, 5m, and 15m:
  - Exponential Moving Averages (EMA 9, 21, 50)
  - Relative Strength Index (RSI 14)
  - MACD (12, 26, 9) and Signal Histogram
  - Volume Delta & Buy/Sell volume imbalance
- Generate clear directional predictions (BULLISH, BEARISH, NEUTRAL) with confidence scores (0-100%).
- Provide concrete, human-readable analytical reasons for each timeframe (e.g. "1m: Bullish EMA cross with +2.4x volume surge; 5m: MACD bullish momentum; 15m: Resistance rejection").

### 2.3 Orderbook Wall Detection & Dynamic Trade Setup
- Parse bids and asks from live depth stream.
- Identify liquidity clusters (support walls on bids, resistance walls on asks).
- Dynamically calculate:
  - Current live mark price
  - Optimal Entry price (considering wall proximity and pullback levels)
  - Take Profit 1 (TP1): First heavy resistance wall / liquidity pocket
  - Take Profit 2 (TP2): Secondary supply wall / breakout extension
  - Stop Loss (SL): Protected placement just below key support wall
  - Risk/Reward Ratio (e.g. 1:2.8)

### 2.4 Sandwich Attack & Frontrunning (MEV) Analytics Engine
- Real-time simulation and analysis of orderbook depth slippage.
- Estimate price impact for block trades ($10,000, $50,000, $100,000, $500,000).
- Frontrunning Risk Index (0-100%): evaluates mempool/taker order pressure against orderbook depth elasticity.
- Sandwich Vulnerability Analyzer: Detects when a large market swap can be sandwiched (Attacker Frontrun Buy -> Victim Swap -> Attacker Backrun Sell).
- Compute estimated extractor profit and victim slippage loss.

### 2.5 Real-Time Interactive Mobile-First Dashboard UI
- Dark-mode pro cyberpunk/fintech trading terminal design.
- Full mobile responsiveness with responsive viewport, touch gestures, and clean tabs.
- Live updating metrics:
  - Ticker banner with live BTC/USDT price, 24h change, ping latency.
  - Active Trade Signal Card: Direction badge, Entry, TP1, TP2, SL, Risk/Reward.
  - Multi-Timeframe Forecast Grid: 1m, 5m, 15m forecast cards with reasons.
  - Orderbook Walls Visualizer: Interactive visual chart highlighting major bid/ask walls.
  - MEV & Sandwich Attack Radar: Real-time risk gauge, slippage impact table, visual transaction flow diagram.
  - Live trades ticker stream.
- Zero external CDN dependencies for offline/isolated resilience.

### 2.6 Automated Test Suite
- Comprehensive unit tests covering WebSocket feeds, indicators, orderbook wall calculation, entry/TP/SL logic, and MEV sandwich calculations.
