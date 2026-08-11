# Methodology: Identifying Cross-Platform Hedgers Between Polymarket and Hyperliquid HIP-3

## Research Question

This research investigates whether traders who bet on Polymarket's Finance-category markets — covering stocks, commodities, indices, and macro events — simultaneously hold or held correlated perpetual positions on Hyperliquid, specifically on HIP-3 builder-deployed exchanges such as trade.xyz, where the same real-world assets (NVDA, GOLD, SP500, TSLA, etc.) are tradeable as on-chain perpetual futures contracts.

The central hypothesis is that a trader betting "Will NVDA hit $150 before year-end?" on Polymarket while simultaneously holding an NVDA perpetual position on Hyperliquid is either hedging their prediction market bet or expressing the same directional view on two separate on-chain venues — a provable, verifiable, on-chain behavioural pattern.

**Final confirmed result: 158 unique wallets, across 198 distinct wallet-asset hedging relationships, were confirmed as genuine cross-platform hedgers — meaning both the asset and the timing genuinely overlapped between a live Polymarket bet and an active Hyperliquid/trade.xyz position.**

---

## Background: What Is HIP-3?

HIP-3 is a Hyperliquid standard that allows independent builders to deploy and operate their own perpetual markets on top of Hyperliquid's infrastructure. Trade.xyz was the first team to deploy under HIP-3, launching 24/7 perpetual markets for US equities, indices, and commodities — including NVDA, TSLA, AAPL, AMZN, GOOGL, META, MSFT, SP500, GOLD, SILVER, and crude oil. These markets are fully on-chain, USDC-margined, and accessible to any Hyperliquid wallet holder. This makes trade.xyz the natural venue for anyone who wants to take a leveraged directional view on exactly the same assets that Polymarket Finance markets bet on.

---

## Part 1 — Building the Polymarket Dataset

### 1.1 Identifying Relevant Markets

**Tool:** Polymarket Gamma API (`gamma-api.polymarket.com/markets`)

Markets were fetched using `tag_id=120`, which corresponds to Polymarket's internal "Finance" category. This tag covers stocks, commodities, indices, and macro events — directly overlapping with trade.xyz's asset universe.

The raw pull returned thousands of markets. Since many Finance-tagged markets were unrelated to assets actually tradeable on HIP-3 (e.g. niche crypto FDV questions, regulatory decisions, company-specific executive appointments), a keyword filter was applied to the `question` field of each market. The filter matched against known HIP-3-tradable tickers and their common names:

```
nvidia / nvda, tesla / tsla, apple / aapl, amazon / amzn,
google / googl / alphabet, meta / facebook, microsoft / msft,
gold, silver, oil / crude / brent / wti, s&p / sp500,
nasdaq, spacex, intel / intc, microstrategy / mstr, fed,
interest rate, inflation, cpi, gdp, recession, rate cut
```

This produced a working dataset of **2,004 HIP-3-relevant Polymarket markets**, each recorded with its `conditionId`, `startDate`, `endDate`, `question` text, and resolution status.

**Early dead end — The Graph subgraph:** Before settling on Polymarket's own APIs, the project began by querying The Graph's Polymarket subgraph (`Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp`). The initial query used `positions` as the entity. This produced only 1-2 results per market, even for markets with hundreds of known traders. Investigation revealed that the `positions` entity in the Polymarket subgraph tracks **liquidity provider** positions, not bettor activity. The subgraph was abandoned in favour of Polymarket's own REST APIs.

### 1.2 Collecting Bettor Wallet Addresses

**Tool:** Polymarket Data API (`data-api.polymarket.com/trades`)

For each of the 2,004 markets, the `/trades` endpoint was paginated (500 records per page) and every `proxyWallet` field was extracted — this is the address that executed each trade on-chain. The collection was run with checkpointing every 25 markets to allow safe interruption and resumption.

**Result:** **116,054 unique proxy wallet addresses** were collected and saved to `unique_wallets.json`. A per-market breakdown (`markets_with_bettors.json`) was also saved, preserving each market's question text, time window, and full bettor list — this file became essential for the temporal matching step later in the pipeline.

---

## Part 2 — Resolving Proxy Wallets to Real Identities

### 2.1 The Problem With Proxy Wallets

