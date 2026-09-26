"""
Binance WebSocket Client with Resilience, Reconnection, and Synthetic Fallback.
Handles live streams for trades, depth, and multi-timeframe klines.
"""

import asyncio
import json
import logging
import random
import time
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger("binance_bot.ws")


class BinanceWebSocketClient:
    def __init__(
        self,
        symbol: str = "btcusdt",
        ws_base_url: str = "wss://stream.binance.com:9443/ws",
        on_trade: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_depth: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_kline: Optional[Callable[[Dict[str, Any]], None]] = None,
        force_fallback: bool = False,
    ):
        self.symbol = symbol.lower()
        self.ws_base_url = ws_base_url
        self.on_trade = on_trade
        self.on_depth = on_depth
        self.on_kline = on_kline
        self.force_fallback = force_fallback

        self.is_running = False
        self.is_connected = False
        self.is_using_fallback = False
        self.last_ping_time = 0.0
        self.latency_ms = 18.5

        # Latest cached state
        self.latest_price = 68420.0
        self.latest_trade: Optional[Dict[str, Any]] = None
        self.latest_depth: Optional[Dict[str, Any]] = None
        self.latest_klines: Dict[str, Dict[str, Any]] = {
            "1m": {},
            "5m": {},
            "15m": {},
        }

        # Multi-timeframe historical candle storage for indicator calculation
        self.history_candles: Dict[str, List[Dict[str, float]]] = {
            "1m": [],
            "5m": [],
            "15m": [],
        }

        self._task: Optional[asyncio.Task] = None
        self._seed_initial_history()

    def _seed_initial_history(self):
        """Seed realistic initial historical candles for 1m, 5m, and 15m intervals."""
        base_p = 68200.0
        now = time.time()

        for interval, count, sec_step in [("1m", 60, 60), ("5m", 48, 300), ("15m", 40, 900)]:
            candles = []
            curr_p = base_p
            for i in range(count):
                ts = now - (count - i) * sec_step
                change = (random.random() - 0.48) * (curr_p * 0.003)
                o = curr_p
                c = o + change
                h = max(o, c) + random.random() * (curr_p * 0.0015)
                l = min(o, c) - random.random() * (curr_p * 0.0015)
                vol = random.uniform(8.5, 45.0)
                candles.append({
                    "time": ts,
                    "open": round(o, 2),
                    "high": round(h, 2),
                    "low": round(l, 2),
                    "close": round(c, 2),
                    "volume": round(vol, 4),
                })
                curr_p = c
            self.history_candles[interval] = candles
            self.latest_price = curr_p

    def get_stream_url(self) -> str:
        streams = [
            f"{self.symbol}@aggTrade",
            f"{self.symbol}@depth20@100ms",
            f"{self.symbol}@kline_1m",
            f"{self.symbol}@kline_5m",
            f"{self.symbol}@kline_15m",
        ]
        return f"{self.ws_base_url}/{'/'.join(streams)}"

    async def start(self):
        """Starts WebSocket ingestion or fallback loop."""
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stops the ingestion loop cleanly."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self):
        backoff = 1.0
        while self.is_running:
            if self.force_fallback:
                self.is_using_fallback = True
                await self._run_synthetic_generator()
                return

            try:
                import websockets
                url = self.get_stream_url()
                logger.info(f"Connecting to Binance WSS: {url}")
                async with websockets.connect(url, ping_interval=20, ping_timeout=10, close_timeout=5) as ws:
                    self.is_connected = True
                    self.is_using_fallback = False
                    backoff = 1.0
                    logger.info("Connected to Binance WebSocket stream.")

                    while self.is_running:
                        msg_str = await ws.recv()
                        self._handle_raw_message(msg_str)
            except Exception as e:
                self.is_connected = False
                if not self.is_using_fallback:
                    logger.warning(f"Binance WS connection failed ({e}). Switching to high-fidelity synthetic fallback while reconnecting...")
                self.is_using_fallback = True
                await self._run_synthetic_step(duration_seconds=min(backoff * 5, 30))
                backoff = min(backoff * 2.0, 60.0)

    def _handle_raw_message(self, raw_str: str):
        try:
            data = json.loads(raw_str)
            event_type = data.get("e")

            if event_type == "aggTrade":
                self._process_trade(data)
            elif event_type == "depthUpdate" or "bids" in data:
                self._process_depth(data)
            elif event_type == "kline":
                self._process_kline(data)
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _process_trade(self, data: Dict[str, Any]):
        p = float(data.get("p", self.latest_price))
        q = float(data.get("q", 0.1))
        is_buyer_maker = bool(data.get("m", False))
        self.latest_price = p

        trade = {
            "type": "trade",
            "time": data.get("T", int(time.time() * 1000)),
            "price": p,
            "quantity": q,
            "side": "SELL" if is_buyer_maker else "BUY",
            "isMaker": is_buyer_maker,
            "source": "live" if not self.is_using_fallback else "synthetic",
        }
        self.latest_trade = trade
        if self.on_trade:
            self.on_trade(trade)

    def _process_depth(self, data: Dict[str, Any]):
        raw_bids = data.get("bids", data.get("b", []))
        raw_asks = data.get("asks", data.get("a", []))

        bids = [[float(p), float(q)] for p, q in raw_bids[:20]]
        asks = [[float(p), float(q)] for p, q in raw_asks[:20]]

        depth = {
            "type": "depth",
            "time": data.get("E", int(time.time() * 1000)),
            "bids": bids,
            "asks": asks,
            "source": "live" if not self.is_using_fallback else "synthetic",
        }
        self.latest_depth = depth
        if self.on_depth:
            self.on_depth(depth)

    def _process_kline(self, data: Dict[str, Any]):
        k = data.get("k", {})
        interval = k.get("i", "1m")
        if interval in self.latest_klines:
            candle = {
                "time": k.get("t", int(time.time() * 1000)),
                "open": float(k.get("o", self.latest_price)),
                "high": float(k.get("h", self.latest_price)),
                "low": float(k.get("l", self.latest_price)),
                "close": float(k.get("c", self.latest_price)),
                "volume": float(k.get("v", 0.0)),
                "isClosed": bool(k.get("x", False)),
            }
            self.latest_klines[interval] = candle

            if candle["isClosed"]:
                self.history_candles[interval].append({
                    "time": candle["time"] / 1000.0,
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": candle["volume"],
                })
                if len(self.history_candles[interval]) > 100:
                    self.history_candles[interval].pop(0)

            if self.on_kline:
                self.on_kline({"interval": interval, "candle": candle})

    async def _run_synthetic_generator(self):
        """Continuous synthetic realistic market data loop when in full offline fallback mode."""
        while self.is_running:
            await self._run_synthetic_step(duration_seconds=1.0)

    async def _run_synthetic_step(self, duration_seconds: float):
        """Generates realistic orderbook depth, trade ticks, and updates klines for a given interval."""
        steps = max(1, int(duration_seconds / 0.2))
        for _ in range(steps):
            # Check if active
            if not self.is_running and not self.force_fallback:
                break

            # 1. Price random walk with slight momentum
            delta = (random.random() - 0.49) * (self.latest_price * 0.0004)
            self.latest_price = round(max(1000.0, self.latest_price + delta), 2)

            # 2. Synthetic Trade
            side = "BUY" if delta >= 0 else "SELL"
            qty = round(random.uniform(0.01, 3.5) if random.random() > 0.15 else random.uniform(5.0, 28.0), 4)
            trade = {
                "type": "trade",
                "time": int(time.time() * 1000),
                "price": self.latest_price,
                "quantity": qty,
                "side": side,
                "isMaker": random.random() > 0.5,
                "source": "synthetic",
            }
            self.latest_trade = trade
            if self.on_trade:
                self.on_trade(trade)

            # 3. Synthetic Orderbook with Liquidity Walls
            bids = []
            asks = []
            spread = 0.5
            p = self.latest_price

            for i in range(1, 21):
                bp = round(p - (i * spread) - (random.random() * 0.3), 2)
                bq = round(random.uniform(0.5, 4.0) if i not in (5, 12) else random.uniform(45.0, 110.0), 3)
                bids.append([bp, bq])

                ap = round(p + (i * spread) + (random.random() * 0.3), 2)
                aq = round(random.uniform(0.5, 4.0) if i not in (6, 14) else random.uniform(40.0, 105.0), 3)
                asks.append([ap, aq])

            depth = {
                "type": "depth",
                "time": int(time.time() * 1000),
                "bids": bids,
                "asks": asks,
                "source": "synthetic",
            }
            self.latest_depth = depth
            if self.on_depth:
                self.on_depth(depth)

            # 4. Update candle bars
            for interval in ["1m", "5m", "15m"]:
                if self.history_candles[interval]:
                    last = self.history_candles[interval][-1]
                    last["high"] = max(last["high"], self.latest_price)
                    last["low"] = min(last["low"], self.latest_price)
                    last["close"] = self.latest_price
                    last["volume"] += qty * 0.1

            await asyncio.sleep(0.2)
