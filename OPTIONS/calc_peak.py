import pandas as pd
import glob

files = sorted(glob.glob(r'C:\Users\kpn_i\.gemini\antigravity-ide\scratch\OPTIONS\data\raw\2026-07-08\*.parquet'))
df_list = []
for f in files:
    df = pd.read_parquet(f)
    df_list.append(df)

if df_list:
    df = pd.concat(df_list)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=5, minutes=30) # IST
    
    # Filter for time after the trade was opened (12:37:56)
    df_filtered = df[df['timestamp'] >= pd.to_datetime('2026-07-08 12:37:56')]
    
    ce = df_filtered[(df_filtered['strike'] == 23950.0) & (df_filtered['option_type'] == 'CE')]
    nifty = df_filtered[(df_filtered['underlying'] == 'NIFTY') & (df_filtered['option_type'] == '')]
    
    print("Nifty Start at 12:37:56: 24197.6 (from ledger)")
    if not nifty.empty:
        max_nifty = nifty['ltp'].max()
        print(f"Nifty Max since entry: {max_nifty}")
        print(f"Nifty Min since entry: {nifty['ltp'].min()}")
        # Calculate exactly when it went up by 40-50 pts
        target_nifty_time = nifty[nifty['ltp'] >= 24197.6 + 40]['timestamp'].min()
        print(f"Time when Nifty went up 40+ points: {target_nifty_time}")
    
    if not ce.empty:
        print(f"Max CE Price overall since entry: {ce['ltp'].max()}")
        print(f"Min CE Price overall since entry: {ce['ltp'].min()}")
        
        if 'target_nifty_time' in locals() and pd.notna(target_nifty_time):
            # Look at CE price exactly at or up to that time
            ce_during_move = ce[ce['timestamp'] <= target_nifty_time]
            print(f"Max CE Price during this 40-pt Nifty move: {ce_during_move['ltp'].max()}")
            print(f"Min CE Price during this 40-pt Nifty move: {ce_during_move['ltp'].min()}")
