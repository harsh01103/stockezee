import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
from opportunities.scorer import score_momentum_opportunities

def test_scorer_negative_momentum():
    """
    Test that negative momentum (crashing option) scores 0.0 and doesn't get artificially boosted
    by an absolute value function.
    """
    # Create an artificial dataframe mimicking opportunities input
    df = pl.DataFrame({
        "underlying": ["NIFTY", "NIFTY", "BANKNIFTY", "BANKNIFTY"],
        "expiry": ["2026-08-25", "2026-08-25", "2026-08-25", "2026-08-25"],
        "strike": [24000.0, 24000.0, 50000.0, 50000.0],
        "option_type": ["CE", "PE", "CE", "PE"],
        "composite_alpha_score": [35.0, -35.0, 15.0, -10.0], # CE mooning, PE crashing
        "delta": [0.65, -0.65, 0.65, -0.65],
        "s_ema_cross": [2.0, -2.0, 1.0, -1.0],
        "s_vwap": [2.0, -2.0, 1.0, -1.0],
        "s_ba_press": [5.0, -5.0, 2.0, -2.0],
        "s_oi_accel": [5.0, -5.0, 2.0, -2.0],
        "bid": [100.0, 100.0, 200.0, 200.0],
        "ask": [101.0, 101.0, 201.0, 201.0]
    })
    
    scored_df = score_momentum_opportunities(df)
    
    # Extract scores
    ce_mooning_score = scored_df.filter(pl.col("option_type") == "CE").head(1).select("opportunity_score").item()
    pe_crashing_score = scored_df.filter(pl.col("option_type") == "PE").head(1).select("opportunity_score").item()
    
    print(f"CE Mooning Score: {ce_mooning_score}")
    print(f"PE Crashing Score: {pe_crashing_score}")
    
    # PE has heavily negative composite score. Its final score should be drastically lower than CE
    # because the directional features should be clipped to 0, not absolute-valued.
    assert ce_mooning_score > 80.0, "Mooning option should have high score"
    assert pe_crashing_score < 50.0, "Crashing option should have very low score"
    
    # Specifically check the selection_score, which adds flow bonuses
    ce_selection = scored_df.filter(pl.col("option_type") == "CE").head(1).select("selection_score").item()
    pe_selection = scored_df.filter(pl.col("option_type") == "PE").head(1).select("selection_score").item()
    
    # The flow bonus for the PE should be 0 because it's negative
    assert pe_selection == pe_crashing_score, "Crashing option should get 0 flow bonus"
    assert ce_selection > ce_mooning_score, "Mooning option should get flow bonus"

if __name__ == "__main__":
    test_scorer_negative_momentum()
    print("Scorer logic tests passed.")
