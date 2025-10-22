# -*- coding: utf-8 -*-
"""
team-digest CLI
Generate daily/weekly/monthly digests from Markdown logs and (optionally) post to Slack.

Subcommands:
  - daily:   Single-day digest
  - weekly:  Inclusive date-range digest
  - monthly: Calendar month (or month-to-date) digest
  - init:    Copy packaged examples (logs/configs) to a local folder

Conventions
-----------
- Logs directory contains files named: notes-YYYY-MM-DD.md
- Each file may contain sections (H2): Summary, Decisions, Actions, Risks, Dependencies, Notes
- Actions may have optional tags like [high], [medium], [low] (case-insensitive)
- Owner is inferred from the start of the action text after the tag, up to " to " or first token(s)
"""

from __future__ import annotations

import argparse
import dataclasses as dc
import datetime as dt
import io
import json
import os
import re
import sys
import textwrap
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    # Python 3.9+
    from importlib.resources import files, as_file
except Exception:
    files = None
    as_file = None

# ----------------------------
# Data structures
# ----------------------------

SECTION_NAMES = ("Summary", "Decisions", "Actions", "Risks", "Dependencies", "Notes")
DATE_RX = re.compile(r"notes-(\d{4}-\d{2}-\d{2})\.md$", re.I)
H2_RX = re.compile(r"^\s*##\s*(.+?)\s*$", re.M)
BULLET_RX = re.compile(r"^\s*[-*]\s+(.*\S)\s*$", re.M)
PRIO_RX = re.compile(r"\[(high|medium|low)\]", re.I)

@dataclass
class DayDoc:
    date: dt.date
    path: Path
    sections: Dict[str, List[str]]   # section_name -> lines
    actions: List[str]               # raw action lines (bullets only)
    counts_by_prio: Counter          # high/medium/low counts

# ----------------------------
# Utilities
# ----------------------------

def parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)

def fmt_date(d: dt.date) -> str:
    return d.isoformat()

