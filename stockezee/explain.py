"""Explainability layer: rule traces rendered in Beginner or Pro mode."""


def explain(result, mode="beginner"):
    if mode not in ("beginner", "pro"):
        raise ValueError("mode must be 'beginner' or 'pro'")
    on = [s for s in result.signals if s.triggered]
    off = [s for s in result.signals if not s.triggered]
    if mode == "pro":
        lines = [f"{result.symbol}: {result.verdict} (score {result.score}/{len(result.signals)})"]
        lines += [f"  [+] {s.name}: {s.reason}" for s in on]
        lines += [f"  [-] {s.name}: {s.reason}" for s in off]
        return "\n".join(lines)
    if not on:
        why = "none of our checks are currently positive"
    else:
        why = "; ".join(s.name for s in on) + " look favourable"
    return (f"{result.symbol} is rated {result.verdict}. {result.score} of {len(result.signals)} checks "
            f"passed: {why}. Not investment advice.")
