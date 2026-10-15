"""Integration tests: data -> indicators -> screener -> explainability -> backtest -> API."""
from fastapi.testclient import TestClient
from stockezee import data, screener, explain, backtest
from stockezee.api import app

client = TestClient(app)


def test_pipeline_end_to_end():
    df = data.validate(data.synthetic_ohlcv())
    res = screener.screen("RELIANCE", df, {"pe": 22.0, "roe": 17.5, "debt_equity": 0.4})
    text = explain.explain(res, "pro")
    assert res.symbol in text and str(res.score) in text
    m = backtest.metrics(backtest.backtest(df["Close"], backtest.ema_cross_signal(df["Close"])))
    assert set(m) == {"total_return", "sharpe", "max_drawdown", "trades"}


def test_api_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_api_screen_beginner_and_pro():
    b = client.get("/screen/reliance").json()
    p = client.get("/screen/reliance?mode=pro").json()
    assert b["symbol"] == "RELIANCE" and "Not investment advice" in b["explanation"]
    assert "[+]" in p["explanation"] and b["verdict"] == p["verdict"]


def test_api_rejects_bad_mode():
    assert client.get("/screen/tcs?mode=hacker").status_code == 400


def test_api_backtest_fields():
    r = client.get("/backtest/infy").json()
    assert r["symbol"] == "INFY" and "sharpe" in r and r["trades"] >= 0
