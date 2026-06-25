# Data Directory

This directory contains the output files produced by the research pipeline.
Large intermediate files are excluded from the repository — see the **Regenerating Large Files** section below.

---

## Files Included in This Repo

| File | Size | Produced by | Description |
|---|---|---|---|
| `finance_markets.json` | ~600KB | `01_fetch_finance_markets.py` | 2,004 Polymarket Finance-category markets with conditionId, question text, and time windows |
| `final_confirmed_hedgers.json` | ~200KB | `02_asset_and_temporal_match.py` | 323 raw confirmed matches across 158 unique wallets — every case where a wallet held a trade.xyz position during a matching Polymarket bet window |
| `final_episode_count.json` | ~50KB | `03_compute_hedge_episodes.py` | 198 unique (wallet, asset) hedging relationships — the headline metric, deduped from price-ladder market inflation |
| `final_summary_stats.json` | <10KB | `01_summarize_results.py` | Top-level summary statistics: counts by asset, top repeat wallets |
| `sequence_analysis_results.json` | ~100KB | `05_sequence_analysis.py` | Per-match entry/exit timing: which platform each wallet entered first, PM trade timestamps vs HL position open times |
| `deep_dive_part1_results.json` | <10KB | `04_hedging_frequency_and_concentration.py` | Speed of hedging (avg hours gap), frequency distribution, top-10/50/1% concentration metrics |
| `q18_direction_final.json` | <10KB | `05_directional_analysis.py` | Directional pattern breakdown: HL Long/Short vs PM buying Yes/No, genuine hedge vs doubling down split |
| `hedgers_over_time.json` | <10KB | `07_hedgers_over_time.py` | Monthly confirmed match counts and unique wallet counts from Oct 2025–Jun 2026 |
| `volume_by_asset.json` | <10KB | `02_volume_and_nominal_volume.py` | Nominal and dollar volume broken down per asset across all confirmed hedge markets |
| `nominal_volume.json` | ~30KB | `02_volume_and_nominal_volume.py` | Per-wallet nominal and dollar volume on confirmed hedge markets |
| `bet_size_stats.json` | ~20KB | `03_bet_size_statistics.py` | Per-wallet highest/lowest/average single bet size; overall distribution stats |
| `structural_hedger_profiles.json` | ~20KB | `09_structural_hedger_profiles.py` | Full behavioral profiles for the 4 wallets with 4+ distinct asset hedging relationships |

---

## Files NOT Included (Too Large — Regenerate Locally)

| File | Approx Size | How to regenerate |
|---|---|---|
| `unique_wallets.json` | ~5.7MB | Run `01_data_collection/02_collect_bettor_addresses.py` |
| `markets_with_bettors.json` | ~8MB | Run `01_data_collection/02_collect_bettor_addresses.py` |
| `eoa_wallets.json` | ~15MB | Run `01_data_collection/03_resolve_proxy_wallets.py` |
| `hl_xyz_fills/` | ~3GB | Run `02_hyperliquid/02_download_tradexyz_fills_from_s3.py` (requires AWS credentials) |
| `xyz_fills_matched_to_polymarket.parquet` | ~150MB | Run `02_hyperliquid/03_filter_fills_to_polymarket_wallets.py` |
| `xyz_fills_with_pnl.parquet` | ~50MB | Run `04_analysis/06_pnl_breakdown.py` (extract step) |
| `hl_open_positions.json` | ~2MB | Run `02_hyperliquid/01_check_open_positions_native_api.py` |
| `enriched_matches.json` | ~1MB | Run `03_matching/04_fetch_polymarket_trade_history.py` |
| `pm_trade_history_for_matches.json` | ~2MB | Run `03_matching/04_fetch_polymarket_trade_history.py` |

---

## Full Pipeline Execution Order

Run scripts in this exact order. Each step depends on the output of the previous.

```
scripts/01_data_collection/01_fetch_finance_markets.py
scripts/01_data_collection/02_collect_bettor_addresses.py
scripts/01_data_collection/03_resolve_proxy_wallets.py
scripts/02_hyperliquid/01_check_open_positions_native_api.py
scripts/02_hyperliquid/02_download_tradexyz_fills_from_s3.py
scripts/02_hyperliquid/03_filter_fills_to_polymarket_wallets.py
scripts/03_matching/01_build_candidate_list.py
scripts/03_matching/02_asset_and_temporal_match.py
scripts/03_matching/03_compute_hedge_episodes.py
scripts/03_matching/04_fetch_polymarket_trade_history.py
scripts/03_matching/05_sequence_analysis.py
scripts/04_analysis/01_summarize_results.py
scripts/04_analysis/02_volume_and_nominal_volume.py
scripts/04_analysis/03_bet_size_statistics.py
scripts/04_analysis/04_hedging_frequency_and_concentration.py
scripts/04_analysis/05_directional_analysis.py
scripts/04_analysis/06_pnl_breakdown.py
scripts/04_analysis/07_hedgers_over_time.py
scripts/04_analysis/08_multi_wallet_and_multi_asset.py
scripts/04_analysis/09_structural_hedger_profiles.py
```

---

## API Keys and Credentials Required

| Credential | Used in | Where to get it |
|---|---|---|
| Alchemy Polygon RPC URL | `03_resolve_proxy_wallets.py` | `alchemy.com` (free tier) |
| AWS Access Key + Secret | `02_download_tradexyz_fills_from_s3.py` | AWS IAM console (free account, ~cents of S3 cost) |

No API key is needed for: Polymarket Gamma API, Polymarket Data API, or Hyperliquid's native API — all are free and open.
