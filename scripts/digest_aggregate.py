#!/usr/bin/env python
# scripts/digest_aggregate.py
import argparse, re, sys, io, os, datetime as dt
from pathlib import Path

SECTION_ORDER = ["Summary", "Decisions", "Actions", "Risks", "Dependencies", "Notes"]
PRIORITY_TAGS = {"high": 0, "medium": 1, "low": 2}

def parse_args():
    p = argparse.ArgumentParser(description="Aggregate logs into a digest.")
    p.add_argument("--logs-dir", default="logs")
    p.add_argument("--start", required=True)   # YYYY-MM-DD
    p.add_argument("--end", required=True)     # YYYY-MM-DD inclusive
    p.add_argument("--output", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--expect-missing", dest="expect_missing", action="store_true")
    p.add_argument("--group-actions", dest="group_actions", action="store_true")
    return p.parse_args()

# Accept ##..######, any case, optional punctuation/text after section name
# Examples: "## Summary", "### Summary:", "## Summary — week 42", "## SUMMARY -"
def read_sections(text: str) -> dict:
    secs = {}
    text = text.replace("\r\n", "\n")
    for sec in SECTION_ORDER:
        pat = re.compile(
            rf"^[ \t]*#{2,6}\s*{re.escape(sec)}\b.*$"   # heading line
            rf"([\s\S]*?)"                               # body (lazy)
            rf"(?=^[ \t]*#{2,6}\s+\S|\Z)",              # next heading or EOF
            re.M | re.I,
        )
        m = pat.search(text)
        if m:
            secs[sec] = m.group(1).strip()
    return secs

def daterange(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)

def collect_bullets(block: str):
    if not block:
        return []
    items = []
    for ln in block.splitlines():
        s = ln.strip()
        if s.startswith("-") or s.startswith("*"):
            items.append(s)
    return items

def detect_priority(line: str):
    for tag, rank in PRIORITY_TAGS.items():
        if re.search(rf"\[{tag}\]", line, re.I):
            return tag, rank
    return None, 999

def main():
    a = parse_args()
    logs_dir = Path(a.logs_dir)
    start = dt.date.fromisoformat(a.start)
    end   = dt.date.fromisoformat(a.end)

    acc = {k: [] for k in SECTION_ORDER}
    action_items = []
    matched = []

    for d in daterange(start, end):
        p = logs_dir / f"notes-{d.isoformat()}.md"
        if not p.exists():
            continue
        matched.append(p.as_posix())
        t = io.open(p, "r", encoding="utf-8").read()
        secs = read_sections(t)
        for k in ["Summary", "Decisions", "Risks", "Dependencies", "Notes"]:
            if secs.get(k):
                acc[k].append(secs[k].strip())
        for line in collect_bullets(secs.get("Actions", "")):
            tag, rank = detect_priority(line)
            action_items.append((rank, tag or "", line))

    # <- This is the line that got broken in your copy:
    if not matched and not a.expect_missing:
        sys.stderr.write(f"[weekly] No log files matched {start}..{end} in {logs_dir}\n")
        sys.exit(2)

    title = a.title or f"Team Digest ({start.isoformat()} - {end.isoformat()})"
    out = [f"# {title}", ""]
    out.append(
        f"_Range: {start.isoformat()} → {end.isoformat()} | Source: {a.logs_dir} | "
        f"Days matched: {len(matched)} | Actions: {len(action_items)}_"
    )
    out.append("")

    def emit_block(name: str):
        out.append(f"## {name}")
        items = acc[name]
        if items:
            for x in items:
                out.append(x)
                out.append("")
        else:
            out.append(f"_No {name.lower()}._")
            out.append("")

    emit_block("Summary")
    emit_block("Decisions")

    out.append("## Actions")
    if action_items:
        if a.group_actions:
            buckets = {"high": [], "medium": [], "low": [], "other": []}
            for rank, tag, line in sorted(action_items, key=lambda t: (t[0], t[2])):
                key = (tag or "other").lower()
                if key not in buckets:
                    key = "other"
                buckets[key].append(line)
            for head in ["high", "medium", "low", "other"]:
                if not buckets[head]:
                    continue
                label = "Other" if head == "other" else head.capitalize()
                out.append(f"### {label} priority")
                out.extend(buckets[head])
                out.append("")
        else:
            for _, __, line in sorted(action_items, key=lambda t: (t[0], t[2])):
                out.append(line)
            out.append("")
    else:
        out.append("_No actions._")
        out.append("")

    emit_block("Risks")
    emit_block("Dependencies")
    emit_block("Notes")

    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    io.open(a.output, "w", encoding="utf-8").write("\n".join(out).rstrip() + "\n")

if __name__ == "__main__":
    main()
