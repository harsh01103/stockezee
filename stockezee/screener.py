"""Rule-based screeners (technical + fundamental) that return a flag AND the evidence behind it."""
from dataclasses import dataclass, field
from . import indicators as ind


@dataclass
class Signal:
    name: str
    triggered: bool
    reason: str
    value: float = float("nan")


@dataclass
class ScreenResult:
    symbol: str
    signals: list = field(default_factory=list)

    @property
    def score(self):
        return sum(1 for s in self.signals if s.triggered)

    @property
    def verdict(self):
        if self.score >= 4:
            return "STRONG BUY"
        if self.score >= 3:
            return "BUY"
        if self.score >= 2:
            return "WATCH"
        return "AVOID"


def technical_signals(df):
    c = df["Close"]
    out = []
    r = ind.rsi(c).iloc[-1]
    out.append(Signal("RSI", bool(r < 35), f"RSI(14) = {r:.1f}; below 35 means oversold", float(r)))
    e20, e50 = ind.ema(c, 20).iloc[-1], ind.ema(c, 50).iloc[-1]
    out.append(Signal("EMA trend", bool(e20 > e50), f"EMA20 {e20:.1f} vs EMA50 {e50:.1f}", float(e20 - e50)))
    m = ind.macd(c)
    out.append(Signal("MACD", bool(m["hist"].iloc[-1] > 0 and m["hist"].iloc[-2] <= 0),
                      f"MACD histogram {m['hist'].iloc[-1]:.2f}; bullish cross needs a sign change to positive",
                      float(m["hist"].iloc[-1])))
    b = ind.bollinger(c)
    out.append(Signal("Bollinger", bool(c.iloc[-1] < b["lower"].iloc[-1]),
                      f"Close {c.iloc[-1]:.1f} vs lower band {b['lower'].iloc[-1]:.1f}", float(c.iloc[-1] - b["lower"].iloc[-1])))
    v = ind.vwap(df).iloc[-1]
    out.append(Signal("VWAP", bool(c.iloc[-1] > v), f"Close {c.iloc[-1]:.1f} vs VWAP {v:.1f}", float(c.iloc[-1] - v)))
    return out


def fundamental_signals(f):
    """f: dict with pe, roe (percent), debt_equity."""
    return [
        Signal("P/E", bool(0 < f["pe"] < 25), f"P/E = {f['pe']}; value zone is 0-25", float(f["pe"])),
        Signal("ROE", bool(f["roe"] > 15), f"ROE = {f['roe']}%; quality threshold is 15%", float(f["roe"])),
        Signal("Debt/Equity", bool(f["debt_equity"] < 1.0), f"D/E = {f['debt_equity']}; safe below 1.0", float(f["debt_equity"])),
    ]


def screen(symbol, df, fundamentals=None):
    res = ScreenResult(symbol, technical_signals(df))
    if fundamentals:
        res.signals += fundamental_signals(fundamentals)
    return res
