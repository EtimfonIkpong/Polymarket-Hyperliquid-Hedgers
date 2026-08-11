import json
import os
import csv
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("direction_tight_v2.json", "r") as f:
    direction_data = json.load(f)

results = direction_data["match_results"]

# ── Per wallet: count every hedge and doubledown instance ─
wallet_stats = defaultdict(lambda: {
    "hedge_count":   0,
    "doubledown_count": 0,
    "neutral_count": 0,
    "total_matches": 0,
    "assets":        set(),
    "hedge_markets":      [],
    "doubledown_markets": [],
    "neutral_markets":    [],
})

for r in results:
    eoa     = r["eoa"]
    coin    = r["coin"]
    hl_side = r["hl_side"]
    pm_dir  = r["pm_dir"]
    q       = r["question"]

    wallet_stats[eoa]["total_matches"] += 1
    wallet_stats[eoa]["assets"].add(coin)

    is_hedge = (hl_side == "Long"  and pm_dir == "Bearish") or \
               (hl_side == "Short" and pm_dir == "Bullish")
    is_same  = (hl_side == "Long"  and pm_dir == "Bullish") or \
               (hl_side == "Short" and pm_dir == "Bearish")

    if is_hedge:
        wallet_stats[eoa]["hedge_count"] += 1
        wallet_stats[eoa]["hedge_markets"].append(
            {"coin": coin, "hl_side": hl_side, "pm_dir": pm_dir, "question": q})
    elif is_same:
        wallet_stats[eoa]["doubledown_count"] += 1
        wallet_stats[eoa]["doubledown_markets"].append(
            {"coin": coin, "hl_side": hl_side, "pm_dir": pm_dir, "question": q})
    else:
        wallet_stats[eoa]["neutral_count"] += 1
        wallet_stats[eoa]["neutral_markets"].append(
            {"coin": coin, "hl_side": hl_side, "pm_dir": pm_dir, "question": q})

# ── Sort by hedge count descending ───────────────────────
sorted_wallets = sorted(
    wallet_stats.items(),
    key=lambda x: (-x[1]["hedge_count"], -x[1]["total_matches"])
)

# ── Print ─────────────────────────────────────────────────
print(f"{'='*75}")
print(f"ALL 96 WALLETS — HEDGE vs DOUBLEDOWN BREAKDOWN")
print(f"(Every instance counted, not just dominant pattern)")
print(f"{'='*75}")
print(f"\n{'Wallet':<44} {'Total':>5} {'Hedge':>6} {'DD':>5} "
      f"{'Neut':>5} {'Assets'}")
print(f"{'─'*75}")

for eoa, stats in sorted_wallets:
    assets = ", ".join(sorted(stats["assets"]))
    print(f"{eoa:<44} "
          f"{stats['total_matches']:>5} "
          f"{stats['hedge_count']:>6} "
          f"{stats['doubledown_count']:>5} "
          f"{stats['neutral_count']:>5}  "
          f"{assets}")

# ── Summary stats ─────────────────────────────────────────
total_hedges     = sum(s["hedge_count"]      for s in wallet_stats.values())
total_doubledown = sum(s["doubledown_count"] for s in wallet_stats.values())
total_neutral    = sum(s["neutral_count"]    for s in wallet_stats.values())
total_all        = total_hedges + total_doubledown + total_neutral

wallets_with_any_hedge = sum(
    1 for s in wallet_stats.values() if s["hedge_count"] > 0)
wallets_only_hedge = sum(
    1 for s in wallet_stats.values()
    if s["hedge_count"] > 0 and s["doubledown_count"] == 0)
wallets_only_dd = sum(
    1 for s in wallet_stats.values()
    if s["doubledown_count"] > 0 and s["hedge_count"] == 0)
wallets_mixed = sum(
    1 for s in wallet_stats.values()
    if s["hedge_count"] > 0 and s["doubledown_count"] > 0)

print(f"\n{'='*75}")
print(f"SUMMARY")
print(f"{'='*75}")
print(f"Total wallets analyzed        : {len(wallet_stats)}")
print(f"Total match instances         : {total_all}")
print(f"  Genuine hedges              : {total_hedges} ({total_hedges/total_all*100:.1f}%)")
print(f"  Doubling down               : {total_doubledown} ({total_doubledown/total_all*100:.1f}%)")
print(f"  Neutral                     : {total_neutral} ({total_neutral/total_all*100:.1f}%)")
print(f"\nWallet-level breakdown:")
print(f"  Wallets with ANY hedge      : {wallets_with_any_hedge}")
print(f"  Wallets hedge-only          : {wallets_only_hedge}")
print(f"  Wallets doubledown-only     : {wallets_only_dd}")
print(f"  Wallets with BOTH           : {wallets_mixed}")


# ── Save CSV ──────────────────────────────────────────────
csv_rows = []
for eoa, stats in sorted_wallets:
    csv_rows.append({
        "wallet":              eoa,
        "total_matches":       stats["total_matches"],
        "hedge_count":         stats["hedge_count"],
        "doubledown_count":    stats["doubledown_count"],
        "neutral_count":       stats["neutral_count"],
        "assets":              ", ".join(sorted(stats["assets"])),
        "hedge_pct":           round(stats["hedge_count"] /
                                stats["total_matches"] * 100, 1)
                                if stats["total_matches"] else 0,
        "hedge_markets":       " | ".join(
                                m["question"] for m in stats["hedge_markets"]),
        "doubledown_markets":  " | ".join(
                                m["question"] for m in stats["doubledown_markets"]),
    })

with open("wallet_behavior_breakdown.csv", "w", newline="",
          encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "wallet", "total_matches", "hedge_count", "doubledown_count",
        "neutral_count", "assets", "hedge_pct",
        "hedge_markets", "doubledown_markets"
    ])
    writer.writeheader()
    writer.writerows(csv_rows)

# ── Save JSON ─────────────────────────────────────────────
with open("wallet_behavior_breakdown.json", "w") as f:
    json.dump({
        "total_wallets":          len(wallet_stats),
        "wallets_with_any_hedge": wallets_with_any_hedge,
        "wallets_hedge_only":     wallets_only_hedge,
        "wallets_doubledown_only": wallets_only_dd,
        "wallets_mixed":          wallets_mixed,
        "total_hedge_instances":  total_hedges,
        "total_doubledown_instances": total_doubledown,
        "wallets": {
            eoa: {
                "total_matches":      s["total_matches"],
                "hedge_count":        s["hedge_count"],
                "doubledown_count":   s["doubledown_count"],
                "neutral_count":      s["neutral_count"],
                "assets":             sorted(s["assets"]),
                "hedge_pct":          round(s["hedge_count"] /
                                      s["total_matches"] * 100, 1)
                                      if s["total_matches"] else 0,
                "hedge_markets":      s["hedge_markets"],
                "doubledown_markets": s["doubledown_markets"],
            }
            for eoa, s in sorted_wallets
        }
    }, f, indent=2)

print(f"\n✅ Saved to:")
print(f"   wallet_behavior_breakdown.csv")
print(f"   wallet_behavior_breakdown.json")
