"""Tests added after the first mutation run: boundary, default-parameter and exact-value checks."""
import numpy as np
import pandas as pd
import pytest
from stockezee import data, indicators as ind, screener, backtest


@pytest.fixture(scope="module")
def df():
    return data.synthetic_ohlcv(seed=7)


def test_window_of_one_is_valid():
    s = pd.Series([1.0, 2.0, 3.0])
    assert ind.sma(s, 1).tolist() == [1.0, 2.0, 3.0]
    assert ind.ema(s, 1).tolist() == [1.0, 2.0, 3.0]


def test_negative_window_rejected():
    with pytest.raises(ValueError):
        ind.sma(pd.Series([1.0, 2.0]), -3)


def test_golden_macd_bollinger_vwap(df):
    c = df["Close"]
    m = ind.macd(c).iloc[-1]
    assert (m["macd"], m["signal"], m["hist"]) == pytest.approx((m["macd"], m["signal"], m["macd"] - m["signal"]))
    assert m["macd"] == pytest.approx(ind.ema(c, 12).iloc[-1] - ind.ema(c, 26).iloc[-1])
    assert m["signal"] == pytest.approx(ind.ema(ind.macd(c)["macd"], 9).iloc[-1])
    b = ind.bollinger(c).iloc[-1]
    w = c.iloc[-20:]
    assert b["mid"] == pytest.approx(w.mean())
    assert b["upper"] == pytest.approx(w.mean() + 2 * w.std(ddof=0))
    assert b["lower"] == pytest.approx(w.mean() - 2 * w.std(ddof=0))
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    assert ind.vwap(df).iloc[-1] == pytest.approx((tp * df["Volume"]).sum() / df["Volume"].sum())


def test_rsi_matches_reference_formula():
    s = pd.Series([44.0, 44.3, 44.1, 43.6, 44.3, 44.8, 45.1, 45.4, 45.8, 46.1, 45.9, 46.0, 45.6, 46.3, 46.3, 46.0])
    d = s.diff(); g = d.clip(lower=0); l = -d.clip(upper=0)
    ag = g.ewm(alpha=1 / 14, adjust=False).mean(); al = l.ewm(alpha=1 / 14, adjust=False).mean()
    expected = 100 - 100 / (1 + ag / al)
    assert ind.rsi(s).iloc[-1] == pytest.approx(expected.iloc[-1])
    assert ind.rsi(s, 5).iloc[-1] != pytest.approx(ind.rsi(s, 14).iloc[-1])


def test_rsi_all_losses_is_zero():
    s = pd.Series(np.arange(40, 1, -1, dtype=float))
    assert ind.rsi(s).iloc[-1] == pytest.approx(0.0)


def _frame(n=60, price=100.0):
    idx = pd.bdate_range("2025-01-01", periods=n)
    return pd.DataFrame({"Open": price, "High": price, "Low": price, "Close": price, "Volume": 1000}, index=idx)


@pytest.fixture
def patch(monkeypatch):
    def _p(rsi=50.0, e20=1.0, e50=1.0, hist=(0.0, 0.0), lower_gap=1.0, vwap_gap=0.0):
        n = 60
        monkeypatch.setattr(screener.ind, "rsi", lambda c: pd.Series([rsi] * n))
        monkeypatch.setattr(screener.ind, "ema", lambda c, k: pd.Series([e20 if k == 20 else e50] * n))
        monkeypatch.setattr(screener.ind, "macd", lambda c: pd.DataFrame({"hist": [0.0] * (n - 2) + list(hist)}))
        monkeypatch.setattr(screener.ind, "bollinger", lambda c: pd.DataFrame({"lower": [-999.0] * (n - 1) + [100.0 - lower_gap]}))
        monkeypatch.setattr(screener.ind, "vwap", lambda d: pd.Series([1e9] * (n - 1) + [100.0 - vwap_gap]))
        return {s.name: s for s in screener.technical_signals(_frame())}
    return _p


def test_rsi_boundary(patch):
    assert patch(rsi=34.9)["RSI"].triggered
    assert not patch(rsi=35.0)["RSI"].triggered
    assert patch(rsi=34.0)["RSI"].value == 34.0


def test_ema_boundary(patch):
    assert patch(e20=2.0, e50=1.0)["EMA trend"].triggered
    assert not patch(e20=1.0, e50=1.0)["EMA trend"].triggered
    assert patch(e20=5.0, e50=2.0)["EMA trend"].value == 3.0


def test_macd_cross_logic(patch):
    assert patch(hist=(-0.1, 0.2))["MACD"].triggered
    assert patch(hist=(0.0, 0.2))["MACD"].triggered
    assert not patch(hist=(0.1, 0.2))["MACD"].triggered
    assert not patch(hist=(-0.2, -0.1))["MACD"].triggered
    assert not patch(hist=(-0.1, 0.0))["MACD"].triggered
    assert patch(hist=(-0.1, 0.2))["MACD"].value == 0.2


