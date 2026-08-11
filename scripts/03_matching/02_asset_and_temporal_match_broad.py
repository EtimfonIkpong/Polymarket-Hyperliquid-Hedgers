import requests
import json
import os
import time
from datetime import datetime, timezone

os.chdir(r"C:\Users\Etimfon\Desktop")

HL_API       = "https://api.hyperliquid.xyz/info"
HEADERS      = {"Content-Type": "application/json"}
MATCHES_FILE = "asset_matched_wallets.json"
OUTPUT_FILE  = "phase4_temporal_matches.json"


# ── Convert Polymarket ISO timestamp → epoch milliseconds ───
def iso_to_ms(iso_str):
    iso_str = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(iso_str)
    return int(dt.timestamp() * 1000)


# ── Pull a wallet's FULL fill history (paginated) ────────────
def get_all_fills(address):
    all_fills  = []
    start_time = 0
    end_time   = int(datetime.now(timezone.utc).timestamp() * 1000)

    while True:
        payload = {
            "type":      "userFillsByTime",
            "user":      address,
            "startTime": start_time,
            "endTime":   end_time,
        }
        try:
            resp = requests.post(HL_API, json=payload,
                                  headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                time.sleep(5)
                continue
            if not resp.ok:
                break

            fills = resp.json()
            if not isinstance(fills, list) or not fills:
                break

            all_fills.extend(fills)

            if len(fills) < 2000:
                break  # last page reached

            latest_time = max(f["time"] for f in fills)
            start_time  = latest_time + 1
            time.sleep(0.3)

        except Exception as e:
            print(f"    ⚠ Error: {e}")
            break

    return all_fills


# ── Reconstruct open/close intervals for one coin ────────────
def reconstruct_intervals(fills, coin):
    coin_fills = sorted(
        [f for f in fills if f.get("coin") == coin],
        key=lambda f: f["time"]
    )
    if not coin_fills:
        return []

    intervals = []
    pos        = 0.0
    open_start = None

    for f in coin_fills:
        try:
            sz = float(f.get("sz", 0))
        except (TypeError, ValueError):
            sz = 0.0
        side  = f.get("side")  # "B" = buy, "A" = sell
        delta = sz if side == "B" else -sz

        # Prefer the API's own startPosition when available (more robust)
        start_pos = f.get("startPosition")
        start_pos = float(start_pos) if start_pos is not None else pos
        end_pos   = start_pos + delta

        if start_pos == 0 and end_pos != 0:
            open_start = f["time"]
        elif start_pos != 0 and end_pos == 0 and open_start is not None:
            intervals.append((open_start, f["time"]))
            open_start = None

        pos = end_pos

    if open_start is not None:   # still open as of now
        intervals.append((open_start,
                          int(datetime.now(timezone.utc).timestamp() * 1000)))

    return intervals


def windows_overlap(a_start, a_end, b_start, b_end):
    return a_start <= b_end and b_start <= a_end


# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":

    with open(MATCHES_FILE, "r") as f:
        matches = json.load(f)

    unique_eoas = list(set(m["eoa"] for m in matches))
    print(f"Pulling full fill history for {len(unique_eoas)} wallets...\n")

    fills_cache = {}
    for i, eoa in enumerate(unique_eoas):
        print(f"[{i+1}/{len(unique_eoas)}] {eoa[:14]}... fetching fills")
        fills = get_all_fills(eoa)
        fills_cache[eoa] = fills
        print(f"    → {len(fills)} fills total")
        time.sleep(0.5)

    print(f"\nChecking temporal overlap for {len(matches)} asset matches...\n")

    confirmed = []
    for m in matches:
        eoa   = m["eoa"]
        coin  = m["hl_coin_held"]
        fills = fills_cache.get(eoa, [])

        # Coin may be stored plain ("NVDA") or HIP-3 prefixed ("xyz:NVDA")
        intervals = reconstruct_intervals(fills, coin)
        if not intervals:
            intervals = reconstruct_intervals(fills, f"xyz:{coin}")

        try:
            w_start, w_end = m["market_window"].split(" → ")
            ws_ms = iso_to_ms(w_start)
            we_ms = iso_to_ms(w_end)
        except Exception:
            continue

        overlap_found = any(
            windows_overlap(s, e, ws_ms, we_ms) for s, e in intervals
        )

        result = {**m, "temporal_overlap_confirmed": overlap_found}
        confirmed.append(result)

        status = "✅ CONFIRMED HEDGE" if overlap_found else "— no timing overlap"
        print(f"{eoa[:14]}... | {coin:<8} | {status}")

    true_hedgers = [c for c in confirmed if c["temporal_overlap_confirmed"]]

    with open(OUTPUT_FILE, "w") as f:
        json.dump({
            "total_asset_matches":        len(matches),
            "confirmed_temporal_hedges":  len(true_hedgers),
            "unique_confirmed_wallets":   len(set(t["eoa"] for t in true_hedgers)),
            "all_results":                confirmed
        }, f, indent=2)

    print(f"\n{'─'*55}")
    print(f"✅ Done!")
    print(f"   Asset-level matches        : {len(matches)}")
    print(f"   Confirmed TIMING overlaps  : {len(true_hedgers)}")
    print(f"   Unique confirmed wallets   : "
          f"{len(set(t['eoa'] for t in true_hedgers))}")
    print(f"   Saved to: {OUTPUT_FILE}")
