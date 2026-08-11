# Polymarket × Hyperliquid HIP-3 Hedging Research

An on-chain investigation into whether traders who bet on Polymarket's Finance-category markets simultaneously hold correlated perpetual positions on Hyperliquid's HIP-3 builder-deployed exchanges — specifically trade.xyz, where the same real-world assets (NVDA, GOLD, SP500, TSLA, etc.) are tradeable as on-chain perpetual futures.

---

## Headline Findings

| Metric | Value |
|---|---|
| Polymarket Finance bettors (resolved real wallets) | **63,264** |
| Wallets also active on trade.xyz | **1,413** |
| Confirmed cross-platform hedgers (asset + timing) | **158** |
| Unique wallet-asset hedging relationships | **198** |
| % of Finance bettors who hedge on HIP-3 | **0.25%** |
| Peak hedging month | **November 2025 (71 wallets)** |
| Most hedged asset by frequency | **NVDA (117 confirmed matches)** |
| Most hedged asset by nominal volume | **GOLD ($38,384)** |
| Genuine hedges (opposite directions) | **58.9%** |
| Traders doubling down (same direction) | **37.9%** |
| Avg HL position size ÷ PM bet size | **15,091x** |
| Top 10 traders' share of hedge volume | **49.8%** |

---

## What Counts as "Hedging"

A wallet is only counted as a confirmed hedger if **both** conditions hold simultaneously:

1. They placed a bet on a Polymarket market whose question names a specific asset (e.g. "Will NVDA hit $150?")
2. They held an active position in that **same asset** on Hyperliquid/trade.xyz during the **exact time window** that Polymarket market was open for betting

Asset-match alone (same asset, different time) was not sufficient — the timing had to genuinely overlap. This reduced the candidate pool from 1,413 wallets down to 158.

---

## Key Insight

The 15,091x average ratio between Hyperliquid position size and Polymarket bet size fundamentally reframes the finding:

> These are not Polymarket bettors hedging on Hyperliquid.
> They are **Hyperliquid traders placing small, correlated side bets on Polymarket.**

The median Polymarket bet among confirmed hedgers was **$17.00**, while a typical trade.xyz position runs $5,000–$20,000 notional. Polymarket functions as a high-leverage, low-capital directional expression tool — not a precision hedge instrument.

---

## Data Sources

| Source | What It Provides | Auth Required |
|---|---|---|
| Polymarket Gamma API | Market metadata, categories, time windows | None |
| Polymarket Data API | Per-market trade history with wallet addresses | None |
| Polymarket CLOB API | Proxy wallet → EOA resolution (Magic users) | None |
| Alchemy (Polygon RPC) | On-chain `getOwners()` calls for Gnosis Safe proxy wallets | Free API key |
| Hyperliquid native API | Live open position snapshots (no key, no rate cap daily) | None |
| Hydromancer Reservoir (S3) | Complete trade.xyz fill history since launch (Oct 13 2025) | AWS credentials (free, ~cents cost) |

### Tools That Were Evaluated But Not Used in Final Pipeline

- **The Graph (Polymarket subgraph):** The `positions` entity tracks liquidity providers, not bettors. Abandoned early.
- **HyperTracker (CoinMarketMan):** Excellent data but 100 request/day free tier was far too restrictive for bulk analysis at this scale.

---

## Pipeline Overview

```
PHASE 1 — Polymarket Data Collection
  ├── Fetch 2,004 Finance-category markets (Gamma API)
  ├── Collect 116,054 proxy wallet addresses (Data API)
  └── Resolve 63,264 real EOAs (Alchemy RPC + web3.py)

PHASE 2 — Hyperliquid Cross-Reference
  ├── Snapshot: 451 wallets with current open positions (native API)
  └── History: Download complete trade.xyz archive (Hydromancer S3)
              → 337M fills, filtered to 1,759,220 matched fills
              → 1,413 wallets trading both platforms

PHASE 3 — Matching
  ├── Reconstruct position open/close intervals from fills
  ├── Match asset keywords against Polymarket questions
  ├── Apply temporal overlap test
  └── 158 confirmed hedgers, 198 wallet-asset relationships

PHASE 4 — Analysis
  ├── Entry/exit sequencing (which platform first?)
  ├── Directional analysis (Long+Yes? Short+No? genuine hedge?)
  ├── Full vs partial hedge sizing
  ├── P&L breakdown by entry/exit pattern
  ├── Volume and nominal volume by asset
  ├── Concentration (top 10 traders = 49.8% of volume)
  ├── Temporal trend (peak Nov 2025, rapid decline after)
  └── Structural hedger behavioral profiling (4 wallets)
```

