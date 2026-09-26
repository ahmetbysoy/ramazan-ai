"""
Orderbook Liquidity Wall Detection & Dynamic Trade Setup Calculator.
Identifies support/resistance clusters from live depth and computes Entry, TP1, TP2, and SL levels.
"""

from typing import Dict, List, Any, Optional, Tuple


class OrderbookWallDetector:
    def __init__(self, wall_threshold_btc: float = 15.0):
        self.wall_threshold_btc = wall_threshold_btc

    def analyze_orderbook(
        self,
        bids: List[List[float]],
        asks: List[List[float]],
        mark_price: float,
        bias_direction: str = "BULLISH",
    ) -> Dict[str, Any]:
        """
        Detects heavy orderbook walls and computes dynamic Entry, TP1, TP2, and SL levels.
        """
        if not bids or not asks:
            return self._fallback_levels(mark_price, bias_direction)

        # 1. Total Cumulative Depth Calculation
        total_bid_vol = sum(q for _, q in bids[:20])
        total_ask_vol = sum(q for _, q in asks[:20])
        total_vol = total_bid_vol + total_ask_vol
        bid_dominance = round((total_bid_vol / total_vol) * 100.0, 1) if total_vol > 0 else 50.0

        # 2. Wall Detection (Clusters exceeding threshold or top percentiles)
        avg_bid_vol = total_bid_vol / len(bids[:20]) if bids else 1.0
        avg_ask_vol = total_ask_vol / len(asks[:20]) if asks else 1.0

        bid_walls = []
        for p, q in bids[:20]:
            if q >= max(self.wall_threshold_btc, avg_bid_vol * 1.8):
                bid_walls.append({
                    "price": round(p, 2),
                    "volume": round(q, 3),
                    "strength": "HIGH" if q > avg_bid_vol * 3 else "MEDIUM",
                    "distancePct": round(abs(mark_price - p) / mark_price * 100.0, 2),
                })

        ask_walls = []
        for p, q in asks[:20]:
            if q >= max(self.wall_threshold_btc, avg_ask_vol * 1.8):
                ask_walls.append({
                    "price": round(p, 2),
                    "volume": round(q, 3),
                    "strength": "HIGH" if q > avg_ask_vol * 3 else "MEDIUM",
                    "distancePct": round(abs(p - mark_price) / mark_price * 100.0, 2),
                })

        # Sort walls: bid walls descending, ask walls ascending
        bid_walls.sort(key=lambda x: x["price"], reverse=True)
        ask_walls.sort(key=lambda x: x["price"])

        # 3. Dynamic Trade Setup Calculation (Entry, TP1, TP2, SL)
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        spread = round(best_ask - best_bid, 2)

        is_bullish = "BULL" in bias_direction.upper()

        if is_bullish:
            # Bullish Setup
            # Optimal Entry: current mark price or slight dip to top bid
            entry = round(best_bid, 2)

            # Support for SL: just below the primary bid wall (or 0.35% below if no wall found)
            if bid_walls:
                primary_support = bid_walls[0]["price"]
                sl = round(primary_support - max(15.0, primary_support * 0.0015), 2)
            else:
                sl = round(entry * 0.995, 2)

            # Take Profits: targeting ask walls
            if len(ask_walls) >= 2:
                tp1 = ask_walls[0]["price"]
                tp2 = ask_walls[1]["price"]
            elif len(ask_walls) == 1:
                tp1 = ask_walls[0]["price"]
                tp2 = round(tp1 + (tp1 - entry) * 0.7, 2)
            else:
                tp1 = round(entry * 1.006, 2)
                tp2 = round(entry * 1.012, 2)

        else:
            # Bearish / Short Setup
            entry = round(best_ask, 2)

            # Resistance for SL: just above primary ask wall
            if ask_walls:
                primary_res = ask_walls[0]["price"]
                sl = round(primary_res + max(15.0, primary_res * 0.0015), 2)
            else:
                sl = round(entry * 1.005, 2)

            # Take Profits: targeting bid walls downwards
            if len(bid_walls) >= 2:
                tp1 = bid_walls[0]["price"]
                tp2 = bid_walls[1]["price"]
            elif len(bid_walls) == 1:
                tp1 = bid_walls[0]["price"]
                tp2 = round(tp1 - (entry - tp1) * 0.7, 2)
            else:
                tp1 = round(entry * 0.994, 2)
                tp2 = round(entry * 0.988, 2)

        # Risk / Reward
        risk = abs(entry - sl)
        reward = abs(tp1 - entry)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 1.5

        return {
            "markPrice": round(mark_price, 2),
            "spread": spread,
            "bidDominance": bid_dominance,
            "totalBidVolume": round(total_bid_vol, 2),
            "totalAskVolume": round(total_ask_vol, 2),
            "bidWalls": bid_walls[:5],
            "askWalls": ask_walls[:5],
            "tradeSetup": {
                "direction": "LONG" if is_bullish else "SHORT",
                "entry": entry,
                "tp1": tp1,
                "tp2": tp2,
                "sl": sl,
                "riskRewardRatio": f"1:{rr_ratio}",
                "expectedPnlPct": round(abs(tp1 - entry) / entry * 100.0, 2),
                "invalidationReason": f"Stop loss placed below primary support wall (${sl:,.2f})" if is_bullish else f"Stop loss placed above primary resistance wall (${sl:,.2f})",
            }
        }

    def _fallback_levels(self, mark_price: float, bias_direction: str) -> Dict[str, Any]:
        is_bullish = "BULL" in bias_direction.upper()
        entry = round(mark_price, 2)
        tp1 = round(entry * 1.007, 2) if is_bullish else round(entry * 0.993, 2)
        tp2 = round(entry * 1.014, 2) if is_bullish else round(entry * 0.986, 2)
        sl = round(entry * 0.995, 2) if is_bullish else round(entry * 1.005, 2)

        return {
            "markPrice": entry,
            "spread": 0.5,
            "bidDominance": 50.0,
            "totalBidVolume": 50.0,
            "totalAskVolume": 50.0,
            "bidWalls": [],
            "askWalls": [],
            "tradeSetup": {
                "direction": "LONG" if is_bullish else "SHORT",
                "entry": entry,
                "tp1": tp1,
                "tp2": tp2,
                "sl": sl,
                "riskRewardRatio": "1:2.0",
                "expectedPnlPct": 0.7,
                "invalidationReason": "Default volatility boundary placement",
            }
        }
