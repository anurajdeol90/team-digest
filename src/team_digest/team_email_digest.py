from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------
# Version (import safely; don't crash if package metadata not available)
# ---------------------------------------------------------------------
try:
    from . import __version__
except Exception:  # pragma: no cover
    __version__ = "0"

# ---------------------------------------------------------------------
# Normalization + parsing helpers (tolerant)
# ---------------------------------------------------------------------

SEC_RX = re.compile(
    r"^##\s*(Summary|Decisions|Actions|Risks|Dependencies|Notes)\s*$",
    re.IGNORECASE,
)

# Accept real bullets, escaped "\-", asterisk, or Unicode bullet
BULLET_RX = re.compile(r"^\s*(?:-|\*|•|\\-)\s+")
PRIORITY_RX = re.compile(r"\[(high|medium|low)\]", re.IGNORECASE)

NBSP = "\u00A0"


def _normalize_line(s: str) -> str:
    """
    Make Markdown lines uniform so the parser is resilient:

    - convert "•" or "*" bullets to "- "
    - unescape leading "\- " to "- "
    - normalize em dashes to "-"
    - convert NBSP to normal space
    - strip trailing \r\n
    """
    s = s.rstrip("\r\n")

    # Replace Unicode bullet with hyphen bullet
    if s.lstrip().startswith("• "):
        s = s.replace("• ", "- ", 1)

    # Replace leading "*" bullet with "-"
    s = re.sub(r"^(\s*)\*\s+", r"\1- ", s)

    # Unescape "\- " → "- " at the start of a line
    s = re.sub(r"^(\s*)\\-\s+", r"\1- ", s)

    # Normalize em-dash and en-dash to "-"
    s = s.replace("—", "-").replace("–", "-")

    # NBSP → space
    s = s.replace(NBSP, " ")

    return s


def _is_section_header(line: str) -> Optional[str]:
    m = SEC_RX.match(line)
    if not m:
        return None
    # Canonicalize capitalization
    name = m.group(1).strip().title()
    return name


def _is_bullet(line: str) -> bool:
    return bool(BULLET_RX.match(line))


def _extract_priority(line: str) -> Optional[str]:
    m = PRIORITY_RX.search(line)
    if not m:
        return None
    return m.group(1).lower()


def _extract_owner_guess(line: str) -> Optional[str]:
    """
    Naive owner guesser from the beginning of the bullet, e.g.:

    - [high] Alex to configure Slack...
    - Anuraj Deol to verify window...
    - Priya - prepare slides

    We take the first token(s) before " to " or " - ".
    """
    # strip bullet prefix
    line = BULLET_RX.sub("", line).strip()

    # remove leading [priority]
    line = PRIORITY_RX.sub("", line).strip()

    # split heuristics
    for sep in (" to ", " - "):
        if sep in line:
            left = line.split(sep, 1)[0].strip()
            # One or two capitalized words looks like a name
            if re.match(r"^[A-Z][a-z]+(\s+[A-Z][a-z]+)?$", left):
                return left
    # fallback: first capitalized word
    m = re.match(r"^([A-Z][a-z]+)", line)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class DaySections:
    date: dt.date
    summary: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class ActionItem:
    text: str
    owner: Optional[str]
    priority: Optional[str]
    date: dt.date


# ---------------------------------------------------------------------
# File scanning + parsing
# ---------------------------------------------------------------------

def _iter_filenames_by_date(logs_dir: Path, start: dt.date, end: dt.date) -> List[Tuple[dt.date, Path]]:
    rx = re.compile(r"notes-(\d{4}-\d{2}-\d{2})\.md$", re.IGNORECASE)
    matches: List[Tuple[dt.date, Path]] = []
    for p in sorted(logs_dir.glob("notes-*.md")):
        m = rx.search(p.name)
        if not m:
            continue
        d = dt.date.fromisoformat(m.group(1))
        if start <= d <= end:
            matches.append((d, p))
    return sorted(matches, key=lambda t: t[0])


