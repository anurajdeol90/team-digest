#!/usr/bin/env python
# scripts/digest_daily.py
#
# Daily digest that mirrors weekly style:
# - tolerant section slicing (##..######), mojibake fixes
# - wide bullet detection (- * +, 1./1), checkboxes, unicode bullets/dashes)
# - optional grouping of Actions by [high]/[medium]/[low] and [p0]/[p1]/[p2]
# - sorting inside groups by name (if detected) then text
# - omit empty sections entirely

import argparse, re, sys, io, os, datetime as dt
from pathlib import Path

SECTION_ORDER = ["Summary", "Decisions", "Actions", "Risks", "Dependencies", "Notes"]

# priority ranks: lower = higher priority
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
P_EQUIV = {"p0": "high", "p1": "medium", "p2": "low"}  # map pN -> label

# Wide bullet detection: -, *, +, numbered 1./1), checkboxes, unicode bullets/dashes
BULLET_RE = re.compile(
    r'^[\s\u00A0]*('
    r'(?:[-*+])|'              # -, *, +
    r'(?:\d+[.)])|'            # 1. or 1)
    r'(?:\[[ xX\-]\])|'        # [ ], [x], [-]
    r'[\u2022\u2023\u2043\u2219\u25AA\u25AB\u25CF\u25E6\u2013\u2014]'  # • ‣ ⁃ ∙ ▪ ▫ ● ◦ – —
    r')\s+',
    re.M
)

# Same as BULLET_RE but allows optional leading backslash (escaped bullets in logs)
LEAD_TOKEN_RE = re.compile(
    r'^[\s\u00A0]*\\?(?:[-*+]|\d+[.)]|\[[ xX\-]\]|[\u2022\u2023\u2043\u2219\u25AA\u25AB\u25CF\u25E6\u2013\u2014])\s+'
)

# tolerant header locator
HDR_LINE = re.compile(r'^[ \t]*#{2,6}\s*([A-Za-z][^\n#]*)$', re.M)

# fix common mojibake from mis-decoding
MOJIBAKE_FIXES = {
    "â€“": "–", "â€”": "—", "â€˜": "‘", "â€™": "’",
    "â€œ": "“", "â€\x9d": "”", "â€¢": "•",
}

def fix_mojibake(s: str) -> str:
    for k, v in MOJIBAKE_FIXES.items():
        s = s.replace(k, v)
    return s

def normalize_heading(raw: str) -> str:
    return raw.strip().split()[0].rstrip(":-—–").lower()

def slice_sections(text: str) -> dict:
    text = fix_mojibake(text.replace("\r\n", "\n"))
    sections = {}
    matches = list(HDR_LINE.finditer(text))
    if not matches:
        return sections
    for i, m in enumerate(matches):
        raw = m.group(1)
        base = normalize_heading(raw)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        for canonical in SECTION_ORDER:
            if base == canonical.lower():
                sections[canonical] = body
                break
    return sections

def collect_bullets(block: str):
    if not block:
        return []
    out = []
    for ln in block.splitlines():
        s = ln.rstrip()
        if not s.strip():
            continue
        if BULLET_RE.match(s) or LEAD_TOKEN_RE.match(s):
            out.append(s.strip())
    return out

def clean_item_text(line: str) -> str:
    s = LEAD_TOKEN_RE.sub("", line).strip()
    s = re.sub(r'^[\\]+', "", s).strip()
    return s

def normalize_block_text(block: str) -> str:
    if not block:
        return ""
    lines = []
    for ln in fix_mojibake(block).splitlines():
        ln = re.sub(r'^[ \t]*\\(?=[-*+])', "", ln)
        lines.append(ln)
    return "\n".join(lines).strip()

def detect_priority(line: str):
    m = re.search(r"\[(high|medium|low|p0|p1|p2)\]", line, re.I)
    if m:
        tag = m.group(1).lower()
        label = P_EQUIV.get(tag, tag)
        return label, PRIORITY_RANK.get(label, 3)
    return "other", 3

