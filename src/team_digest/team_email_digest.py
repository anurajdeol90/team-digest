# src/team_digest/team_email_digest.py
from __future__ import annotations

import argparse
import dataclasses as dc
import datetime as dt
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# External (declared in pyproject)
import regex as rxx  # drop-in replacement for 're' with better features
import requests
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # YAML config is optional

# Local
from ._footer import append_footer
try:
    from . import __version__
except Exception:  # pragma: no cover
    __version__ = "unknown"

# --------- Parsing helpers ---------

SECTION_RX = rxx.compile(r"(?m)^(#{2,3})\s*(Summary|Decisions|Actions|Risks|Dependencies|Notes)\s*$")
BULLET_RX  = rxx.compile(r"(?m)^\s*[-*+]\s+(.*)$")
DATE_IN_NAME = re.compile(r"notes-(\d{4}-\d{2}-\d{2})\.md$", re.I)

PRIORITY_RX = re.compile(r"\[(high|medium|low)\]", re.I)
OWNER_RX    = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+to\b")

# --------- Data models ---------

@dc.dataclass
class DayDoc:
    date: dt.date
    path: Path
    sections: Dict[str, List[str]]  # section -> lines

@dc.dataclass
class Actions:
    high: List[str] = dc.field(default_factory=list)
    medium: List[str] = dc.field(default_factory=list)
    low: List[str] = dc.field(default_factory=list)
    unknown: List[str] = dc.field(default_factory=list)

# --------- IO & config ---------

def load_config(fp: Optional[str]) -> Dict:
    if not fp:
        return {}
    p = Path(fp)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {fp}")
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".yml", ".yaml"}:
        if yaml is None:
            raise RuntimeError("PyYAML not installed; cannot read YAML config")
        return yaml.safe_load(text) or {}
    return json.loads(text)

# --------- Markdown parsing ---------

def split_sections(md: str) -> Dict[str, List[str]]:
    """Return mapping of section -> list of lines (without the section header)."""
    anchors = []
    for m in SECTION_RX.finditer(md):
        hdr = m.group(2).strip()
        anchors.append((hdr, m.start(), m.end()))
    out: Dict[str, List[str]] = {}
    for i, (name, hdr_start, content_start) in enumerate(anchors):
        content_end = anchors[i + 1][1] if i + 1 < len(anchors) else len(md)
        body = md[content_start:content_end]
        # Keep non-empty lines; we preserve bullets where present
        lines = [ln.rstrip() for ln in body.splitlines() if ln.strip() != ""]
        out[name] = lines
    return out

def parse_actions(lines: List[str]) -> Actions:
    """Extract bullet lines and categorize by [high]/[medium]/[low]."""
    acts = Actions()
    for ln in lines:
        m = BULLET_RX.search(ln)
        if not m:
            continue
        text = m.group(1).strip()
        pm = PRIORITY_RX.search(text)
        if pm:
            pr = pm.group(1).lower()
            if pr == "high":
                acts.high.append(text)
            elif pr == "medium":
                acts.medium.append(text)
            elif pr == "low":
                acts.low.append(text)
            else:
                acts.unknown.append(text)
        else:
            acts.unknown.append(text)
    return acts

def detect_owners(bullets: Iterable[str]) -> Counter:
    c = Counter()
    for b in bullets:
        m = OWNER_RX.search(b)
        if m:
            c[m.group(1)] += 1
    return c

# --------- Log discovery ---------

def filename_date(p: Path) -> Optional[dt.date]:
    m = DATE_IN_NAME.search(p.name)
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except Exception:
        return None

def find_daily_file(logs_dir: Path, date: dt.date) -> Optional[Path]:
    cand = logs_dir / f"notes-{date.isoformat()}.md"
    return cand if cand.exists() else None

def find_range_files(logs_dir: Path, start: dt.date, end: dt.date) -> List[Path]:
    out: List[Path] = []
    for p in sorted(logs_dir.glob("notes-*.md")):
        d = filename_date(p)
        if not d:
            continue
        if start <= d <= end:
            out.append(p)
    return out