def parse_markdown_file(path: Path, date: dt.date) -> DaySections:
    sec = DaySections(date=date)
    current = None

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raw = path.read_text(errors="replace")

    for raw_line in raw.splitlines():
        line = _normalize_line(raw_line)

        # Section switch?
        sname = _is_section_header(line)
        if sname:
            current = sname
            continue

        # Bullet under current section?
        if _is_bullet(line) and current:
            if current == "Summary":
                sec.summary.append(line)
            elif current == "Decisions":
                sec.decisions.append(line)
            elif current == "Actions":
                sec.actions.append(line)
            elif current == "Risks":
                sec.risks.append(line)
            elif current == "Dependencies":
                sec.dependencies.append(line)
            elif current == "Notes":
                sec.notes.append(line)
            continue

        # If no header yet but we see a bullet, put into Notes as fallback
        if _is_bullet(line) and not current:
            sec.notes.append(line)

    return sec


# ---------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------

@dataclass
class Aggregate:
    days: List[DaySections]
    actions: List[ActionItem]
    kpis: Dict[str, int]


def _collect_actions(days: Iterable[DaySections]) -> List[ActionItem]:
    items: List[ActionItem] = []
    for d in days:
        for a in d.actions:
            pr = _extract_priority(a)
            owner = _extract_owner_guess(a)
            items.append(ActionItem(text=a, owner=owner, priority=pr, date=d.date))
    return items


def _compute_kpis(days: List[DaySections], actions: List[ActionItem]) -> Dict[str, int]:
    return {
        "days": len(days),
        "actions": len(actions),
        "high": sum(1 for a in actions if a.priority == "high"),
        "medium": sum(1 for a in actions if a.priority == "medium"),
        "low": sum(1 for a in actions if a.priority == "low"),
        "decisions": sum(len(d.decisions) for d in days),
        "risks": sum(len(d.risks) for d in days),
        "owners": len({a.owner for a in actions if a.owner}),
    }


def aggregate_range(logs_dir: Path, start: dt.date, end: dt.date, expect_missing: bool = True) -> Aggregate:
    matches = _iter_filenames_by_date(logs_dir, start, end)
    days: List[DaySections] = []
    for d, p in matches:
        days.append(parse_markdown_file(p, d))

    actions = _collect_actions(days)
    kpis = _compute_kpis(days, actions)
    return Aggregate(days=days, actions=actions, kpis=kpis)


# ---------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------

def _fmt_lines(lines: List[str]) -> str:
    if not lines:
        return "_No items._"
    # Emit as-is (already normalized to "- " leading bullets)
    return "\n".join(lines)


def _fmt_section(title: str, bullets: List[str]) -> str:
    body = "_No {}._".format(title.lower()) if not bullets else "\n".join(bullets)
    return f"## {title}\n{body}\n"


def _fmt_actions_grouped(actions: List[ActionItem]) -> str:
    if not actions:
        return "## Actions\n_No actions._\n"

    # owner -> priority -> list[ActionItem]
    buckets: Dict[str, Dict[str, List[ActionItem]]] = {}
    for a in actions:
        owner = a.owner or "Unassigned"
        pr = a.priority or "medium"
        buckets.setdefault(owner, {}).setdefault(pr, []).append(a)

    order_pr = ["high", "medium", "low"]

    out = io.StringIO()
    out.write("## Actions\n")
    for owner in sorted(buckets.keys(), key=lambda s: s.lower()):
        out.write(f"### {owner}\n")
        for pr in order_pr:
            lst = buckets[owner].get(pr, [])
            if not lst:
                continue
            out.write(f"#### {pr.title()} priority\n")
            for a in lst:
                out.write(f"{a.text}\n")
    out.write("\n")
    return out.getvalue()


def _fmt_kpis(title: str, agg: Aggregate, owner_breakdown: bool = False) -> str:
    k = agg.kpis
    lines = [
        "## Executive KPIs",
        f"- **Actions:** {k['actions']} (High: {k['high']}, Medium: {k['medium']}, Low: {k['low']})",
        f"- **Decisions:** {k['decisions']}   ·   **Risks:** {k['risks']}",
        f"- **Owners:** {k['owners']}   ·   **Days with notes:** {k['days']}",
        "",
    ]

    if owner_breakdown and agg.actions:
        # owner -> counts by priority
        owners: Dict[str, Dict[str, int]] = {}
        for a in agg.actions:
            owner = a.owner or "Unassigned"
            owners.setdefault(owner, {"high": 0, "medium": 0, "low": 0, "total": 0})
            owners[owner][a.priority or "medium"] += 1
            owners[owner]["total"] += 1

        hdr = ["Owner", "High", "Medium", "Low", "Total"]
        lines.append("#### Owner breakdown (top)")
        lines.append("| " + " | ".join(hdr) + " |")
        lines.append("|:------|----:|------:|---:|-----:|")
        for owner in sorted(owners.keys(), key=lambda s: (-owners[s]["total"], s.lower())):
            o = owners[owner]
            lines.append(f"| {owner} | {o['high']} | {o['medium']} | {o['low']} | **{o['total']}** |")
        lines.append("")

    return "\n".join(lines)


