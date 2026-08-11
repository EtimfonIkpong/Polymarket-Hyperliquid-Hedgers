# Polymarket × Hyperliquid HIP-3 Hedging Research

An on-chain investigation into whether traders who bet on Polymarket's Finance-category markets simultaneously hold correlated perpetual positions on Hyperliquid's HIP-3 builder-deployed exchanges — specifically trade.xyz, where the same real-world assets (NVDA, GOLD, SP500, TSLA, etc.) are tradeable as on-chain perpetual futures.

---

## Headline Findings

| Metric | Value |
|---|---|
| Polymarket Finance bettors (resolved EOAs) | **63,264** |
| Wallets also active on trade.xyz | **1,413** |
| Broad overlap (asset + market window) | **158 wallets (0.25%)** |
| Strict overlap (asset + bet-holding window) | **118 wallets (0.19%)** |
| Wallets with direction data | **96** |
| Dominant pattern: doubling down | **57 wallets (59.4%)** |
| Dominant pattern: genuine hedge | **31 wallets (32.3%)** |
| Peak hedging month | **November 2025 (65 wallets)** |
| Total PM dollar volume from genuine hedgers | **~$11.5K** |
| Median PM bet size | **$17.00** |
| Avg PM/HL ratio (corrected) | **0.054641** |
| Median PM/HL ratio | **0.002396** |

---

## The Central Finding

Cross-platform hedging between Polymarket and trade.xyz essentially does not exist at meaningful scale.

A rigorous search of 338 million trade.xyz fills matched against 63,264 Polymarket Finance bettors finds:

- Only **0.19%** of Finance bettors had any strict asset-and-time overlap with trade.xyz
- Of those, **59.4%** were doubling down (same directional view on both platforms), not hedging
- Only **32.3%** showed genuine opposite-direction positioning consistent with hedging
- Activity peaked in **November 2025** and collapsed to 1 match by June 2026 — consistent with launch-window novelty, not persistent behaviour

---

## What "Hedging" Means Here

A wallet qualifies as a confirmed match if **both** hold:

1. They bet on a Polymarket market naming a specific asset (e.g. "Will NVDA hit $150?")
2. They held an active trade.xyz position in that **same asset** during the **exact window they personally held their Polymarket bet** — not just while the market was open

The strict ("tight") definition produces **118 wallets**. A broader definition (overlap with the full market window) produces 158.

---

## Direction Analysis — Corrected Method

Previous analysis used buy price as a proxy for direction — a method that fails because:
- Price measures favourite-vs-longshot, not Yes-vs-No
- "Yes" is not always bullish (e.g. "Will MSFT dip to $465?" — Yes = bearish)

The corrected method uses the actual `outcomeIndex` field from re-fetched Polymarket trade history plus question polarity classification (bullish-if-yes / bearish-if-yes / neutral per market question).

**Corrected wallet-level results (96 wallets):**

| Pattern | Wallets | % |
|---|---|---|
| HL Long + PM Bullish (doubling down) | 42 | 43.8% |
| HL Long + PM Bearish (genuine hedge) | 17 | 17.7% |
| HL Short + PM Bearish (doubling down) | 15 | 15.6% |
| HL Short + PM Bullish (genuine hedge) | 14 | 14.6% |
| Neutral | 8 | 8.3% |
| **Genuine hedges total** | **31** | **32.3%** |
| **Doubling down total** | **57** | **59.4%** |

---

## Entry Timing

- **62.3%** — HL position opened first (median 8.3 days before PM bet)
- **37.7%** — PM bet placed first (median 4.0 days before HL opened)

These are primarily Hyperliquid traders who subsequently place small correlated bets on Polymarket.

---

## Temporal Decay (Tight Set — 118 Wallets)

| Month | Matches | Unique Wallets |
|---|---|---|
| Oct 2025 | 3 | 3 |
| Nov 2025 | 107 | 65 |
| Dec 2025 | 87 | 37 |
| Jan 2026 | 17 | 17 |
| Feb 2026 | 1 | 1 |
| Mar 2026 | 3 | 3 |
| May 2026 | 1 | 1 |
| Jun 2026 | 1 | 1 |

Activity concentrated almost entirely in trade.xyz's first two months of operation.

---

## Data Sources

| Source | Purpose | Auth Required |
|---|---|---|
| Polymarket Gamma API | Market metadata | None |
| Polymarket Data API | Trade history + bettor addresses | None |
| Polymarket CLOB API | Magic-login proxy resolution | None |
| Alchemy (Polygon RPC) | On-chain `getOwners()` for proxy resolution | Free API key |
| Hyperliquid native API | Live open-position snapshot | None |
| Hydromancer Reservoir (AWS S3) | Complete trade.xyz fill archive since launch | AWS credentials |

---

## Pipeline Overview

```
Phase 1 — Polymarket data collection
  2,004 Finance markets → 116,054 proxy addresses → 63,264 EOAs

Phase 2 — Hyperliquid cross-reference
  338M trade.xyz fills → 1.76M matched → 1,413 wallets

Phase 3 — Matching (two definitions)
  Broad  (market window overlap)   : 158 wallets
  Strict (bet-holding window)      : 118 wallets
  Re-fetch PM history with real outcome tokens
  Classify question polarity

Phase 4 — Analysis
  Direction (corrected): outcomeIndex + polarity
  Timing: entry/exit gaps, days before resolution
  Volume: dollar and nominal by wallet
  Behavior: hedge vs doubledown per wallet
```

---

## Installation

```bash
git clone https://github.com/EtimfonIkpong/Polymarket-Hyperliquid-Hedgers.git
cd Polymarket-Hyperliquid-Hedgers
pip install -r requirements.txt
```

See `data/README.md` for execution order and credential requirements.

---

## Limitations

- 45.3% of proxy wallets unresolved (inactive Magic/email accounts)
- trade.xyz only — other HIP-3 dexes not covered
- Keyword matching is substring-based (minor false positive risk)
- HL direction from first fill in interval
- 19 matches unevaluable (no PM trade data retrievable)
- 22 wallets missing direction (outcomeIndex null)
- No Arkham entity labelling completed

See [`METHODOLOGY.md`](./METHODOLOGY.md) for full detail on every decision, dead end, and reviewer correction applied.
