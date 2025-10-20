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

# Accept ##..######, any case, and optional punctuation/text after section name
# Examples matched: "## Summary", "###  Summary:", "## Summary — week", "## SUMMARY -"
def read_sections(text):
    secs = {}
    text = text.replace("\r\n", "\n")
    for sec in SECTION_ORDER:
        pat = re.compile(
            rf"^[ \t]*#{2,6}\s*{re.escape(sec)}\b.*$"   # the heading line, flexible suffix
            rf"([\s\S]*?)"                               # section body (lazy)
            rf"(?=^[ \t]*#{2,6}\s+\S|\Z)",              # until next heading or EOF
            re.M | re.I,
        )
        m = pat.search(text)
        if m:
            secs[sec] = m.group(1).strip()
    return secs

def daterange(start, end):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)

def collect_bullets(block):
    if not block:
        return []
    items = []
    for ln in block.splitlines():
        s = ln.strip()
        if s.startswith("-") or s.startswith("*"):
            items.append(s)
    return items

def detect_priority(line):
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
        if not
