## Methodology: Identifying Cross-Platform Hedgers Between Polymarket and Hyperliquid HIP-3

---

### Research Question

This research investigates whether traders who bet on Polymarket's Finance-category markets simultaneously hold or held correlated perpetual positions on Hyperliquid's HIP-3 builder-deployed exchanges, specifically trade.xyz, where the same real-world assets (NVDA, GOLD, SP500, TSLA, etc.) are tradeable as on-chain perpetual futures.

The central question: is cross-platform hedging between prediction markets and perpetual DEXs a real, observable behaviour, or does an exhaustive search of on-chain data find essentially nothing?

---

### Background: Why Trade.xyz

HIP-3 is a Hyperliquid standard allowing independent builders to deploy perpetual markets on Hyperliquid's infrastructure. Trade.xyz launched on October 13, 2025 as the first HIP-3 deployer, offering 24/7 perpetual markets for US equities, indices, and commodities — NVDA, TSLA, AAPL, AMZN, GOOGL, META, MSFT, SP500, GOLD, SILVER, and crude oil. These assets map directly onto the types of questions Polymarket's Finance category asks. This made trade.xyz the most natural venue to test the hedging hypothesis.

---

### Phase 1: Building the Polymarket Dataset

**Step 1 — Market identification**

Polymarket's Gamma API (`gamma-api.polymarket.com/markets`) was queried using `tag_id=120`, which corresponds to Polymarket's internal Finance category. The raw pull returned thousands of markets, many of which were unrelated to assets tradeable on trade.xyz — niche crypto FDV questions, regulatory decisions, executive appointment questions. A keyword filter was applied to each market's question text, matching against known HIP-3-tradable tickers and their common names: nvidia/nvda, tesla/tsla, apple/aapl, amazon/amzn, google/googl/alphabet, meta/facebook, microsoft/msft, gold, silver, oil/crude/brent/wti, s&p/sp500, nasdaq, spacex, intel/intc, palantir/pltr, and macroeconomic terms like fed, interest rate, inflation, cpi, gdp. This produced a working dataset of **2,004 HIP-3-relevant Polymarket markets**, each recorded with its `conditionId`, `startDate`, `endDate`, and question text.

An early attempt was made using The Graph's Polymarket subgraph. The `positions` entity in the subgraph was queried, but it turned out to track liquidity provider positions, not bettor activity — markets with hundreds of known traders showed only 1–2 positions. This path was abandoned in favour of Polymarket's own REST APIs.

**Step 2 — Collecting bettor addresses**

For each of the 2,004 markets, Polymarket's Data API (`data-api.polymarket.com/trades`) was paginated at 500 records per page. Every `proxyWallet` field was extracted — this is the on-chain address that executed each trade. The collection ran with checkpointing every 25 markets to allow safe interruption and resumption. This produced **116,054 unique proxy wallet addresses**, saved alongside a per-market breakdown that preserved each market's question text, time window, and full bettor list.

---

### Phase 2: Resolving Proxy Wallets to Real Identities

**The problem with proxy wallets**

Polymarket does not allow users to trade directly from their personal wallet. When a user first signs up, a dedicated smart-contract proxy wallet is deployed on Polygon specifically for that user. All bets, USDC, and outcome tokens live inside this proxy — not in the user's real wallet. This meant the 116,054 addresses collected were Polymarket-specific contract addresses, not the addresses these people use anywhere else including Hyperliquid. Cross-referencing them directly against Hyperliquid would find zero matches, not because nobody hedges, but because we would be comparing the wrong addresses.

**Two proxy architectures**

Two different proxy types exist depending on how the user signed up. For MetaMask and browser wallet users, Polymarket deploys a Gnosis Safe smart contract. The `getOwners()` function can be called on any Gnosis Safe to return the owner's real wallet address — this was done using the web3.py library with direct Polygon RPC calls. For email and Google login users (via Magic), Polymarket deploys a different custom minimal proxy contract. These were resolved using Polymarket's CLOB API profile endpoint (`clob.polymarket.com/profile/{proxy_address}`), which returns ownership information including the real EOA.

