import json
import os
import pandas as pd

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("sequence_analysis_results.json", "r") as f:
    sequences = json.load(f)

df = pd.DataFrame(sequences)
df["hl_open"] = pd.to_datetime(df["hl_open"], format="mixed", utc=True)
df["month"] = df["hl_open"].dt.to_period("M").astype(str)

monthly = df.groupby("month").agg(
    confirmed_matches=("eoa", "count"),
    unique_wallets=("eoa", "nunique")
).reset_index()

print(f"{'─'*50}\nQ10: HEDGING ACTIVITY OVER TIME\n{'─'*50}")
print(monthly.to_string(index=False))

monthly.to_json("hedgers_over_time.json", orient="records", indent=2)
print(f"\n✅ Saved to hedgers_over_time.json")
