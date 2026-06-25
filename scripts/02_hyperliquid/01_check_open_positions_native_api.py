import requests
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

os.chdir(r"C:\Users\Etimfon\Desktop")

# ── CONFIG ───────────────────────────────────────────────
HL_API           = "https://api.hyperliquid.xyz/info"
EOA_FILE         = "eoa_wallets.json"
OUTPUT_FILE      = "hl_open_positions.json"
CHECKPOINT_FILE  = "hl_checkpoint.json"
SAVE_EVERY       = 500
MAX_WORKERS      = 8        # ~8 req/sec keeps us safely under the 10/sec cap

HEADERS = {"Content-Type": "application/json"}


# ── Step 1: Discover all active dexes (main + every HIP-3 dex) ──
def get_active_dexes():
    print("Fetching active perp DEXs (main + HIP-3 builders)...")
    resp = requests.post(HL_API, json={"type": "perpDexs"},
                          headers=HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    all_dexes = [""]  # "" = main Hyperliquid perp dex
    for d in data:
        if isinstance(d, dict) and d.get("name"):
            all_dexes.append(d["name"])

    # First pass: only main + xyz (trade.xyz — directly maps to our
    # Polymarket Finance markets: stocks, commodities, indices).
    # The other builder dexes (flx, vntl, hyna, km, abcd, cash, para)
    # can be scanned in a second pass later if needed.
    priority_dexes = [d for d in all_dexes if d in ("", "xyz")]

    print(f"  All dexes found     : {[d if d else 'main' for d in all_dexes]}")
    print(f"  Scanning this pass  : {[d if d else 'main' for d in priority_dexes]}")
    print(f"  (Remaining {len(all_dexes) - len(priority_dexes)} dexes can be "
          f"scanned in a second pass later)\n")
    return priority_dexes


# ── Step 2: Check one wallet across all dexes ────────────
def check_wallet(address, dexes):
    open_positions = {}   # dex_label -> [coins]
    for dex in dexes:
        payload = {"type": "clearinghouseState", "user": address}
        if dex:
            payload["dex"] = dex

        for attempt in range(3):
            try:
                resp = requests.post(HL_API, json=payload,
                                      headers=HEADERS, timeout=10)
                if resp.status_code == 429:
                    time.sleep(3 * (attempt + 1))
                    continue
                if not resp.ok:
                    break

                data = resp.json()
                positions = data.get("assetPositions", [])
                coins = []
                for p in positions:
                    pos = p.get("position", {})
                    szi = pos.get("szi", "0")
                    try:
                        if float(szi) != 0:
                            coins.append(pos.get("coin"))
                    except (TypeError, ValueError):
                        pass

                if coins:
                    open_positions[dex if dex else "main"] = coins
                break

            except Exception:
                time.sleep(1)
                continue

    return address, open_positions


# ── Load / Save checkpoint ───────────────────────────────
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"completed": {}}

def save_checkpoint(completed):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"completed": completed}, f)


# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":

    # Load Polymarket EOAs
    with open(EOA_FILE, "r") as f:
        eoa_data = json.load(f)
    all_eoas = list(set(a.lower() for a in eoa_data.get("eoa_addresses", [])))
    print(f"Loaded {len(all_eoas):,} Polymarket EOAs\n")

    # Get all active dexes dynamically
    dexes = get_active_dexes()

    # Resume from checkpoint if exists
    checkpoint = load_checkpoint()
    completed  = checkpoint["completed"]

    remaining = [a for a in all_eoas if a not in completed]
    total     = len(all_eoas)

    if completed:
        print(f"Resuming — {len(completed):,} already checked\n")

    print(f"Remaining   : {len(remaining):,}")
    print(f"Dexes/wallet: {len(dexes)}")
    print(f"Workers     : {MAX_WORKERS}")
    print(f"Est. time   : ~{(len(remaining) * len(dexes) / MAX_WORKERS) / 60:.0f} minutes\n")

    done = len(completed)
    has_open_count = sum(1 for v in completed.values() if v)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_wallet, addr, dexes): addr
                   for addr in remaining}

        for future in as_completed(futures):
            address, positions = future.result()
            completed[address] = positions
            done += 1

            if positions:
                has_open_count += 1
                dex_summary = ", ".join(
                    f"{d}:{','.join(c)}" for d, c in positions.items())
                print(f"[{done:,}/{total:,}] {address[:14]}... "
                      f"✅ OPEN POSITION → {dex_summary}")
            else:
                if done % 50 == 0:  # don't spam every "no position" line
                    print(f"[{done:,}/{total:,}] {address[:14]}... "
                          f"no open position")

            if done % SAVE_EVERY == 0:
                save_checkpoint(completed)
                print(f"  💾 Checkpoint saved — {done:,}/{total:,} done, "
                      f"{has_open_count:,} wallets with open positions so far\n")

    # Final save
    save_checkpoint(completed)

    overlap_wallets = {addr: pos for addr, pos in completed.items() if pos}

    with open(OUTPUT_FILE, "w") as f:
        json.dump({
            "polymarket_eoas_checked": len(all_eoas),
            "dexes_checked":           dexes,
            "wallets_with_open_positions": len(overlap_wallets),
            "overlap_wallets":         overlap_wallets
        }, f, indent=2)

    print(f"\n✅ Done!")
    print(f"   Polymarket EOAs checked        : {len(all_eoas):,}")
    print(f"   Wallets with OPEN HL positions  : {len(overlap_wallets):,}")
    print(f"   Saved to                       : {OUTPUT_FILE}")
