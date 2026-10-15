import re

with open('runner.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Search for key patterns
patterns = [
    'BULLISH', 'BEARISH', 'direction', 'flip', 'CE', 'PE', 
    'last_trade', 'cooldown', 'consecutive', 'loss_streak',
    'trade_count', 'same_dir', 'throttle', 'whipsaw',
    'CHOPPY', 'TRENDING', 'is_trending', 'mean_rev',
    'ib_high', 'ib_low', 'initial_balance',
    'regime_confidence', 'compression',
    'build_trade_idea', 'publish_signal', 'run_momentum', 'run_mean_rev',
    'daily_pnl', 'daily_loss'
]

for pat in patterns:
    matches = [(i+1, line.rstrip()) for i, line in enumerate(content.split('\n')) if pat.lower() in line.lower()]
    if matches:
        print(f'\n--- {pat} ({len(matches)} matches) ---')
        for ln, text in matches[:5]:  # first 5 only
            print(f'  L{ln}: {text[:120].encode("ascii", "replace").decode()}')
        if len(matches) > 5:
            print(f'  ... and {len(matches)-5} more')
