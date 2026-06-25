import requests
import json
import os
import time
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

DATA_API_URL = "https://data-api.polymarket.com"

# ── Step 1: Re-derive conditionId + proxy for each confirmed match ──
with open("final_confirmed_hedgers.json", "r") as f:
    confirmed = json.load(f)["matches"]

with open("eoa_wallets.json", "r") as f:
    eoa_data = json.load(f)
eoa_to_proxies = defaultdict(list)
for proxy, info in eoa_data["proxy_to_eoa_map"].items():
    eoa_to_proxies[info["eoa"]].append(proxy)

with open("markets_with_bettors.json", "r") as f:
    markets = json.load(f)

proxy_to_markets = defaultdict(list)
for m in markets:
    for bettor in m.get("bettors", []):
        proxy_to_markets[bettor.lower()].append(m)

enriched = []
for c in confirmed:
    eoa = c["eoa"]
    for proxy in eoa_to_proxies.get(eoa, []):
        match_found = False
        for m in proxy_to_markets.get(proxy, []):
            if m.get("question") == c["question"]:
                enriched.append({**c, "proxy": proxy,
                                  "conditionId": m.get("conditionId")})
                match_found = True
                break
        if match_found:
            break

print(f"Re-derived market details for {len(enriched)}/{len(confirmed)} matches")

# Group by unique market to minimize API calls
condition_to_proxies = defaultdict(set)
for m in enriched:
    if m.get("conditionId"):
        condition_to_proxies[m["conditionId"]].add(m["proxy"])

print(f"Unique Polymarket markets to query: {len(condition_to_proxies)}\n")

with open("enriched_matches.json", "w") as f:
    json.dump(enriched, f, indent=2)


# ── Step 2: Pull ALL trades for each unique market ───────
def get_trades_for_market(condition_id):
    trades, offset, limit = [], 0, 500
    while True:
        resp = requests.get(f"{DATA_API_URL}/trades",
                            params={"market": condition_id,
                                    "limit": limit, "offset": offset},
                            timeout=15)
        if not resp.ok:
            break
        data = resp.json()
        if not data:
            break

        if offset == 0 and data:
            print(f"    (sample trade fields: {list(data[0].keys())})")

        trades.extend(data)
        if len(data) < limit:
            break
        offset += limit
        time.sleep(0.15)
    return trades


proxy_trade_history = defaultdict(lambda: defaultdict(list))

for i, (cid, proxies) in enumerate(condition_to_proxies.items()):
    print(f"[{i+1}/{len(condition_to_proxies)}] market {cid[:16]}...")
    trades = get_trades_for_market(cid)

    relevant = [t for t in trades if isinstance(t, dict) and
                (t.get("proxyWallet") or "").lower() in proxies]

    for t in relevant:
        pw = t["proxyWallet"].lower()
        proxy_trade_history[pw][cid].append({
            "side":      t.get("side"),
            "timestamp": t.get("timestamp"),
            "size":      t.get("size"),
            "price":     t.get("price"),
        })

    print(f"    → {len(trades)} total trades, {len(relevant)} from our wallets")
    time.sleep(0.2)

with open("pm_trade_history_for_matches.json", "w") as f:
    json.dump({pw: dict(cids) for pw, cids in proxy_trade_history.items()},
              f, indent=2)

print(f"\n✅ Saved to pm_trade_history_for_matches.json")
