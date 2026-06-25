import requests
import json
import time
import os
from web3 import Web3
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── CONFIG ───────────────────────────────────────────────
POLYGON_RPC      = "https://polygon-mainnet.g.alchemy.com/v2/p9yHkU0VWVk-F_4XfDXfk"
WALLETS_FILE     = "unique_wallets.json"
OUTPUT_FILE      = "eoa_wallets.json"
CHECKPOINT_FILE  = "resolve_checkpoint.json"
SAVE_EVERY       = 200
MAX_WORKERS      = 30        # parallel threads

# ── Connect to Polygon ───────────────────────────────────
w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))

SAFE_ABI = [{
    "inputs": [],
    "name": "getOwners",
    "outputs": [{"type": "address[]", "name": ""}],
    "stateMutability": "view",
    "type": "function"
}]


# ── Method 1: Gnosis Safe (MetaMask users) ───────────────
def resolve_via_safe(proxy_address):
    try:
        checksum = Web3.to_checksum_address(proxy_address)
        contract = w3.eth.contract(address=checksum, abi=SAFE_ABI)
        owners   = contract.functions.getOwners().call()
        if owners:
            return owners[0].lower(), "safe"
    except:
        pass
    return None, None


# ── Method 2: CLOB API (Magic/email users) ───────────────
def resolve_via_clob(proxy_address):
    try:
        resp = requests.get(
            f"https://clob.polymarket.com/profile/{proxy_address}",
            timeout=5
        )
        if resp.ok:
            data = resp.json()
            eoa  = data.get("eoa") or data.get("owner") or data.get("address")
            if eoa:
                return eoa.lower(), "clob"
    except:
        pass
    return None, None


# ── Resolve one proxy → EOA ──────────────────────────────
def resolve_proxy(proxy_address):
    eoa, method = resolve_via_safe(proxy_address)
    if eoa:
        return proxy_address, eoa, method
    eoa, method = resolve_via_clob(proxy_address)
    if eoa:
        return proxy_address, eoa, method
    return proxy_address, None, "unresolved"


# ── Load / Save checkpoint ───────────────────────────────
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"completed": {}, "unresolved": []}

def save_checkpoint(completed, unresolved):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"completed": completed,
                   "unresolved": list(unresolved)}, f)


# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":

    if not w3.is_connected():
        print("❌ Could not connect to Polygon. Check your Alchemy RPC key.")
        exit()
    print(f"✅ Connected to Polygon (block #{w3.eth.block_number})\n")

    with open(WALLETS_FILE, "r") as f:
        proxy_wallets = json.load(f)
    print(f"Loaded {len(proxy_wallets):,} proxy wallets\n")

    checkpoint  = load_checkpoint()
    completed   = checkpoint["completed"]
    unresolved  = set(checkpoint["unresolved"])

    if completed:
        print(f"Resuming — {len(completed):,} already resolved\n")

    remaining = [p for p in proxy_wallets
                 if p not in completed and p not in unresolved]
    total     = len(proxy_wallets)

    print(f"Remaining  : {len(remaining):,}")
    print(f"Workers    : {MAX_WORKERS}")
    print(f"Est. time  : ~{(len(remaining) * 0.3 / MAX_WORKERS) / 60:.0f} minutes\n")

    done_count = len(completed) + len(unresolved)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(resolve_proxy, p): p for p in remaining}

        for future in as_completed(futures):
            proxy, eoa, method = future.result()
            done_count += 1

            if eoa:
                completed[proxy] = {"eoa": eoa, "method": method}
                status = f"→ {eoa[:14]}... ({method})"
            else:
                unresolved.add(proxy)
                status = "→ unresolved"

            print(f"[{done_count:,}/{total:,}] {proxy[:14]}... {status}")

            if done_count % SAVE_EVERY == 0:
                save_checkpoint(completed, unresolved)
                resolved_pct = len(completed) / done_count * 100
                print(f"  💾 Checkpoint — {len(completed):,} resolved "
                      f"({resolved_pct:.0f}%), {len(unresolved):,} unresolved")

    # Final output
    eoa_list = list(set(v["eoa"] for v in completed.values()))

    with open(OUTPUT_FILE, "w") as f:
        json.dump({
            "eoa_addresses":    eoa_list,
            "proxy_to_eoa_map": completed,
            "unresolved":       list(unresolved)
        }, f, indent=2)

    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print(f"\n✅ Done!")
    print(f"   Total proxies      : {len(proxy_wallets):,}")
    print(f"   Resolved to EOA    : {len(completed):,}")
    print(f"   Unresolved         : {len(unresolved):,}")
    print(f"   Unique EOAs found  : {len(eoa_list):,}")
    print(f"   Saved to           : {OUTPUT_FILE}")
