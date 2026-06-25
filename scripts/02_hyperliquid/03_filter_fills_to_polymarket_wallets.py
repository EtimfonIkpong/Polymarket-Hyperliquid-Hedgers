import pandas as pd
import json
import os
import glob

os.chdir(r"C:\Users\Etimfon\Desktop")

OUTPUT_FILE = "xyz_fills_matched_to_polymarket.parquet"
CHECKPOINT_EVERY = 25   # save progress periodically, just in case

# ── Load our resolved Polymarket EOAs ────────────────────
with open("eoa_wallets.json", "r") as f:
    eoa_data = json.load(f)
eoa_set = set(addr.lower() for addr in eoa_data["eoa_addresses"])
print(f"Loaded {len(eoa_set):,} Polymarket EOAs to filter against\n")

files = sorted(glob.glob("hl_xyz_fills/*.parquet"))
print(f"Found {len(files)} files to process — "
      f"processing ONE AT A TIME to keep memory usage low\n")

matched_chunks = []
total_scanned  = 0

for i, filepath in enumerate(files):
    # Only load the columns we actually need (lighter on memory)
    df = pd.read_parquet(
        filepath,
        columns=["address", "coin", "side", "price",
                 "size", "direction", "timestamp"]
    )
    total_scanned += len(df)

    df["address"] = df["address"].str.lower()
    matched = df[df["address"].isin(eoa_set)]

    if len(matched) > 0:
        matched_chunks.append(matched.copy())

    print(f"[{i+1}/{len(files)}] {os.path.basename(filepath)} → "
          f"{len(df):,} scanned, {len(matched):,} matched")

    del df, matched   # free memory immediately before next file

    # Periodic checkpoint save, in case the laptop struggles again
    if (i + 1) % CHECKPOINT_EVERY == 0 and matched_chunks:
        partial = pd.concat(matched_chunks, ignore_index=True)
        partial.to_parquet(OUTPUT_FILE)
        print(f"  💾 Checkpoint saved ({len(partial):,} matched rows so far)\n")

# ── Final save ────────────────────────────────────────────
if matched_chunks:
    result_df = pd.concat(matched_chunks, ignore_index=True)
else:
    result_df = pd.DataFrame()

print(f"\n{'─'*55}")
print(f"Total fills scanned : {total_scanned:,}")
print(f"Matched fills        : {len(result_df):,}")
print(f"Unique wallets        : "
      f"{result_df['address'].nunique() if len(result_df) else 0:,}")
print(f"{'─'*55}")

if len(result_df):
    result_df.to_parquet(OUTPUT_FILE)
    print("\nBreakdown by coin:")
    print(result_df['coin'].value_counts().head(20))

print(f"\n✅ Saved to {OUTPUT_FILE}")