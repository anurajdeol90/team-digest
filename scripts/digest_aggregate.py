#!/usr/bin/env python
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from team_digest.team_digest_runtime import aggregate_range


def _write_output(text: str, output: str | None) -> None:
    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    else:
        print(text)


def _common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--logs-dir", required=True, help="Directory containing Markdown daily logs"
    )
    p.add_argument("--output", help="Write digest to this file (stdout if omitted)")
    p.add_argument("--group-actions", action="store_true")
    p.add_argument("--flat-by-name", action="store_true")
    p.add_argument("--emit-kpis", action="store_true")
    p.add_argument("--owner-breakdown", action="store_true")
    p.add_argument("--owner-top", type=int, default=8)


def _parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def main() -> int:
    ap = argparse.ArgumentParser(prog="team-digest")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # daily
    p_daily = sub.add_parser(
        "daily", help="Generate a digest for a single day (YYYY-MM-DD)"
    )
    _common_args(p_daily)
    p_daily.add_argument("--date", type=_parse_date, required=True)

    # weekly
    p_week = sub.add_parser("weekly", help="Generate a digest for a date range")
    _common_args(p_week)
    p_week.add_argument("--start", type=_parse_date, required=False)
    p_week.add_argument("--end", type=_parse_date, required=False)

    # monthly (alias of weekly; dates optional -> first day of month to today)
    p_month = sub.add_parser(
        "monthly", help="Generate a monthly digest for the current month or given range"
    )
    _common_args(p_month)
    p_month.add_argument("--start", type=_parse_date, required=False)
    p_month.add_argument("--end", type=_parse_date, required=False)

    args = ap.parse_args()
    logs_dir = Path(args.logs_dir)

    if args.cmd == "daily":
        start = end = args.date
    else:
        today = dt.date.today()
        start = args.start
        end = args.end
        if args.cmd == "monthly":
            if start is None:
                start = today.replace(day=1)
            if end is None:
                end = today
        # weekly without explicit dates -> last 7 days ending today
        if args.cmd == "weekly" and (start is None or end is None):
            end = end or today
            start = start or (end - dt.timedelta(days=6))

    text = aggregate_range(
        logs_dir=logs_dir,
        start=start,
        end=end,
        title=None,
        group_actions=args.group_actions,
        flat_by_name=args.flat_by_name,
        emit_kpis=args.emit_kpis,
        owner_breakdown=args.owner_breakdown,
        owner_top=args.owner_top,
    )
    _write_output(text, getattr(args, "output", None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