Polymarket does not allow traders to interact with markets using their own personal wallet directly. Instead, when a user signs up for Polymarket, a dedicated smart-contract "proxy wallet" is deployed on the Polygon blockchain specifically for that user. All of their bets, USDC balances, and outcome tokens are held inside this proxy — not in their personal wallet.

This means the 116,054 addresses collected in Part 1 are **not** the addresses these people use anywhere else — including Hyperliquid. They are Polymarket-specific contract addresses. Cross-referencing them against Hyperliquid would find zero matches, not because nobody hedges, but because we'd be comparing the wrong addresses.

The real owner address — the wallet that controls and funded the proxy — needed to be recovered for every proxy.

### 2.2 Two Types of Proxy Wallets

Two different proxy architectures exist depending on how the user signed up:

| User type | Proxy contract type | Resolution method |
|---|---|---|
| MetaMask / Rabby / browser wallet | Gnosis Safe smart contract | On-chain call to `getOwners()` on Polygon |
| Email / Google login (Magic) | Custom Polymarket minimal proxy | Polymarket CLOB API profile endpoint |

**Method 1 — Gnosis Safe (MetaMask users):** A Gnosis Safe is a multi-signature smart contract that stores a list of owner addresses on-chain. The `getOwners()` function can be called against any Safe contract to retrieve the address(es) that control it. Since Polymarket creates one Safe per MetaMask user, calling this function on each proxy address returns the user's real wallet address. This was done using the `web3.py` library.

**Method 2 — CLOB API (Magic/email users):** For users who signed up with email or Google via Magic, the proxy is a different contract type that doesn't expose a `getOwners()` function. Instead, Polymarket's own CLOB API profile endpoint (`clob.polymarket.com/profile/{proxy_address}`) returns ownership information including the real EOA, if the account is registered.

### 2.3 Why Alchemy Was Required

Resolving 116,054 proxy wallets via `getOwners()` requires making one live Polygon RPC call per address. The public free Polygon RPC endpoint (`polygon-rpc.com`) is rate-limited and unreliable under concurrent load. At 30 parallel worker threads making rapid on-chain read calls, the public endpoint frequently timed out or returned errors.

Alchemy's free-tier dedicated Polygon RPC endpoint provided materially higher throughput and reliability, allowing the resolution to complete in approximately 20 minutes rather than an estimated 10+ hours sequentially. The Alchemy key is used **exclusively for reading** public on-chain data (`getOwners()` is a pure view function) — no private keys or funds are involved.

### 2.4 Resolution Results

The resolution script ran with 30 parallel threads and checkpointed every 50 wallets. Spot checks were performed by manually verifying sample proxy addresses on Polygonscan — the "Contract Creator" field on Polygonscan is the address that deployed the contract, which in Polymarket's architecture is the same as the owner EOA. Every verified sample matched the resolved address.

```
Total proxy wallets processed : 116,054
Resolved to real EOA          :  63,540  (54.7%)
Unresolved                    :  52,514  (45.3%)
Unique EOAs in resolved set   :  63,264
```

The 52,514 unresolved addresses were predominantly inactive or very low-activity Magic/email login accounts not registered in the CLOB API's profile system, or accounts created before Polymarket standardised its wallet architecture. These accounts tend to be low-volume, low-activity traders — less likely to also be active on Hyperliquid.

**Output:** `eoa_wallets.json` — containing the full proxy→EOA mapping, the flat list of 63,264 unique EOA addresses, and the list of unresolved proxies.

---

## Part 3 — Cross-Referencing With Hyperliquid: Three Approaches

### 3.1 Attempt 1: HyperTracker (CoinMarketMan API)

HyperTracker (`ht-api.coinmarketman.com`) was the first tool evaluated for cross-referencing. It offers enriched, pre-aggregated Hyperliquid data including wallet intelligence, reconstructed closed-trade history, open-interest snapshots, and position-level metrics — all via a clean REST API.

**What worked:** The `/positions/coins` endpoint (listing all coins with open positions) and `/positions/open/coin/{coin}` (all wallets with open positions for a specific coin) both worked on the free plan and returned real data. This produced the first meaningful signal: **451 wallets** from the Polymarket EOA set were confirmed to currently hold open positions on Hyperliquid or trade.xyz.