def test_bollinger_boundary(patch):
    assert patch(lower_gap=-1.0)["Bollinger"].triggered       # close below lower band
    assert not patch(lower_gap=0.0)["Bollinger"].triggered     # equal is not a breach
    assert patch(lower_gap=-3.0)["Bollinger"].value == -3.0


def test_vwap_boundary(patch):
    assert patch(vwap_gap=1.0)["VWAP"].triggered
    assert not patch(vwap_gap=0.0)["VWAP"].triggered
    assert patch(vwap_gap=2.5)["VWAP"].value == 2.5


@pytest.mark.parametrize("pe,roe,de,exp", [
    (24.99, 15.01, 0.99, (True, True, True)),
    (25.0, 15.0, 1.0, (False, False, False)),
    (-5.0, 16, 0.5, (False, True, True)),
    (0.01, 20, 3.0, (True, True, False)),
])
def test_fundamental_boundaries(pe, roe, de, exp):
    got = tuple(s.triggered for s in screener.fundamental_signals({"pe": pe, "roe": roe, "debt_equity": de}))
    assert got == exp


def test_fundamental_values_and_reasons():
    pe, roe, de = screener.fundamental_signals({"pe": 22.0, "roe": 17.5, "debt_equity": 0.4})
    assert (pe.value, roe.value, de.value) == (22.0, 17.5, 0.4)
    assert "22.0" in pe.reason and "17.5" in roe.reason and "0.4" in de.reason


def test_screen_adds_fundamentals_only_when_given(df):
    assert len(screener.screen("X", df).signals) == 5
    assert len(screener.screen("X", df, {"pe": 10, "roe": 20, "debt_equity": 0.1}).signals) == 8


def test_signal_values_and_reasons(df):
    sig = {s.name: s for s in screener.technical_signals(df)}
    c = df["Close"]
    assert sig["RSI"].value == pytest.approx(ind.rsi(c).iloc[-1])
    assert sig["EMA trend"].value == pytest.approx(ind.ema(c, 20).iloc[-1] - ind.ema(c, 50).iloc[-1])
    assert sig["MACD"].value == pytest.approx(ind.macd(c)["hist"].iloc[-1])
    assert sig["Bollinger"].value == pytest.approx(c.iloc[-1] - ind.bollinger(c)["lower"].iloc[-1])
    assert sig["VWAP"].value == pytest.approx(c.iloc[-1] - ind.vwap(df).iloc[-1])
    assert "RSI(14)" in sig["RSI"].reason and "EMA20" in sig["EMA trend"].reason


@pytest.mark.parametrize("seed", range(1, 8))
def test_default_cross_windows(seed):
    c = data.synthetic_ohlcv(seed=seed)["Close"]
    assert backtest.ema_cross_signal(c).equals((ind.ema(c, 20) > ind.ema(c, 50)).astype(int))
    assert not backtest.ema_cross_signal(c).equals(backtest.ema_cross_signal(c, 5, 10))


def test_backtest_first_bar_and_costs():
    c = pd.Series([100.0, 110.0, 121.0, 108.9])
    sig = pd.Series([1, 1, 0, 0])
    bt = backtest.backtest(c, sig, cost=0.01)
    assert bt["buy_hold"].iloc[0] == 1.0
    assert bt["strategy_ret"].tolist() == pytest.approx([0.0, 0.09, 0.10, -0.01])
    assert bt["buy_hold"].iloc[-1] == pytest.approx(1.089)


def test_metrics_exact():
    eq = pd.Series([1.0, 1.1, 0.99, 1.2])
    ret = eq.pct_change().fillna(0)
    bt = pd.DataFrame({"position": [0, 1, 1, 0], "strategy_ret": ret, "equity": eq})
    m = backtest.metrics(bt)
    assert m["total_return"] == pytest.approx(0.2)
    assert m["max_drawdown"] == pytest.approx(0.99 / 1.1 - 1)
    assert m["trades"] == 1
    assert m["sharpe"] == pytest.approx(ret.mean() * 252 / (ret.std(ddof=0) * np.sqrt(252)))


def test_validate_returns_frame_and_checks_each_price_column(df):
    assert data.validate(df) is df
    for col in ["Open", "High", "Low", "Close"]:
        bad = df.copy()
        bad.iloc[0, bad.columns.get_loc(col)] = 0.0
        with pytest.raises(ValueError):
            data.validate(bad)
    small = df.copy(); small[["Open", "High", "Low", "Close"]] = 0.5
    assert data.validate(small) is small
    zero_vol = df.copy(); zero_vol["Volume"] = 0
    assert data.validate(zero_vol) is zero_vol
