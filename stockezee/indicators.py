"""Technical indicators: SMA, EMA, RSI, MACD, Bollinger Bands, VWAP."""
import pandas as pd


def sma(s, n):
    if n <= 0:
        raise ValueError("window must be positive")
    return s.rolling(n).mean()


def ema(s, n):
    if n <= 0:
        raise ValueError("window must be positive")
    return s.ewm(span=n, adjust=False).mean()


def rsi(s, n=14):
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    out = 100 - 100 / (1 + rs)
    return out.fillna(100.0).where(avg_gain.notna())


def macd(s, fast=12, slow=26, signal=9):
    line = ema(s, fast) - ema(s, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(s, n=20, k=2.0):
    mid = sma(s, n)
    sd = s.rolling(n).std(ddof=0)
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def vwap(df):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()
