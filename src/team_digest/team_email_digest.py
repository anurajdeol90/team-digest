#!/usr/bin/env python
# Console entry point for `team-digest`
from __future__ import annotations
import argparse, datetime as dt, io
from pathlib import Path

from .team_digest_runtime import aggregate_range
from .slack_delivery import post_markdown

def write_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    io.open(path, "w", encoding="utf-8").write(text)

def cmd_daily(a):
    logs = Path(a.logs_dir)
    day  = dt.date.fromisoformat(a.date)
    md = aggregate_range(
        logs_dir=logs, start=day, end=day,
        title=a.title or f"Team Digest ({day.isoformat()})",
        group_actions=a.group_actions, flat_by_name=a.flat_by_name,
        emit_kpis=False, owner_breakdown=False
    )
    write_output(Path(a.output), md)
    if a.post_to_slack: post_markdown(md)

def cmd_weekly(a):
    logs  = Path(a.logs_dir)
    start = dt.date.fromisoformat(a.start)
    end   = dt.date.fromisoformat(a.end)
    md = aggregate_range(
        logs_dir=logs, start=start, end=end,
        title=a.title or f"Team Digest ({start.isoformat()} - {end.isoformat()})",
        group_actions=a.group_actions, flat_by_name=a.flat_by_name,
        emit_kpis=a.emit_kpis, owner_breakdown=a.owner_breakdown, owner_top=a.owner_top
    )
    write_output(Path(a.output), md)
    if a.post_to_slack: post_markdown(md)

def cmd_monthly(a):
    logs = Path(a.logs_dir)
    if a.year and a.month:
        start = dt.date(int(a.year), int(a.month), 1)
        end = (start.replace(day=1) + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    else:
        # month-to-date (UTC) default
        today = dt.datetime.utcnow().date()
        start = today.replace(day=1)
        end   = today

    if a.latest_with_data and not (a.year and a.month):
        months = []
        for p in logs.glob("notes-*.md"):
            m = re.search(r"notes-(\d{4}-\d{2})-\d{2}\.md$", p.name)
            if m: months.append(m.group(1))
        if months:
            latest = sorted(set(months))[-1]
            y, m = latest.split("-")
            start = dt.date(int(y), int(m), 1)
            end = (start.replace(day=1) + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)

    md = aggregate_range(
        logs_dir=logs, start=start, end=end,
        title=a.title or f"Team Digest ({start.isoformat()} - {end.isoformat()})",
        group_actions=a.group_actions, flat_by_name=a.flat_by_name,
        emit_kpis=True, owner_breakdown=True, owner_top=a.owner_top
    )
    write_output(Path(a.output), md)
    if a.post_to_slack: post_markdown(md)

def main(argv=None):
    import sys, re
    argv = argv or sys.argv[1:]

    ap = argparse.ArgumentParser(prog="team-digest", description="Generate Daily/Weekly/Monthly digests from logs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--logs-dir", default="logs")
        p.add_argument("--title", default="")
        p.add_argument("--output", required=True)
        p.add_argument("--group-actions", action="store_true")
        p.add_argument("--flat-by-name", action="store_true")
        p.add_argument("--post-to-slack", action="store_true", help="Post the rendered markdown to Slack via SLACK_WEBHOOK_URL")

    # daily
    p1 = sub.add_parser("daily", help="Build a daily digest for a single date")
    common(p1)
    p1.add_argument("--date", default=dt.datetime.utcnow().date().isoformat(), help="YYYY-MM-DD")
    p1.set_defaults(func=cmd_daily)

    # weekly (generic range)
    p2 = sub.add_parser("weekly", help="Build a digest for a date range (inclusive)")
    common(p2)
    p2.add_argument("--start", required=True, help="YYYY-MM-DD")
    p2.add_argument("--end", required=True, help="YYYY-MM-DD")
    p2.add_argument("--emit-kpis", action="store_true")
    p2.add_argument("--owner-breakdown", action="store_true")
    p2.add_argument("--owner-top", type=int, default=8)
    p2.set_defaults(func=cmd_weekly)

    # monthly
    p3 = sub.add_parser("monthly", help="Build a digest for a calendar month (or month-to-date)")
    common(p3)
    p3.add_argument("--year", type=int, help="4-digit year (optional)")
    p3.add_argument("--month", type=int, help="1-12 (optional)")
    p3.add_argument("--latest-with-data", action="store_true", dest="latest_with_data")
    p3.add_argument("--owner-top", type=int, default=8)
    p3.set_defaults(func=cmd_monthly)

    args = ap.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
