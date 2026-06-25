import pandas as pd
import requests
import json
import os
import time
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

GAMMA_URL = "https://gamma-api.polymarket.com"

# ── Load everything ───────────────────────────────────────
with open("sequence_analysis_results.json", "r") as f:
    sequences = json.load(f)

with open("enriched_matches.json", "r") as f:
    enriched = json.load(f)

with open("pm_trade_history_for_matches.json", "r") as f:
    pm_history = json.load(f)

hl_fills = pd.read_parquet("xyz_fills_with_pnl.parquet")
hl_fills["timestamp"] = pd.to_datetime(hl_fills["timestamp"], utc=True)

# Map (eoa, question) -> proxy + conditionId
eoa_q_to_market = {}
for m in enriched:
    eoa_q_to_market[(m["eoa"], m["question"])] = {
        "proxy": m.get("proxy"), "conditionId": m.get("conditionId")
    }


# ── Step 1: Compute HL realized PnL for each match's interval ──
def hl_pnl_for_interval(address, coin, start, end):
    mask = (
        (hl_fills["address"] == address) &
        (hl_fills["coin"].str.contains(coin, na=False)) &
        (hl_fills["timestamp"] >= pd.Timestamp(start)) &
        (hl_fills["timestamp"] <= pd.Timestamp(end))
    )
    subset = hl_fills[mask]
    return subset["realized_pnl"].fillna(0).sum(), subset["is_liquidation"].any()


# ── Step 2: Gather conditionIds needing resolution data ──
needs_resolution = set()
for r in sequences:
    if r["pm_exit_type"] == "held to resolution":
        key = (r["eoa"], r["question"])
        market = eoa_q_to_market.get(key)
        if market and market.get("conditionId"):
            needs_resolution.add(market["conditionId"])

print(f"Fetching resolution outcomes for {len(needs_resolution)} markets...")

resolution_data = {}
for i, cid in enumerate(needs_resolution):
    try:
        resp = requests.get(f"{GAMMA_URL}/markets",
                            params={"condition_ids": cid}, timeout=10)
        if resp.ok:
            data = resp.json()
            if data and isinstance(data, list):
                m = data[0]
                prices = json.loads(m.get("outcomePrices", "[]"))
                outcomes = json.loads(m.get("outcomes", "[]"))
                resolution_data[cid] = {"prices": prices, "outcomes": outcomes}
    except Exception as e:
        pass
    if (i + 1) % 30 == 0:
        print(f"  ...{i+1}/{len(needs_resolution)}")
    time.sleep(0.1)

print(f"✅ Got resolution data for {len(resolution_data)} markets\n")


# ── Step 3: Compute PM PnL per match ──────────────────────
def pm_pnl(proxy, cid, exit_type):
    trades = pm_history.get(proxy, {}).get(cid, [])
    buys  = [t for t in trades if "buy"  in (t.get("side") or "").lower()]
    sells = [t for t in trades if "sell" in (t.get("side") or "").lower()]

    cost = sum(float(t["price"]) * float(t["size"]) for t in buys)

    if exit_type == "sold early":
        proceeds = sum(float(t["price"]) * float(t["size"]) for t in sells)
        return proceeds - cost

    # held to resolution — need winning outcome
    res = resolution_data.get(cid)
    if not res or not buys:
        return None

    buy_outcome_idx = buys[0].get("outcomeIndex")
    try:
        won = float(res["prices"][int(buy_outcome_idx)]) > 0.5
    except (IndexError, ValueError, TypeError):
        return None

    total_size = sum(float(t["size"]) for t in buys)
    payout = total_size * 1.0 if won else 0.0
    return payout - cost


# ── Step 4: Combine everything per match ──────────────────
final_rows = []
for r in sequences:
    key = (r["eoa"], r["question"])
    market = eoa_q_to_market.get(key)
    if not market:
        continue

    hl_pnl, had_liquidation = hl_pnl_for_interval(
        r["eoa"], r["coin"], r["hl_open"], r["hl_close"])

    pm_result = pm_pnl(market["proxy"], market["conditionId"], r["pm_exit_type"])

    final_rows.append({
        **r,
        "hl_pnl": round(hl_pnl, 2),
        "hl_liquidated": bool(had_liquidation),
        "pm_pnl": round(pm_result, 2) if pm_result is not None else None,
    })

df = pd.DataFrame(final_rows)
df.to_csv("pnl_breakdown_full.csv", index=False)

# ── Step 5: Summary by entry/exit pattern ─────────────────
print(f"{'='*70}")
print("P&L BREAKDOWN BY ENTRY/EXIT PATTERN")
print(f"{'='*70}\n")

for (entry, exit_) in df[["entry_order", "exit_order"]].drop_duplicates().values:
    sub = df[(df.entry_order == entry) & (df.exit_order == exit_)]
    valid_pm = sub["pm_pnl"].dropna()

    print(f"Enter: {entry} | Exit: {exit_}  (n={len(sub)})")
    print(f"  HL P&L  → avg: ${sub['hl_pnl'].mean():,.2f} | "
          f"win rate: {(sub['hl_pnl'] > 0).mean()*100:.0f}%")
    if len(valid_pm) > 0:
        print(f"  PM P&L  → avg: ${valid_pm.mean():,.2f} | "
              f"win rate: {(valid_pm > 0).mean()*100:.0f}%")
    else:
        print(f"  PM P&L  → no resolved data")
    print()

print(f"✅ Full details saved to pnl_breakdown_full.csv")