def _append_footer(txt: str) -> str:
    return txt.rstrip() + f"\n\n---\n_Digest generated by team-digest v{__version__} (https://pypi.org/project/team-digest/)_\n"


def render_markdown(
    title: str,
    agg: Aggregate,
    *,
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
    group_actions: bool = False,
    emit_kpis: bool = False,
    owner_breakdown: bool = False,
) -> str:
    out = io.StringIO()
    # Title + range line
    if start and end:
        out.write(f"# {title}\n\n_Range: {start.isoformat()} → {end.isoformat()} | "
                  f"Source: logs | Days matched: {agg.kpis['days']} | Actions: {agg.kpis['actions']}_\n\n")
    else:
        out.write(f"# {title}\n\n")

    if emit_kpis:
        out.write(_fmt_kpis(title, agg, owner_breakdown))
        out.write("\n")

    # Merge sections across days
    summary = [b for d in agg.days for b in d.summary]
    decisions = [b for d in agg.days for b in d.decisions]
    risks = [b for d in agg.days for b in d.risks]
    dependencies = [b for d in agg.days for b in d.dependencies]
    notes = [b for d in agg.days for b in d.notes]

    out.write(_fmt_section("Summary", summary))
    out.write(_fmt_section("Decisions", decisions))

    if group_actions:
        out.write(_fmt_actions_grouped(agg.actions))
    else:
        out.write(_fmt_section("Actions", [a.text for a in agg.actions]))

    out.write(_fmt_section("Risks", risks))
    out.write(_fmt_section("Dependencies", dependencies))
    out.write(_fmt_section("Notes", notes))

    return _append_footer(out.getvalue())


# ---------------------------------------------------------------------
# Slack posting (optional)
# ---------------------------------------------------------------------

def post_to_slack(filepath: Path, webhook: str) -> None:
    """
    Simple Slack webhook poster that sends the file content as a code block.
    Keep it minimal; customers can replace with their own formatting.
    """
    try:
        import requests  # type: ignore
    except Exception:
        print("requests not installed; skipping Slack post", file=sys.stderr)
        return

    text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    payload = {"text": f"```\n{text}\n```"}
    r = requests.post(webhook, json=payload, timeout=15)
    r.raise_for_status()


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="team-digest",
        description="Generate Daily/Weekly/Monthly digests from logs.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # common
    def common(sp: argparse.ArgumentParser):
        sp.add_argument("--logs-dir", dest="logs_dir", default="logs", help="Path to logs (default: logs)")
        sp.add_argument("--output", "-o", dest="output", required=True, help="Output file (.md or .json)")
        sp.add_argument("--format", dest="fmt", choices=["md", "json"], default="md")
        sp.add_argument("--group-actions", action="store_true")
        sp.add_argument("--post", choices=["slack"])
        sp.add_argument("--slack-webhook", dest="slack_webhook")

    # daily
    sp_d = sub.add_parser("daily", help="Build a daily digest for a single date")
    common(sp_d)
    sp_d.add_argument("--date", required=True, help="YYYY-MM-DD")

    # weekly
    sp_w = sub.add_parser("weekly", help="Build a digest for a date range (inclusive)")
    common(sp_w)
    sp_w.add_argument("--start", required=True, help="YYYY-MM-DD")
    sp_w.add_argument("--end", required=True, help="YYYY-MM-DD")
    sp_w.add_argument("--emit-kpis", action="store_true")
    sp_w.add_argument("--owner-breakdown", action="store_true")

    # monthly
    sp_m = sub.add_parser("monthly", help="Build a digest for a calendar month (or month-to-date)")
    common(sp_m)
    sp_m.add_argument("--year", type=int)   # optional if latest-with-data
    sp_m.add_argument("--month", type=int)  # optional if latest-with-data
    sp_m.add_argument("--latest-with-data", action="store_true",
                      help="If set, picks the month containing the latest log with data")
    sp_m.add_argument("--emit-kpis", action="store_true")
    sp_m.add_argument("--owner-breakdown", action="store_true")

    # version
    p.add_argument("-V", action="version", version=f"team-digest {__version__}")

    return p.parse_args(argv)


