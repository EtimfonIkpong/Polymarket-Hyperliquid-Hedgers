import pandas as pd
import json
import os
from collections import defaultdict, Counter

os.chdir(r"C:\Users\Etimfon\Desktop")

# ── Load all required data ────────────────────────────────
with open("final_confirmed_hedgers.json", "r") as f:
    confirmed = json.load(f)

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

question_to_cid = {}
question_to_end = {}
for m in markets_raw:
    q   = m.get("question", "")
    cid = m.get("conditionId")
    end = m.get("endDate")
    if q and cid:
        question_to_cid[q] = cid
        question_to_end[q] = end


# ── Timestamp helpers ─────────────────────────────────────
def unix_to_ts(val):
    """Convert unix seconds or ms to UTC pandas Timestamp."""
    if val is None:
        return None
    try:
        v = int(val)
        # unix seconds if < 10^12, else milliseconds
        return pd.Timestamp(v, unit="s", tz="UTC") if v < 10**12 \
               else pd.Timestamp(v, unit="ms", tz="UTC")
    except Exception:
        return None


def iso_to_ts(val):
    """Convert ISO string to UTC pandas Timestamp."""
    if not val:
        return None
    try:
        s = str(val).replace("Z", "+00:00")
        ts = pd.Timestamp(s)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts
    except Exception:
        return None


def windows_overlap(a_start, a_end, b_start, b_end):
    """
    Returns True if two time windows share ANY point in time.
    Standard interval overlap: a starts before b ends AND b starts before a ends.
    """
    if any(x is None for x in [a_start, a_end, b_start, b_end]):
        return False
    return a_start <= b_end and b_start <= a_end


# ── Reconstruct HL intervals from fills ───────────────────
def get_hl_intervals(address, coin):
    coin_fills = fills[
        (fills["address"] == address) &
        (fills["coin"].str.contains(coin, na=False))
    ].sort_values("timestamp")

    if coin_fills.empty:
        return []

    intervals, pos, open_start = [], 0.0, None
    for _, row in coin_fills.iterrows():
        try:
            sz = float(row["size"])
        except (TypeError, ValueError):
            sz = 0.0
        side  = row.get("side", "")
        delta = sz if side in ("B", "buy", "Buy") else -sz
        was_zero = (pos == 0)
        pos += delta

        if was_zero and pos != 0:
            open_start = row["timestamp"]
        elif not was_zero and pos == 0 and open_start is not None:
            intervals.append((open_start, row["timestamp"]))
            open_start = None

    if open_start is not None:
        intervals.append((open_start, pd.Timestamp.now(tz="UTC")))

    return intervals


# ══════════════════════════════════════════════════════════
# MAIN: Apply tight test to ALL 323 confirmed matches
# ══════════════════════════════════════════════════════════
print("Applying tight temporal test to all 323 matches...\n")

tight_matches  = []
loose_only     = []
no_pm_data     = []
no_hl_data     = []
gaps_pm_first  = []
gaps_hl_first  = []

for match in confirmed["matches"]:
    eoa      = match["eoa"]
    coin     = match["coin"]
    question = match["question"]

    cid     = question_to_cid.get(question)
    proxies = eoa_to_proxies.get(eoa, [])

    if not cid or not proxies:
        no_pm_data.append(match)
        continue

    # ── Get PM bet-holding window ─────────────────────────
    # Find which proxy has trades for this market
    pm_trades = []
    used_proxy = None
    for proxy in proxies:
        trades = pm_history.get(proxy.lower(), {}).get(cid, [])
        if trades:
            pm_trades = trades
            used_proxy = proxy
            break

    if not pm_trades:
        no_pm_data.append(match)
        continue

    buys  = [t for t in pm_trades if "buy"  in (t.get("side") or "").lower()]
    sells = [t for t in pm_trades if "sell" in (t.get("side") or "").lower()]

    if not buys:
        no_pm_data.append(match)
        continue

    # PM bet window: first buy → last sell (or market endDate)
    try:
        pm_bet_start = min(unix_to_ts(t["timestamp"]) for t in buys
                           if t.get("timestamp"))
    except Exception:
        no_pm_data.append(match)
        continue

    if sells:
        try:
            pm_bet_end = max(unix_to_ts(t["timestamp"]) for t in sells
                             if t.get("timestamp"))
        except Exception:
            pm_bet_end = iso_to_ts(question_to_end.get(question))
    else:
        pm_bet_end = iso_to_ts(question_to_end.get(question))

    if pm_bet_start is None or pm_bet_end is None:
        no_pm_data.append(match)
        continue

    # Ensure end is after start
    if pm_bet_end <= pm_bet_start:
        pm_bet_end = pm_bet_start + pd.Timedelta(hours=1)

    # ── Get HL position intervals ─────────────────────────
    intervals = get_hl_intervals(eoa, coin)
    if not intervals:
        no_hl_data.append(match)
        continue

    # Find the best-matching HL interval
    best_interval = min(intervals,
                        key=lambda iv: abs((iv[0] - pm_bet_start).total_seconds()))
    hl_open, hl_close = best_interval

    # ── Test tight overlap ────────────────────────────────
    tight = windows_overlap(hl_open, hl_close, pm_bet_start, pm_bet_end)

    record = {
        "eoa":           eoa,
        "coin":          coin,
        "question":      question,
        "pm_bet_start":  str(pm_bet_start),
        "pm_bet_end":    str(pm_bet_end),
        "pm_held_days":  round((pm_bet_end - pm_bet_start).total_seconds()
                                / 86400, 1),
        "hl_open":       str(hl_open),
        "hl_close":      str(hl_close),
        "tight_overlap": tight,
    }

    if tight:
        tight_matches.append(record)
        # Gap: positive = HL opened after PM bet (PM first)
        #      negative = HL opened before PM bet (HL first)
        gap_hrs = (hl_open - pm_bet_start).total_seconds() / 3600
        if gap_hrs >= 0:
            gaps_pm_first.append(gap_hrs)
        else:
            gaps_hl_first.append(abs(gap_hrs))
    else:
        loose_only.append(record)

