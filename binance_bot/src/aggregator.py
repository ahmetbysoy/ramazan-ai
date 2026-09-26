"""
Real-Time Market Data Aggregator.
Combines Binance WSS data, indicators, multi-timeframe predictions, depth walls, and MEV metrics.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional

from src.websocket_client import BinanceWebSocketClient
from src.predictor import MultiTimeframePredictor
from src.orderbook_walls import OrderbookWallDetector
from src.mev_sandwich import MevSandwichAnalyzer
from src.indicators import calculate_volume_delta


class MarketDataAggregator:
    def __init__(self, symbol: str = "btcusdt"):
        self.symbol = symbol.lower()
        self.ws_client = BinanceWebSocketClient(
            symbol=self.symbol,
            on_trade=self._on_trade,
            on_depth=self._on_depth,
            on_kline=self._on_kline,
        )
        self.predictor = MultiTimeframePredictor()
        self.wall_detector = OrderbookWallDetector()
        self.mev_analyzer = MevSandwichAnalyzer()

        # Buffer for recent trades
        self.recent_trades: List[Dict[str, Any]] = []

        # Latest computed analytics payload
        self.latest_payload: Dict[str, Any] = {}

    def _on_trade(self, trade: Dict[str, Any]):
        self.recent_trades.append(trade)
        if len(self.recent_trades) > 50:
            self.recent_trades.pop(0)

    def _on_depth(self, depth: Dict[str, Any]):
        pass

    def _on_kline(self, kline_event: Dict[str, Any]):
        pass

    async def start(self):
        await self.ws_client.start()

    async def stop(self):
        await self.ws_client.stop()

    def compute_full_snapshot(self) -> Dict[str, Any]:
        """Calculates and returns the complete real-time market and MEV analytics state."""
        mark_price = self.ws_client.latest_price
        depth = self.ws_client.latest_depth or {"bids": [], "asks": []}
        bids = depth.get("bids", [])
        asks = depth.get("asks", [])

        # 1. Volume Delta
        vol_metrics = calculate_volume_delta(self.recent_trades)

        # 2. Multi-Timeframe Prediction (1m, 5m, 15m)
        pred_res = self.predictor.analyze_all(
            self.ws_client.history_candles,
            volume_delta=vol_metrics["netDelta"],
        )

        # 3. Orderbook Walls & Dynamic Trade Setup (Entry, TP1, TP2, SL)
        consensus_direction = pred_res["consensus"]
        trade_setup = self.wall_detector.analyze_orderbook(
            bids=bids,
            asks=asks,
            mark_price=mark_price,
            bias_direction=consensus_direction,
        )

        # 4. MEV Sandwich & Frontrunning Analytics
        mev_res = self.mev_analyzer.analyze_mev_risk(
            bids=bids,
            asks=asks,
            recent_trades=self.recent_trades,
            mark_price=mark_price,
        )

        self.latest_payload = {
            "symbol": self.symbol.upper(),
            "timestamp": int(time.time() * 1000),
            "markPrice": mark_price,
            "isLiveWs": self.ws_client.is_connected,
            "isUsingFallback": self.ws_client.is_using_fallback,
            "latencyMs": self.ws_client.latency_ms,
            "volumeDelta": vol_metrics,
            "predictions": pred_res,
            "orderbook": trade_setup,
            "mevAnalytics": mev_res,
            "recentTrades": self.recent_trades[-15:],
        }
        return self.latest_payload
