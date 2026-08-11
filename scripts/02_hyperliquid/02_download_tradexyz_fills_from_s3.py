import boto3
import botocore
import os
import time
from datetime import datetime, timedelta, timezone

os.chdir(r"C:\Users\Etimfon\Desktop")

# ── CONFIG ───────────────────────────────────────────────
AWS_ACCESS_KEY = "AKIA6MJOTKMPIW6KVFKO"
AWS_SECRET_KEY = "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"
BUCKET         = "hydromancer-reservoir"
REGION         = "ap-northeast-1"
LOCAL_DIR      = "hl_xyz_fills"

# Trade[XYZ] launched 2025-10-13 — pull complete history by default.
# Set a later START_DATE below if you only want a shorter window.
START_DATE = datetime(2025, 10, 13, tzinfo=timezone.utc)
END_DATE   = datetime.now(timezone.utc)


s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION,
)


def download_day(date_str):
    key = f"by_dex/xyz/fills/perp/all/date={date_str}/fills.parquet"
    local_path = os.path.join(LOCAL_DIR, f"fills_{date_str}.parquet")

    if os.path.exists(local_path):
        return "skipped (already downloaded)"

    try:
        s3.download_file(
            BUCKET, key, local_path,
            ExtraArgs={"RequestPayer": "requester"}
        )
        size_kb = os.path.getsize(local_path) / 1024
        return f"✅ {size_kb:.1f} KB"
    except botocore.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return "— no data this day"
        return f"⚠ Error: {code}"
    except Exception as e:
        return f"⚠ Error: {e}"


if __name__ == "__main__":

    os.makedirs(LOCAL_DIR, exist_ok=True)

    total_days = (END_DATE - START_DATE).days + 1
    print(f"Downloading trade.xyz fills: {START_DATE.date()} → "
          f"{END_DATE.date()} ({total_days} days)\n")

    results = {"downloaded": 0, "empty": 0, "errors": 0, "skipped": 0}

    current = START_DATE
    day_num = 1
    while current <= END_DATE:
        date_str = current.strftime("%Y-%m-%d")
        status = download_day(date_str)

        print(f"[{day_num}/{total_days}] {date_str} → {status}")

        if status.startswith("✅"):
            results["downloaded"] += 1
        elif "no data" in status:
            results["empty"] += 1
        elif "skipped" in status:
            results["skipped"] += 1
        else:
            results["errors"] += 1

        current += timedelta(days=1)
        day_num += 1
        time.sleep(0.1)

    print(f"\n{'─'*50}")
    print(f"✅ Files downloaded : {results['downloaded']}")
    print(f"— Days with no data : {results['empty']}")
    print(f"  Already skipped   : {results['skipped']}")
    print(f"⚠ Errors            : {results['errors']}")
    print(f"{'─'*50}")
    print(f"\nAll files saved to: {LOCAL_DIR}/")