tight_wallets = set(m["eoa"] for m in tight_matches)
loose_wallets = set(m["eoa"] for m in loose_only)

print(f"{'═'*60}")
print(f"RESULTS: BROAD vs TIGHT TEMPORAL TEST (Full 323)")
print(f"{'═'*60}")
print(f"\nBroad test (market window overlap):")
print(f"  Matches : 323")
print(f"  Wallets : 158")
print(f"\nTight test (wallet bet-holding window):")
print(f"  Matches : {len(tight_matches)}")
print(f"  Wallets : {len(tight_wallets)}")
print(f"\nDropped by tighter test:")
print(f"  Matches : {len(loose_only)}")
print(f"  Wallets : {len(loose_wallets - tight_wallets)} "
      f"(no longer qualify at all)")
print(f"\nCould not evaluate (no PM trade data):")
print(f"  Matches : {len(no_pm_data)}")
print(f"\nCould not evaluate (no HL fill data):")
print(f"  Matches : {len(no_hl_data)}")

# Gap analysis
print(f"\n{'─'*60}")
print(f"GAP ANALYSIS (tight confirmed set)")
print(f"{'─'*60}")
if gaps_pm_first:
    sorted_pm = sorted(gaps_pm_first)
    print(f"PM entered first ({len(gaps_pm_first)} matches):")
    print(f"  Avg gap to HL open : "
          f"{sum(gaps_pm_first)/len(gaps_pm_first):.1f} hrs "
          f"({sum(gaps_pm_first)/len(gaps_pm_first)/24:.1f} days)")
    print(f"  Median gap         : "
          f"{sorted_pm[len(sorted_pm)//2]:.1f} hrs "
          f"({sorted_pm[len(sorted_pm)//2]/24:.1f} days)")
if gaps_hl_first:
    avg_abs = sum(gaps_hl_first)/len(gaps_hl_first)
    sorted_hl = sorted(gaps_hl_first)
    print(f"HL entered first ({len(gaps_hl_first)} matches):")
    print(f"  Avg gap to PM bet  : {avg_abs:.1f} hrs ({avg_abs/24:.1f} days)")
    print(f"  Median gap         : "
          f"{sorted_hl[len(sorted_hl)//2]:.1f} hrs "
          f"({sorted_hl[len(sorted_hl)//2]/24:.1f} days)")

# Save
with open("tight_confirmed_v2.json", "w") as f:
    json.dump({
        "broad_matches":       323,
        "broad_wallets":       158,
        "tight_matches":       len(tight_matches),
        "tight_wallets":       len(tight_wallets),
        "loose_only_matches":  len(loose_only),
        "no_pm_data":          len(no_pm_data),
        "no_hl_data":          len(no_hl_data),
        "gap_analysis": {
            "pm_first_count":  len(gaps_pm_first),
            "pm_first_avg_hrs": round(sum(gaps_pm_first)/len(gaps_pm_first), 1)
                                if gaps_pm_first else None,
            "pm_first_median_hrs": sorted(gaps_pm_first)[len(gaps_pm_first)//2]
                                   if gaps_pm_first else None,
            "hl_first_count":  len(gaps_hl_first),
            "hl_first_avg_hrs": round(sum(gaps_hl_first)/len(gaps_hl_first), 1)
                                if gaps_hl_first else None,
        },
        "matches": tight_matches,
    }, f, indent=2)

print(f"\n✅ Saved to tight_confirmed_v2.json")