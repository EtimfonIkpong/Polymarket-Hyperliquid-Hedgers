import requests
import json
import time
import os

# ── CONFIG ───────────────────────────────────────────────
DATA_API_URL    = "https://data-api.polymarket.com"
MARKETS_FILE    = "finance_markets.json"      # already saved from phase1.py
CHECKPOINT_FILE = "checkpoint.json"           # saves progress as we go
OUTPUT_FILE     = "markets_with_bettors.json" # final output
WALLETS_FILE    = "unique_wallets.json"        # flat list of all wallets
SAVE_EVERY      = 25                           # save progress every 25 markets


# ── Get bettor addresses for one market ─────────────────
def get_bettors(condition_id):
    wallets = set()
    offset  = 0
    limit   = 500

    while True:
        params = {
            "market": condition_id,
            "limit":  limit,
            "offset": offset
        }
        try:
            resp = requests.get(f"{DATA_API_URL}/trades", params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            print(f"    ⚠ Request failed: {e} — skipping")
            break

        if not data or not isinstance(data, list):
            break

        for trade in data:
            if not isinstance(trade, dict):
                continue
            wallet = trade.get("proxyWallet")
            if wallet:
                wallets.add(wallet)

        if len(data) < limit:
            break

        offset += limit
        time.sleep(0.2)

    return list(wallets)


# ── Load checkpoint (resume where we left off) ──────────
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"completed": [], "results": [], "all_wallets": []}


# ── Save checkpoint ──────────────────────────────────────
def save_checkpoint(checkpoint):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f)


# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":

    # Load markets
    with open(MARKETS_FILE, "r") as f:
        markets = json.load(f)
    print(f"Loaded {len(markets)} markets from {MARKETS_FILE}")

    # Load checkpoint (resume if exists)
    checkpoint    = load_checkpoint()
    completed_ids = set(checkpoint["completed"])
    results       = checkpoint["results"]
    all_wallets   = set(checkpoint["all_wallets"])

    if completed_ids:
        print(f"Resuming from checkpoint — {len(completed_ids)} markets already done\n")
    else:
        print("Starting fresh\n")

    # Filter to only markets not yet processed
    remaining = [m for m in markets if m.get("conditionId") not in completed_ids]
    total     = len(markets)

    print(f"Markets remaining : {len(remaining)}")
    print(f"Estimated time    : ~{len(remaining) * 0.5 / 60:.0f} minutes\n")

    for i, market in enumerate(remaining):
        cid      = market.get("conditionId")
        question = market.get("question", "")

        if not cid:
            continue

        wallets = get_bettors(cid)
        all_wallets.update(wallets)

        results.append({
            "question":     question,
            "conditionId":  cid,
            "startDate":    market.get("startDate"),
            "endDate":      market.get("endDate"),
            "bettors":      wallets,
            "bettor_count": len(wallets)
        })

        completed_ids.add(cid)

        done_total = len(completed_ids)
        print(f"[{done_total}/{total}] {question[:55]}... → {len(wallets)} bettors")

        # Save checkpoint every SAVE_EVERY markets
        if done_total % SAVE_EVERY == 0:
            checkpoint = {
                "completed":   list(completed_ids),
                "results":     results,
                "all_wallets": list(all_wallets)
            }
            save_checkpoint(checkpoint)
            print(f"  💾 Checkpoint saved ({done_total}/{total} done, "
                  f"{len(all_wallets)} unique wallets so far)")

        time.sleep(0.2)

    # Save final outputs
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)

    with open(WALLETS_FILE, "w") as f:
        json.dump(list(all_wallets), f, indent=2)

    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print(f"\n✅ Done!")
    print(f"   Markets processed : {len(results)}")
    print(f"   Unique wallets    : {len(all_wallets)}")
    print(f"   Saved to          : {OUTPUT_FILE} + {WALLETS_FILE}")
