"""
Unit tests for MEV Frontrunning and Sandwich Attack Analytics Engine.
"""

from src.mev_sandwich import MevSandwichAnalyzer


def test_slippage_calculation():
    analyzer = MevSandwichAnalyzer()
    # 5 levels of asks: 1 BTC each at 60000, 60010, 60020, 60030, 60040
    asks = [
        [60000.0, 1.0],  # $60,000
        [60010.0, 1.0],  # $60,010
        [60020.0, 1.0],  # $60,020
    ]
    # Small trade under level 1 ($10,000) -> 0 slippage against best ask
    slip_small = analyzer.calculate_slippage(asks, 10_000)
    assert slip_small["slippagePct"] == 0.0
    assert slip_small["avgPrice"] == 60000.0

    # Large trade spanning levels ($100,000) -> slippage > 0
    slip_large = analyzer.calculate_slippage(asks, 100_000)
    assert slip_large["slippagePct"] > 0.0
    assert slip_large["avgPrice"] > 60000.0


def test_mev_risk_analysis():
    analyzer = MevSandwichAnalyzer()
    asks = [[60000.0 + i * 5, 0.5] for i in range(15)]
    bids = [[59995.0 - i * 5, 0.5] for i in range(15)]
    recent_trades = [{"quantity": 2.5}, {"quantity": 0.1}]

    res = analyzer.analyze_mev_risk(bids, asks, recent_trades, mark_price=60000.0)

    assert "frontrunRiskScore" in res
    assert 0 <= res["frontrunRiskScore"] <= 100
    assert res["riskLevel"] in ["LOW", "ELEVATED", "CRITICAL"]
    assert len(res["slippageMatrix"]) == 4

    sim = res["sandwichSimulation"]
    assert len(sim["executionSteps"]) == 3
    assert sim["executionSteps"][0]["action"] == "FRONTRUN_BUY"
    assert sim["executionSteps"][1]["action"] == "VICTIM_EXECUTION"
    assert sim["executionSteps"][2]["action"] == "BACKRUN_SELL"