def _date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _month_bounds(year: int, month: int) -> Tuple[dt.date, dt.date]:
    start = dt.date(year, month, 1)
    if month == 12:
        end = dt.date(year, 12, 31)
    else:
        end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    return start, end


def _latest_month_with_data(logs_dir: Path) -> Tuple[int, int]:
    rx = re.compile(r"notes-(\d{4})-(\d{2})-(\d{2})\.md$", re.IGNORECASE)
    y_m: List[Tuple[int, int]] = []
    for p in logs_dir.glob("notes-*.md"):
        m = rx.search(p.name)
        if not m:
            continue
        y, mth = int(m.group(1)), int(m.group(2))
        y_m.append((y, mth))
    if not y_m:
        today = dt.date.today()
        return today.year, today.month
    y_m.sort()
    return y_m[-1]


def _write_output(path: Path, txt_or_json, fmt: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        path.write_text(json.dumps(txt_or_json, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text(txt_or_json, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    logs_dir = Path(args.logs_dir)
    output = Path(args.output)

    if args.cmd == "daily":
        d = _date(args.date)
        agg = aggregate_range(logs_dir, d, d)
        title = f"Team Digest ({d.isoformat()})"
        if args.fmt == "json":
            payload = {
                "title": title,
                "date": d.isoformat(),
                "kpis": agg.kpis,
                "sections": {
                    "summary": [b for d0 in agg.days for b in d0.summary],
                    "decisions": [b for d0 in agg.days for b in d0.decisions],
                    "actions": [a.text for a in agg.actions],
                    "risks": [b for d0 in agg.days for b in d0.risks],
                    "dependencies": [b for d0 in agg.days for b in d0.dependencies],
                    "notes": [b for d0 in agg.days for b in d0.notes],
                },
            }
            _write_output(output, payload, "json")
        else:
            txt = render_markdown(
                title, agg, group_actions=args.group_actions
            )
            _write_output(output, txt, "md")

    elif args.cmd == "weekly":
        s, e = _date(args.start), _date(args.end)
        agg = aggregate_range(logs_dir, s, e)
        title = f"Team Digest ({s.isoformat()} - {e.isoformat()})"
        if args.fmt == "json":
            payload = {
                "title": title,
                "start": s.isoformat(),
                "end": e.isoformat(),
                "kpis": agg.kpis,
            }
            _write_output(output, payload, "json")
        else:
            txt = render_markdown(
                title,
                agg,
                start=s,
                end=e,
                group_actions=args.group_actions,
                emit_kpis=args.emit_kpis,
                owner_breakdown=args.owner_breakdown,
            )
            _write_output(output, txt, "md")

    elif args.cmd == "monthly":
        if args.latest_with_data:
            y, mth = _latest_month_with_data(logs_dir)
        else:
            today = dt.date.today()
            y = args.year or today.year
            mth = args.month or today.month

        s, e = _month_bounds(y, mth)
        agg = aggregate_range(logs_dir, s, e)
        title = f"Team Digest ({s.isoformat()} - {e.isoformat()})"
        if args.fmt == "json":
            payload = {
                "title": title,
                "start": s.isoformat(),
                "end": e.isoformat(),
                "kpis": agg.kpis,
            }
            _write_output(output, payload, "json")
        else:
            txt = render_markdown(
                title,
                agg,
                start=s,
                end=e,
                group_actions=args.group_actions,
                emit_kpis=args.emit_kpis,
                owner_breakdown=args.owner_breakdown,
            )
            _write_output(output, txt, "md")

    else:  # pragma: no cover
        raise SystemExit(2)

    # Optional: Slack post
    if args.post == "slack" and args.slack_webhook:
        try:
            post_to_slack(output, args.slack_webhook)
        except Exception as ex:  # pragma: no cover
            print(f"Slack post failed: {ex}", file=sys.stderr)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