**What failed:** The free tier enforces a hard cap of **100 API requests per day**. Scanning the full 315-coin universe for both open and closed positions required 600+ requests minimum — far beyond the daily quota. A second attempt to bulk-pull 30 days of position history via the `/positions` endpoint ran correctly for the first 4 coins (NVDA, TSLA, AAPL, AMZN) producing 10,000+ position records each, then hit the rate limit on the 5th coin and stopped. Upgrading to a paid plan was the only path forward with HyperTracker, and was deferred.

**Bugs discovered and fixed during this phase:**
- HIP-3 coin identifiers use a `xyz:` prefix (e.g. `xyz:NVDA`). When passed in a URL, the colon needed to be percent-encoded (`xyz%3ANVDA`) — without this, the API silently returned empty results.
- `SPX` on Hyperliquid is an unrelated memecoin (SPX6900), not the S&P 500 index. The correct HIP-3 ticker is `xyz:SP500`.

### 3.2 Attempt 2: Hyperliquid's Native Public API

The approach was then switched to Hyperliquid's own public `info` API (`api.hyperliquid.xyz/info`) — completely free, no API key required, with a weight-based rate limit of 1,200 per minute (each `clearinghouseState` call has weight 2, allowing approximately 600 calls per minute).

The `perpDexs` endpoint was used to dynamically discover all active trading venues: the main Hyperliquid exchange plus 8 HIP-3 builder dexes — `xyz`, `flx`, `vntl`, `hyna`, `km`, `abcd`, `cash`, and `para`. Checking all 9 venues for all 63,264 wallets was estimated at approximately 20 hours of runtime.

For the first pass, the check was scoped to `main` + `xyz` only, cutting estimated runtime to approximately 3.5 hours with 8 parallel workers. The `clearinghouseState` endpoint was called per wallet per dex — if `szi` (position size) was non-zero for any asset, the wallet was recorded as having an active position.

**Result:** **451 wallets** currently holding open positions (confirming the HyperTracker finding). This approach was reliable but slow, and critically only captured wallets with positions **open at that exact moment** — anyone who had already closed a hedge was invisible.

### 3.3 Breakthrough: Hydromancer's Reservoir Archive

Hydromancer (`docs.hydromancer.xyz`) maintains a free, public AWS S3 archive of complete Hyperliquid historical data — all fills, daily position snapshots, and candles — covering the main exchange and every HIP-3 deployer, with full history since each platform's launch.

The key insight: instead of checking 63,264 wallets one-at-a-time via API, the entire historical fill archive for trade.xyz could be **downloaded once** and filtered locally — no rate limits, no per-wallet queries, complete history.

**Access:** The S3 bucket (`s3://hydromancer-reservoir`) is "requester pays" — meaning a standard AWS account is used, and the requester pays AWS S3 transfer costs (a few cents for this volume of data). Hydromancer itself charges nothing. Access requires an AWS IAM access key with S3 read permissions.

**Download structure used:**
```
by_dex/xyz/fills/perp/all/date=YYYY-MM-DD/fills.parquet
```

One parquet file per calendar day, containing every trade.xyz fill for that date — with fields including `address`, `coin`, `side`, `price`, `size`, `direction`, `timestamp`, `realized_pnl`, `fee`, `is_liquidation`, and `start_position`.

Trade.xyz's complete history (launch date October 13, 2025, through the research date) spans **251 daily files**, which were downloaded using `boto3` with atomic write logic (download to `.tmp` first, rename on success) to protect against incomplete files from interrupted downloads.

---

## Part 4 — The Final Matching Pipeline

### 4.1 Filtering the Archive to Known Polymarket Wallets

All 251 daily parquet files were processed **one at a time** (to control memory usage — the largest single file exceeded 130MB, and loading all 251 simultaneously would require several gigabytes of RAM). Each file was loaded with only the required columns, filtered to addresses present in the 63,264-address Polymarket EOA set, and then discarded from memory before the next file was loaded.

**Scale:** The archive contained **337,724,184 total fills** across all of trade.xyz's history. After filtering:

```
Total fills scanned              : 337,724,184
Matched fills (Polymarket EOAs)  :   1,759,220
Unique matching wallets          :       1,413
```

**1,413 wallets** that traded on trade.xyz were confirmed to also be Polymarket Finance bettors. This filtered dataset was saved as `xyz_fills_matched_to_polymarket.parquet`.

### 4.2 Reconstructing Position Open/Close Intervals

