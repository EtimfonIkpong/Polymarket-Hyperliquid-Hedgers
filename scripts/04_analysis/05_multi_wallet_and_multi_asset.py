import json
import os
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

# ── Load data ─────────────────────────────────────────────
with open("eoa_wallets.json", "r") as f:
    eoa_data = json.load(f)

with open("final_episode_count.json", "r") as f:
    episodes = json.load(f)

# ── Q3a: Which EOAs control MULTIPLE Polymarket proxy wallets? ──
eoa_to_proxies = defaultdict(list)
for proxy, info in eoa_data["proxy_to_eoa_map"].items():
    eoa_to_proxies[info["eoa"]].append(proxy)

multi_proxy_eoas = {eoa: proxies for eoa, proxies in eoa_to_proxies.items()
                     if len(proxies) > 1}

print(f"{'─'*55}")
print(f"Q3: Wallets that funded MULTIPLE Polymarket accounts")
print(f"{'─'*55}")
print(f"Total EOAs with >1 Polymarket proxy: {len(multi_proxy_eoas):,}")

# Now check: of OUR 158 confirmed hedgers, how many fall into this?
confirmed_eoas = set(p["eoa"] for p in episodes["pairs"])
confirmed_multi_proxy = {eoa: proxies for eoa, proxies in multi_proxy_eoas.items()
                          if eoa in confirmed_eoas}

print(f"Of our 158 confirmed hedgers, how many run multiple "
      f"Polymarket accounts: {len(confirmed_multi_proxy)}")
for eoa, proxies in list(confirmed_multi_proxy.items())[:10]:
    print(f"  {eoa} → {len(proxies)} Polymarket proxies: {proxies}")

# ── Q4: Which wallets hedge MULTIPLE different assets? ───
wallet_assets = defaultdict(set)
for pair in episodes["pairs"]:
    wallet_assets[pair["eoa"]].add(pair["coin"])

multi_asset_wallets = {w: assets for w, assets in wallet_assets.items()
                        if len(assets) > 1}

print(f"\n{'─'*55}")
print(f"Q4: Wallets hedging MULTIPLE different assets")
print(f"{'─'*55}")
print(f"Total: {len(multi_asset_wallets)} of 158 wallets\n")
for w, assets in sorted(multi_asset_wallets.items(),
                        key=lambda x: -len(x[1]))[:15]:
    print(f"  {w} → {sorted(assets)}")

# ── Save results ──────────────────────────────────────────
with open("multi_wallet_multi_asset_results.json", "w") as f:
    json.dump({
        "total_eoas_with_multiple_polymarket_proxies": len(multi_proxy_eoas),
        "confirmed_hedgers_with_multiple_proxies": confirmed_multi_proxy,
        "wallets_hedging_multiple_assets": {w: sorted(a) for w, a in multi_asset_wallets.items()},
    }, f, indent=2)

print(f"\n✅ Saved to multi_wallet_multi_asset_results.json")
