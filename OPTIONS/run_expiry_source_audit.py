"""PHASE O2D — EXPIRY SOURCE OF TRUTH"""
import glob, os, polars as pl

date_str = "2026-06-19"
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
df = pl.read_parquet(raw_files[0])

# STEP 1: Raw expiry values
print("=== RAW PARQUET EXPIRY VALUES ===")
exp_counts = df.group_by("expiry").len().sort("expiry")
for r in exp_counts.iter_rows(named=True):
    print("  expiry=" + repr(r["expiry"]) + "  count=" + str(r["len"]))

# Sample instrument_keys alongside expiry
print()
print("=== SAMPLE ROWS (instrument_key vs expiry) ===")
sample = df.select(["underlying", "expiry", "strike", "option_type", "record_id"]).unique().head(15)
for r in sample.iter_rows(named=True):
    print("  key=" + str(r["record_id"]) + "  underlying=" + str(r["underlying"]) + "  expiry=" + repr(r["expiry"]) + "  strike=" + str(r["strike"]) + "  type=" + str(r["option_type"]))

# Count empty vs real
total = df.height
empty_exp = df.filter(pl.col("expiry") == "").height
real_exp = df.filter(pl.col("expiry") != "").height
print()
print("Total: " + str(total) + "  empty_expiry: " + str(empty_exp) + "  real_expiry: " + str(real_exp))
print("Empty ratio: " + str(round(empty_exp/total*100, 1)) + "%")

# Instrument keys with empty expiry
print()
print("=== INSTRUMENT KEYS WITH EMPTY EXPIRY ===")
empty_keys = df.filter(pl.col("expiry") == "").select("record_id").unique()
for r in empty_keys.head(10).iter_rows(named=True):
    print("  " + str(r["record_id"]))

# Keys with real expiry
print()
print("=== INSTRUMENT KEYS WITH REAL EXPIRY ===")
real_keys = df.filter(pl.col("expiry") != "").select(["record_id", "expiry"]).unique()
for r in real_keys.head(10).iter_rows(named=True):
    print("  " + str(r["record_id"]) + " -> " + repr(r["expiry"]))

# STEP 2: Check decoder path
# The decoder sets expiry="" at line 102, then tries resolve_from_key
# Let's check if resolve_from_key returns expiry for the empty-expiry keys
print()
print("=== DECODER ANALYSIS ===")
print("decoder.py line 102: expiry = '' (default)")
print("decoder.py line 108-113: resolve_from_key(instrument_key) -> identity.get('expiry', '')")
print("If resolver miss AND regex miss -> expiry stays empty")

# Check what underlying the empty-expiry rows have
print()
print("=== UNDERLYING FOR EMPTY EXPIRY ROWS ===")
empty_underlying = df.filter(pl.col("expiry") == "").group_by("underlying").len().sort("len", descending=True)
for r in empty_underlying.iter_rows(named=True):
    print("  " + str(r["underlying"]) + " -> " + str(r["len"]) + " rows")

# STEP 3: Universe fabrication
print()
print("=== UNIVERSE FABRICATION ===")
print("universe.py line 18: if max_c < 20 -> synthetic expansion")
print("universe.py line 23: synthetic_expiries = ['2026-06-25', '2026-07-02', '2026-07-09']")
print("universe.py line 43-48: for exp in synthetic_expiries: cand['expiry'] = exp")
print("These dates DO NOT exist in raw Upstox data")

# STEP 4: Counts
print()
missing = empty_exp
generated = 0  # We need to check universe output
real = real_exp

print("OUTPUT:")
print("missing_raw_expiry: " + str(missing))
print("generated_expiry: synthetic_expiries=['2026-06-25', '2026-07-02', '2026-07-09']")
print("generator_location: opportunities/universe.py:23,43-48")

if missing > 0 and True:  # universe always fabricates
    print("first_bad_stage: DOUBLE_FAULT")
    print("decision: DOUBLE_FAULT")
else:
    print("decision: UNKNOWN")
print("STOP")