---

## Directional Findings (Q18)

Of 282 confirmed matches with directional data:

```
HL Short + PM Buying Yes   : 101  (35.8%)  ← genuine hedge
HL Long  + PM Buying Yes   :  84  (29.8%)  ← doubling down
HL Long  + PM Buying No    :  65  (23.0%)  ← genuine hedge
HL Short + PM Buying No    :  23   (8.2%)  ← doubling down
Neutral                    :   9   (3.2%)

Genuine hedges (opposite)  : 166  (58.9%)
Doubling down (same dir.)  : 107  (37.9%)
```

The largest single pattern: traders who are **short on Hyperliquid while buying Yes on Polymarket** — a classic backstop hedge against a short position going wrong.

---

## Structural Hedgers

Four wallets were confirmed hedging across **4 or more completely different assets** simultaneously — identified as the most sophisticated traders in the dataset:

| Wallet | Assets Hedged | HL PnL (total) | Profile |
|---|---|---|---|
| `0x947db9...` | NVDA, AAPL, GOLD, GOOGL | +$682 | Systematic, likely algorithmic (3,756 gold fills) |
| `0xbb999d...` | NVDA, AAPL, MSFT, GOOGL | +$33 | Long-term holder, uses PM as insurance |
| `0xfece5d...` | NVDA, GOLD, GOOGL, META | -$161 | Speculative, less disciplined |
| `0x2203e8...` | NVDA, TSLA, AMZN, MSFT | +$17 | Relative value / market cap arbitrage |

---

## Temporal Trend

Hedging activity peaked sharply in November–December 2025 (trade.xyz's first full months of operation) and has declined steadily since.

| Month | Confirmed Matches | Unique Wallets |
|---|---|---|
| Oct 2025 | 3 | 3 |
| Nov 2025 | 146 | 71 |
| Dec 2025 | 104 | 44 |
| Jan 2026 | 19 | 19 |
| Feb 2026 | 4 | 4 |
| Mar 2026 | 3 | 3 |
| May 2026 | 2 | 2 |
| Jun 2026 | 1 | 1 |

---

## Installation

```bash
git clone https://github.com/your-username/polymarket-hyperliquid-hedgers.git
cd polymarket-hyperliquid-hedgers
pip install -r requirements.txt
```

---

## Running the Pipeline

See `data/README.md` for the full execution order, required credentials, and which data files can be downloaded vs must be regenerated locally.

---

## Limitations

- **54.7% proxy resolution rate** — 45.3% of Polymarket proxy wallets could not be resolved to a real EOA, primarily inactive Magic/email login accounts
- **trade.xyz only** — the Hydromancer archive covers trade.xyz (HIP-3) from Oct 13 2025. Other HIP-3 builder dexes and pre-launch activity are not captured
- **Keyword matching** — asset matching relies on a manually-built keyword list; assets not in the list would produce missed matches
- **No Arkham labelling** — confirmed wallets were not labelled at API scale (Arkham requires separate API application). Manual spot-checks are recommended for the highest-frequency wallets
- **Polymarket total volume unavailable** — the % of total Finance market volume attributable to hedgers was not computed (Gamma API volume field name was not confirmed)

---

## Read the Full Methodology

See [`METHODOLOGY.md`](./METHODOLOGY.md) for a detailed, step-by-step account of every decision made in the research pipeline — including dead ends, bugs found and fixed, and honest caveats about each data source.