def read_daydoc(p: Path) -> DayDoc:
    d = filename_date(p)
    if not d:
        raise ValueError(f"Cannot parse date from filename: {p.name}")
    md = p.read_text(encoding="utf-8")
    secs = split_sections(md)
    return DayDoc(date=d, path=p, sections=secs)

# --------- Aggregation ---------

def aggregate_sections(daydocs: List[DayDoc]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {k: [] for k in ["Summary", "Decisions", "Actions", "Risks", "Dependencies", "Notes"]}
    for d in sorted(daydocs, key=lambda x: x.date):
        for sec in out.keys():
            out[sec].extend(d.sections.get(sec, []))
    return out

def aggregate_actions(daydocs: List[DayDoc]) -> Actions:
    acts = Actions()
    for d in daydocs:
        a = parse_actions(d.sections.get("Actions", []))
        acts.high.extend(a.high)
        acts.medium.extend(a.medium)
        acts.low.extend(a.low)
        acts.unknown.extend(a.unknown)
    return acts

# --------- Rendering (Markdown) ---------

def kpis_block(daydocs: List[DayDoc], acts: Actions) -> str:
    decisions = sum(1 for d in daydocs for ln in d.sections.get("Decisions", []) if BULLET_RX.search(ln))
    risks     = sum(1 for d in daydocs for ln in d.sections.get("Risks", []) if BULLET_RX.search(ln))
    owners_c  = Counter()
    owners_c.update(detect_owners(acts.high))
    owners_c.update(detect_owners(acts.medium))
    owners_c.update(detect_owners(acts.low))
    owners_c.update(detect_owners(acts.unknown))
    owners = len(owners_c)
    days_with_notes = len(daydocs)
    total_actions = len(acts.high) + len(acts.medium) + len(acts.low) + len(acts.unknown)

    lines = []
    lines.append("## Executive KPIs")
    lines.append(f"- **Actions:** {total_actions} (High: {len(acts.high)}, Medium: {len(acts.medium)}, Low: {len(acts.low)})")
    lines.append(f"- **Decisions:** {decisions}   ·   **Risks:** {risks}")
    lines.append(f"- **Owners:** {owners}   ·   **Days with notes:** {days_with_notes}")
    return "\n".join(lines)

def owner_breakdown_table(acts: Actions, top_n: int = 9999) -> str:
    table: Dict[str, Counter] = defaultdict(Counter)
    for prio, lst in (("High", acts.high), ("Medium", acts.medium), ("Low", acts.low), ("Unknown", acts.unknown)):
        for item in lst:
            m = OWNER_RX.search(item)
            owner = m.group(1) if m else "Unassigned"
            table[owner][prio] += 1
            table[owner]["Total"] += 1

    rows = sorted(table.items(), key=lambda kv: (-kv[1]["Total"], kv[0]))[:top_n]

    lines = []
    lines.append("\n#### Owner breakdown (top)")
    lines.append("| Owner | High | Medium | Low | Total |")
    lines.append("|:------|----:|------:|---:|-----:|")
    for owner, cnt in rows:
        lines.append(f"| {owner} | {cnt['High']} | {cnt['Medium']} | {cnt['Low']} | **{cnt['Total']}** |")
    return "\n".join(lines)

def ensure_nonempty(block_title: str, lines: List[str]) -> str:
    if not any(BULLET_RX.search(ln) for ln in lines):
        return f"## {block_title}\n_No {block_title.lower()}._"
    return "## " + block_title + "\n" + "\n".join(lines)

def render_daily(title: str, day: DayDoc, group_actions: bool) -> str:
    secs = day.sections
    acts = parse_actions(secs.get("Actions", []))
    out = [f"# {title}"]
    out.append(ensure_nonempty("Summary", secs.get("Summary", [])))
    out.append(ensure_nonempty("Decisions", secs.get("Decisions", [])))

    out.append("## Actions")
    if group_actions:
        if acts.high:
            out.append("### High priority")
            out.extend([f"- {t}" for t in acts.high])
        if acts.medium:
            out.append("### Medium priority")
            out.extend([f"- {t}" for t in acts.medium])
        if acts.low:
            out.append("### Low priority")
            out.extend([f"- {t}" for t in acts.low])
        if acts.unknown:
            out.append("### Unclassified")
            out.extend([f"- {t}" for t in acts.unknown])
        if not (acts.high or acts.medium or acts.low or acts.unknown):
            out.append("_No actions._")
    else:
        out.extend(secs.get("Actions", []) or ["_No actions._"])

    out.append(ensure_nonempty("Risks", secs.get("Risks", [])))
    out.append(ensure_nonempty("Dependencies", secs.get("Dependencies", [])))
    out.append(ensure_nonempty("Notes", secs.get("Notes", [])))
    return "\n\n".join(out)

def render_range_common_header(title: str, start: dt.date, end: dt.date, logs_dir: Path, daydocs: List[DayDoc], acts: Actions) -> List[str]:
    total_actions = len(acts.high) + len(acts.medium) + len(acts.low) + len(acts.unknown)
    head = [f"# {title}", f"\n_Range: {start.isoformat()} → {end.isoformat()} | Source: {logs_dir} | Days matched: {len(daydocs)} | Actions: {total_actions}_\n"]
    return head

def render_weekly(title: str, logs_dir: Path, start: dt.date, end: dt.date, daydocs: List[DayDoc], group_actions: bool, emit_kpis: bool, owner_breakdown: bool) -> str:
    acts = aggregate_actions(daydocs)
    agg = aggregate_sections(daydocs)
    out: List[str] = []
    out.extend(render_range_common_header(title, start, end, logs_dir, daydocs, acts))

    if emit_kpis:
        out.append(kpis_block(daydocs, acts))
        if owner_breakdown:
            out.append(owner_breakdown_table(acts))

    out.append(ensure_nonempty("Summary", agg.get("Summary", [])))
    out.append(ensure_nonempty("Decisions", agg.get("Decisions", [])))

    out.append("## Actions")
    if group_actions:
        if acts.high:
            out.append("### High priority")
            out.extend([f"- {t}" for t in acts.high])
        if acts.medium:
            out.append("### Medium priority")
            out.extend([f"- {t}" for t in acts.medium])
        if acts.low:
            out.append("### Low priority")
            out.extend([f"- {t}" for t in acts.low])
        if acts.unknown:
            out.append("### Unclassified")
            out.extend([f"- {t}" for t in acts.unknown])
        if not (acts.high or acts.medium or acts.low or acts.unknown):
            out.append("_No actions._")
    else:
        out.extend(agg.get("Actions", []) or ["_No actions._"])

    out.append(ensure_nonempty("Risks", agg.get("Risks", [])))
    out.append(ensure_nonempty("Dependencies", agg.get("Dependencies", [])))
    out.append(ensure_nonempty("Notes", agg.get("Notes", [])))
    return "\n\n".join(out)

def render_monthly(title: str, logs_dir: Path, start: dt.date, end: dt.date, daydocs: List[DayDoc], group_actions: bool, emit_kpis: bool, owner_breakdown: bool) -> str:
    acts = aggregate_actions(daydocs)
    agg = aggregate_sections(daydocs)
    out: List[str] = []
    out.extend(render_range_common_header(title, start, end, logs_dir, daydocs, acts))

    if emit_kpis:
        out.append(kpis_block(daydocs, acts))
        if owner_breakdown:
            out.append(owner_breakdown_table(acts))

    out.append(ensure_nonempty("Summary", agg.get("Summary", [])))
    out.append(ensure_nonempty("Decisions", agg.get("Decisions", [])))

    out.append("## Actions")
    if group_actions:
        if acts.high:
            out.append("### High priority")
            out.extend([f"- {t}" for t in acts.high])
        if acts.medium:
            out.append("### Medium priority")
            out.extend([f"- {t}" for t in acts.medium])
        if acts.low:
            out.append("### Low priority")
            out.extend([f"- {t}" for t in acts.low])
        if acts.unknown:
            out.append("### Unclassified")
            out.extend([f"- {t}" for t in acts.unknown])
        if not (acts.high or acts.medium or acts.low or acts.unknown):
            out.append("_No actions._")
    else:
        out.extend(agg.get("Actions", []) or ["_No actions._"])

    out.append(ensure_nonempty("Risks", agg.get("Risks", [])))
    out.append(ensure_nonempty("Dependencies", agg.get("Dependencies", [])))
    out.append(ensure_nonempty("Notes", agg.get("Notes", [])))
    return "\n\n".join(out)

# --------- Slack ---------

def post_to_slack(webhook: str, text: str) -> None:
    resp = requests.post(webhook, json={"text": text}, timeout=15)
    if resp.status_code >= 300:
        raise RuntimeError(f"Slack webhook failed: {resp.status_code} {resp.text[:200]}")

# --------- CLI ---------

def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--logs-dir", dest="logs_dir", required=False, default="logs", help="Path to Markdown logs directory")
    p.add_argument("--output", "-o", dest="output", required=False, help="Output file (md or json). Default: stdout")
    p.add_argument("--format", dest="format", choices=["md", "json"], default="md", help="Output format")
    p.add_argument("--group-actions", dest="group_actions", action="store_true", help="Group actions by priority")
    p.add_argument("--config", dest="config", help="YAML/JSON config file (overrides CLI)")
    p.add_argument("--post", dest="post", choices=["slack"], help="Post digest to a target (currently: slack)")
    p.add_argument("--slack-webhook", dest="slack_webhook", help="Slack webhook URL for --post slack")
    p.add_argument("-V", "--version", action="version", version=f"team-digest {__version__}")

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate Daily/Weekly/Monthly digests from logs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # daily
    ap_d = sub.add_parser("daily", help="Build a daily digest for a single date")
    add_common_args(ap_d)
    ap_d.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")

    # weekly
    ap_w = sub.add_parser("weekly", help="Build a digest for a date range (inclusive)")
    add_common_args(ap_w)
    ap_w.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    ap_w.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    ap_w.add_argument("--emit-kpis", action="store_true", help="Include KPI block")
    ap_w.add_argument("--owner-breakdown", action="store_true", help="Include owner breakdown table")

    # monthly
    ap_m = sub.add_parser("monthly", help="Build a digest for a calendar month (or month-to-date)")
    add_common_args(ap_m)
    ap_m.add_argument("--month", help="Month YYYY-MM (default: current month)")
    ap_m.add_argument("--latest-with-data", action="store_true", help="If no logs in current month yet, back up to last month with data")
    ap_m.add_argument("--emit-kpis", action="store_true", help="Include KPI block")
    ap_m.add_argument("--owner-breakdown", action="store_true", help="Include owner breakdown table")

    return ap.parse_args(argv)

# --------- Glue ---------

def merge_config(args: argparse.Namespace) -> argparse.Namespace:
    cfg = load_config(getattr(args, "config", None))
    for key, val in cfg.items():
        if getattr(args, key, None) in (None, False, "", 0):
            setattr(args, key, val)
    return args

def ensure_slack_ok(args: argparse.Namespace) -> Optional[str]:
    if args.post == "slack":
        wh = args.slack_webhook or os.getenv("SLACK_WEBHOOK")
        if not wh:
            raise SystemExit("Slack posting requested but no --slack-webhook or SLACK_WEBHOOK set.")
        return wh
    return None

def write_output(args: argparse.Namespace, text_md: str, json_obj: Optional[dict] = None) -> None:
    if args.format == "json":
        payload = json.dumps(json_obj if json_obj is not None else {"markdown": text_md}, ensure_ascii=False, indent=2)
        out_bytes = payload.encode("utf-8")
    else:
        stamped = append_footer(text_md, "md")
        out_bytes = stamped.encode("utf-8")
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "wb") as f:
            f.write(out_bytes)
    else:
        # stdout path
        import sys
        sys.stdout.buffer.write(out_bytes)

