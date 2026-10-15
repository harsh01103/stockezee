import re

with open(r"c:\Users\kpn_i\.gemini\antigravity-ide\scratch\OPTIONS\runner.py", "r", encoding="utf-8") as f:
    code = f.read()

# We need to refactor run_momentum_engine.
# 1. Compute raw rolling features on df_res (price_velocity_raw, volume_burst_raw, oi_accel_raw).
# 2. Extract df_latest = df_res.unique(subset=["underlying", "expiry", "strike", "option_type"], keep="last")
# 3. Compute z-scores on df_latest using `.over(["underlying", "option_type"])`.

# Let's do a targeted string replacement using a script to be safe.

def patch_runner():
    global code
    # Replace zscore_group
    code = code.replace(
        'zscore_group = ["timestamp", "underlying", "option_type"]',
        'zscore_group = ["underlying", "option_type"]'
    )
    
    # Change .over("timestamp") to .over(zscore_group) for standardizations
    code = code.replace('.over("timestamp")', '.over(zscore_group)')
    
    # We must insert df_latest extraction AFTER raw rolling features but BEFORE z-scores?
    # Actually, if we just change the assignment from df_res to df_latest halfway through?
    # No, it's easier to compute ALL raw features on df_res, then do df_latest, then do z-scores.
    pass

# Alternatively, I can just supply the entirely rewritten run_momentum_engine.
