import json
import os
import pandas as pd
from collections import Counter

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("sequence_analysis_results.json", "r") as f:
    sequences = json.load(f)

with open("enriched_matches.json", "r") as f:
    enriched = json.load(f)

with open("pm_trade_history_for_matches.json", "r") as f:
    pm_history = json.load(f)

fills = pd.read_parquet("xyz_fills_matched_to_polymarket.parquet")
fills["timestamp"] = pd.to_datetime(fills["timestamp"], format="mixed", utc=True)

eoa_q_to_market = {(m["eoa"], m["question"]): m for m in enriched}

direction_counter  = Counter()
hl_side_counter    = Counter()
pm_direction_counter = Counter()

for r in sequences:
    market = eoa_q_to_market.get((r["eoa"], r["question"]))
    if not market:
        continue

    # ── HL direction ─────────────────────────────────────
    mask = (
        (fills["address"] == r["eoa"]) &
        (fills["coin"].str.contains(r["coin"], na=False)) &
        (fills["timestamp"] >= pd.Timestamp(r["hl_open"])) &
        (fills["timestamp"] <= pd.Timestamp(r["hl_close"]))
    )
    subset = fills[mask]
    if subset.empty:
        continue
    hl_side = "Long" if subset.iloc[0]["side"] in ("B", "buy", "Buy") else "Short"
    hl_side_counter[hl_side] += 1

    # ── PM direction — inferred from avg buy price ────────
    # Price > 0.50 = buying Yes (bullish, thinks event likely)
    # Price < 0.50 = buying No  (bearish, thinks event unlikely)
    # Price = 0.50 = neutral
    proxy, cid = market.get("proxy"), market.get("conditionId")
    trades = pm_history.get(proxy, {}).get(cid, [])
    buys = [t for t in trades if "buy" in (t.get("side") or "").lower()]
    if not buys:
        continue

    try:
        prices = [float(t["price"]) for t in buys if t.get("price")]
        avg_price = sum(prices) / len(prices)
    except (TypeError, ValueError, ZeroDivisionError):
        continue

    if avg_price > 0.55:
        pm_dir = "Buying Yes (bullish)"
    elif avg_price < 0.45:
        pm_dir = "Buying No  (bearish)"
    else:
        pm_dir = "Neutral (near 50/50)"

    pm_direction_counter[pm_dir] += 1
    direction_counter[f"HL: {hl_side:<5}  |  PM: {pm_dir}"] += 1

total = sum(direction_counter.values())

print(f"{'─'*65}")
print(f"Q18: DIRECTIONAL PATTERNS (PM direction via price proxy)")
print(f"{'─'*65}")

print(f"\nHyperliquid side:")
for side, count in hl_side_counter.most_common():
    print(f"  {side:<8} : {count:>3} ({count/total*100:.1f}%)")

print(f"\nPolymarket side (inferred from avg buy price):")
for direction, count in pm_direction_counter.most_common():
    print(f"  {direction:<30} : {count:>3} ({count/total*100:.1f}%)")

print(f"\nCombined patterns:")
for pattern, count in direction_counter.most_common():
    print(f"  {pattern:<55} : {count:>3} ({count/total*100:.1f}%)")

print(f"\n{'─'*65}")
print(f"Total matches analyzed: {total}")

# Key insight check: are they doubling down or hedging?
long_yes = direction_counter.get("HL: Long   |  PM: Buying Yes (bullish)", 0)
long_no  = direction_counter.get("HL: Long   |  PM: Buying No  (bearish)", 0)
short_yes = direction_counter.get("HL: Short  |  PM: Buying Yes (bullish)", 0)
short_no  = direction_counter.get("HL: Short  |  PM: Buying No  (bearish)", 0)

same_direction = long_yes + short_no   # both bullish or both bearish
hedge_direction = long_no + short_yes  # opposite directions

print(f"\nKey insight:")
print(f"  Same direction on both platforms (doubling down) : "
      f"{same_direction} ({same_direction/total*100:.1f}%)")
print(f"  Opposite directions (genuine hedge)              : "
      f"{hedge_direction} ({hedge_direction/total*100:.1f}%)")

with open("q18_direction_final.json", "w") as f:
    json.dump({
        "hl_side": dict(hl_side_counter),
        "pm_direction_inferred": dict(pm_direction_counter),
        "combined_patterns": dict(direction_counter),
        "same_direction_count": same_direction,
        "opposite_direction_count": hedge_direction,
        "total_analyzed": total
    }, f, indent=2)

print(f"\n✅ Saved to q18_direction_final.json")