def cmd_daily(args: argparse.Namespace) -> None:
    args = merge_config(args)
    logs_dir = Path(args.logs_dir)
    try:
        target_date = dt.date.fromisoformat(args.date)
    except Exception:
        raise SystemExit(f"Invalid --date: {args.date}")

    p = find_daily_file(logs_dir, target_date)
    if not p:
        txt = f"# Team Digest ({target_date.isoformat()})\n\n_No log for {target_date.isoformat()} in {logs_dir}_\n"
        write_output(args, txt, {"date": target_date.isoformat(), "found": False})
        return

    day = read_daydoc(p)
    title = f"Team Digest ({target_date.isoformat()})"
    md = render_daily(title, day, args.group_actions)
    write_output(args, md, {"date": target_date.isoformat(), "found": True})

    wh = ensure_slack_ok(args)
    if wh:
        post_to_slack(wh, md)

def cmd_weekly(args: argparse.Namespace) -> None:
    args = merge_config(args)
    logs_dir = Path(args.logs_dir)
    try:
        start = dt.date.fromisoformat(args.start)
        end   = dt.date.fromisoformat(args.end)
    except Exception:
        raise SystemExit("Invalid --start/--end dates")

    files = find_range_files(logs_dir, start, end)
    daydocs = [read_daydoc(p) for p in files]
    title = f"Team Digest ({start.isoformat()} - {end.isoformat()})"
    md = render_weekly(title, logs_dir, start, end, daydocs, args.group_actions, args.emit_kpis, args.owner_breakdown)
    write_output(args, md, {"start": start.isoformat(), "end": end.isoformat(), "count": len(daydocs)})

    wh = ensure_slack_ok(args)
    if wh:
        post_to_slack(wh, md)

