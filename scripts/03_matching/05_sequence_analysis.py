import pandas as pd
import json
import os
from collections import defaultdict, Counter

os.chdir(r"C:\Users\Etimfon\Desktop")

# ── Load everything ───────────────────────────────────────
with open("enriched_matches.json", "r") as f:
    enriched = json.load(f)

with open("pm_trade_history_for_matches.json", "r") as f:
    pm_history = json.load(f)

fills = pd.read_parquet("xyz_fills_matched_to_polymarket.parquet")
fills["timestamp"] = pd.to_datetime(fills["timestamp"], utc=True)


def ts_to_dt(ts):
    """Polymarket timestamp -> pandas UTC Timestamp (handles sec or ms)."""
    ts = int(ts)
    if ts < 10**12:   # looks like seconds
        ts *= 1000
    return pd.Timestamp(ts, unit="ms", tz="UTC")


# ── Reconstruct HL position intervals per (address, coin) ──
def reconstruct_intervals(group_df):
    g = group_df.sort_values("timestamp")
    intervals, pos, open_start = [], 0.0, None
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
    if open_start is not None:
        intervals.append((open_start, pd.Timestamp.now(tz="UTC")))
    return intervals


print("Reconstructing HL intervals per wallet/coin...")
hl_intervals = {}
for (addr, coin), g in fills.groupby(["address", "coin"]):
    hl_intervals[(addr, coin.replace("xyz:", ""))] = reconstruct_intervals(g)


# ── Analyze each confirmed match ──────────────────────────
results = []
pattern_counter = Counter()

for m in enriched:
    eoa, proxy, cid, coin = m["eoa"], m.get("proxy"), m.get("conditionId"), m["coin"]
    if not cid:
        continue

    pm_trades = pm_history.get(proxy, {}).get(cid, [])
    if not pm_trades:
        continue

    buys  = [t for t in pm_trades if "buy"  in (t.get("side") or "").lower()]
    sells = [t for t in pm_trades if "sell" in (t.get("side") or "").lower()]

    if not buys:
        continue

    pm_entry = min(ts_to_dt(t["timestamp"]) for t in buys)
    pm_exit  = max(ts_to_dt(t["timestamp"]) for t in sells) if sells else None

    intervals = hl_intervals.get((eoa, coin), [])
    if not intervals:
        continue

    # pick the HL interval closest to / overlapping the PM entry
    best = min(intervals, key=lambda iv: abs((iv[0] - pm_entry).total_seconds()))
    hl_open, hl_close = best

    entry_order = "Polymarket first" if pm_entry <= hl_open else "Hyperliquid first"

    if pm_exit is not None:
        exit_order = "Polymarket first" if pm_exit <= hl_close else "Hyperliquid first"
        pm_exit_type = "sold early"
    else:
        # never sold — treat market resolution (window end) as their PM exit
        try:
            res_time = pd.Timestamp(m["market_window"].split(" → ")[1])
        except Exception:
            res_time = None
        exit_order = ("Polymarket first" if res_time and res_time <= hl_close
                      else "Hyperliquid first" if res_time else "unknown")
        pm_exit_type = "held to resolution"

    pattern = f"Enter: {entry_order} | Exit: {exit_order}"
    pattern_counter[pattern] += 1

    results.append({
        "eoa": eoa, "coin": coin, "question": m["question"],
        "pm_entry": str(pm_entry), "pm_exit": str(pm_exit), "pm_exit_type": pm_exit_type,
        "hl_open": str(hl_open), "hl_close": str(hl_close),
        "entry_order": entry_order, "exit_order": exit_order,
    })

print(f"\n{'─'*60}")
print(f"Matches analyzed: {len(results)}\n")
print("Entry/Exit pattern breakdown:")
for pattern, count in pattern_counter.most_common():
    print(f"  {pattern:<55} : {count}")

with open("sequence_analysis_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Saved to sequence_analysis_results.json")
