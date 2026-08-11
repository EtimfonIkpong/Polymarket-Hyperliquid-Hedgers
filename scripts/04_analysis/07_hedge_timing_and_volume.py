import json
import os
import csv
from collections import defaultdict
import pandas as pd

os.chdir(r"C:\Users\Etimfon\Desktop")

with open("wallet_behavior_breakdown.json", "r") as f:
    behavior = json.load(f)

with open("pm_history_all_323.json", "r") as f:
    pm_history = json.load(f)

with open("eoa_wallets.json", "r") as f:
    eoa_data = json.load(f)

with open("markets_with_bettors.json", "r") as f:
    markets_raw = json.load(f)

fills = pd.read_parquet("xyz_fills_with_pnl.parquet")
fills["timestamp"] = pd.to_datetime(fills["timestamp"], format="mixed", utc=True)

# ── Build lookups ─────────────────────────────────────────
eoa_to_proxies = defaultdict(list)
for proxy, info in eoa_data["proxy_to_eoa_map"].items():
    eoa_to_proxies[info["eoa"]].append(proxy)

question_to_market = {}
for m in markets_raw:
    q = m.get("question", "")
    if q:
        question_to_market[q] = m


def unix_to_dt(val):
    if val is None:
        return None
    try:
        v = int(val)
        return pd.Timestamp(v, unit="s", tz="UTC") if v < 10**12 \
               else pd.Timestamp(v, unit="ms", tz="UTC")
    except Exception:
        return None


def iso_to_dt(val):
    if not val:
        return None
    try:
        s = str(val).replace("Z", "+00:00")
        ts = pd.Timestamp(s)
        return ts.tz_localize("UTC") if ts.tzinfo is None else ts
    except Exception:
        return None


# ── Only wallets with at least one genuine hedge ──────────
hedge_wallets = {
    eoa: data for eoa, data in behavior["wallets"].items()
    if data["hedge_count"] > 0
}

print(f"Wallets with genuine hedges : {len(hedge_wallets)}\n")

timing_rows = []
volume_rows = []

for eoa, wallet_data in hedge_wallets.items():
    proxies              = eoa_to_proxies.get(eoa, [])
    total_dollar_vol     = 0.0
    total_nominal_vol    = 0.0
    total_trades         = 0

    for hedge_match in wallet_data["hedge_markets"]:
        coin     = hedge_match["coin"]
        question = hedge_match["question"]
        hl_side  = hedge_match["hl_side"]
        pm_dir   = hedge_match["pm_dir"]

        market   = question_to_market.get(question, {})
        end_date = iso_to_dt(market.get("endDate"))
        cid      = market.get("conditionId")

        if not cid:
            continue

        # ── PM trade data ─────────────────────────────────
        pm_trades = []
        for proxy in proxies:
            trades = pm_history.get(proxy.lower(), {}).get(cid, [])
            if trades:
                pm_trades = trades
                break

        buys  = [t for t in pm_trades
                 if "buy"  in (t.get("side") or "").lower()]
        sells = [t for t in pm_trades
                 if "sell" in (t.get("side") or "").lower()]

        if not buys:
            continue

        # ── HL position data for this (wallet, coin) ──────
        coin_fills = fills[
            (fills["address"] == eoa) &
            (fills["coin"].str.contains(coin, na=False))
        ].sort_values("timestamp")

        hl_open_dt   = coin_fills.iloc[0]["timestamp"]  if not coin_fills.empty else None
        hl_close_dt  = coin_fills.iloc[-1]["timestamp"] if not coin_fills.empty else None
        hl_entry_px  = round(float(coin_fills.iloc[0]["price"]), 4) \
                       if not coin_fills.empty else None
        hl_exit_px   = round(float(coin_fills.iloc[-1]["price"]), 4) \
                       if not coin_fills.empty else None
        hl_fills_n   = len(coin_fills)
        hl_pnl       = round(float(coin_fills["realized_pnl"].fillna(0).sum()), 2) \
                       if not coin_fills.empty else None

        # hl_notional = sum of (price x size) across ALL fills
        # Captures full traded value, not just the opening fill
        if not coin_fills.empty:
            cf = coin_fills.copy()
            cf["fill_notional"] = (
                cf["price"].astype(float) * cf["size"].astype(float)
            )
            hl_notional = round(float(cf["fill_notional"].sum()), 2)
            # Weighted avg entry price from buy fills only
            buy_fills = cf[cf["side"].isin(["B", "buy", "Buy"])]
            if not buy_fills.empty:
                total_buy_size = float(buy_fills["size"].astype(float).sum())
                hl_avg_entry   = round(
                    float((buy_fills["price"].astype(float) *
                           buy_fills["size"].astype(float)).sum())
                    / total_buy_size, 4
                ) if total_buy_size > 0 else None
                hl_total_size  = round(total_buy_size, 4)
            else:
                hl_avg_entry  = None
                hl_total_size = None
        else:
            hl_notional   = None
            hl_avg_entry  = None
            hl_total_size = None

        # ── One row per PM buy ────────────────────────────
        for buy in buys:
            ts    = unix_to_dt(buy.get("timestamp"))
            price = float(buy.get("price", 0) or 0)
            size  = float(buy.get("size", 0) or 0)
            token = buy.get("token_bought", "Unknown")

            if ts and end_date:
                days_before = (end_date - ts).total_seconds() / 86400
            else:
                days_before = None

            dollar_vol  = price * size
            nominal_vol = size * 1.0

            total_dollar_vol  += dollar_vol
            total_nominal_vol += nominal_vol
            total_trades      += 1

            timing_rows.append({
                # ── Wallet ──────────────────────────────
                "wallet":                    eoa,
                # ── Polymarket side ──────────────────────
                "pm_coin":                   coin,
                "pm_direction":              pm_dir,
                "pm_question":               question,
                "pm_token_bought":           token,
                "pm_buy_price":              round(price, 4),
                "pm_shares_bought":          round(size, 2),
                "pm_dollar_spent":           round(dollar_vol, 2),
                "pm_nominal_value":          round(nominal_vol, 2),
                "pm_buy_timestamp":          ts.isoformat() if ts else None,
                "pm_market_end_date":        end_date.isoformat() if end_date else None,
                "pm_days_before_resolution": round(days_before, 1)
                                             if days_before is not None else None,
                "pm_sold_early":             "Yes" if sells else "No",
                # ── Hyperliquid side ─────────────────────
                "hl_coin":                   coin,
                "hl_side":                   hl_side,
                "hl_open_timestamp":         hl_open_dt.isoformat()
                                             if hl_open_dt is not None else None,
                "hl_close_timestamp":        hl_close_dt.isoformat()
                                             if hl_close_dt is not None else None,
                "hl_avg_entry_price":        hl_avg_entry,
                "hl_exit_price":             hl_exit_px,
                "hl_total_buy_size":         hl_total_size,
                "hl_total_notional_all_fills": hl_notional,
                "hl_realized_pnl":           hl_pnl,
                "hl_fills_count":            hl_fills_n,
            })

        # Sell volume also counts toward wallet volume
        for sell in sells:
            price = float(sell.get("price", 0) or 0)
            size  = float(sell.get("size", 0) or 0)
            total_dollar_vol  += price * size
            total_nominal_vol += size * 1.0
            total_trades      += 1

    volume_rows.append({
        "wallet":               eoa,
        "hedge_count":          wallet_data["hedge_count"],
        "doubledown_count":     wallet_data["doubledown_count"],
        "assets_hedged":        ", ".join(wallet_data["assets"]),
        "total_pm_trades":      total_trades,
        "total_dollar_volume":  round(total_dollar_vol, 2),
        "total_nominal_volume": round(total_nominal_vol, 2),
        "avg_dollar_per_trade": round(total_dollar_vol / total_trades, 2)
                                if total_trades else 0,
    })


