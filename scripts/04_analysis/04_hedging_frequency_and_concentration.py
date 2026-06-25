import json
import os
import pandas as pd
from collections import defaultdict, Counter

os.chdir(r"C:\Users\Etimfon\Desktop")

# ── Load everything we need ───────────────────────────────
with open("sequence_analysis_results.json", "r") as f:
    sequences = json.load(f)

with open("final_episode_count.json", "r") as f:
    episodes = json.load(f)

with open("nominal_volume.json", "r") as f:
    nominal = json.load(f)


# ══════════════════════════════════════════════════════════
# Q4: How quickly do traders hedge after opening a PM position?
# ══════════════════════════════════════════════════════════
gaps_hours = []
for r in sequences:
    try:
        pm_entry = pd.Timestamp(r["pm_entry"])
        hl_open  = pd.Timestamp(r["hl_open"])
        gap = (hl_open - pm_entry).total_seconds() / 3600   # hours, can be negative
        gaps_hours.append(gap)
    except Exception:
        continue

pm_then_hl = [g for g in gaps_hours if g >= 0]
hl_then_pm = [g for g in gaps_hours if g < 0]

print(f"{'─'*60}\nQ4: SPEED OF HEDGING\n{'─'*60}")
print(f"Matches where PM came first, then HL opened : {len(pm_then_hl)}")
if pm_then_hl:
    print(f"  Avg gap    : {sum(pm_then_hl)/len(pm_then_hl):.1f} hours "
          f"({sum(pm_then_hl)/len(pm_then_hl)/24:.1f} days)")
    print(f"  Median gap : {sorted(pm_then_hl)[len(pm_then_hl)//2]:.1f} hours")
print(f"\nMatches where HL came first, then PM bet placed : {len(hl_then_pm)}")
if hl_then_pm:
    avg_abs = sum(abs(g) for g in hl_then_pm)/len(hl_then_pm)
    print(f"  Avg gap    : {avg_abs:.1f} hours ({avg_abs/24:.1f} days)")


# ══════════════════════════════════════════════════════════
# Q4-dup: Frequency of hedging (how often does each trader hedge?)
# ══════════════════════════════════════════════════════════
wallet_episode_count = Counter(p["eoa"] for p in episodes["pairs"])
freq_dist = Counter(wallet_episode_count.values())

print(f"\n{'─'*60}\nFREQUENCY: Wallet-asset relationships per trader\n{'─'*60}")
for n_relationships, n_wallets in sorted(freq_dist.items()):
    print(f"  {n_relationships} relationship(s) : {n_wallets} wallets")


# ══════════════════════════════════════════════════════════
# Q17: Concentration — do a few wallets dominate hedge volume?
# ══════════════════════════════════════════════════════════
by_wallet = nominal["by_wallet"]
sorted_wallets = sorted(by_wallet.items(), key=lambda x: -x[1]["nominal"])
total_nominal = sum(v["nominal"] for v in by_wallet.values())
n = len(sorted_wallets)

def share_of_top(k):
    top_sum = sum(v["nominal"] for _, v in sorted_wallets[:k])
    return top_sum / total_nominal * 100

top1pct_n = max(1, round(n * 0.01))

print(f"\n{'─'*60}\nQ17: CONCENTRATION OF HEDGE VOLUME\n{'─'*60}")
print(f"Total wallets in hedge volume   : {n}")
print(f"Top 10 traders share            : {share_of_top(10):.1f}%")
print(f"Top 50 traders share            : {share_of_top(min(50,n)):.1f}%")
print(f"Top 1% ({top1pct_n} traders) share     : {share_of_top(top1pct_n):.1f}%")
print(f"\nTop 5 wallets:")
for eoa, v in sorted_wallets[:5]:
    print(f"  {eoa} : ${v['nominal']:,.2f} "
          f"({v['nominal']/total_nominal*100:.1f}% of total)")

with open("deep_dive_part1_results.json", "w") as f:
    json.dump({
        "speed_pm_first_avg_hours": sum(pm_then_hl)/len(pm_then_hl) if pm_then_hl else None,
        "speed_hl_first_avg_hours": sum(abs(g) for g in hl_then_pm)/len(hl_then_pm) if hl_then_pm else None,
        "frequency_distribution": dict(freq_dist),
        "concentration_top10_pct": share_of_top(10),
        "concentration_top50_pct": share_of_top(min(50,n)),
        "concentration_top1pct_pct": share_of_top(top1pct_n),
    }, f, indent=2)

print(f"\n✅ Saved to deep_dive_part1_results.json")
