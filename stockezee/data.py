"""Data layer: yfinance loader (live) and deterministic synthetic generator (offline/tests)."""
import numpy as np
import pandas as pd


def synthetic_ohlcv(n=300, seed=7, start_price=2400.0):
    """Deterministic geometric-random-walk OHLCV frame used for offline demos and tests."""
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0004, 0.014, n)
    close = start_price * np.exp(np.cumsum(ret))
    open_ = np.r_[start_price, close[:-1]] * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    vol = rng.integers(1_000_000, 5_000_000, n)
    idx = pd.bdate_range("2025-01-01", periods=n)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def load_nse(symbol, period="2y"):
    """Fetch daily OHLCV for an NSE symbol (e.g. RELIANCE.NS) through yfinance."""
    import yfinance as yf  # imported lazily so the package works offline
    df = yf.download(symbol, period=period, auto_adjust=True, progress=False)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df.dropna()


def validate(df):
    """Reject frames that are missing columns, empty, or contain non-positive prices."""
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    if df.empty:
        raise ValueError("empty dataframe")
    if (df[["Open", "High", "Low", "Close"]] <= 0).any().any():
        raise ValueError("non-positive price found")
    return df
