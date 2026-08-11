import pandas as pd
import os
import csv

os.chdir(r"C:\Users\Etimfon\Desktop")

df = pd.read_csv("hedge_entry_timing.csv")
df["pm_days_before_resolution"] = pd.to_numeric(
    df["pm_days_before_resolution"], errors="coerce")
df["hl_total_notional_all_fills"] = pd.to_numeric(
    df["hl_total_notional_all_fills"], errors="coerce")
df["pm_dollar_spent"] = pd.to_numeric(df["pm_dollar_spent"], errors="coerce")
df["pm_buy_timestamp"] = pd.to_datetime(df["pm_buy_timestamp"], utc=True,
                                         errors="coerce")
df["hl_open_timestamp"] = pd.to_datetime(df["hl_open_timestamp"], utc=True,
                                          errors="coerce")
df["pm_market_end_date"] = pd.to_datetime(df["pm_market_end_date"], utc=True,
                                           errors="coerce")

# ── HL notional corrected: divide by 2 ───────────────────
df["hl_notional_usd"] = df["hl_total_notional_all_fills"] / 2

# ── PM/HL ratio ───────────────────────────────────────────
df["pm_hl_ratio"] = df["pm_dollar_spent"] / df["hl_notional_usd"]
df["pm_hl_ratio"].replace([float("inf"), float("-inf")], pd.NA, inplace=True)

# ── PM bet size buckets ───────────────────────────────────
def size_bucket(x):
    if x >= 1000:  return "A: >=$1000"
    elif x >= 100: return "B: $100-$999"
    elif x >= 25:  return "C: $25-$99"
    else:          return "D: $2-$24"

df["pm_size_bucket"] = df["pm_dollar_spent"].apply(size_bucket)

print(f"{'='*65}")
print(f"PM BET SIZE BUCKETS")
print(f"{'='*65}")
print(f"{'Bucket':<18} {'Rows':>5} {'Wallets':>8} "
      f"{'Avg $':>9} {'Avg ratio':>11} {'Avg days':>10}")
print(f"{'─'*65}")

for label in ["A: >=$1000","B: $100-$999","C: $25-$99","D: $2-$24"]:
    grp = df[df["pm_size_bucket"] == label]
    if grp.empty:
        continue
    valid_ratio = grp["pm_hl_ratio"].dropna()
    valid_days  = grp["pm_days_before_resolution"].dropna()
    print(f"{label:<18} {len(grp):>5} "
          f"{grp['wallet'].nunique():>8} "
          f"${grp['pm_dollar_spent'].mean():>8.2f} "
          f"{valid_ratio.mean():>10.4f} "
          f"{valid_days.mean():>10.1f}")

# ── Overall average ratio ─────────────────────────────────
valid_ratio = df["pm_hl_ratio"].dropna()
print(f"\nOverall avg PM/HL ratio (corrected HL notional ÷2): "
      f"{valid_ratio.mean():.6f}")
print(f"Median PM/HL ratio                                 : "
      f"{valid_ratio.median():.6f}")
print(f"(ratio < 1 means PM bet is smaller than HL position)")

# ── Special: rows where pm_dollar_spent >= $100 ──────────
big = df[df["pm_dollar_spent"] >= 100].copy()
big_wallets = big["wallet"].unique()

print(f"\n{'='*65}")
print(f"SPECIAL: ROWS WITH PM SPEND >= $100")
print(f"{'='*65}")
print(f"Matching rows    : {len(big)}")
print(f"Unique wallets   : {len(big_wallets)}")

# Days from HL open to PM buy (entry gap)
big["entry_gap_days"] = (
    big["pm_buy_timestamp"] - big["hl_open_timestamp"]
).dt.total_seconds() / 86400

# Days from PM buy to market resolution
big["pm_to_resolution_days"] = (
    big["pm_market_end_date"] - big["pm_buy_timestamp"]
).dt.total_seconds() / 86400

print(f"\nPer wallet breakdown:")
print(f"{'Wallet':<44} {'Rows':>4} {'PM$':>8} "
      f"{'Entry gap':>10} {'PM→Res':>10}")
print(f"{'─'*80}")
for wallet in big_wallets:
    w = big[big["wallet"] == wallet]
    avg_entry = w["entry_gap_days"].mean()
    avg_res   = w["pm_to_resolution_days"].mean()
    print(f"{wallet:<44} {len(w):>4} "
          f"${w['pm_dollar_spent'].sum():>7.2f} "
          f"{avg_entry:>10.1f}d "
          f"{avg_res:>10.1f}d")

print(f"\nKey stats for >= $100 group:")
print(f"  Avg entry gap (HL open → PM buy) : "
      f"{big['entry_gap_days'].mean():.1f} days")
print(f"  Median entry gap                 : "
      f"{big['entry_gap_days'].median():.1f} days")
print(f"  Avg PM buy → resolution          : "
      f"{big['pm_to_resolution_days'].mean():.1f} days")
print(f"  Median PM buy → resolution       : "
      f"{big['pm_to_resolution_days'].median():.1f} days")

# ── Save CSV ──────────────────────────────────────────────
df["entry_gap_days"] = (
    df["pm_buy_timestamp"] - df["hl_open_timestamp"]
).dt.total_seconds() / 86400

df["pm_to_resolution_days"] = (
    df["pm_market_end_date"] - df["pm_buy_timestamp"]
).dt.total_seconds() / 86400

df["hl_notional_usd"]   = df["hl_total_notional_all_fills"] / 2
df["pm_hl_ratio"]       = df["pm_dollar_spent"] / df["hl_notional_usd"]
df["pm_size_bucket"]    = df["pm_dollar_spent"].apply(size_bucket)

df.to_csv("bet_size_ratio_analysis.csv", index=False)

# Special wallets CSV
big.to_csv("special_100plus_hedgers.csv", index=False)

print(f"\n✅ Saved:")
print(f"   bet_size_ratio_analysis.csv  — all rows with ratios + buckets")
print(f"   special_100plus_hedgers.csv  — the >= $100 per bet rows")
