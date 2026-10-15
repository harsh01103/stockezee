import json
from pathlib import Path

def evaluate_signal_quality(metrics: dict) -> dict:
    """
    Evaluates signal quality.
    Reject if: IC < 0.02, stability < 0.60, train/val drift > 20%
    """
    reasons = []
    passed = True
    
    avg_ic = metrics.get("avg_ic", 0.0)
    stability = metrics.get("stability", 0.0)
    drift = metrics.get("train_val_drift", 0.0)
    
    if avg_ic < 0.02:
        passed = False
        reasons.append(f"IC < 0.02 ({avg_ic:.4f})")
        
    if stability < 0.60:
        passed = False
        reasons.append(f"stability < 0.60 ({stability:.2f})")
        
    if drift > 0.20:
        passed = False
        reasons.append(f"train/val drift > 20% ({drift:.2%})")
        
    report = {
        "passed": passed,
        "avg_ic": avg_ic,
        "stability": stability,
        "train_val_drift": drift,
        "reasons": reasons
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/signal_quality.json", "w") as f:
        json.dump(report, f, indent=2)
        
    return report
