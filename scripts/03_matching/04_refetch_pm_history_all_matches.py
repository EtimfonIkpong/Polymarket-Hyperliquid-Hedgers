import requests
import json
import os
import time
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

DATA_API_URL = "https://data-api.polymarket.com"

# ── Load all 323 confirmed matches ────────────────────────
with open("final_confirmed_hedgers.json", "r") as f:
    confirmed = json.load(f)

with open("eoa_wallets.json", "r") as f:
    eoa_data = json.load(f)

with open("markets_with_bettors.json", "r") as f:
    markets_raw = json.load(f)

print(f"Total confirmed matches : {len(confirmed['matches'])}")

# ── Build lookup: EOA → proxy wallets ────────────────────
eoa_to_proxies = defaultdict(list)
for proxy, info in eoa_data["proxy_to_eoa_map"].items():
    eoa_to_proxies[info["eoa"]].append(proxy)

# ── Build lookup: question → conditionId ─────────────────
question_to_cid = {}
for m in markets_raw:
    q   = m.get("question", "")
    cid = m.get("conditionId")
    if q and cid:
        question_to_cid[q] = cid

# ── Build complete set of (proxy, conditionId) pairs ──────
# For every confirmed match, find the proxy wallet(s) and conditionId
all_pairs = set()
missing_cid     = 0
missing_proxy   = 0

for match in confirmed["matches"]:
    eoa      = match["eoa"]
    question = match["question"]

    cid = question_to_cid.get(question)
    if not cid:
        missing_cid += 1
        continue

    proxies = eoa_to_proxies.get(eoa, [])
    if not proxies:
        missing_proxy += 1
        continue

    for proxy in proxies:
        all_pairs.add((proxy.lower(), cid))

print(f"Missing conditionId     : {missing_cid}")
print(f"Missing proxy           : {missing_proxy}")
print(f"Unique (proxy, cid) pairs to fetch: {len(all_pairs)}\n")

# ── Group by conditionId to minimise API calls ────────────
cid_to_proxies = defaultdict(set)
for proxy, cid in all_pairs:
    cid_to_proxies[cid].add(proxy)

print(f"Unique markets to fetch : {len(cid_to_proxies)}")
print(f"(Each fetched once regardless of how many wallets bet on it)\n")


# ── Question polarity classifier ──────────────────────────
import re

def classify_polarity(question):
    q = question.lower()
    neutral_patterns  = [
        r'close between \$\d+ and \$\d+', r'between \$\d+ and \$\d+',
        r'up or down', r'higher or lower',
    ]
    bearish_patterns  = [
        r'dip to', r'fall to', r'drop to', r'close below',
        r'close at <', r'close under', r'below \$',
        r'finish below', r'end below', r'trade below',
        r'less than \$', r'under \$', r'fall below',
        r'drop below', r'close at or below', r'<\$', r'< \$',
    ]
    bullish_patterns  = [
        r'hit \$', r'reach \$', r'above \$', r'exceed \$',
        r'cross \$', r'surpass \$', r'top \$',
        r'close above', r'finish above', r'end above',
        r'trade above', r'at or above', r'first to \$',
        r'beat \$', r'largest company', r'biggest company',
        r'highest market cap', r'>\$', r'> \$',
        r'up on', r'finish week',
    ]
    for pat in neutral_patterns:
        if re.search(pat, q): return "neutral"
    for pat in bearish_patterns:
        if re.search(pat, q): return "bearish"
    for pat in bullish_patterns:
        if re.search(pat, q): return "bullish"
    return "bullish"

# Build question→polarity map
question_to_polarity = {
    q: classify_polarity(q) for q in question_to_cid
}

# Build cid→question map
cid_to_question = {v: k for k, v in question_to_cid.items()}


# ── Fetch trades for each unique market ───────────────────
def fetch_trades(condition_id):
    trades, offset, limit = [], 0, 500
    while True:
        resp = requests.get(
            f"{DATA_API_URL}/trades",
            params={"market": condition_id,
                    "limit": limit, "offset": offset},
            timeout=15
        )
        if not resp.ok:
            break
        data = resp.json()
        if not data:
            break
        trades.extend(data)
        if len(data) < limit:
            break
        offset += limit
        time.sleep(0.15)
    return trades


print("Fetching trades for all 323 matches...\n")

# New history storage: proxy → cid → [trades with direction]
new_history    = defaultdict(lambda: defaultdict(list))
markets_done   = 0
total_relevant = 0

for cid, target_proxies in cid_to_proxies.items():
    question = cid_to_question.get(cid, "")
    polarity = classify_polarity(question)
    all_trades = fetch_trades(cid)

    relevant = [t for t in all_trades
                if isinstance(t, dict) and
                (t.get("proxyWallet") or "").lower() in target_proxies]

    for t in relevant:
        proxy = (t.get("proxyWallet") or "").lower()
        side  = (t.get("side") or "").lower()
        if "buy" not in side:
            # still store sells for bet-window end calculation
            new_history[proxy][cid].append({
                "side":      t.get("side"),
                "timestamp": t.get("timestamp"),
                "size":      t.get("size"),
                "price":     t.get("price"),
                "outcome":   t.get("outcome") or "",
                "outcomeIndex": t.get("outcomeIndex"),
                "token_bought": None,
                "true_direction": None,
                "question_polarity": polarity,
            })
            continue

        outcome_label = t.get("outcome") or ""
        outcome_idx   = t.get("outcomeIndex")

        if outcome_label:
            token = outcome_label.strip()
        elif outcome_idx is not None:
            token = "Yes" if int(outcome_idx) == 0 else "No"
        else:
            token = "Unknown"

        if token == "Yes":
            true_dir = {"bullish":"Bullish","bearish":"Bearish"}.get(polarity,"Neutral")
        elif token == "No":
            true_dir = {"bullish":"Bearish","bearish":"Bullish"}.get(polarity,"Neutral")
        else:
            true_dir = "Unknown"

        new_history[proxy][cid].append({
            "side":             t.get("side"),
            "timestamp":        t.get("timestamp"),
            "size":             t.get("size"),
            "price":            t.get("price"),
            "outcome":          outcome_label,
            "outcomeIndex":     outcome_idx,
            "token_bought":     token,
            "true_direction":   true_dir,
            "question_polarity": polarity,
        })

    total_relevant += len(relevant)
    markets_done   += 1

    if markets_done % 20 == 0 or len(relevant) > 0:
        print(f"[{markets_done}/{len(cid_to_proxies)}] "
              f"{question[:50]}... "
              f"→ {len(relevant)} relevant trades")
    time.sleep(0.2)

print(f"\nTotal markets fetched   : {markets_done}")
print(f"Total relevant trades   : {total_relevant}")

# Save
with open("pm_history_all_323.json", "w") as f:
    json.dump({p: dict(c) for p, c in new_history.items()}, f, indent=2)

print(f"\n✅ Saved to pm_history_all_323.json")
print(f"   Proxies with data : {len(new_history)}")
