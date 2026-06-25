import json
import os
import pandas as pd
from collections import defaultdict

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("final_confirmed_hedgers.json", "r") as f:
    confirmed = json.load(f)

fills = pd.read_parquet("xyz_fills_with_pnl.parquet")
fills["timestamp"] = pd.to_datetime(fills["timestamp"], format="mixed", utc=True)

with open("pm_trade_history_for_matches.json", "r") as f:
    pm_history = json.load(f)

with open("enriched_matches.json", "r") as f:
    enriched = json.load(f)

eoa_q_to_market = {(m["eoa"], m["question"]): m for m in enriched}

TARGET_WALLETS = [
    "0x947db9d96aea1650d4879eba95e0d6aa0dd93e90",
    "0xbb999dd40dbd4be23a6b76ba65b94be3d817d8ac",
    "0xfece5d531c16508de2bd445e772e51d143c0d147",
    "0x2203e88248a59eec300f2bffecceabe29e0986b4",
]

all_output = {}

for wallet in TARGET_WALLETS:
    print(f"\n{'='*70}")
    print(f"WALLET: {wallet}")
    print(f"{'='*70}")

    wallet_matches = [m for m in confirmed["matches"] if m["eoa"] == wallet]
    by_asset = defaultdict(list)
    for m in wallet_matches:
        by_asset[m["coin"]].append(m)

    wallet_output = {}

    for coin, matches in by_asset.items():
        print(f"\n  ── {coin} ({len(matches)} market match(es)) ──────────────")
        asset_output = []

        # Get HL position details for this coin
        coin_fills = fills[
            (fills["address"] == wallet) &
            (fills["coin"].str.contains(coin, na=False))
        ].sort_values("timestamp")

        if not coin_fills.empty:
            first_fill = coin_fills.iloc[0]
            last_fill  = coin_fills.iloc[-1]
            hl_side    = "Long" if first_fill["side"] in ("B","buy","Buy") else "Short"
            total_pnl  = coin_fills["realized_pnl"].fillna(0).sum()
            print(f"  HL Position  : {hl_side}")
            print(f"  HL Period    : {first_fill['timestamp'].date()} → "
                  f"{last_fill['timestamp'].date()}")
            print(f"  HL PnL       : ${total_pnl:,.2f}")
            print(f"  HL Fills     : {len(coin_fills)}")
        else:
            hl_side = "Unknown"
            total_pnl = None

        print(f"\n  Matched Polymarket bets:")
        for i, m in enumerate(matches, 1):
            market = eoa_q_to_market.get((wallet, m["question"]), {})
            proxy  = market.get("proxy")
            cid    = market.get("conditionId")

            pm_trades = pm_history.get(proxy, {}).get(cid, []) if proxy and cid else []
            buys  = [t for t in pm_trades if "buy"  in (t.get("side") or "").lower()]
            sells = [t for t in pm_trades if "sell" in (t.get("side") or "").lower()]

            try:
                avg_price = sum(float(t["price"]) for t in buys) / len(buys)
                total_bet = sum(float(t["price"]) * float(t["size"]) for t in buys)
                pm_dir = "Yes (bullish)" if avg_price > 0.55 else \
                         "No (bearish)"  if avg_price < 0.45 else "Neutral"
            except (ZeroDivisionError, TypeError, ValueError):
                avg_price, total_bet, pm_dir = 0, 0, "Unknown"

            print(f"\n    [{i}] {m['question']}")
            print(f"        Window   : {m['market_window']}")
            print(f"        PM side  : Buying {pm_dir} @ avg ${avg_price:.2f}")
            print(f"        PM spent : ${total_bet:.2f}")
            print(f"        PM sells : {len(sells)}")

            asset_output.append({
                "question":   m["question"],
                "window":     m["market_window"],
                "pm_direction": pm_dir,
                "pm_avg_price": round(avg_price, 4),
                "pm_spent":   round(total_bet, 2),
                "pm_sold_early": len(sells) > 0,
            })

        wallet_output[coin] = {
            "hl_side": hl_side,
            "hl_pnl": round(total_pnl, 2) if total_pnl is not None else None,
            "pm_matches": asset_output
        }

    all_output[wallet] = wallet_output

import decimal

class SafeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)

with open("structural_hedger_profiles.json", "w") as f:
    json.dump(all_output, f, indent=2, cls=SafeEncoder)

print(f"\n\n✅ Saved full profiles to structural_hedger_profiles.json")