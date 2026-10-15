import numpy as np
import pandas as pd
import pytest
from stockezee import data, indicators as ind, screener, explain, backtest


@pytest.fixture
def df():
    return data.synthetic_ohlcv()


def test_sma_known_values():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert ind.sma(s, 3).iloc[-1] == 4.0
    assert np.isnan(ind.sma(s, 3).iloc[1])


def test_ema_first_value_equals_input():
    s = pd.Series([10.0, 11.0, 12.0])
    assert ind.ema(s, 3).iloc[0] == 10.0


@pytest.mark.parametrize("fn", [ind.sma, ind.ema])
def test_window_must_be_positive(fn):
    with pytest.raises(ValueError):
        fn(pd.Series([1.0, 2.0]), 0)


def test_rsi_bounds(df):
    r = ind.rsi(df["Close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_rsi_monotonic_rise_is_100():
    s = pd.Series(np.arange(1, 40, dtype=float))
    assert ind.rsi(s).iloc[-1] == 100.0


def test_macd_hist_is_line_minus_signal(df):
    m = ind.macd(df["Close"])
    assert np.allclose(m["hist"], m["macd"] - m["signal"])


def test_bollinger_band_ordering(df):
    b = ind.bollinger(df["Close"]).dropna()
    assert (b["upper"] >= b["mid"]).all() and (b["mid"] >= b["lower"]).all()


def test_vwap_within_price_range(df):
    v = ind.vwap(df)
    assert v.iloc[0] == pytest.approx((df["High"].iloc[0] + df["Low"].iloc[0] + df["Close"].iloc[0]) / 3)


def test_validate_rejects_bad_frames(df):
    with pytest.raises(ValueError):
        data.validate(df.drop(columns=["Volume"]))
    with pytest.raises(ValueError):
        data.validate(df.iloc[0:0])
    bad = df.copy()
    bad.iloc[3, bad.columns.get_loc("Close")] = -1
    with pytest.raises(ValueError):
        data.validate(bad)


def test_synthetic_is_deterministic():
    assert data.synthetic_ohlcv(seed=1).equals(data.synthetic_ohlcv(seed=1))


def test_fundamentals_thresholds():
    sig = {s.name: s.triggered for s in screener.fundamental_signals({"pe": 22.0, "roe": 17.5, "debt_equity": 0.4})}
    assert sig == {"P/E": True, "ROE": True, "Debt/Equity": True}
    sig = {s.name: s.triggered for s in screener.fundamental_signals({"pe": 40.0, "roe": 9.0, "debt_equity": 2.0})}
    assert sig == {"P/E": False, "ROE": False, "Debt/Equity": False}


def test_pe_zero_boundary_not_triggered():
    assert not screener.fundamental_signals({"pe": 0.0, "roe": 20, "debt_equity": 0.1})[0].triggered


@pytest.mark.parametrize("score,verdict", [(0, "AVOID"), (1, "AVOID"), (2, "WATCH"), (3, "BUY"), (4, "STRONG BUY"), (6, "STRONG BUY")])
def test_verdict_bands(score, verdict):
    r = screener.ScreenResult("X", [screener.Signal(str(i), i < score, "") for i in range(8)])
    assert r.score == score and r.verdict == verdict


def test_explain_modes(df):
    r = screener.screen("TCS", df, {"pe": 22.0, "roe": 17.5, "debt_equity": 0.4})
    assert "[+]" in explain.explain(r, "pro")
    assert "Not investment advice" in explain.explain(r, "beginner")
    with pytest.raises(ValueError):
        explain.explain(r, "expert")


def test_explain_beginner_no_positive_signals():
    r = screener.ScreenResult("X", [screener.Signal("A", False, "")])
    assert "none of our checks" in explain.explain(r)


def test_backtest_no_lookahead(df):
    c = df["Close"]
    sig = backtest.ema_cross_signal(c)
    bt = backtest.backtest(c, sig)
    assert bt["position"].iloc[0] == 0
    assert (bt["position"].iloc[1:] == sig.shift(1).iloc[1:]).all()


def test_backtest_costs_reduce_return(df):
    c = df["Close"]
    sig = backtest.ema_cross_signal(c)
    free = backtest.backtest(c, sig, cost=0.0)["equity"].iloc[-1]
    paid = backtest.backtest(c, sig, cost=0.005)["equity"].iloc[-1]
    assert paid < free


def test_backtest_length_mismatch(df):
    with pytest.raises(ValueError):
        backtest.backtest(df["Close"], pd.Series([1, 0]))


def test_metrics_zero_vol():
    bt = pd.DataFrame({"position": [0, 0, 0], "strategy_ret": [0.0, 0.0, 0.0], "equity": [1.0, 1.0, 1.0]})
    assert backtest.metrics(bt)["sharpe"] == 0.0
