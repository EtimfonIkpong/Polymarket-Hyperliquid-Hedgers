import json
import os
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("final_confirmed_hedgers.json", "r") as f:
    data = json.load(f)

matches = data["matches"]

# The real unit of analysis: unique (wallet, asset) relationships
wallet_asset_pairs = set()
pair_market_count  = defaultdict(int)

for m in matches:
    pair = (m["eoa"], m["coin"])
    wallet_asset_pairs.add(pair)
    pair_market_count[pair] += 1

print(f"{'─'*55}")
print(f"Raw market-level matches      : {len(matches):,}")
print(f"Unique wallets                : "
      f"{len(set(m['eoa'] for m in matches)):,}")
print(f"Unique (wallet, asset) pairs  : {len(wallet_asset_pairs):,}")
print(f"{'─'*55}")
print(f"\n→ {len(wallet_asset_pairs)} is the cleanest number to report:")
print(f"  each one represents one genuine wallet-asset hedging")
print(f"  relationship, regardless of how many overlapping")
print(f"  Polymarket price-ladder markets it was split across.\n")

# Distribution: how many markets per relationship (to show the
# price-ladder effect quantitatively)
counts = sorted(pair_market_count.values(), reverse=True)
print("Markets-per-relationship distribution:")
print(f"  1 market   : {sum(1 for c in counts if c == 1)}")
print(f"  2-5 markets: {sum(1 for c in counts if 2 <= c <= 5)}")
print(f"  6+ markets : {sum(1 for c in counts if c >= 6)}")

with open("final_episode_count.json", "w") as f:
    json.dump({
        "raw_matches": len(matches),
        "unique_wallets": len(set(m['eoa'] for m in matches)),
        "unique_wallet_asset_pairs": len(wallet_asset_pairs),
        "pairs": [{"eoa": w, "coin": c, "market_count": pair_market_count[(w,c)]}
                  for w, c in wallet_asset_pairs]
    }, f, indent=2)

print(f"\n✅ Saved to final_episode_count.json")
