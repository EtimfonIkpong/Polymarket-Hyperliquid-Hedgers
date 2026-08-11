import requests
import json
import os
import time
import re
from collections import defaultdict, Counter

os.chdir(r"C:\Users\Etimfon\Desktop")

DATA_API_URL = "https://data-api.polymarket.com"

# ── Load what we need ─────────────────────────────────────
with open("enriched_matches.json", "r") as f:
    enriched = json.load(f)

# Unique (proxy, conditionId, question) combinations
unique_markets = {}
for m in enriched:
    proxy = m.get("proxy")
    cid   = m.get("conditionId")
    if proxy and cid:
        unique_markets[(proxy, cid)] = m.get("question", "")

print(f"Unique (proxy, market) pairs to re-fetch: {len(unique_markets)}\n")


# ══════════════════════════════════════════════════════════
# STEP 1: Question polarity — is "Yes" bullish or bearish?
# ══════════════════════════════════════════════════════════
def classify_question_polarity(question):
    """
    Returns:
        'bullish'  — Yes = bullish (price goes up / event is positive)
        'bearish'  — Yes = bearish (price goes down / dip / below)
        'neutral'  — Yes = neither (range, between, tie-breaker)
    """
    q = question.lower()

    # ── Bearish-if-yes patterns ───────────────────────────
    bearish_patterns = [
        r'dip to', r'fall to', r'drop to', r'close below',
        r'close at <', r'close under', r'below \$',
        r'close between',       # range = neutral but treated as bearish-if-yes
        r'finish below', r'end below', r'trade below',
        r'less than \$', r'under \$',
        r'fall below', r'drop below',
        r'close at or below', r'at or below',
        r'<\$', r'< \$',
    ]

    # ── Neutral patterns ──────────────────────────────────
    neutral_patterns = [
        r'close between \$\d+ and \$\d+',
        r'between \$\d+ and \$\d+',
        r'up or down',
        r'higher or lower',
    ]

    # ── Bullish-if-yes patterns ───────────────────────────
    bullish_patterns = [
        r'hit \$', r'reach \$', r'above \$', r'exceed \$',
        r'cross \$', r'surpass \$', r'top \$',
        r'close above', r'finish above', r'end above',
        r'trade above', r'at or above',
        r'first to \$', r'beat \$',
        r'largest company', r'biggest company',
        r'highest market cap',
        r'>\$', r'> \$',
        r'up on', r'finish week',   # "Up or Down" daily markets
    ]

    # Check neutral first (most specific)
    for pat in neutral_patterns:
        if re.search(pat, q):
            return "neutral"

    # Then bearish
    for pat in bearish_patterns:
        if re.search(pat, q):
            return "bearish"

    # Then bullish
    for pat in bullish_patterns:
        if re.search(pat, q):
            return "bullish"

    # Default: most Finance markets are bullish-framed
    return "bullish"