For each unique (wallet, coin) pair in the filtered dataset, fills were sorted chronologically and walked through sequentially to reconstruct when each position was open and when it was closed. The logic tracked running position size (`pos`), incrementing on buys and decrementing on sells:

- When `pos` transitions from 0 to non-zero: position opened (record `open_time`)
- When `pos` transitions from non-zero to 0: position closed (record `close_time`, save interval)
- If `pos` is still non-zero at the end of the dataset: position remains open (close time set to current date)

The archive's own `start_position` field was used where available as a cross-check against the running accumulation.

### 4.3 Asset Matching

For each reconstructed position interval, the corresponding Polymarket bettor history was checked (via the proxy→EOA mapping and the per-market bettor lists from `markets_with_bettors.json`) for any market whose question text named the same asset.

The keyword matching list was expanded beyond the original 13 assets to include tickers discovered directly in the trade.xyz fill data that had not been anticipated:

| Original list | Added during analysis |
|---|---|
| NVDA, TSLA, AAPL, AMZN, GOOGL, META, MSFT, GOLD, SILVER, CL, SP500, XYZ100, SPCX, INTC, MSTR | PLTR (Palantir), SKHX (SK Hynix), EUR, COPPER, CRCL (Circle) |

### 4.4 Temporal Matching — The Critical Filter

Asset-match alone (same asset on both platforms, at any time) produced 1,413 wallets. The defining filter — which reduced this to the final 158 — required that the Hyperliquid position was **genuinely open at some point during the exact window the Polymarket bet was active**.

Formally: for a match to be confirmed, there must exist at least one point in time `t` such that:
```
market_startDate ≤ t ≤ market_endDate
AND
position_open_time ≤ t ≤ position_close_time
```

This is a strict test. A wallet that held an NVDA position in October 2025 but only placed their NVDA Polymarket bet in March 2026 (after the position closed) would **not** be confirmed — the timing doesn't overlap.

**Final result: 323 raw confirmed matches, across 158 unique wallets.**

### 4.5 Refining the Count — Wallet-Asset Pairs

Polymarket frequently splits one underlying directional view into many near-duplicate "price-ladder" markets. For example, "Will NVDA hit $200 / $190 / $165 / $150 before 2026?" are four separate yes/no markets, but they represent one underlying view about NVDA's price trajectory. A wallet betting on all four simultaneously, while holding an NVDA position, would produce four separate "confirmed matches" in the raw count.

To avoid inflating the finding, the cleanest unit of analysis is **unique (wallet, asset) pairs** — one underlying hedging relationship regardless of how many overlapping price-ladder markets it spans.

```
Raw market-level matches         : 323
Unique wallets                   : 158
Unique (wallet, asset) pairs     : 198
  ↳ 153 wallets hedged via 1 market
  ↳  41 wallets hedged via 2–5 overlapping markets
  ↳   4 wallets hedged via 6+ markets (price-ladder effect)
```

---

## Part 5 — Deeper Analysis

### 5.1 Entry and Exit Sequencing

To determine which platform traders entered first, per-trade timestamps (not just market-level windows) were pulled from the Polymarket Data API for the exact markets involved in each confirmed match. The `trades` endpoint returned every buy and sell for each of the 161 unique markets involved, filtered to only the specific wallets in our confirmed set.

These per-trade timestamps were compared against the Hyperliquid position's `open_time` from the reconstructed intervals:

- **If PM trade timestamp < HL position open_time:** trader entered Polymarket first
- **If HL position open_time < PM trade timestamp:** trader entered Hyperliquid first

The average gap between the two entry points was computed for each group.

**Results:**
- PM first group: average gap of **415 hours (~17 days)** before opening HL position
- HL first group: average gap of **475 hours (~20 days)** before placing PM bet

These gaps indicate deliberate, sustained positions rather than rapid reactive hedging.

### 5.2 Directional Analysis

**Hyperliquid side:** determined from the first fill in each position interval — a "B" (buy) side fill indicates a long position, "A" (sell) side indicates a short.

**Polymarket side:** the `outcome` field in the trade data was null for all records (not stored when the trade history was originally collected). The direction was instead inferred from the average buy price: shares bought above $0.55 indicate "buying Yes" (bullish), below $0.45 indicate "buying No" (bearish).

**Results (282 matches analyzed):**