def read_file(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def list_logs_in_range(logs_dir: Path, start: dt.date, end: dt.date) -> List[Path]:
    out: List[Tuple[dt.date, Path]] = []
    for p in sorted(logs_dir.glob("notes-*.md")):
        m = DATE_RX.search(p.name)
        if not m:
            continue
        d = parse_date(m.group(1))
        if start <= d <= end:
            out.append((d, p))
    out.sort(key=lambda x: x[0])
    return [p for _, p in out]

def list_logs_for_month(logs_dir: Path, year: int, month: int, latest_with_data: bool) -> Tuple[dt.date, dt.date, List[Path]]:
    # window: entire month (or month-to-date if latest_with_data is True and today is in same month)
    if latest_with_data:
        today = dt.date.today()
        if today.year == year and today.month == month:
            start = dt.date(year, month, 1)
            end = today
        else:
            # if asked for past month with latest_with_data=True, still the full month
            start = dt.date(year, month, 1)
            # last day of month
            if month == 12:
                end = dt.date(year, 12, 31)
            else:
                end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    else:
        start = dt.date(year, month, 1)
        if month == 12:
            end = dt.date(year, 12, 31)
        else:
            end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    paths = list_logs_in_range(logs_dir, start, end)
    return start, end, paths

def extract_sections(text: str) -> Dict[str, List[str]]:
    """
    Return a dict of section -> list of lines (content only, without heading line).
    Missing sections return [] later via defaultdict behavior.
    """
    matches = list(H2_RX.finditer(text))
    sections: Dict[str, List[str]] = {name: [] for name in SECTION_NAMES}
    if not matches:
        return sections

    # Append sentinel end
    boundaries = matches + [re.search(r"\Z", text)]
    for i in range(len(matches)):
        sec_name = matches[i].group(1).strip()
        start = matches[i].end()
        end = boundaries[i + 1].start()
        body = text[start:end].strip("\n")
        if sec_name in sections:
            # keep exact lines (we'll parse bullets later)
            sections[sec_name] = [ln.rstrip() for ln in body.splitlines() if ln.strip()]
    return sections

def extract_bullets(lines: List[str]) -> List[str]:
    """
    From raw section lines, return just bullet lines as text without the bullet prefix.
    """
    norm = []
    for ln in lines:
        m = BULLET_RX.match(ln)
        if m:
            norm.append(m.group(1).strip())
    return norm

def infer_priority(text: str) -> str:
    m = PRIO_RX.search(text or "")
    if not m:
        return "medium"  # default if unspecified
    return m.group(1).lower()

def infer_owner(text: str) -> str:
    """
    Heuristic: After removing [prio] tags, owner is the token(s) up to " to " or first 1-2 words.
    Examples:
      "[high] Alex to configure Slack" -> "Alex"
      "[medium] Anuraj Deol to retest" -> "Anuraj Deol"
      "Priya to prepare slides" -> "Priya"
    """
    t = PRIO_RX.sub("", text).strip()
    # Up to " to "
    parts = t.split(" to ", 1)
    head = parts[0].strip()
    # Allow 1–3 tokens as owner
    tokens = head.split()
    if len(tokens) >= 2:
        # try to keep two tokens (handles "Anuraj Deol")
        owner = " ".join(tokens[:2])
    else:
        owner = tokens[0] if tokens else "Unknown"
    return owner

def parse_day_doc(path: Path) -> DayDoc:
    text = read_file(path)
    m = DATE_RX.search(path.name)
    day = parse_date(m.group(1)) if m else None
    if day is None:
        raise ValueError(f"Cannot infer date from filename: {path}")

    secs = extract_sections(text)
    actions = extract_bullets(secs.get("Actions", []))
    counts = Counter()
    for a in actions:
        counts[infer_priority(a)] += 1

    return DayDoc(
        date=day,
        path=path,
        sections=secs,
        actions=actions,
        counts_by_prio=counts,
    )

def ensure_output_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Rendering
# ----------------------------

def render_counts_line(start: dt.date, end: dt.date, src: str, day_docs: List[DayDoc]) -> str:
    total_actions = sum(len(d.actions) for d in day_docs)
    return f"_Range: {fmt_date(start)} → {fmt_date(end)} | Source: {src} | Days matched: {len(day_docs)} | Actions: {total_actions}_\n"

def group_actions(actions: List[str]) -> Dict[str, List[str]]:
    out = {"high": [], "medium": [], "low": []}
    for a in actions:
        out[infer_priority(a)].append(a)
    return out

def aggregate_sections(day_docs: List[DayDoc]) -> Dict[str, List[str]]:
    agg = {name: [] for name in SECTION_NAMES}
    for d in day_docs:
        for name in SECTION_NAMES:
            if name == "Actions":
                # handled separately if grouping is requested
                agg[name].extend(d.actions)
            else:
                # merge bullets; if the section was plain text, keep lines as-is
                lines = d.sections.get(name, [])
                # If they were paragraph lines, keep them; otherwise pull only bullets
                if any(BULLET_RX.match(x or "") for x in lines):
                    agg[name].extend(extract_bullets(lines))
                else:
                    # treat each line as its own bullet for consistency
                    agg[name].extend([ln.strip() for ln in lines if ln.strip()])
    return agg

def render_md_daily(day: DayDoc, output_grouped: bool) -> str:
    lines = [f"# Team Digest ({fmt_date(day.date)})", ""]
    # Sections except Actions
    for sec in ("Summary", "Decisions"):
        bullets = extract_bullets(day.sections.get(sec, [])) or []
        lines.append(f"## {sec}")
        if bullets:
            for b in bullets:
                lines.append(f"- {b}")
        else:
            lines.append(f"_No {sec.lower()}._")
        lines.append("")

    # Actions
    lines.append("## Actions")
    acts = day.actions
    if not acts:
        lines.append("_No actions._")
    else:
        if output_grouped:
            groups = group_actions(acts)
            for prio in ("High", "Medium", "Low"):
                key = prio.lower()
                lines.append(f"### {prio} priority")
                if groups[key]:
                    for a in groups[key]:
                        a = PRIO_RX.sub(lambda m: f"[{m.group(1).lower()}]", a)
                        lines.append(f"- {a}")
                else:
                    lines.append(f"_No {prio.lower()} priority actions._")
                lines.append("")
        else:
            for a in acts:
                lines.append(f"- {a}")
            lines.append("")
    # Risks / Dependencies / Notes
    for sec in ("Risks", "Dependencies", "Notes"):
        bullets = extract_bullets(day.sections.get(sec, [])) or []
        lines.append(f"## {sec}")
        if bullets:
            for b in bullets:
                lines.append(f"- {b}")
        else:
            lines.append(f"_No {sec.lower()}._")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def render_md_range(
    title: str,
    start: dt.date,
    end: dt.date,
    day_docs: List[DayDoc],
    src: str,
    output_grouped: bool,
    emit_kpis: bool,
    owner_breakdown: bool,
) -> str:
    lines: List[str] = [f"# {title}", "", render_counts_line(start, end, src, day_docs), ""]
    agg = aggregate_sections(day_docs)

    # KPIs (weekly/monthly only)
    if emit_kpis:
        totals = Counter()
        for d in day_docs:
            totals.update(d.counts_by_prio)
        owners = Counter()
        for d in day_docs:
            for a in d.actions:
                owners[infer_owner(a)] += 1

        lines.append("## Executive KPIs")
        total_actions = sum(totals.values())
        lines.append(f"- **Actions:** {total_actions} (High: {totals.get('high',0)}, Medium: {totals.get('medium',0)}, Low: {totals.get('low',0)})")
        decisions_count = len(agg.get("Decisions", []))
        risks_count = len(agg.get("Risks", []))
        owners_count = len([o for o,c in owners.items() if c>0])
        lines.append(f"- **Decisions:** {decisions_count}   ·   **Risks:** {risks_count}")
        lines.append(f"- **Owners:** {owners_count}   ·   **Days with notes:** {len(day_docs)}")
        lines.append("")

        if owner_breakdown and total_actions:
            # owner breakdown by priority
            ob: Dict[str, Counter] = defaultdict(Counter)
            for d in day_docs:
                for a in d.actions:
                    o = infer_owner(a)
                    ob[o][infer_priority(a)] += 1
            # sort owners by total desc
            ranked = sorted(ob.items(), key=lambda kv: (kv[1]["high"], kv[1]["medium"], kv[1]["low"], sum(kv[1].values())), reverse=True)

            lines.append("#### Owner breakdown (top)")
            lines.append("| Owner | High | Medium | Low | Total |")
            lines.append("|:------|----:|------:|---:|-----:|")
            for owner, cnt in ranked:
                total = cnt.get("high",0)+cnt.get("medium",0)+cnt.get("low",0)
                lines.append(f"| {owner} | {cnt.get('high',0)} | {cnt.get('medium',0)} | {cnt.get('low',0)} | **{total}** |")
            lines.append("")

    # Summary / Decisions
    for sec in ("Summary", "Decisions"):
        lines.append(f"## {sec}")
        bullets = agg.get(sec, [])
        if bullets:
            for b in bullets:
                lines.append(f"- {b}")
        else:
            lines.append(f"_No {sec.lower()}._")
        lines.append("")

    # Actions
    lines.append("## Actions")
    acts = agg.get("Actions", [])
    if not acts:
        lines.append("_No actions._")
        lines.append("")
    else:
        if output_grouped:
            groups = group_actions(acts)
            for prio in ("High", "Medium", "Low"):
                key = prio.lower()
                lines.append(f"### {prio} priority")
                if groups[key]:
                    # sort actions alphabetically for readability (owner+task naturally float)
                    for a in sorted(groups[key], key=lambda s: s.lower()):
                        a = PRIO_RX.sub(lambda m: f"[{m.group(1).lower()}]", a)
                        lines.append(f"- {a}")
                else:
                    lines.append(f"_No {prio.lower()} priority actions._")
                lines.append("")
        else:
            for a in acts:
                lines.append(f"- {a}")
            lines.append("")

    # Risks / Dependencies / Notes
    for sec in ("Risks", "Dependencies", "Notes"):
        lines.append(f"## {sec}")
        bullets = agg.get(sec, [])
        if bullets:
            for b in bullets:
                lines.append(f"- {b}")
        else:
            lines.append(f"_No {sec.lower()}._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"

def render_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

# ----------------------------
# Slack posting
# ----------------------------

def post_slack_markdown(md_text: str, webhook_url: str) -> Tuple[bool, str]:
    try:
        import requests
        # Slack classic webhooks accept simple payload with 'text'
        r = requests.post(webhook_url, json={"text": md_text})
        if r.ok:
            return True, "ok"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)

# ----------------------------
# Subcommand runners
# ----------------------------

def run_daily(args) -> str:
    logs = Path(args.logs_dir).resolve()
    d = parse_date(args.date)
    # find exact file
    path = logs / f"notes-{fmt_date(d)}.md"
    if not path.exists():
        # allow alternative extensions (rare)
        candidates = list(logs.glob(f"notes-{fmt_date(d)}.*"))
        if not candidates:
            return f"# Team Digest ({fmt_date(d)})\n\n_No log for {fmt_date(d)} in {logs.name}_\n"
        path = candidates[0]
    day = parse_day_doc(path)
    return render_md_daily(day, args.group_actions)

def run_range(args, start: dt.date, end: dt.date, title: str) -> str:
    logs = Path(args.logs_dir).resolve()
    paths = list_logs_in_range(logs, start, end)
    day_docs = [parse_day_doc(p) for p in paths]
    return render_md_range(
        title=title,
        start=start,
        end=end,
        day_docs=day_docs,
        src=logs.name,
        output_grouped=args.group_actions,
        emit_kpis=args.emit_kpis,
        owner_breakdown=args.owner_breakdown,
    )

def run_weekly(args) -> str:
    start = parse_date(args.start)
    end = parse_date(args.end)
    title = f"Team Digest ({fmt_date(start)} - {fmt_date(end)})"
    return run_range(args, start, end, title)

def run_monthly(args) -> str:
    # Default: current month-to-date; allow --year/--month override
    year = args.year
    month = args.month
    if not year or not month:
        today = dt.date.today()
        year = year or today.year
        month = month or today.month
    start, end, paths = list_logs_for_month(Path(args.logs_dir), year, month, args.latest_with_data)
    day_docs = [parse_day_doc(p) for p in paths]
    title = f"Team Digest ({fmt_date(start)} - {fmt_date(end)})"
    return render_md_range(
        title=title,
        start=start,
        end=end,
        day_docs=day_docs,
        src=Path(args.logs_dir).name,
        output_grouped=args.group_actions,
        emit_kpis=args.emit_kpis,
        owner_breakdown=args.owner_breakdown,
    )

def run_init(args) -> str:
    if files is None or as_file is None:
        return "importlib.resources not available on this Python; cannot copy examples.\n"
    try:
        src = files("team_digest").joinpath("examples")
        dest = Path(args.dest).resolve()
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / "examples"
        # copy tree
        import shutil
        shutil.copytree(src, target, dirs_exist_ok=True)
        msg = [f"Examples copied to: {target}", "", "Next:"]
        msg.append(f'  team-digest weekly  --logs-dir "{target / "logs"}" --start 2025-10-13 --end 2025-10-19 --output weekly.md --group-actions --emit-kpis --owner-breakdown')
        msg.append(f'  team-digest daily   --logs-dir "{target / "logs"}" --date  2025-10-17 --output daily.md  --group-actions')
        msg.append(f'  team-digest monthly --logs-dir "{target / "logs"}" --output monthly.md --group-actions --emit-kpis')
        return "\n".join(msg) + "\n"
    except Exception as e:
        return f"ERROR: failed to copy examples: {e}\n"

# ----------------------------
# CLI
# ----------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="team-digest",
        description="Generate Daily/Weekly/Monthly digests from logs.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # Common flags mixin via functions to avoid typos
    def add_common(o: argparse.ArgumentParser):
        o.add_argument("--logs-dir", dest="logs_dir", default="logs", help="Folder containing notes-YYYY-MM-DD.md files")
        o.add_argument("--format", dest="format", choices=["md", "json"], default="md", help="Output format (md/json)")
        o.add_argument("-o", "--output", dest="output", default="", help="Output file path (if omitted, prints to stdout)")
        o.add_argument("--group-actions", action="store_true", help="Group actions by [high|medium|low] in output")
        o.add_argument("--post", choices=["slack"], default="", help="Post the digest to a destination (e.g., slack)")
        o.add_argument("--slack-webhook", default=os.environ.get("SLACK_WEBHOOK",""), help="Slack webhook URL")

    # daily
    pd = sub.add_parser("daily", help="Build a daily digest for a single date")
    add_common(pd)
    pd.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
    pd.set_defaults(func=lambda a: run_daily(a))

    # weekly
    pw = sub.add_parser("weekly", help="Build a digest for a date range (inclusive)")
    add_common(pw)
    pw.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    pw.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    pw.add_argument("--emit-kpis", action="store_true", help="Include Executive KPIs at the top")
    pw.add_argument("--owner-breakdown", action="store_true", help="Include owner breakdown table (with --emit-kpis)")
    pw.set_defaults(func=lambda a: run_weekly(a))

    # monthly
    pm = sub.add_parser("monthly", help="Build a digest for a calendar month (or month-to-date)")
    add_common(pm)
    pm.add_argument("--year", type=int, help="Year (defaults to current year if omitted)")
    pm.add_argument("--month", type=int, help="Month 1-12 (defaults to current month if omitted)")
    pm.add_argument("--latest-with-data", action="store_true", help="If current month, use month-to-date; else full month")
    pm.add_argument("--emit-kpis", action="store_true", help="Include Executive KPIs at the top")
    pm.add_argument("--owner-breakdown", action="store_true", help="Include owner breakdown table (with --emit-kpis)")
    pm.set_defaults(func=lambda a: run_monthly(a))

    # init
    pi = sub.add_parser("init", help="Copy packaged examples (logs/configs) to a folder")
    pi.add_argument("--to", dest="dest", default=".", help="Destination directory (default: .)")
    pi.set_defaults(func=lambda a: run_init(a))
    return p

def handle_output(text: str, fmt: str, output: str, post: str, slack_webhook: str) -> int:
    # If format is json, text should be json already. Here we only post/print/write.
    if output:
        outp = Path(output).resolve()
        ensure_output_dir(outp)
        outp.write_text(text, encoding="utf-8")
        print(textwrap.dedent(f"""\
            ---- Preview (first 60 lines) ----
            {''.join(text.splitlines(True)[:60])}""").rstrip())
    else:
        sys.stdout.write(text)

    # Post, if requested
    if post == "slack":
        if not slack_webhook:
            print("WARNING: --post slack was set but no --slack-webhook provided (and SLACK_WEBHOOK env not set). Skipping post.", file=sys.stderr)
        else:
            ok, msg = post_slack_markdown(text, slack_webhook)
            if ok:
                print("Posted to Slack ✓")
            else:
                print(f"Slack post failed: {msg}", file=sys.stderr)
                return 2
    return 0

def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Dispatch
    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2

    result_text = args.func(args)
    # Allow JSON output if requested: wrap a minimal structure
    if args.format == "json":
        payload = {"digest": result_text}
        result_text = render_json(payload)

    return handle_output(
        text=result_text,
        fmt=args.format,
        output=getattr(args, "output", ""),
        post=getattr(args, "post", ""),
        slack_webhook=getattr(args, "slack_webhook", ""),
    )

if __name__ == "__main__":
    raise SystemExit(main())
