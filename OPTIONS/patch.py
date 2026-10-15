import re

with open(r"c:\Users\kpn_i\.gemini\antigravity-ide\scratch\OPTIONS\runner.py", "r", encoding="utf-8") as f:
    runner_code = f.read()

with open(r"c:\Users\kpn_i\.gemini\antigravity-ide\scratch\OPTIONS\new_momentum.py", "r", encoding="utf-8") as f:
    new_func = f.read()

start_pattern = r'def run_momentum_engine\(df_res, t0\):'
start_match = re.search(start_pattern, runner_code)
start_idx = start_match.start()

next_func_pattern = r'\ndef run_mean_reversion_engine\('
end_match = re.search(next_func_pattern, runner_code[start_idx:])
end_idx = start_idx + end_match.start()

patched_code = runner_code[:start_idx] + new_func + runner_code[end_idx:]

with open(r"c:\Users\kpn_i\.gemini\antigravity-ide\scratch\OPTIONS\runner.py", "w", encoding="utf-8") as f:
    f.write(patched_code)

print("Patched successfully!")