# ── Summary ───────────────────────────────────────────────
valid_days = [r["pm_days_before_resolution"] for r in timing_rows
              if r["pm_days_before_resolution"] is not None]
valid_days.sort()
n = len(valid_days)

print(f"{'='*60}")
print(f"HEDGE ENTRY TIMING (days before market resolution)")
print(f"{'='*60}")
print(f"Total hedge buy transactions : {len(timing_rows)}")
print(f"With timing data             : {n}")
if valid_days:
    print(f"\n  Min      : {valid_days[0]:.1f} days")
    print(f"  25th pct : {valid_days[n//4]:.1f} days")
    print(f"  Median   : {valid_days[n//2]:.1f} days")
    print(f"  75th pct : {valid_days[3*n//4]:.1f} days")
    print(f"  Max      : {valid_days[-1]:.1f} days")
    print(f"  Mean     : {sum(valid_days)/n:.1f} days")

    late   = sum(1 for d in valid_days if d <= 7)
    mid    = sum(1 for d in valid_days if 7 < d <= 30)
    early  = sum(1 for d in valid_days if d > 30)
    print(f"\n  Within 1 week of resolution  : {late}  ({late/n*100:.1f}%)")
    print(f"  1 week – 1 month before      : {mid}   ({mid/n*100:.1f}%)")
    print(f"  More than 1 month before     : {early} ({early/n*100:.1f}%)")

total_dv = sum(r["total_dollar_volume"] for r in volume_rows)
total_nv = sum(r["total_nominal_volume"] for r in volume_rows)
print(f"\n{'='*60}")
print(f"PM VOLUME — GENUINE HEDGER WALLETS")
print(f"{'='*60}")
print(f"Total dollar volume  : ${total_dv:,.2f}")
print(f"Total nominal volume : ${total_nv:,.2f}")

# ── Save CSVs ─────────────────────────────────────────────
timing_fields = [
    "wallet",
    "pm_coin", "pm_direction", "pm_question",
    "pm_token_bought", "pm_buy_price", "pm_shares_bought",
    "pm_dollar_spent", "pm_nominal_value",
    "pm_buy_timestamp", "pm_market_end_date",
    "pm_days_before_resolution", "pm_sold_early",
    "hl_coin", "hl_side",
    "hl_open_timestamp", "hl_close_timestamp",
    "hl_avg_entry_price", "hl_exit_price",
    "hl_total_buy_size", "hl_total_notional_all_fills",
    "hl_realized_pnl", "hl_fills_count",
]
with open("hedge_entry_timing.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=timing_fields)
    writer.writeheader()
    writer.writerows(timing_rows)

volume_fields = [
    "wallet", "hedge_count", "doubledown_count", "assets_hedged",
    "total_pm_trades", "total_dollar_volume",
    "total_nominal_volume", "avg_dollar_per_trade",
]
with open("hedger_pm_volume.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=volume_fields)
    writer.writeheader()
    writer.writerows(
        sorted(volume_rows, key=lambda x: -x["total_dollar_volume"]))

print(f"\n✅ Saved to:")
print(f"   hedge_entry_timing.csv  — every hedge buy with PM + HL timestamps")
print(f"   hedger_pm_volume.csv    — total PM volume per hedger wallet")
