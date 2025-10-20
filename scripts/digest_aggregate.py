#!/usr/bin/env python
# scripts/digest_aggregate.py
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
# Same as BULLET_RE but allows an optional leading backslash (escaped bullets in logs)
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

def daterange(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)

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
        ln = re.sub(r'^[ \t]*\\(?=[-*+])', "", ln)  # drop leading backslash before a bullet
        lines.append(ln)
    return "\n".join(lines).strip()

def detect_priority(line: str):
    m = re.search(r"\[(high|medium|low|p0|p1|p2)\]", line, re.I)
    if m:
        tag = m.group(1).lower()
        label = P_EQUIV.get(tag, tag)
        return label, PRIORITY_RANK.get(label, 3)
    return "other", 3

# --- extract owner name for secondary sort ---
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

# NEW: strip any leading priority tag so we don't duplicate labels
def strip_priority_tag(s: str) -> str:
    return re.sub(r'^\s*\[(?:high|medium|low|p0|p1|p2)\]\s*', '', s, flags=re.I)

def main():
    p = argparse.ArgumentParser(description="Aggregate logs into a weekly (or arbitrary range) digest.")
    p.add_argument("--logs-dir", default="logs")
    p.add_argument("--start", required=True)   # YYYY-MM-DD inclusive
    p.add_argument("--end", required=True)     # YYYY-MM-DD inclusive
    p.add_argument("--output", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--expect-missing", action="store_true")
    p.add_argument("--group-actions", action="store_true")
    p.add_argument("--flat-by-name", action="store_true", help="Sort actions globally by name→priority→text")
    args = p.parse_args()

    logs_dir = Path(args.logs_dir)
    start = dt.date.fromisoformat(args.start)
    end   = dt.date.fromisoformat(args.end)

    acc = {k: [] for k in SECTION_ORDER}
    action_items = []  # list of (rank,label,who,text)
    matched = []

    for d in daterange(start, end):
        pth = logs_dir / f"notes-{d.isoformat()}.md"
        if not pth.exists():
            continue
        matched.append(pth.as_posix())
        t = io.open(pth, "r", encoding="utf-8").read()
        secs = slice_sections(t)

        # narrative
        for k in ["Summary", "Decisions", "Risks", "Dependencies", "Notes"]:
            if secs.get(k):
                txt = normalize_block_text(secs[k])
                if txt:
                    acc[k].append(txt)

        # actions
        actions_block = secs.get("Actions", "")
        bullets = collect_bullets(actions_block)
        if not bullets and actions_block:
            lines = [L.strip() for L in actions_block.splitlines() if L.strip()]
            if any(re.search(r"\[(?:high|medium|low|p0|p1|p2)\]", L, re.I) for L in lines):
                bullets = lines
        for line in bullets:
            label, rank = detect_priority(line)
            text = clean_item_text(line)
            who  = extract_name(text).lower()
            action_items.append((rank, label, who, text))

    title = args.title or f"Team Digest ({start.isoformat()} - {end.isoformat()})"
    out = [f"# {title}", ""]
    out.append(
        f"_Range: {start.isoformat()} → {end.isoformat()} | Source: {args.logs_dir} | "
        f"Days matched: {len(matched)} | Actions: {len(action_items)}_"
    )
    out.append("")

    def emit_block(name: str):
        items = [x for x in acc[name] if x]
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
        if args.flat_by_name:
            # Global: name → priority → text, show ONE standardized tag
            for _, label, who, text in sorted(action_items, key=lambda t: (t[2], t[0], t[3].lower())):
                cleaned = strip_priority_tag(text)
                tag = f"[{label}]" if label != "other" else "[other]"
                out.append(f"- {tag} {cleaned}")
            out.append("")
        elif args.group_actions:
            # Bucketed: priority → name → text; no per-line tag (bucket header implies priority)
            buckets = {"high": [], "medium": [], "low": [], "other": []}
            for rank, label, who, text in sorted(action_items, key=lambda t: (t[0], t[2], t[3].lower())):
                key = label if label in buckets else "other"
                buckets[key].append(f"- {strip_priority_tag(text)}")
            for head, title_h in [("high","High"), ("medium","Medium"), ("low","Low"), ("other","Other")]:
                if buckets[head]:
                    out.append(f"### {title_h} priority")
                    out.extend(buckets[head])
                    out.append("")
        else:
            # Flat legacy: priority → name → text; show one standardized tag for clarity
            for _, label, who, text in sorted(action_items, key=lambda t: (t[0], t[2], t[3].lower())):
                cleaned = strip_priority_tag(text)
                tag = f"[{label}]" if label != "other" else "[other]"
                out.append(f"- {tag} {cleaned}")
            out.append("")

    emit_block("Risks")
    emit_block("Dependencies")
    emit_block("Notes")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    io.open(args.output, "w", encoding="utf-8").write("\n".join(out).rstrip() + "\n")

if __name__ == "__main__":
    main()
