import pandas as pd
import json
import os
import csv
from collections import Counter, defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

# ── Load the timing CSV we just built ────────────────────
df = pd.read_csv("hedge_entry_timing.csv")
df["pm_buy_timestamp"]   = pd.to_datetime(df["pm_buy_timestamp"],   utc=True, errors="coerce")
df["pm_market_end_date"] = pd.to_datetime(df["pm_market_end_date"], utc=True, errors="coerce")
df["hl_open_timestamp"]  = pd.to_datetime(df["hl_open_timestamp"],  utc=True, errors="coerce")
df["hl_close_timestamp"] = pd.to_datetime(df["hl_close_timestamp"], utc=True, errors="coerce")

print(f"Total hedge buy rows loaded : {len(df)}")
print(f"Wallets                     : {df['wallet'].nunique()}\n")

rows = []
entry_order_counter = Counter()
exit_order_counter  = Counter()

for _, r in df.iterrows():
    pm_buy   = r["pm_buy_timestamp"]
    hl_open  = r["hl_open_timestamp"]
    pm_end   = r["pm_market_end_date"]   # PM exit proxy (resolution)
    hl_close = r["hl_close_timestamp"]

    # ── Entry gap ─────────────────────────────────────────
    if pd.notna(pm_buy) and pd.notna(hl_open):
        entry_gap_days = (hl_open - pm_buy).total_seconds() / 86400
        # Positive = HL opened AFTER PM buy (PM first)
        # Negative = HL opened BEFORE PM buy (HL first)
        if entry_gap_days >= 0:
            entry_order = "PM first"
        else:
            entry_order = "HL first"
        entry_order_counter[entry_order] += 1
    else:
        entry_gap_days = None
        entry_order    = "Unknown"

    # ── Exit gap ──────────────────────────────────────────
    # Use PM market end date as PM exit proxy
    # (actual sell timestamp would be better but many held to resolution)
    if pd.notna(pm_end) and pd.notna(hl_close):
        exit_gap_days = (hl_close - pm_end).total_seconds() / 86400
        # Positive = HL closed AFTER PM resolved (PM exited first)
        # Negative = HL closed BEFORE PM resolved (HL exited first)
        if exit_gap_days <= 0:
            exit_order = "HL first"
        else:
            exit_order = "PM first"
        exit_order_counter[exit_order] += 1
    else:
        exit_gap_days = None
        exit_order    = "Unknown"

    rows.append({
        "wallet":           r["wallet"],
        "coin":             r["pm_coin"],
        "hl_side":          r["hl_side"],
        "pm_direction":     r["pm_direction"],
        "pm_question":      r["pm_question"],
        # Entry
        "pm_buy_timestamp": str(r["pm_buy_timestamp"]) if pd.notna(pm_buy)
                            else None,
        "hl_open_timestamp": str(r["hl_open_timestamp"]) if pd.notna(hl_open)
                             else None,
        "entry_gap_days":   round(entry_gap_days, 1) if entry_gap_days is not None
                            else None,
        "entry_order":      entry_order,
        # Exit
        "pm_end_date":      str(r["pm_market_end_date"]) if pd.notna(pm_end)
                            else None,
        "hl_close_timestamp": str(r["hl_close_timestamp"]) if pd.notna(hl_close)
                              else None,
        "exit_gap_days":    round(exit_gap_days, 1) if exit_gap_days is not None
                            else None,
        "exit_order":       exit_order,
        # Context
        "pm_buy_price":     r["pm_buy_price"],
        "pm_dollar_spent":  r["pm_dollar_spent"],
        "hl_notional":      r["hl_notional"],
        "hl_realized_pnl":  r["hl_realized_pnl"],
    })

# ── Summary stats ─────────────────────────────────────────
valid_entry = [r["entry_gap_days"] for r in rows
               if r["entry_gap_days"] is not None]
valid_exit  = [r["exit_gap_days"]  for r in rows
               if r["exit_gap_days"]  is not None]

valid_entry.sort()
valid_exit.sort()

print(f"{'='*60}")
print(f"ENTRY ORDER — GENUINE HEDGES")
print(f"{'='*60}")
total = sum(entry_order_counter.values())
for order, cnt in entry_order_counter.most_common():
    print(f"  {order:<12} : {cnt} ({cnt/total*100:.1f}%)")

if valid_entry:
    n = len(valid_entry)
    pm_first_gaps = [g for g in valid_entry if g >= 0]
    hl_first_gaps = [abs(g) for g in valid_entry if g < 0]
    print(f"\nEntry gap distribution (all {n} hedge instances):")
    print(f"  Min     : {valid_entry[0]:.1f} days")
    print(f"  25th %  : {valid_entry[n//4]:.1f} days")
    print(f"  Median  : {valid_entry[n//2]:.1f} days")
    print(f"  75th %  : {valid_entry[3*n//4]:.1f} days")
    print(f"  Max     : {valid_entry[-1]:.1f} days")
    if pm_first_gaps:
        print(f"\n  PM-first gaps (HL opened X days after PM):")
        print(f"    Median : {sorted(pm_first_gaps)[len(pm_first_gaps)//2]:.1f} days")
        print(f"    Avg    : {sum(pm_first_gaps)/len(pm_first_gaps):.1f} days")
    if hl_first_gaps:
        print(f"\n  HL-first gaps (HL opened X days before PM):")
        print(f"    Median : {sorted(hl_first_gaps)[len(hl_first_gaps)//2]:.1f} days")
        print(f"    Avg    : {sum(hl_first_gaps)/len(hl_first_gaps):.1f} days")

print(f"\n{'='*60}")
print(f"EXIT ORDER — GENUINE HEDGES")
print(f"{'='*60}")
total_exit = sum(exit_order_counter.values())
for order, cnt in exit_order_counter.most_common():
    print(f"  {order:<12} : {cnt} ({cnt/total_exit*100:.1f}%)")

if valid_exit:
    n = len(valid_exit)
    print(f"\nExit gap distribution ({n} instances with data):")
    print(f"  Median  : {valid_exit[n//2]:.1f} days (HL close vs PM resolution)")
    print(f"  Avg     : {sum(valid_exit)/n:.1f} days")

# ── Wallet-level summary ──────────────────────────────────
wallet_entry = defaultdict(list)
for r in rows:
    if r["entry_gap_days"] is not None:
        wallet_entry[r["wallet"]].append(r["entry_gap_days"])

print(f"\n{'='*60}")
print(f"WALLET-LEVEL ENTRY ORDER")
print(f"{'='*60}")
w_pm_first   = sum(1 for gaps in wallet_entry.values() if sum(gaps)/len(gaps) >= 0)
w_hl_first   = sum(1 for gaps in wallet_entry.values() if sum(gaps)/len(gaps) < 0)
w_total      = len(wallet_entry)
print(f"  Wallets where PM entered first (avg) : {w_pm_first} ({w_pm_first/w_total*100:.1f}%)")
print(f"  Wallets where HL entered first (avg) : {w_hl_first} ({w_hl_first/w_total*100:.1f}%)")

# ── Save CSV ──────────────────────────────────────────────
fields = [
    "wallet", "coin", "hl_side", "pm_direction", "pm_question",
    "pm_buy_timestamp", "hl_open_timestamp",
    "entry_gap_days", "entry_order",
    "pm_end_date", "hl_close_timestamp",
    "exit_gap_days", "exit_order",
    "pm_buy_price", "pm_dollar_spent", "hl_notional", "hl_realized_pnl",
]
with open("hedge_entry_exit_gaps.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ Saved to hedge_entry_exit_gaps.csv")