| Pattern | Count | % |
|---|---|---|
| HL Short + PM Buying Yes | 101 | 35.8% |
| HL Long + PM Buying Yes | 84 | 29.8% |
| HL Long + PM Buying No | 65 | 23.0% |
| HL Short + PM Buying No | 23 | 8.2% |
| Neutral | 9 | 3.2% |

```
Genuine hedges (opposite directions) : 166  (58.9%)
Doubling down (same direction)        : 107  (37.9%)
Neutral                               :   9   (3.2%)
```

More than half of confirmed cross-platform activity represents genuine hedging — taking opposite directional positions to offset risk. The largest single pattern (35.8%) is traders who are **short on Hyperliquid** while **buying Yes on Polymarket** — a classic hedge against a short position in case the trade moves against them.

### 5.3 Hedge Sizing — Full vs Partial

The dollar size of each Hyperliquid position entry was compared against the dollar size of the corresponding Polymarket bet (`price × size` for both) to produce a hedge ratio:

```
hedge_ratio = HL_position_dollar_size / PM_bet_dollar_size
```

**Results:**
```
Full hedge (ratio 0.7x–1.3x)  :   6  (2.1%)
Over-hedged (ratio > 1.3x)    : 274  (97.2%)
Partial hedge (ratio < 0.7x)  :   1  (0.4%)
Average ratio                 : 15,091x
```

The 15,091x average ratio reveals a critical reframing of the entire finding: traders are **not using Polymarket to hedge their Hyperliquid positions** in any precise size-matched sense. Rather, these are primarily **Hyperliquid traders** (large positions, often leveraged) who place small correlated Polymarket bets on the same assets alongside their main trade. The median Polymarket bet size was $17.00, while a typical Hyperliquid position might be $5,000–$20,000 notional. Polymarket functions as a small directional side bet, not a precision hedge instrument.

### 5.4 Volume and Nominal Volume

Two distinct volume metrics were computed and kept separate:

**Dollar volume** (`price × size`): the actual cash paid or received per trade — the real capital deployed.

**Nominal volume** (`size × $1.00`): the full face-value exposure. Every Polymarket outcome share resolves to exactly $1 if it wins, independent of the price paid. A share bought for $0.30 controls $1.00 of face value — the same notional/nominal distinction used in options and futures markets.

**Results (across all confirmed hedge markets):**
```
Total nominal volume  : $84,047
Total dollar volume   : ~$41,779
Avg price paid        : ~49.7% of face value
```

**By asset (nominal):**
```
GOLD    : $38,384  (45.7%)
NVDA    : $23,645  (28.1%)
GOOGL   :  $6,722   (8.0%)
TSLA    :  $5,869   (7.0%)
AMZN    :  $5,384   (6.4%)
AAPL    :  $2,192   (2.6%)
```

Gold and NVDA together account for **73.8%** of all nominal hedge volume.

### 5.5 Bet Sizing

Individual bet sizes (dollar volume per trade) across 517 hedge-related trades:

```
Highest single bet : $5,698.99  (by 0x6973...)
Lowest single bet  : $0.02      (by 0xe08a...)
Average bet size   : $80.81
Median bet size    : $17.00
```

The gap between mean ($80.81) and median ($17.00) confirms a heavily right-skewed distribution — a small number of large bets pull the average up significantly, while the typical hedge bet is modest.

### 5.6 Frequency of Hedging

```
130 wallets hedged exactly once    (82.3%)
 20 wallets hedged twice           (12.7%)
  4 wallets hedged 3 times          (2.5%)
  4 wallets hedged 4 times          (2.5%)
```

82% are one-time cross-platform hedgers. The 28 repeat hedgers (18%) represent the most sophisticated, deliberate cohort.

### 5.7 Concentration

```
Top 10 traders share of hedge volume  : 49.8%
Top 50 traders share                  : 91.9%
Top 1% (1–2 wallets)                  : 17.5%
```

Hedging activity is highly concentrated — the top 10 traders account for nearly half of all hedge volume, consistent with other DeFi markets where a small number of sophisticated actors drive the majority of activity.

### 5.8 Hedging Over Time

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

The sharp peak in November–December 2025 coincides with trade.xyz's first full months of operation and a period of high Polymarket activity around post-election macro markets (Fed rate decisions, S&P 500 outcomes, major earnings). Activity has declined steadily since January 2026 as those specific markets resolved.

