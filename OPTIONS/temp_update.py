import os

source_file = r'c:\Users\kpn_i\.gemini\antigravity-ide\brain\12de9290-1a03-4cab-bb9d-8bfd9d4a60c6\strategy_reference.md'
dest_file = r'c:\Users\kpn_i\.gemini\antigravity-ide\brain\45656487-3205-4deb-b1b8-09b4d0bd97c0\strategy_reference.md'

with open(source_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Update version and date
content = content.replace('Version:** 3.0', 'Version:** 3.1')
content = content.replace('July 10, 2026', 'July 23, 2026')

# Update Mermaid diagram
mermaid_old = """    J -->|"Trending"| K["Momentum Breakout Engine"]
    J -->|"Choppy"| L["Mean Reversion Engine"]
    K --> M["Multi-Dimensional Scoring"]
    L --> M"""
mermaid_new = """    J -->|"Trending"| K["Momentum Breakout Engine"]
    J -->|"Choppy"| L["Mean Reversion Engine"]
    J -->|"After 14:30"| K2["Power Hour Engine"]
    K --> M["Multi-Dimensional Scoring"]
    L --> M
    K2 --> M"""
content = content.replace(mermaid_old, mermaid_new)

# Add Webhook Payload Fix section
telemetry_old = "## 15. Telemetry & ML Data Collection"
telemetry_new = """## 15. Telemetry & ML Data Collection

### The v3.1 Webhook & Labeling Upgrade
As of the v3.1 fix, the Python engine explicitly propagates its entire context to the Node.js backend to prevent "blind" execution:
1. **Full Feature Pass-Through**: The `_features` dictionary (containing all ML Z-scores and regime flags) is serialized and pushed via the webhook. The Node.js ledger now records exact volatility and trend regimes for every trade.
2. **Dynamic Strategy Tagging**: Trades are no longer hardcoded as "Momentum Breakout". The dataframes are injected with an `_engine` alias, allowing the Node.js frontend to dynamically label trades as **Mean Reversion**, **Momentum Breakout**, or **Power Hour** depending on which logic path generated the signal."""
content = content.replace(telemetry_old, telemetry_new)

with open(dest_file, 'w', encoding='utf-8') as f:
    f.write(content)

with open(dest_file + '.metadata.json', 'w', encoding='utf-8') as f:
    f.write('{"UserFacing":true,"RequestFeedback":false,"Summary":"Updated Strategy Reference for v3.1 with webhook payload fixes and Power Hour engine."}')

print("Successfully generated updated strategy reference.")
