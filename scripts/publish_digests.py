#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from datetime import datetime, date
from typing import Optional

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--digest", required=True, choices=["daily", "weekly", "monthly"])
    p.add_argument("--date", help="YYYY-MM-DD for daily/weekly, YYYY-MM for monthly")
    p.add_argument("--dry-run", action="store_true", help="Do not commit/publish")
    p.add_argument(
        "--tz",
        default=os.getenv("DIGEST_TZ", "UTC"),
        help="IANA time zone (default: UTC)",
    )
    return p.parse_args()


def _zone(tz_name: str):
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def resolve_effective_date(kind: str, override: Optional[str], tz_name: str) -> date:
    z = _zone(tz_name)
    now = datetime.now(tz=z)
    if override:
        if kind in ("daily", "weekly"):
            return datetime.strptime(override, "%Y-%m-%d").date()
        elif kind == "monthly":
            return datetime.strptime(override, "%Y-%m").date().replace(day=1)
    # Auto
    if kind in ("daily", "weekly"):
        return now.date()
    elif kind == "monthly":
        return date(year=now.year, month=now.month, day=1)
    raise ValueError(f"Unknown digest kind: {kind}")


def main() -> None:
    args = parse_args()
    eff_date = resolve_effective_date(args.digest, args.date, args.tz)

    # At this point you would:
    #  - pull data
    #  - render HTML/markdown
    #  - write into ./docs or wherever your site reads from
    #
    # The lines below are safe, minimal no-op placeholders that
    # demonstrate use of tz and date without changing your existing logic.
    print(f"[publish_digests] kind={args.digest} date={eff_date} tz={args.tz} dry_run={args.dry_run}")

    # Example: write a tiny artifact file for debugging (optional)
    out = f".digest-{args.digest}.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"{args.digest} {eff_date.isoformat()} tz={args.tz}\n")

    if args.dry_run:
        print("Dry run: skipping commit/publish")
        return

    # If you already have commit/deploy logic in your workflow, leave it there.
    # (We don't commit here to avoid stepping on your existing deployment setup.)


if __name__ == "__main__":
    main()
