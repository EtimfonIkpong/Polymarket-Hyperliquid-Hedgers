import json
import os
from collections import defaultdict
import statistics

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("pm_trade_history_for_matches.json", "r") as f:
    pm_history = json.load(f)

with open("enriched_matches.json", "r") as f:
    enriched = json.load(f)

proxy_to_eoa = {m["proxy"]: m["eoa"] for m in enriched if m.get("proxy")}

wallet_trade_amounts = defaultdict(list)   # eoa -> [dollar amounts]
all_amounts = []

for proxy, markets in pm_history.items():
    eoa = proxy_to_eoa.get(proxy, proxy)
    for cid, trades in markets.items():
        for t in trades:
            try:
                size  = float(t["size"])
                price = float(t["price"])
            except (TypeError, ValueError, KeyError):
                continue
            amount = price * size   # actual cash wagered on this trade
            wallet_trade_amounts[eoa].append(amount)
            all_amounts.append(amount)

# ── Per-trader stats ──────────────────────────────────────
per_trader = {}
for eoa, amounts in wallet_trade_amounts.items():
    per_trader[eoa] = {
        "highest": round(max(amounts), 2),
        "lowest":  round(min(amounts), 2),
        "average": round(statistics.mean(amounts), 2),
        "trade_count": len(amounts),
    }

print(f"{'─'*65}")
print(f"BET SIZE STATS — PER TRADER (while hedging)")
print(f"{'─'*65}")
print(f"{'Wallet':<44} {'High':>10} {'Low':>8} {'Avg':>8}")
for eoa, s in sorted(per_trader.items(), key=lambda x: -x[1]["highest"])[:15]:
    print(f"{eoa:<44} ${s['highest']:>8,.2f} ${s['lowest']:>6,.2f} "
          f"${s['average']:>6,.2f}")

# ── Overall stats across ALL trades, ALL traders ──────────
print(f"\n{'─'*65}")
print(f"OVERALL — across all {len(all_amounts):,} hedge-related trades")
print(f"{'─'*65}")
print(f"Highest single bet  : ${max(all_amounts):,.2f}")
print(f"Lowest single bet   : ${min(all_amounts):,.2f}")
print(f"Average bet size    : ${statistics.mean(all_amounts):,.2f}")
print(f"Median bet size     : ${statistics.median(all_amounts):,.2f}")

# Who placed the single highest and lowest bets?
max_amt = max(all_amounts)
min_amt = min(all_amounts)
for eoa, s in per_trader.items():
    if s["highest"] == round(max_amt, 2):
        print(f"\nHighest single bet was by: {eoa} (${s['highest']:,.2f})")
        break
for eoa, s in per_trader.items():
    if s["lowest"] == round(min_amt, 2):
        print(f"Lowest single bet was by:  {eoa} (${s['lowest']:,.2f})")
        break

with open("bet_size_stats.json", "w") as f:
    json.dump({
        "overall": {
            "highest": round(max(all_amounts), 2),
            "lowest":  round(min(all_amounts), 2),
            "average": round(statistics.mean(all_amounts), 2),
            "median":  round(statistics.median(all_amounts), 2),
            "total_trades": len(all_amounts),
        },
        "per_trader": per_trader
    }, f, indent=2)

print(f"\n✅ Saved to bet_size_stats.json")
