"""
Multi-Timeframe Analytical Predictor (1m, 5m, 15m).
Synthesizes EMAs, RSI, MACD, and Volume Delta to provide concrete trade signals and rationales.
"""

from typing import Dict, List, Any
from src.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
)


class MultiTimeframePredictor:
    def __init__(self):
        pass

    def analyze_timeframe(
        self,
        interval: str,
        candles: List[Dict[str, float]],
        volume_delta: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Analyzes a single timeframe (1m, 5m, or 15m) and produces a deterministic prediction.
        """
        if not candles or len(candles) < 15:
            return {
                "interval": interval,
                "direction": "NEUTRAL",
                "confidence": 50,
                "score": 0,
                "rsi": 50.0,
                "macd": 0.0,
                "reasons": [f"{interval}: Insufficient historical bars for statistical significance."],
            }

        closes = [c["close"] for c in candles]
        curr_price = closes[-1]

        # 1. Indicator Calculations
        ema9 = calculate_ema(closes, 9)[-1]
        ema21 = calculate_ema(closes, 21)[-1] if len(closes) >= 21 else ema9
        rsi = calculate_rsi(closes, 14)
        macd = calculate_macd(closes)
        bb = calculate_bollinger_bands(closes, 20)

        # 2. Score Evaluation (-100 to +100)
        bull_points = 0
        bear_points = 0
        reasons = []

        # EMA Trend
        if curr_price > ema9 > ema21:
            bull_points += 30
            reasons.append(f"Price (${curr_price:,.1f}) riding above aligned EMA-9 (${ema9:,.1f}) and EMA-21 (${ema21:,.1f})")
        elif curr_price < ema9 < ema21:
            bear_points += 30
            reasons.append(f"Price (${curr_price:,.1f}) rejected below declining EMA-9 (${ema9:,.1f}) and EMA-21 (${ema21:,.1f})")
        else:
            reasons.append("EMA-9 and EMA-21 converging in consolidation range")

        # RSI Momentum
        if rsi > 58:
            if rsi > 75:
                bear_points += 15
                reasons.append(f"RSI overextended at {rsi:.1f} (Overbought exhaustion risk)")
            else:
                bull_points += 25
                reasons.append(f"Bullish momentum expansion with healthy RSI at {rsi:.1f}")
        elif rsi < 42:
            if rsi < 25:
                bull_points += 15
                reasons.append(f"RSI oversold at {rsi:.1f} (Mean reversion bounce potential)")
            else:
                bear_points += 25
                reasons.append(f"Bearish momentum acceleration with depressed RSI at {rsi:.1f}")
        else:
            reasons.append(f"RSI neutral at {rsi:.1f} within equilibrium band (42-58)")

        # MACD Histogram
        if macd["histogram"] > 0:
            bull_points += 20
            reasons.append(f"MACD histogram positive (+{macd['histogram']:.2f}) signaling bullish momentum dominance")
        elif macd["histogram"] < 0:
            bear_points += 20
            reasons.append(f"MACD histogram negative ({macd['histogram']:.2f}) confirming ongoing selling pressure")
        else:
            reasons.append("MACD histogram neutral")

        # Volume Flow Delta
        if volume_delta > 5.0:
            bull_points += 25
            reasons.append(f"Aggressive taker buy volume surge (+{volume_delta:.1f} BTC net delta)")
        elif volume_delta < -5.0:
            bear_points += 25
            reasons.append(f"Aggressive taker sell volume cascade ({volume_delta:.1f} BTC net delta)")

        net_score = bull_points - bear_points
        if net_score >= 25:
            direction = "BULLISH"
            confidence = min(95, 60 + int(net_score * 0.35))
        elif net_score <= -25:
            direction = "BEARISH"
            confidence = min(95, 60 + int(abs(net_score) * 0.35))
        else:
            direction = "NEUTRAL"
            confidence = 50 + int(abs(net_score) * 0.2)

        return {
            "interval": interval,
            "direction": direction,
            "confidence": confidence,
            "score": net_score,
            "rsi": rsi,
            "macd": macd["histogram"],
            "ema9": ema9,
            "ema21": ema21,
            "reasons": reasons,
        }

    def analyze_all(
        self,
        history_candles: Dict[str, List[Dict[str, float]]],
        volume_delta: float = 0.0,
    ) -> Dict[str, Any]:
        """Analyzes 1m, 5m, and 15m simultaneously and computes combined consensus."""
        results = {}
        for interval in ["1m", "5m", "15m"]:
            candles = history_candles.get(interval, [])
            results[interval] = self.analyze_timeframe(interval, candles, volume_delta)

        # Consensus weighting: 1m (20%), 5m (35%), 15m (45%)
        w_score = (
            results["1m"]["score"] * 0.20
            + results["5m"]["score"] * 0.35
            + results["15m"]["score"] * 0.45
        )

        if w_score >= 30:
            consensus = "STRONG_BULLISH" if w_score >= 55 else "BULLISH"
        elif w_score <= -30:
            consensus = "STRONG_BEARISH" if w_score <= -55 else "BEARISH"
        else:
            consensus = "NEUTRAL"

        return {
            "consensus": consensus,
            "weightedScore": round(w_score, 1),
            "timeframes": results,
        }
