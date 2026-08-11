import requests
import json
import time

# ── CONFIG ──────────────────────────────────────────────
# ⚠️  Replace this with your NEW API key (the old one was shared publicly)
GRAPH_API_KEY = "99fda5b6b16877c17dca59c77f6eb0f3"
GAMMA_URL     = "https://gamma-api.polymarket.com"
DATA_API_URL  = "https://data-api.polymarket.com"


# ── STEP 1: Get Finance markets from Gamma API ───────────
# ── Keywords that map to HIP-3 assets on trade.xyz ──────
HIP3_KEYWORDS = [
    # Stocks
    "nvidia", "nvda", "tesla", "tsla", "apple", "aapl", "amazon", "amzn",
    "google", "googl", "microsoft", "msft", "meta", "netflix", "nflx",
    "s&p", "sp500", "nasdaq", "dow jones",
    # Commodities
    "gold", "silver", "oil", "crude", "brent", "wti",
    # Macro
    "fed", "interest rate", "inflation", "cpi", "gdp", "recession",
    "rate cut", "rate hike", "federal reserve"
]

def matches_hip3(question):
    q = question.lower()
    return any(kw in q for kw in HIP3_KEYWORDS)


def get_finance_markets():
    print("Fetching Finance markets from Gamma API...")
    markets = []
    offset  = 0
    limit   = 100
    MAX_MARKETS = 2000  # safety cap

    while len(markets) < MAX_MARKETS:
        params = {
            "tag_id": 120,
            "closed": "true",
            "active": "true",
            "limit":  limit,
            "offset": offset
        }
        resp = requests.get(f"{GAMMA_URL}/markets", params=params)
        data = resp.json()

        if not data:
            break

        for m in data:
            if not isinstance(m, dict):
                continue
            question = m.get("question", "")
            if not matches_hip3(question):  # only keep HIP-3 relevant markets
                continue
            markets.append({
                "question":    question,
                "conditionId": m.get("conditionId"),
                "startDate":   m.get("startDate"),
                "endDate":     m.get("endDate"),
                "closed":      m.get("closed"),
                "tags":        [t.get("label") for t in m.get("tags", [])]
            })

        print(f"  Scanned {offset + len(data)} total | HIP-3 relevant: {len(markets)}")

        if len(data) < limit:
            break

        offset += limit
        time.sleep(0.3)

    return markets


# ── STEP 2: Get actual bettor addresses from Data API ────
# (The subgraph only tracks liquidity providers, not bettors.
#  The Data API tracks every real trade with wallet addresses.)
def get_bettors(condition_id):
    wallets = set()
    offset  = 0
    limit   = 500

    while True:
        params = {
            "market": condition_id,  # conditionId of the market
            "limit":  limit,
            "offset": offset
        }
        resp = requests.get(f"{DATA_API_URL}/trades", params=params)  # /trades not /activity
        
        # debug: print raw response for first call
        if offset == 0:
            print(f"    API status: {resp.status_code} | Records: {len(resp.json()) if resp.ok else 'error'}")

        data = resp.json()

        if not data or not isinstance(data, list):
            break

        for trade in data:
            if not isinstance(trade, dict):
                continue
            wallet = trade.get("proxyWallet")  # correct field name
            if wallet:
                wallets.add(wallet)

        if len(data) < limit:
            break

        offset += limit
        time.sleep(0.2)

    return list(wallets)


# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":

    # Step 1: Get all Finance markets
    markets = get_finance_markets()
    print(f"\nTotal Finance markets found: {len(markets)}")

    with open("finance_markets.json", "w") as f:
        json.dump(markets, f, indent=2)
    print("Saved to finance_markets.json")

    # Step 2: Get bettors for ALL markets
    print("\nFetching bettors from Data API for all markets...")
    results    = []
    all_wallets = set()

    for i, market in enumerate(markets):
        cid = market.get("conditionId")
        if not cid:
            continue

        wallets = get_bettors(cid)
        all_wallets.update(wallets)

        results.append({
            "question":     market["question"],
            "conditionId":  cid,
            "startDate":    market["startDate"],
            "endDate":      market["endDate"],
            "bettors":      wallets,
            "bettor_count": len(wallets)
        })

        print(f"[{i+1}/{len(markets)}] {market['question'][:60]}... → {len(wallets)} bettors")
        time.sleep(0.2)

    # Save full results
    with open("markets_with_bettors.json", "w") as f:
        json.dump(results, f, indent=2)

    # Save flat list of every unique wallet seen
    with open("unique_wallets.json", "w") as f:
        json.dump(list(all_wallets), f, indent=2)

    print(f"\n✅ Done!")
    print(f"   Markets processed : {len(results)}")
    print(f"   Unique wallets    : {len(all_wallets)}")
    print(f"   Saved to          : markets_with_bettors.json + unique_wallets.json")