# ══════════════════════════════════════════════════════════
# STEP 2: Re-fetch trades keeping outcome + outcomeIndex
# ══════════════════════════════════════════════════════════
def fetch_trades_with_outcome(condition_id):
    trades, offset, limit = [], 0, 500
    while True:
        resp = requests.get(
            f"{DATA_API_URL}/trades",
            params={"market": condition_id, "limit": limit, "offset": offset},
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


print("Re-fetching trade history with outcome fields...\n")

# Group by conditionId to avoid re-fetching the same market multiple times
cid_to_proxies = defaultdict(set)
for (proxy, cid) in unique_markets:
    cid_to_proxies[cid].add(proxy)

# New storage — keyed by (proxy, cid) like before but richer fields
new_pm_history = defaultdict(lambda: defaultdict(list))
unique_cids = list(cid_to_proxies.keys())

for i, cid in enumerate(unique_cids):
    proxies  = cid_to_proxies[cid]
    question = next(v for (p, c), v in unique_markets.items() if c == cid)
    polarity = classify_question_polarity(question)

    resp_trades = fetch_trades_with_outcome(cid)

    # Filter to our wallets only
    relevant = [t for t in resp_trades
                if isinstance(t, dict) and
                (t.get("proxyWallet") or "").lower() in proxies]

    for t in relevant:
        proxy = (t.get("proxyWallet") or "").lower()
        side  = (t.get("side") or "").lower()

        if "buy" not in side:
            continue   # only care about buy trades for direction

        outcome_label = t.get("outcome") or ""
        outcome_idx   = t.get("outcomeIndex")

        # Determine token bought
        # outcomeIndex 0 = first listed outcome (usually "Yes")
        # outcomeIndex 1 = second listed outcome (usually "No")
        if outcome_label:
            token_bought = outcome_label.strip()
        elif outcome_idx is not None:
            token_bought = "Yes" if int(outcome_idx) == 0 else "No"
        else:
            token_bought = "Unknown"

        # True direction = polarity + token
        if token_bought == "Yes":
            if polarity == "bullish":   true_dir = "Bullish"
            elif polarity == "bearish": true_dir = "Bearish"
            else:                       true_dir = "Neutral"
        elif token_bought == "No":
            if polarity == "bullish":   true_dir = "Bearish"   # No on bullish = bearish
            elif polarity == "bearish": true_dir = "Bullish"   # No on bearish = bullish
            else:                       true_dir = "Neutral"
        else:
            true_dir = "Unknown"

        new_pm_history[proxy][cid].append({
            "side":         t.get("side"),
            "timestamp":    t.get("timestamp"),
            "size":         t.get("size"),
            "price":        t.get("price"),
            "outcome":      outcome_label,
            "outcomeIndex": outcome_idx,
            "token_bought": token_bought,
            "true_direction": true_dir,
            "question_polarity": polarity,
        })

    print(f"[{i+1}/{len(unique_cids)}] {question[:55]}...")
    print(f"  polarity: {polarity} | relevant trades: {len(relevant)}")
    time.sleep(0.2)

# Save enriched trade history
with open("pm_trade_history_with_direction.json", "w") as f:
    json.dump({p: dict(c) for p, c in new_pm_history.items()}, f, indent=2)

print(f"\n✅ Saved to pm_trade_history_with_direction.json")


# ══════════════════════════════════════════════════════════
# STEP 3: Rerun direction analysis with correct directions
# ══════════════════════════════════════════════════════════
import pandas as pd

with open("sequence_analysis_results.json", "r") as f:
    sequences = json.load(f)

fills = pd.read_parquet("xyz_fills_with_pnl.parquet")
fills["timestamp"] = pd.to_datetime(fills["timestamp"], format="mixed", utc=True)

eoa_q_to_market = {(m["eoa"], m["question"]): m for m in enriched}

direction_counter  = Counter()
hl_side_counter    = Counter()
pm_dir_counter     = Counter()
token_counter      = Counter()
polarity_counter   = Counter()
unknown_count      = 0

for r in sequences:
    market = eoa_q_to_market.get((r["eoa"], r["question"]))
    if not market:
        continue

    # HL direction
    mask = (
        (fills["address"] == r["eoa"]) &
        (fills["coin"].str.contains(r["coin"], na=False)) &
        (fills["timestamp"] >= pd.Timestamp(r["hl_open"])) &
        (fills["timestamp"] <= pd.Timestamp(r["hl_close"]))
    )
    subset = fills[mask]
    if subset.empty:
        continue
    hl_side = "Long" if subset.iloc[0]["side"] in ("B","buy","Buy") else "Short"
    hl_side_counter[hl_side] += 1

    # PM direction — now using true_direction
    proxy = market.get("proxy")
    cid   = market.get("conditionId")
    trades = new_pm_history.get(proxy, {}).get(cid, [])

    if not trades:
        unknown_count += 1
        continue

    # Use the most common true direction across buys
    directions = [t["true_direction"] for t in trades
                  if t.get("true_direction") != "Unknown"]
    tokens     = [t["token_bought"] for t in trades
                  if t.get("token_bought") != "Unknown"]
    polarities = [t["question_polarity"] for t in trades]

    if not directions:
        unknown_count += 1
        continue

    pm_dir   = Counter(directions).most_common(1)[0][0]
    token    = Counter(tokens).most_common(1)[0][0] if tokens else "Unknown"
    polarity = Counter(polarities).most_common(1)[0][0]

    pm_dir_counter[pm_dir] += 1
    token_counter[token]   += 1
    polarity_counter[polarity] += 1

    direction_counter[f"HL: {hl_side:<5}  |  PM: {pm_dir}"] += 1

total = sum(direction_counter.values())

# Coherence split
same_dir   = (direction_counter.get("HL: Long   |  PM: Bullish", 0) +
              direction_counter.get("HL: Short  |  PM: Bearish", 0))
opposite   = (direction_counter.get("HL: Long   |  PM: Bearish", 0) +
              direction_counter.get("HL: Short  |  PM: Bullish", 0))
neutral    = direction_counter.get("HL: Long   |  PM: Neutral", 0) + \
             direction_counter.get("HL: Short  |  PM: Neutral", 0)

print(f"\n{'='*60}")
print(f"CORRECTED DIRECTIONAL ANALYSIS")
print(f"{'='*60}")

print(f"\nQuestion polarity breakdown:")
for pol, cnt in polarity_counter.most_common():
    print(f"  {pol:<10} : {cnt}")

print(f"\nToken actually bought:")
for tok, cnt in token_counter.most_common():
    print(f"  {tok:<10} : {cnt}")

print(f"\nHyperliquid side:")
for side, cnt in hl_side_counter.most_common():
    print(f"  {side:<8} : {cnt} ({cnt/total*100:.1f}%)")

print(f"\nPolymarket TRUE direction (polarity + token):")
for d, cnt in pm_dir_counter.most_common():
    print(f"  {d:<10} : {cnt} ({cnt/total*100:.1f}%)")

print(f"\nCombined patterns:")
for pat, cnt in direction_counter.most_common():
    print(f"  {pat:<40} : {cnt} ({cnt/total*100:.1f}%)")

print(f"\n{'─'*60}")
print(f"Total analyzed   : {total}")
print(f"Unknown/missing  : {unknown_count}")
print(f"{'─'*60}")
print(f"Genuine hedges (opposite directions) : {opposite} ({opposite/total*100:.1f}%)")
print(f"Doubling down    (same direction)    : {same_dir} ({same_dir/total*100:.1f}%)")
print(f"Neutral                              : {neutral} ({neutral/total*100:.1f}%)")

with open("direction_analysis_corrected.json", "w") as f:
    json.dump({
        "total_analyzed": total,
        "unknown_missing": unknown_count,
        "genuine_hedges": opposite,
        "doubling_down": same_dir,
        "neutral": neutral,
        "genuine_hedge_pct": round(opposite/total*100, 2),
        "doubling_down_pct": round(same_dir/total*100, 2),
        "combined_patterns": dict(direction_counter),
        "polarity_breakdown": dict(polarity_counter),
        "token_breakdown": dict(token_counter),
    }, f, indent=2)

print(f"\n✅ Saved to direction_analysis_corrected.json")