**Why Alchemy was needed**

Resolving 116,054 proxy wallets via `getOwners()` requires one live Polygon RPC call per address. The public free Polygon RPC endpoint rate-limited and timed out under concurrent load. Alchemy's free-tier dedicated Polygon endpoint provided the throughput needed to run 30 parallel worker threads, completing the resolution in approximately 20 minutes rather than an estimated 10+ hours sequentially. The Alchemy key was used exclusively for reading public on-chain data — `getOwners()` is a pure view function with no access to private keys or funds.

**Resolution results**

Of the 116,054 proxy wallets processed, **63,540 were resolved** to a real EOA (54.7%), producing **63,264 unique EOA addresses**. The remaining 52,514 were predominantly inactive Magic/email accounts not registered in the CLOB API profile system. Spot checks were performed by manually verifying sample proxy addresses on Polygonscan — the "Contract Creator" field confirmed the resolved EOA in every verified sample.

---

### Phase 3: Cross-Referencing With Hyperliquid

**What didn't work: HyperTracker**

HyperTracker (CoinMarketMan's Hyperliquid data API) was evaluated first. It offers enriched pre-aggregated data including wallet intelligence, reconstructed closed trades, and position history. In practice, the free tier's hard cap of 100 API requests per day was far too restrictive. Even scanning a handful of HIP-3 coins for open and closed positions burned through the daily quota in minutes. Downloading 30 days of position history hit the rate limit after just 4 of 15 tracked coins. Along the way, two bugs were identified and fixed: HIP-3 coin names use a `xyz:` prefix requiring URL-encoding in requests, and `SPX` on Hyperliquid is an unrelated memecoin — the actual S&P 500 market is `xyz:SP500`.

**What worked: Hydromancer Reservoir**

Hydromancer (`docs.hydromancer.xyz`) maintains a free, public AWS S3 archive of complete Hyperliquid historical data covering the main exchange and every HIP-3 deployer, with full history since each platform's launch. The S3 bucket `hydromancer-reservoir` is "requester pays," meaning a standard AWS account incurs only cents of data transfer cost — Hydromancer charges nothing.

The path used was `by_dex/xyz/fills/perp/all/date=YYYY-MM-DD/fills.parquet` — one parquet file per day, containing every trade.xyz fill for that date. Each file includes the fields: address, coin, side, price, size, timestamp, realized_pnl, fee, is_liquidation, and start_position. Files were downloaded using `boto3` with atomic write logic (download to a `.tmp` file first, rename to final name only on success) to protect against incomplete files from interrupted downloads.

**The archive**

Trade.xyz's complete history from launch (October 13, 2025) through the research date spanned **251 daily parquet files**. All 251 were successfully downloaded. The archive contained **337,724,184 total fills** across trade.xyz's entire history.

**Initial snapshot**

Before downloading the full archive, Hyperliquid's native public API (`api.hyperliquid.xyz/info`) was used for a quick current-state snapshot. The `perpDexs` endpoint discovered all active trading venues (main exchange plus 8 HIP-3 dexes: xyz, flx, vntl, hyna, km, abcd, cash, para). The `clearinghouseState` endpoint (weight 2, no API key, ~600 calls per minute) was called for each of the 63,264 EOAs on the main exchange and trade.xyz. This identified **451 wallets** with currently open positions — used as an early signal only, not the final analysis.

---

### Phase 4: The Matching Pipeline

**Filtering the archive**

All 251 daily parquet files were processed one file at a time to control memory usage — the largest single file exceeded 130MB, and loading all 251 simultaneously would require several gigabytes of RAM. Each day's file was loaded with only the required columns, the address column was filtered to the 63,264-address Polymarket EOA set, and the file was discarded from memory before the next was loaded. This produced **1,759,220 matched fills** belonging to **1,413 unique wallets** that traded on both platforms.

**Asset matching**

For each unique (wallet, coin) pair in the filtered dataset, fills were sorted chronologically and walked through to reconstruct exactly when each position was open and when it was closed, tracking running position size through each buy and sell. The keyword matching list was expanded beyond the original planned 13 assets to include tickers discovered directly in the trade.xyz fill data that had not been anticipated: PLTR (Palantir), SKHX (SK Hynix), EUR, COPPER, and CRCL (Circle).

For each reconstructed position interval, the corresponding Polymarket bettor history was checked for any market whose question text named the same asset.

**Broad temporal test**

The initial broad test required only that the HL position interval overlapped with the market's overall active window (startDate → endDate). Finance ladder markets stay open for weeks to months, making this straightforward to satisfy. This produced **323 raw match instances across 158 unique wallets**.

**Strict temporal test (reviewer-required correction)**

The broad test was correctly flagged as too permissive by peer review. The strict definition uses the wallet's own bet-holding window instead of the market's overall window:

- Start: timestamp of the wallet's first buy on that specific market
- End: timestamp of the wallet's last sell (if sold early), or the market's endDate (if held to resolution)

This was implemented using per-trade timestamps from re-fetched Polymarket trade history. The re-fetch was necessary because the original collection only stored price, size, and side not timestamps for each individual trade. An additional bug was identified and corrected: an early version of the overlap function used `b_start >= a_start` as the second condition rather than the correct `b_start <= a_end`, which biased results toward HL-first cases. The correct standard interval overlap test (a_start ≤ b_end AND b_start ≤ a_end) was applied in the final version.

Of 323 broad matches: 19 could not be evaluated because no PM trade data was retrievable for that proxy wallet on that market. Of the remaining 304, **220 passed the strict test and 84 failed**. The strict test confirmed **118 unique wallets**.

---

### Phase 5: Direction Analysis

**Why the original method was wrong**

The first attempt at measuring direction used average buy price as a proxy: prices above $0.55 were labeled "Buying Yes (bullish)" and prices below $0.45 were labeled "Buying No (bearish)." This approach fails in two independent ways. First, price does not identify which token was bought a trader buying the NO token at $0.80 in a market with only 20% probability gets labeled "bullish" when they are clearly bearish. Second, "Yes" is not always bullish. Polymarket includes markets phrased as "Will MSFT dip to $465 in November?" buying Yes on this question is a bearish bet. The original method produced 58.9% genuine hedges, a number that could not be sustained under scrutiny.

**The corrected method**

Polymarket trade history was re-fetched for all 161 unique markets involved in confirmed matches, this time retaining the `outcome` and `outcomeIndex` fields. Direction was determined in two steps. First, the actual token bought was identified: if `outcomeIndex` is 0 the wallet bought the Yes token; if 1 they bought the No token. Second, each market question was classified for polarity whether "Yes" represents a bullish or bearish outcome for the underlying asset. Markets phrased as "hit $X," "reach $X," "above $X," "largest company," or "first to $X" are bullish-if-yes. Markets phrased as "dip to $X," "close below $X," "fall to $X," or "close at <$X" are bearish-if-yes. Markets phrased as "close between $X and $Y" or "up or down" are neutral. True direction is then the combination of polarity and the token actually bought.

**Corrected results**

At the wallet level (each wallet counted once using their dominant direction pattern, 96 wallets with direction data):

- Doubling down (same directional view on both platforms): **57 wallets (59.4%)**
- Genuine hedging (opposite directional positions): **31 wallets (32.3%)**
- Neutral: **8 wallets (8.3%)**

The direction finding reversed completely from the original method. The majority of cross-platform activity is speculative amplification, not risk reduction.

Note: 22 of 118 wallets could not be directionally classified because the outcomeIndex field was null in their stored trade data (trades were stored as sells only, which carry no directional information). These wallets are excluded from directional conclusions.

---

### Phase 6: Deeper Analysis

**Entry and exit sequencing**

For each tight-confirmed match, the gap between the PM buy timestamp and the HL position open timestamp was calculated. A positive gap means PM was entered first and HL opened later; a negative gap means HL was opened first and PM was placed later.

Of 220 tight matches with timing data: 83 (37.7%) had PM entered first with a median gap of 4.0 days before HL opened, and 137 (62.3%) had HL entered first with a median gap of 8.3 days before the PM bet was placed. In the majority of cases, the Hyperliquid position already existed when the Polymarket bet was placed consistent with Hyperliquid traders discovering Polymarket, not Polymarket bettors hedging on Hyperliquid.

**Wallet behavior breakdown**

Each of the 96 wallets was assessed individually counting every hedge and doubledown instance separately rather than relying solely on the dominant pattern. This revealed that 37 wallets had at least one genuine hedge instance even if hedging was not their dominant pattern.

**PM entry timing for genuine hedgers**

Of 68 hedge buy transactions from the 37 wallets with at least one genuine hedge: 39.7% were placed within 1 week of resolution, 44.1% between 1 week and 1 month before resolution, and 16.2% more than 1 month before. The median time between placing the PM bet and market resolution was 9 days, with a maximum of 55 days and an average of 13.0 days.

**High-confidence entry analysis**

34 of those 68 hedge buy transactions were placed at a price of $0.90 or higher per share — entering markets close to certain resolution. These were further broken down by bet size:

For bets of $50 or more: 18 rows from 7 wallets, with a median of just 16 hours and 48 minutes before resolution, and 72.2% buying Yes. For bets of $10–$50: 10 rows from 9 wallets, with a median of 10 days before resolution, and 40% buying Yes. For bets under $10: 6 rows from 5 wallets, with a median of 15 days before resolution, and only 16.7% buying Yes. The pattern shows that larger bets at high-confidence prices entered very close to resolution and were consistent with near-certainty farming rather than genuine directional hedging.

**PM/HL hedge ratio**

HL notional was computed as the sum of price times size across all fills (not just the first fill, which would understate positions built across multiple entries), divided by 2 to correct for both sides of each fill being counted. The average PM/HL ratio was 0.054641 with a median of 0.002396 — meaning the typical Polymarket bet was 0.2% the size of the corresponding Hyperliquid position. At this ratio, the Polymarket position could not meaningfully offset the Hyperliquid risk in any economically significant sense.

**Bet size distribution**

Of the 37 wallets with at least one genuine hedge: 1 wallet placed a bet of more than $1,000; 5 wallets placed bets between $100 and $999; 11 wallets placed bets between $25 and $99; and 22 wallets placed bets between $2 and $24. The 5 wallets in the $100–$999 range were analyzed in depth none showed periodic or systematic hedging behaviour, all entered the market just once, and all had PM/HL ratios well below 0.01.

---

### Phase 7: Overall Assessment

The research set out to find whether systematic cross-platform hedging exists between Polymarket and trade.xyz. After a rigorous search of 338 million fills matched against 63,264 real wallets:

Only 0.19% of Finance bettors had any strict asset-and-time overlap with trade.xyz. Of those, the dominant behaviour was directional amplification (doubling down), not risk reduction. The median PM/HL ratio of 0.002 means Polymarket bets are economically negligible relative to Hyperliquid positions. Activity was concentrated almost entirely in trade.xyz's first two months of operation and collapsed to near-zero by mid-2026. 

The most accurate characterisation of the observed behaviour is: a small number of Hyperliquid traders occasionally place small, correlated bets on Polymarket about assets they are already trading. This is not hedging in any economically meaningful sense. Cross-platform hedging between Polymarket and trade.xyz, at this point in time, essentially does not exist at detectable scale.
