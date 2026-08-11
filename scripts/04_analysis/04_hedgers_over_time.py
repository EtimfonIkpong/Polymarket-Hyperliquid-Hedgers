import json
import os
import pandas as pd

os.chdir(r"C:\Users\Etimfon\Desktop")

# Use tight confirmed set (118 wallets) not the old broad set
with open("tight_confirmed_v2.json", "r") as f:
    data = json.load(f)

matches = data["matches"]
print(f"Tight confirmed matches: {len(matches)}")

df = pd.DataFrame(matches)
df["hl_open"] = pd.to_datetime(df["hl_open"], format="mixed", utc=True)
df["month"]   = df["hl_open"].dt.to_period("M").astype(str)

monthly = df.groupby("month").agg(
    confirmed_matches=("eoa", "count"),
    unique_wallets=("eoa", "nunique")
).reset_index()

print(f"\n{'─'*50}")
print(f"HEDGING ACTIVITY OVER TIME (tight set — 118 wallets)")
print(f"{'─'*50}")
print(monthly.to_string(index=False))

monthly.to_json("hedgers_over_time.json", orient="records", indent=2)
print(f"\n✅ Saved to hedgers_over_time.json")
