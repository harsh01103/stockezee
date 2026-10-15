"""Vectorised backtester with explicit look-ahead safeguard (signals shifted one bar)."""
import numpy as np
import pandas as pd
from . import indicators as ind


def ema_cross_signal(close, fast=20, slow=50):
    return (ind.ema(close, fast) > ind.ema(close, slow)).astype(int)


def backtest(close, signal, cost=0.001):
    """Trade next bar after signal (shift(1)) -> no look-ahead. cost = per-side fraction."""
    if len(close) != len(signal):
        raise ValueError("close and signal must have equal length")
    pos = signal.shift(1).fillna(0)
    ret = close.pct_change().fillna(0)
    turns = pos.diff().abs().fillna(pos.abs())
    strat = pos * ret - turns * cost
    equity = (1 + strat).cumprod()
    return pd.DataFrame({"position": pos, "strategy_ret": strat, "equity": equity,
                         "buy_hold": (1 + ret).cumprod()})


def metrics(bt, periods=252):
    r = bt["strategy_ret"]
    total = bt["equity"].iloc[-1] - 1
    vol = r.std(ddof=0) * np.sqrt(periods)
    sharpe = (r.mean() * periods) / vol if vol > 0 else 0.0
    dd = (bt["equity"] / bt["equity"].cummax() - 1).min()
    trades = int(bt["position"].diff().abs().fillna(0).sum() // 2)
    return {"total_return": float(total), "sharpe": float(sharpe), "max_drawdown": float(dd), "trades": trades}