def _month_range(month_str: Optional[str]) -> Tuple[dt.date, dt.date]:
    if month_str:
        try:
            y, m = month_str.split("-")
            year, mon = int(y), int(m)
        except Exception:
            raise SystemExit("Invalid --month. Use YYYY-MM.")
        start = dt.date(year, mon, 1)
    else:
        today = dt.date.today()
        start = dt.date(today.year, today.month, 1)
    next_month = dt.date(start.year + (1 if start.month == 12 else 0),
                         1 if start.month == 12 else start.month + 1, 1)
    end = min(dt.date.today(), next_month - dt.timedelta(days=1))
    return start, end

def cmd_monthly(args: argparse.Namespace) -> None:
    args = merge_config(args)
    logs_dir = Path(args.logs_dir)

    start, end = _month_range(args.month)
    files = find_range_files(logs_dir, start, end)

    if not files and args.latest_with_data:
        y, m = start.year, start.month
        for _ in range(12):
            if m == 1:
                y -= 1
                m = 12
            else:
                m -= 1
            start2 = dt.date(y, m, 1)
            next_m = dt.date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
            end2   = next_m - dt.timedelta(days=1)
            files  = find_range_files(logs_dir, start2, end2)
            if files:
                start, end = start2, end2
                break

    daydocs = [read_daydoc(p) for p in files]
    title = f"Team Digest ({start.isoformat()} - {end.isoformat()})"
    md = render_monthly(title, logs_dir, start, end, daydocs, args.group_actions, args.emit_kpis, args.owner_breakdown)
    write_output(args, md, {"start": start.isoformat(), "end": end.isoformat(), "count": len(daydocs)})

    wh = ensure_slack_ok(args)
    if wh:
        post_to_slack(wh, md)

# --------- Entry ---------

def main(argv: Optional[List[str]] = None) -> None:
    ns = parse_args(argv)
    if ns.cmd == "daily":
        cmd_daily(ns)
    elif ns.cmd == "weekly":
        cmd_weekly(ns)
    elif ns.cmd == "monthly":
        cmd_monthly(ns)
    else:  # pragma: no cover
        raise SystemExit(f"Unknown command: {ns.cmd}")

if __name__ == "__main__":  # pragma: no cover
    main()
