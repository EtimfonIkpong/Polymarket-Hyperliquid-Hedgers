import json
import os
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

COIN_KEYWORDS = {
    "NVDA":     ["nvidia", "nvda"],
    "TSLA":     ["tesla", "tsla"],
    "AAPL":     ["apple", "aapl"],
    "AMZN":     ["amazon", "amzn"],
    "GOOGL":    ["google", "googl", "alphabet"],
    "META":     ["meta", "facebook"],
    "MSFT":     ["microsoft", "msft"],
    "GOLD":     ["gold"],
    "SILVER":   ["silver"],
    "CL":       ["oil", "crude", "brent", "wti"],
    "SP500":    ["s&p", "sp500", "s&p 500"],
    "XYZ100":   ["nasdaq"],
    "SPCX":     ["spacex"],
    "INTC":     ["intel", "intc"],
    "MSTR":     ["microstrategy", "mstr"],
}


if __name__ == "__main__":

    with open("eoa_wallets.json", "r") as f:
        eoa_data = json.load(f)
    proxy_to_eoa = {p: info["eoa"] for p, info in
                    eoa_data["proxy_to_eoa_map"].items()}

    with open("markets_with_bettors.json", "r") as f:
        markets = json.load(f)

    print(f"Scanning {len(markets)} markets for asset keyword matches...\n")

    candidates   = []
    coin_counter = defaultdict(int)

    for market in markets:
        question = market.get("question", "").lower()
        matched_coin = None

        for coin, keywords in COIN_KEYWORDS.items():
            if any(kw in question for kw in keywords):
                matched_coin = coin
                break

        if not matched_coin:
            continue

        for proxy in market.get("bettors", []):
            eoa = proxy_to_eoa.get(proxy)
            if not eoa:
                continue   # unresolved proxy — skip

            candidates.append({
                "eoa":          eoa,
                "coin":         matched_coin,
                "question":     market.get("question"),
                "market_window": f"{market.get('startDate')} → {market.get('endDate')}",
            })
            coin_counter[matched_coin] += 1

    unique_eoas = set(c["eoa"] for c in candidates)

    print(f"{'─'*50}")
    print(f"Total candidate matches      : {len(candidates):,}")
    print(f"Unique wallets to check on HL: {len(unique_eoas):,}")
    print(f"{'─'*50}\n")

    print("By asset:")
    for coin, count in sorted(coin_counter.items(),
                              key=lambda x: -x[1]):
        print(f"  {coin:<8} : {count}")

    with open("hl_check_candidates.json", "w") as f:
        json.dump(candidates, f, indent=2)

    print(f"\n✅ Saved {len(candidates)} candidates to "
          f"hl_check_candidates.json")
