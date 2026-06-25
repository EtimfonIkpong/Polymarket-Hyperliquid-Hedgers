import json
import os
import csv

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("final_episode_count.json", "r") as f:
    episodes = json.load(f)

with open("eoa_wallets.json", "r") as f:
    eoa_data = json.load(f)

# Get confirmed hedger EOAs
hedger_eoas = set(p["eoa"] for p in episodes["pairs"])

# Reverse map: EOA → proxy wallets
eoa_to_proxies = {}
for proxy, info in eoa_data["proxy_to_eoa_map"].items():
    eoa = info["eoa"]
    if eoa in hedger_eoas:
        if eoa not in eoa_to_proxies:
            eoa_to_proxies[eoa] = []
        eoa_to_proxies[eoa].append(proxy)

# Flatten to list of proxy wallets
hedger_proxies = []
for eoa, proxies in eoa_to_proxies.items():
    for proxy in proxies:
        hedger_proxies.append({
            "proxy_wallet": proxy,
            "eoa": eoa
        })

# Save as CSV for Dune upload
with open("hedger_proxy_wallets.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["proxy_wallet", "eoa"])
    writer.writeheader()
    writer.writerows(hedger_proxies)

print(f"✅ Confirmed hedger EOAs    : {len(hedger_eoas)}")
print(f"   With resolved proxies   : {len(eoa_to_proxies)}")
print(f"   Total proxy wallets     : {len(hedger_proxies)}")
print(f"   Saved to                : hedger_proxy_wallets.csv")
print(f"\nUpload hedger_proxy_wallets.csv to Dune as a dataset,")
print(f"then use it in the overlay query.")
