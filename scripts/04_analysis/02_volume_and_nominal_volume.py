import json
import os
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("pm_trade_history_for_matches.json", "r") as f:
    pm_history = json.load(f)

with open("enriched_matches.json", "r") as f:
    enriched = json.load(f)

# Map (proxy, conditionId) -> coin
proxy_cid_to_coin = {}
for m in enriched:
    if m.get("proxy") and m.get("conditionId"):
        proxy_cid_to_coin[(m["proxy"], m["conditionId"])] = m["coin"]

coin_nominal = defaultdict(float)
coin_dollar  = defaultdict(float)
coin_trades  = defaultdict(int)

for proxy, markets in pm_history.items():
    for cid, trades in markets.items():
        coin = proxy_cid_to_coin.get((proxy, cid))
        if not coin:
            continue
        for t in trades:
            try:
                size  = float(t["size"])
                price = float(t["price"])
            except (TypeError, ValueError, KeyError):
                continue
            coin_nominal[coin] += size * 1.0
            coin_dollar[coin]  += price * size
            coin_trades[coin]  += 1

print(f"{'─'*60}")
print(f"VOLUME BY ASSET (confirmed hedge markets)")
print(f"{'─'*60}")
print(f"{'Asset':<10} {'Nominal Vol':>15} {'Dollar Vol':>15} {'Trades':>8}")
for coin in sorted(coin_nominal, key=lambda x: -coin_nominal[x]):
    print(f"{coin:<10} ${coin_nominal[coin]:>13,.0f} "
          f"${coin_dollar[coin]:>13,.0f} {coin_trades[coin]:>8,}")

total_nominal = sum(coin_nominal.values())
print(f"\nTotal nominal volume: ${total_nominal:,.2f}")

with open("volume_by_asset.json", "w") as f:
    json.dump({
        "nominal": {k: round(v, 2) for k, v in coin_nominal.items()},
        "dollar":  {k: round(coin_dollar[k], 2) for k in coin_dollar},
        "trades":  dict(coin_trades),
        "total_nominal": round(total_nominal, 2),
    }, f, indent=2)

print(f"\n✅ Saved to volume_by_asset.json")