---

## Part 6 — Key Findings Summary

| Metric | Value |
|---|---|
| Polymarket Finance bettors (resolved EOAs) | 63,264 |
| Proxy resolution rate | 54.7% (63,540 of 116,054) |
| trade.xyz traders who also bet on Polymarket Finance | 1,413 |
| Confirmed cross-platform hedgers (asset + timing) | 158 |
| Unique wallet-asset hedging relationships | 198 |
| % of Finance bettors who are hedgers | 0.25% |
| Peak hedging month | November 2025 (71 wallets) |
| Most hedged asset by frequency | NVDA (117 matches) |
| Most hedged asset by nominal volume | GOLD ($38,384) |
| % genuine hedges (opposite directions) | 58.9% |
| % doubling down (same direction) | 37.9% |
| Average hedge ratio (HL size ÷ PM bet) | 15,091x |
| Median Polymarket bet size | $17.00 |
| Top 10 traders' share of hedge volume | 49.8% |
| Repeat hedgers (more than once) | 28 wallets (17.7%) |

---

## Part 7 — Data Sources and Tools

| Tool / Source | Purpose | Outcome |
|---|---|---|
| Polymarket Gamma API | Market discovery and metadata | Used throughout |
| Polymarket Data API (`/trades`) | Bettor address collection | Used throughout |
| Polymarket CLOB API (`/profile`) | Magic-login proxy resolution | Used as fallback |
| The Graph (Polymarket subgraph) | Initial exploration | Abandoned — wrong entity |
| Alchemy (Polygon RPC) | On-chain proxy resolution at scale | Critical — enabled 30-thread parallel resolution |
| web3.py | `getOwners()` calls on Gnosis Safe contracts | Used for MetaMask-login resolution |
| HyperTracker (CoinMarketMan) | Hyperliquid enriched data | Partially used — rate-limited on free tier |
| Hyperliquid native API | Live open-position snapshot | Used — basis for 451-wallet initial signal |
| Hydromancer Reservoir (AWS S3) | Complete historical trade.xyz archive | Breakthrough — enabled full-history analysis |
| boto3 | AWS S3 download of parquet files | Used for Hydromancer download |
| pandas + pyarrow | Parquet file processing | Used throughout analysis |
| DuckDB | Attempted bulk parquet scan | Trialled but memory-unsafe at full scale |

---

## Part 8 — Limitations and Honest Caveats

**Incomplete proxy resolution:** 45.3% of proxy wallets could not be resolved to a real EOA. These are disproportionately inactive, low-volume, or Magic-login accounts — but any genuinely active hedger in this group would be missed entirely.

**Trade.xyz launch date constraint:** The Hydromancer archive covers trade.xyz from its launch on October 13, 2025. Any Polymarket bets placed before that date cannot be matched against trade.xyz positions — earlier Finance market betting activity is structurally excluded from the hedging analysis.

**Other HIP-3 dexes not covered:** The complete-history analysis covers trade.xyz only. The remaining 7 active HIP-3 builder dexes (`flx`, `vntl`, `hyna`, `km`, `abcd`, `cash`, `para`) were not included in the Hydromancer download phase. Some confirmed hedgers using these venues may be missing from the final count.

**Keyword matching is not exhaustive:** The asset keyword list was built iteratively. Assets traded on trade.xyz but not yet in the keyword list would produce missed matches — the list covers the most significant assets by volume but is not guaranteed complete.

**Hedge ratio interpretation:** The 15,091x average hedge ratio reflects that Polymarket bets are tiny relative to Hyperliquid positions — this is structurally true given Polymarket's design (discrete binary bets, typically small notional) versus leveraged perpetuals. The finding should be framed as "Hyperliquid traders who also use Polymarket for small directional side bets" rather than "Polymarket bettors who hedge on Hyperliquid."

**Arkham entity labelling not completed:** Arkham's API requires a separate application process. The 158 confirmed wallets were not labelled at scale — manual spot-checks are recommended, prioritising the highest-frequency wallets, to determine how many are known funds, market makers, or notable traders versus anonymous retail.

**PM volume field unavailable:** The total Finance market volume on Polymarket was not successfully retrieved from the Gamma API (the correct volume field name was not confirmed during the research period). As a result, the hedgers' percentage share of total Finance market volume (Q6/Q13) was not computed.

