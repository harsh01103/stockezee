"""Regression tests: golden values captured at release v1.0.0 must not drift."""
import pytest
from stockezee import data, indicators as ind, screener, backtest


@pytest.fixture(scope="module")
def df():
    return data.synthetic_ohlcv(seed=7)


def test_golden_indicator_values(df):
    c = df["Close"]
    assert c.iloc[-1] == pytest.approx(1555.256, abs=1e-3)
    assert ind.rsi(c).iloc[-1] == pytest.approx(60.6451, abs=1e-3)
    assert ind.ema(c, 20).iloc[-1] == pytest.approx(1523.5287, abs=1e-3)


def test_golden_screen_verdict(df):
    r = screener.screen("RELIANCE", df, {"pe": 22.0, "roe": 17.5, "debt_equity": 0.4})
    assert (r.score, r.verdict) == (3, "BUY")


def test_golden_backtest_metrics(df):
    c = df["Close"]
    m = backtest.metrics(backtest.backtest(c, backtest.ema_cross_signal(c)))
    assert m["total_return"] == pytest.approx(-0.112234, abs=1e-5)
    assert m["sharpe"] == pytest.approx(-1.495962, abs=1e-5)
    assert m["max_drawdown"] == pytest.approx(-0.137957, abs=1e-5)
    assert m["trades"] == 2
