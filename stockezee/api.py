"""FastAPI service exposing screening, explanation and backtest endpoints."""
from fastapi import FastAPI, HTTPException
from . import data, screener, explain as ex, backtest as bt

app = FastAPI(title="StockEzee API", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/screen/{symbol}")
def screen(symbol: str, mode: str = "beginner", seed: int = 7):
    if mode not in ("beginner", "pro"):
        raise HTTPException(status_code=400, detail="mode must be beginner or pro")
    df = data.validate(data.synthetic_ohlcv(seed=seed))
    res = screener.screen(symbol.upper(), df, {"pe": 22.0, "roe": 17.5, "debt_equity": 0.4})
    return {"symbol": res.symbol, "verdict": res.verdict, "score": res.score,
            "explanation": ex.explain(res, mode)}


@app.get("/backtest/{symbol}")
def run_backtest(symbol: str, seed: int = 7):
    df = data.validate(data.synthetic_ohlcv(seed=seed))
    out = bt.backtest(df["Close"], bt.ema_cross_signal(df["Close"]))
    return {"symbol": symbol.upper(), **bt.metrics(out)}