# --- simple "name" extractor for secondary sort ---
# Tries patterns like:
#   - [high] Alex to ...
#   - [p1] Priya – ...
#   - ... (owner: Anuraj Deol)
NAME_PATTERNS = [
    re.compile(r"\]\s*([A-Z][\w.\- ]{1,40}?)\s+to\b"),            # ] Alex to
    re.compile(r"\]\s*([A-Z][\w.\- ]{1,40}?)\s+[—–-]\s+"),        # ] Priya — ...
    re.compile(r"\(owner:\s*([^)]+?)\)", re.I),                   # (owner: Name)
]
def extract_name(text: str) -> str:
    for rx in NAME_PATTERNS:
        m = rx.search(text)
        if m:
            return m.group(1).strip()
    m = re.search(r"\b([A-Z][a-zA-Z.\-]+(?:\s+[A-Z][a-zA-Z.\-]+)?)\b", text)
    return m.group(1) if m else ""

def main():
    ap = argparse.ArgumentParser(description="Build a daily digest from a single log file.")
    ap.add_argument("--logs-dir", default="logs")
    ap.add_argument("--date", help="YYYY-MM-DD (defaults to today in UTC)", default=dt.datetime.utcnow().date().isoformat())
    ap.add_argument("--output", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--group-actions", action="store_true")
    ap.add_argument("--sort-actions", default="priority,name,text", help="comma list: priority,name,text (order matters)")
    args = ap.parse_args()

    log_path = Path(args.logs_dir) / f"notes-{args.date}.md"
    if not log_path.exists():
        title = args.title or f"Team Digest ({args.date})"
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        io.open(args.output, "w", encoding="utf-8").write(f"# {title}\n\n_No log for {args.date} in {args.logs_dir}_\n")
        sys.exit(0)

    txt = io.open(log_path, "r", encoding="utf-8").read()
    secs = slice_sections(txt)

    # narrative
    collected = {k: [] for k in SECTION_ORDER}
    for k in ["Summary", "Decisions", "Risks", "Dependencies", "Notes"]:
        if secs.get(k):
            t = normalize_block_text(secs[k])
            if t:
                collected[k].append(t)

    # actions
    action_items = []
    actions_block = secs.get("Actions", "")
    bullets = collect_bullets(actions_block)
    if not bullets and actions_block:
        # fallback if priorities present
        lines = [L.strip() for L in actions_block.splitlines() if L.strip()]
        if any(re.search(r"\[(?:high|medium|low|p0|p1|p2)\]", L, re.I) for L in lines):
            bullets = lines
    for line in bullets:
        label, rank = detect_priority(line)
        text = clean_item_text(line)
        who  = extract_name(text).lower()
        action_items.append((rank, label, who, text))

    # sorting behavior
    keys = [k.strip().lower() for k in args.sort_actions.split(",") if k.strip()]
    def sort_key(item):
        rank, label, who, text = item
        parts = []
        for k in keys:
            if k == "priority": parts.append(rank)
            elif k == "name":   parts.append(who)
            elif k == "text":   parts.append(text.lower())
        return tuple(parts) if parts else (rank, who, text.lower())

    action_items.sort(key=sort_key)

    # render
    title = args.title or f"Team Digest ({args.date})"
    out = [f"# {title}", ""]

    def emit_block(name: str):
        items = [x for x in collected[name] if x]
        if not items:
            return  # omit empty section
        out.append(f"## {name}")
        for x in items:
            out.append(x)
            out.append("")

    emit_block("Summary")
    emit_block("Decisions")

    if action_items:
        out.append("## Actions")
        if args.group_actions:
            buckets = {"high": [], "medium": [], "low": [], "other": []}
            for rank, label, who, text in action_items:
                key = label if label in buckets else "other"
                buckets[key].append(f"- {text}")
            for head, title_h in [("high","High"), ("medium","Medium"), ("low","Low"), ("other","Other")]:
                if buckets[head]:
                    out.append(f"### {title_h} priority")
                    out.extend(buckets[head])
                    out.append("")
        else:
            for _, __, ___, text in action_items:
                out.append(f"- {text}")
            out.append("")

    emit_block("Risks")
    emit_block("Dependencies")
    emit_block("Notes")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    io.open(args.output, "w", encoding="utf-8").write("\n".join(out).rstrip() + "\n")

if __name__ == "__main__":
    main()
