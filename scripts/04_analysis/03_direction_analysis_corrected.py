import pandas as pd
import json
import os
from collections import Counter, defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

# ── Load data ─────────────────────────────────────────────
with open("tight_confirmed_v2.json", "r") as f:
    tight = json.load(f)

with open("pm_history_all_323.json", "r") as f:
    pm_history = json.load(f)

with open("eoa_wallets.json", "r") as f:
    eoa_data = json.load(f)

with open("markets_with_bettors.json", "r") as f:
    markets_raw = json.load(f)

fills = pd.read_parquet("xyz_fills_with_pnl.parquet")
fills["timestamp"] = pd.to_datetime(fills["timestamp"], format="mixed", utc=True)

# ── Build lookups ─────────────────────────────────────────
eoa_to_proxies = defaultdict(list)
for proxy, info in eoa_data["proxy_to_eoa_map"].items():
    eoa_to_proxies[info["eoa"]].append(proxy)

question_to_cid = {}
for m in markets_raw:
    q   = m.get("question", "")
    cid = m.get("conditionId")
    if q and cid:
        question_to_cid[q] = cid

tight_matches = tight["matches"]
print(f"Tight matches to analyze : {len(tight_matches)}")
print(f"Tight wallets            : {tight['tight_wallets']}\n")

# ── Direction analysis ────────────────────────────────────
direction_counter = Counter()
hl_side_counter   = Counter()
pm_dir_counter    = Counter()
unknown_count     = 0
results           = []

for m in tight_matches:
    eoa      = m["eoa"]
    coin     = m["coin"]
    question = m["question"]
    cid      = question_to_cid.get(question)
    proxies  = eoa_to_proxies.get(eoa, [])

    if not cid or not proxies:
        unknown_count += 1
        continue

    # ── HL direction from fills in the position window ────
    mask = (
        (fills["address"] == eoa) &
        (fills["coin"].str.contains(coin, na=False)) &
        (fills["timestamp"] >= pd.Timestamp(m["hl_open"])) &
        (fills["timestamp"] <= pd.Timestamp(m["hl_close"]))
    )
    subset = fills[mask]
    if subset.empty:
        unknown_count += 1
        continue

    hl_side = "Long" if subset.iloc[0]["side"] in ("B","buy","Buy") else "Short"
    hl_side_counter[hl_side] += 1

    # ── PM direction from re-fetched history ──────────────
    pm_trades  = []
    for proxy in proxies:
        trades = pm_history.get(proxy.lower(), {}).get(cid, [])
        if trades:
            pm_trades = trades
            break

    if not pm_trades:
        unknown_count += 1
        continue

    # Only buys determine direction
    buy_trades = [t for t in pm_trades
                  if "buy" in (t.get("side") or "").lower()]
    directions = [t.get("true_direction") for t in buy_trades
                  if t.get("true_direction") not in ("Unknown", None)]

    if not directions:
        unknown_count += 1
        continue

    pm_dir = Counter(directions).most_common(1)[0][0]
    pm_dir_counter[pm_dir] += 1

    pattern = f"HL: {hl_side:<5}  |  PM: {pm_dir}"
    direction_counter[pattern] += 1

    results.append({
        "eoa":       eoa,
        "coin":      coin,
        "question":  question,
        "hl_side":   hl_side,
        "pm_dir":    pm_dir,
        "pattern":   pattern,
    })

total = sum(direction_counter.values())

# Coherence split
same_dir = (direction_counter.get("HL: Long   |  PM: Bullish", 0) +
            direction_counter.get("HL: Short  |  PM: Bearish", 0))
opposite = (direction_counter.get("HL: Long   |  PM: Bearish", 0) +
            direction_counter.get("HL: Short  |  PM: Bullish", 0))
neutral  = (direction_counter.get("HL: Long   |  PM: Neutral", 0) +
            direction_counter.get("HL: Short  |  PM: Neutral", 0))

print(f"{'='*60}")
print(f"DIRECTION ANALYSIS — TIGHT SET (220 matches)")
print(f"{'='*60}")

print(f"\nHyperliquid side:")
for side, cnt in hl_side_counter.most_common():
    print(f"  {side:<8} : {cnt} ({cnt/total*100:.1f}%)")

print(f"\nPolymarket TRUE direction (corrected):")
for d, cnt in pm_dir_counter.most_common():
    print(f"  {d:<10} : {cnt} ({cnt/total*100:.1f}%)")

print(f"\nCombined patterns:")
for pat, cnt in direction_counter.most_common():
    print(f"  {pat:<40} : {cnt} ({cnt/total*100:.1f}%)")

print(f"\n{'─'*60}")
print(f"Total analyzed           : {total}")
print(f"Unknown/missing          : {unknown_count}")
print(f"{'─'*60}")
print(f"Genuine hedges (opposite): {opposite} ({opposite/total*100:.1f}%)")
print(f"Doubling down (same dir) : {same_dir} ({same_dir/total*100:.1f}%)")
print(f"Neutral                  : {neutral} ({neutral/total*100:.1f}%)")

