import pandas as pd
import os
import csv

os.chdir(r"C:\Users\Etimfon\Desktop")

df = pd.read_csv("hedge_entry_timing.csv")

print(f"Total hedge buy rows: {len(df)}\n")

# ── Create classification columns ────────────────────────
def classify_size(row):
    spent = row["pm_dollar_spent"]
    if spent >= 50:
        return "Large (>=$50)"
    elif spent >= 10:
        return "Medium ($10-$50)"
    else:
        return "Small (<$10)"

def classify_price(row):
    price = row["pm_buy_price"]
    if price >= 0.9:
        return "High confidence (>=$0.90)"
    elif price >= 0.5:
        return "Mid (>=$0.50)"
    else:
        return "Low (<$0.50)"

df["size_bucket"]  = df.apply(classify_size, axis=1)
df["price_bucket"] = df.apply(classify_price, axis=1)

# ── Q1: How many wallets enter at >= $0.90? ──────────────
high_price = df[df["pm_buy_price"] >= 0.90]
print(f"{'='*60}")
print(f"ENTRIES AT PRICE >= $0.90")
print(f"{'='*60}")
print(f"Total rows at >= $0.90         : {len(high_price)}")
print(f"Unique wallets                 : {high_price['wallet'].nunique()}")
print(f"\nOf those, how many spent >= $50:")
print(f"  >= $50  : {len(high_price[high_price['pm_dollar_spent'] >= 50])}")
print(f"  $10-$50 : {len(high_price[(high_price['pm_dollar_spent'] >= 10) & (high_price['pm_dollar_spent'] < 50)])}")
print(f"  < $10   : {len(high_price[high_price['pm_dollar_spent'] < 10])}")

# Are high-price buyers buying YES or NO?
print(f"\nHigh price (>=$0.90) buyers — token bought:")
token_counts = high_price["pm_token_bought"].value_counts()
total_hp = len(high_price)
for token, cnt in token_counts.items():
    print(f"  {token:<12} : {cnt} ({cnt/total_hp*100:.1f}%)")


# ── Q2: Three size groups — avg days before resolution ────
groups = [
    ("Large (>=$50)",     df[df["pm_dollar_spent"] >= 50]),
    ("Medium ($10-$50)",  df[(df["pm_dollar_spent"] >= 10) &
                              (df["pm_dollar_spent"] < 50)]),
    ("Small (<$10)",      df[df["pm_dollar_spent"] < 10]),
]

print(f"\n{'='*60}")
print(f"AVG DAYS BEFORE RESOLUTION BY SIZE (all price levels)")
print(f"{'='*60}")
print(f"{'Group':<20} {'Rows':>5} {'Wallets':>8} "
      f"{'Avg days':>10} {'Median':>8} {'Pct @>=0.90':>12}")
print(f"{'─'*60}")

for label, grp in groups:
    if grp.empty:
        continue
    valid = grp["pm_days_before_resolution"].dropna()
    avg    = valid.mean()
    median = valid.median()
    hp_pct = (grp["pm_buy_price"] >= 0.90).mean() * 100
    print(f"{label:<20} {len(grp):>5} "
          f"{grp['wallet'].nunique():>8} "
          f"{avg:>10.1f} "
          f"{median:>8.1f} "
          f"{hp_pct:>11.1f}%")


# ── Q3: High-price group (>=$0.90) × size × timing ───────
print(f"\n{'='*60}")
print(f"FOCUS: ENTRIES AT >= $0.90 — BROKEN DOWN BY SIZE")
print(f"{'='*60}")

hp_groups = [
    ("Large (>=$50)",    high_price[high_price["pm_dollar_spent"] >= 50]),
    ("Medium ($10-$50)", high_price[(high_price["pm_dollar_spent"] >= 10) &
                                    (high_price["pm_dollar_spent"] < 50)]),
    ("Small (<$10)",     high_price[high_price["pm_dollar_spent"] < 10]),
]

for label, grp in hp_groups:
    if grp.empty:
        print(f"\n{label}: no entries")
        continue
    valid  = grp["pm_days_before_resolution"].dropna()
    tokens = grp["pm_token_bought"].value_counts()
    yes_pct = tokens.get("Yes", 0) / len(grp) * 100
    no_pct  = tokens.get("No",  0) / len(grp) * 100

    print(f"\n{label} @ price >= $0.90")
    print(f"  Rows / Wallets    : {len(grp)} / {grp['wallet'].nunique()}")
    print(f"  Avg days before   : {valid.mean():.1f}")
    print(f"  Median days before: {valid.median():.1f}")
    print(f"  Buying YES        : {tokens.get('Yes',0)} ({yes_pct:.1f}%)")
    print(f"  Buying NO         : {tokens.get('No',0)} ({no_pct:.1f}%)")
    print(f"  Avg $ spent       : ${grp['pm_dollar_spent'].mean():.2f}")


# ── Add columns and save ──────────────────────────────────
df_out = df.copy()
df_out["entry_size_bucket"]  = df_out.apply(classify_size, axis=1)
df_out["entry_price_bucket"] = df_out.apply(classify_price, axis=1)
df_out["is_high_confidence"] = (df_out["pm_buy_price"] >= 0.90).map(
                                {True: "Yes", False: "No"})

df_out.to_csv("hedge_entry_analysis.csv", index=False)
print(f"\n✅ Saved to hedge_entry_analysis.csv")
