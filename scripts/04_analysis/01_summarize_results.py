import json
import os
from collections import Counter

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("final_confirmed_hedgers.json", "r") as f:
    data = json.load(f)

matches = data["matches"]

coin_counter   = Counter(m["coin"] for m in matches)
wallet_counter = Counter(m["eoa"] for m in matches)

print(f"Total confirmed matches : {data['total_matches']}")
print(f"Unique wallets          : {data['unique_wallets']}\n")

print("── By asset ─────────────────────────")
for coin, count in coin_counter.most_common():
    print(f"  {coin:<10} : {count}")

print("\n── Most repeated wallets (multiple confirmed hedges) ───")
for wallet, count in wallet_counter.most_common(10):
    if count > 1:
        print(f"  {wallet} : {count} confirmed matches")

with open("final_confirmed_hedgers.json", "r") as f:
    pass  # already loaded above

# Save a clean summary
summary = {
    "total_matches": data["total_matches"],
    "unique_wallets": data["unique_wallets"],
    "by_asset": dict(coin_counter.most_common()),
    "top_repeat_wallets": {w: c for w, c in wallet_counter.most_common(10) if c > 1}
}
with open("final_summary_stats.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"\n✅ Saved summary to final_summary_stats.json")
