import pandas as pd
import json
import os
from datetime import datetime, timezone
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

# ── Expanded keyword list — includes assets discovered in the
# ── actual trade.xyz fill data (PLTR, EUR, COPPER, CRCL, SKHX) ──
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
    "CL":       ["oil", "crude", "wti"],
    "BRENTOIL": ["oil", "crude", "brent"],
    "SP500":    ["s&p", "sp500", "s&p 500"],
    "XYZ100":   ["nasdaq"],
    "SPCX":     ["spacex"],
    "INTC":     ["intel", "intc"],
    "MSTR":     ["microstrategy", "mstr"],
    "SNDK":     ["sandisk", "sndk"],
    "MU":       ["micron"],
    "PLTR":     ["palantir", "pltr"],
    "SKHX":     ["sk hynix", "hynix", "skhx"],
    "EUR":      ["euro", "eur/usd", "eurusd"],
    "COPPER":   ["copper"],
    "CRCL":     ["circle", "crcl"],
}


def windows_overlap(a_s, a_e, b_s, b_e):
    return a_s <= b_e and b_s <= a_e


def iso_to_dt(iso_str):
    return pd.Timestamp(iso_str.replace("Z", "+00:00"))


# ── Reconstruct position open/close intervals per coin ───
def reconstruct_intervals(group_df):
    g = group_df.sort_values("timestamp")
    intervals  = []
    pos        = 0.0
    open_start = None

    for _, row in g.iterrows():
        try:
            sz = float(row["size"])
        except (TypeError, ValueError):
            sz = 0.0
        side  = row.get("side")
        delta = sz if side in ("B", "buy", "Buy") else -sz

        was_zero = (pos == 0)
        pos += delta

        if was_zero and pos != 0:
            open_start = row["timestamp"]
        elif (not was_zero) and pos == 0 and open_start is not None:
            intervals.append((open_start, row["timestamp"]))
            open_start = None

    if open_start is not None:   # still open as of last fill
        intervals.append((open_start, pd.Timestamp.now(tz="UTC")))

    return intervals


if __name__ == "__main__":

    # ── Load matched fills (small now — only 1,413 wallets) ──
    fills = pd.read_parquet("xyz_fills_matched_to_polymarket.parquet")
    fills["timestamp"] = pd.to_datetime(fills["timestamp"], utc=True)
    print(f"Loaded {len(fills):,} matched fills across "
          f"{fills['address'].nunique():,} wallets\n")

    # ── Load Polymarket bettor + EOA mapping data ────────────
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

    # ── Reconstruct intervals per (address, coin) ────────────
    print("Reconstructing position intervals per wallet/coin...")
    grouped = fills.groupby(["address", "coin"])

    confirmed = []
    checked   = 0

    for (address, coin), group_df in grouped:
        checked += 1
        clean_coin = coin.replace("xyz:", "")

        # Find matching keyword set for this coin
        keywords = COIN_KEYWORDS.get(clean_coin)
        if not keywords:
            continue

        intervals = reconstruct_intervals(group_df)
        if not intervals:
            continue

        # What did this wallet bet on, on Polymarket?
        proxies = eoa_to_proxies.get(address, [])
        for proxy in proxies:
            for market in proxy_to_markets.get(proxy, []):
                question = market.get("question", "").lower()
                if not any(kw in question for kw in keywords):
                    continue

                try:
                    w_start, w_end = market["startDate"], market["endDate"]
                    ws = iso_to_dt(w_start)
                    we = iso_to_dt(w_end)
                except Exception:
                    continue

                overlap = any(windows_overlap(s, e, ws, we)
                              for s, e in intervals)

                if overlap:
                    confirmed.append({
                        "eoa":        address,
                        "coin":       clean_coin,
                        "question":   market.get("question"),
                        "market_window": f"{w_start} → {w_end}",
                    })

        if checked % 200 == 0:
            print(f"  ...checked {checked:,} wallet/coin groups, "
                  f"{len(confirmed)} confirmed so far")

    unique_wallets = set(c["eoa"] for c in confirmed)

    print(f"\n{'─'*55}")
    print(f"✅ FINAL RESULT")
    print(f"   Wallet/coin groups checked : {checked:,}")
    print(f"   Confirmed temporal matches : {len(confirmed):,}")
    print(f"   Unique confirmed wallets   : {len(unique_wallets):,}")
    print(f"{'─'*55}")

    with open("final_confirmed_hedgers.json", "w") as f:
        json.dump({
            "total_matches":  len(confirmed),
            "unique_wallets": len(unique_wallets),
            "matches":        confirmed
        }, f, indent=2)

    print(f"\nSaved to final_confirmed_hedgers.json")
