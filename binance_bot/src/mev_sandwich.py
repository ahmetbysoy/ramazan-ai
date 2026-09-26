"""
MEV Frontrunning & Sandwich Attack Analytics Engine.
Calculates slippage impact, frontrun vulnerability index, and models transaction sandwich flows.
"""

from typing import List, Dict, Any, Optional


class MevSandwichAnalyzer:
    def __init__(self, gas_cost_usd: float = 3.50):
        self.gas_cost_usd = gas_cost_usd

    def calculate_slippage(self, orderbook_levels: List[List[float]], notional_usd: float) -> Dict[str, float]:
        """
        Simulates filling a market order of size `notional_usd` against orderbook levels.
        Calculates average execution price, worst fill price, and percentage slippage.
        """
        if not orderbook_levels:
            return {"avgPrice": 0.0, "worstPrice": 0.0, "slippagePct": 0.0, "filledUsd": 0.0}

        best_price = orderbook_levels[0][0]
        remaining_usd = notional_usd
        total_btc_bought = 0.0
        worst_price = best_price

        for price, qty in orderbook_levels:
            level_usd = price * qty
            if remaining_usd <= level_usd:
                qty_taken = remaining_usd / price
                total_btc_bought += qty_taken
                worst_price = price
                remaining_usd = 0.0
                break
            else:
                total_btc_bought += qty
                worst_price = price
                remaining_usd -= level_usd

        if total_btc_bought == 0:
            return {"avgPrice": best_price, "worstPrice": best_price, "slippagePct": 0.0, "filledUsd": 0.0}

        avg_price = (notional_usd - remaining_usd) / total_btc_bought
        slippage_pct = round(abs(avg_price - best_price) / best_price * 100.0, 3)

        return {
            "avgPrice": round(avg_price, 2),
            "worstPrice": round(worst_price, 2),
            "slippagePct": slippage_pct,
            "filledUsd": round(notional_usd - remaining_usd, 2),
        }

    def analyze_mev_risk(
        self,
        bids: List[List[float]],
        asks: List[List[float]],
        recent_trades: List[Dict[str, Any]],
        mark_price: float,
    ) -> Dict[str, Any]:
        """
        Calculates frontrunning risk score, slippage impact matrix, and simulates sandwich attack viability.
        """
        # 1. Slippage impact matrix for typical retail / whale trade sizes
        sizes = [10_000, 50_000, 100_000, 500_000]
        slippage_table = []
        for s in sizes:
            slip_buy = self.calculate_slippage(asks, s)
            slip_sell = self.calculate_slippage(bids, s)
            slippage_table.append({
                "sizeUsd": s,
                "buySlippagePct": slip_buy["slippagePct"],
                "sellSlippagePct": slip_sell["slippagePct"],
                "buyWorstPrice": slip_buy["worstPrice"],
                "sellWorstPrice": slip_sell["worstPrice"],
            })

        # 2. Frontrun Risk Index (0-100%)
        # Influenced by orderbook depth thinness + recent large taker bursts
        total_ask_depth_usd = sum(p * q for p, q in asks[:10]) if asks else 1.0
        large_taker_trades = [t for t in recent_trades if float(t.get("quantity", 0)) * mark_price > 25_000]

        depth_elasticity_score = max(0, min(50, int((1.0 - (total_ask_depth_usd / 2_000_000)) * 50)))
        taker_pressure_score = min(50, len(large_taker_trades) * 15)

        frontrun_risk_score = min(98, max(8, depth_elasticity_score + taker_pressure_score))

        # Risk Classification
        if frontrun_risk_score >= 70:
            risk_level = "CRITICAL"
            recommendation = "Extreme frontrunning / sandwich risk. High MEV activity in mempool. Use private RPC / Flashbots."
        elif frontrun_risk_score >= 45:
            risk_level = "ELEVATED"
            recommendation = "Moderate slippage vulnerability on orders > $50K. Tighten slippage tolerance to 0.1%."
        else:
            risk_level = "LOW"
            recommendation = "Deep liquidity pool. Low probability of profitable sandwich extraction."

        # 3. Simulated Sandwich Attack Model (for a hypothetical $100K victim market buy)
        victim_size = 100_000
        victim_slip = self.calculate_slippage(asks, victim_size)

        # Attacker frontruns with $40K buy, raising the price
        attacker_frontrun_size = 40_000
        frontrun_res = self.calculate_slippage(asks, attacker_frontrun_size)

        # Theoretical price shift caused by victim
        price_jump_pct = victim_slip["slippagePct"]
        attacker_gross_profit = attacker_frontrun_size * (price_jump_pct / 100.0) * 0.75
        attacker_net_profit = max(0.0, attacker_gross_profit - (self.gas_cost_usd * 2))

        sandwich_simulation = {
            "victimOrderSizeUsd": victim_size,
            "victimSlippageLossUsd": round(victim_size * (victim_slip["slippagePct"] / 100.0), 2),
            "frontrunnerCapitalUsd": attacker_frontrun_size,
            "estimatedMevProfitUsd": round(attacker_net_profit, 2),
            "isVulnerable": attacker_net_profit > 15.0,
            "executionSteps": [
                {
                    "step": 1,
                    "action": "FRONTRUN_BUY",
                    "actor": "MEV Bot (Searcher)",
                    "detail": f"Searcher injects bribe to prioritize buy before victim at ${mark_price:,.2f}",
                },
                {
                    "step": 2,
                    "action": "VICTIM_EXECUTION",
                    "actor": "Victim Trader",
                    "detail": f"Victim market order fills at inflated price (+{victim_slip['slippagePct']:.2f}% slippage)",
                },
                {
                    "step": 3,
                    "action": "BACKRUN_SELL",
                    "actor": "MEV Bot (Searcher)",
                    "detail": f"Searcher immediately sells back into inflated pool for ${attacker_net_profit:,.2f} net profit",
                },
            ]
        }

        return {
            "frontrunRiskScore": frontrun_risk_score,
            "riskLevel": risk_level,
            "recommendation": recommendation,
            "slippageMatrix": slippage_table,
            "sandwichSimulation": sandwich_simulation,
        }