# ── Comparison table ──────────────────────────────────────
print(f"\n{'='*65}")
print(f"FULL COMPARISON ACROSS ALL THREE DEFINITIONS")
print(f"{'='*65}")
print(f"{'Metric':<45} {'Broad':>8} {'Tight':>8}")
print(f"{'─'*65}")
print(f"{'Confirmed matches':<45} {'323':>8} {'220':>8}")
print(f"{'Unique wallets':<45} {'158':>8} {'118':>8}")
print(f"{'% of Finance bettors (63,264)':<45} {'0.25%':>8} {'0.19%':>8}")
print(f"{'Genuine hedges %':<45} {'32.4%':>8} "
      f"{f'{opposite/total*100:.1f}%' if total else 'n/a':>8}")
print(f"{'Doubling down %':<45} {'59.5%':>8} "
      f"{f'{same_dir/total*100:.1f}%' if total else 'n/a':>8}")
print(f"{'Unevaluable (no PM data)':<45} {'41':>8} {'19':>8}")

# ── Wallet-level aggregation ─────────────────────────────
# For each wallet, determine their DOMINANT direction pattern
# across all their confirmed tight matches

wallet_patterns = defaultdict(lambda: defaultdict(int))
wallet_coins    = defaultdict(set)

for r in results:
    wallet_patterns[r["eoa"]][r["pattern"]] += 1
    wallet_coins[r["eoa"]].add(r["coin"])

# Assign each wallet their most common pattern
wallet_dominant = {}
for eoa, patterns in wallet_patterns.items():
    dominant = Counter(patterns).most_common(1)[0][0]
    wallet_dominant[eoa] = dominant

# Wallet-level coherence
w_same_dir = sum(1 for p in wallet_dominant.values()
                 if "Bullish" in p and "Long" in p or
                    "Bearish" in p and "Short" in p)
w_opposite = sum(1 for p in wallet_dominant.values()
                 if "Bearish" in p and "Long" in p or
                    "Bullish" in p and "Short" in p)
w_neutral  = sum(1 for p in wallet_dominant.values()
                 if "Neutral" in p)
w_total    = len(wallet_dominant)

wallet_pattern_counter = Counter(wallet_dominant.values())

print(f"\n{'='*60}")
print(f"WALLET-LEVEL DIRECTION ANALYSIS")
print(f"(Each wallet counted ONCE using their dominant pattern)")
print(f"{'='*60}")
print(f"\nTotal unique wallets analyzed : {w_total}")

print(f"\nDominant pattern per wallet:")
for pat, cnt in wallet_pattern_counter.most_common():
    print(f"  {pat:<40} : {cnt} ({cnt/w_total*100:.1f}%)")

print(f"\n{'─'*60}")
print(f"Genuine hedges (opposite directions) : "
      f"{w_opposite} ({w_opposite/w_total*100:.1f}%)")
print(f"Doubling down  (same direction)      : "
      f"{w_same_dir} ({w_same_dir/w_total*100:.1f}%)")
print(f"Neutral                              : "
      f"{w_neutral} ({w_neutral/w_total*100:.1f}%)")

print(f"\n{'='*65}")
print(f"FULL COMPARISON: MATCH-LEVEL vs WALLET-LEVEL")
print(f"{'='*65}")
print(f"{'Metric':<45} {'Match':>10} {'Wallet':>10}")
print(f"{'─'*65}")
print(f"{'Total in tight set':<45} {total:>10} {w_total:>10}")
print(f"{'Genuine hedges %':<45} "
      f"{f'{opposite/total*100:.1f}%':>10} "
      f"{f'{w_opposite/w_total*100:.1f}%':>10}")
print(f"{'Doubling down %':<45} "
      f"{f'{same_dir/total*100:.1f}%':>10} "
      f"{f'{w_same_dir/w_total*100:.1f}%':>10}")

# Save everything fresh
with open("direction_tight_v2.json", "w") as f:
    json.dump({
        "tight_matches":   len(tight_matches),
        "tight_wallets":   tight["tight_wallets"],
        "match_level": {
            "total_analyzed":    total,
            "unknown_missing":   unknown_count,
            "genuine_hedges":    opposite,
            "doubling_down":     same_dir,
            "neutral":           neutral,
            "genuine_hedge_pct": round(opposite/total*100, 2) if total else 0,
            "doubling_down_pct": round(same_dir/total*100, 2) if total else 0,
            "combined_patterns": dict(direction_counter),
            "hl_side":           dict(hl_side_counter),
            "pm_direction":      dict(pm_dir_counter),
        },
        "wallet_level": {
            "total_wallets":         w_total,
            "genuine_hedge_wallets": w_opposite,
            "doubling_down_wallets": w_same_dir,
            "neutral_wallets":       w_neutral,
            "genuine_hedge_pct":     round(w_opposite/w_total*100, 2),
            "doubling_down_pct":     round(w_same_dir/w_total*100, 2),
            "dominant_patterns":     dict(wallet_pattern_counter),
        },
        "match_results": results,
    }, f, indent=2)

print(f"\n✅ Saved to direction_tight_v2.json")