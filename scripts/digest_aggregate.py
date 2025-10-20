#!/usr/bin/env python
# scripts/digest_aggregate.py
import argparse, re, sys, io, os, datetime as dt
from pathlib import Path

SECTION_ORDER = ["Summary", "Decisions", "Actions", "Risks", "Dependencies", "Notes"]
PRIORITY_TAGS = {"high": 0, "medium": 1, "low": 2}

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

# Same as BULLET_RE but allows an optional leading backslash before the marker (to unescape)
LEAD_TOKEN_RE = re.compile(
    r'^[\s\u00A0]*\\?(?:[-*+]|\d+[.)]|\[[ xX\-]\]|[\u2022\u2023\u2043\u2219\u25AA\u25AB\u25CF\u25E6\u2013\u2014])\s+'
)

HDR_LINE = re.compile(r'^[ \t]*#{2,6}\s*([A-Za-z][^\n#]*)$', re.M)

MOJIBAKE_FIXES = {
    "â€“": "–", "â€”": "—", "â€˜": "‘", "â€™": "’",
    "â€œ": "“", "â€\x9d": "”", "â€¢": "•",
}

def fix_mojibake(s: str) -> str:
    for k, v in MOJIBAKE_FIXES.items():
        s = s.replace(k, v)
    return s

def parse_args():
    p = argparse.ArgumentParser(description="Aggregate logs into a digest.")
    p.add_argument("--logs-dir", default="logs")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--expect-missing", dest="expect_missing", action="store_true")
    p.add_argument("--group-actions", dest="group_actions", action="store_true")
    return p.parse_args()

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

def detect_priority(line: str):
    for tag, rank in PRIORITY_TAGS.items():
        if re.search(rf"\[{tag}\]", line, re.I):
            return tag, rank
    return None, 999

def clean_item_text(line: str) -> str:
    # Remove any leading bullet/checkbox/number with optional backslash
    s = LEAD_TOKEN_RE.sub("", line).strip()
    # Final tiny cleanup: if someone double-escaped like "\\- ", collapse it
    s = re.sub(r'^[\\]+', "", s).strip()
    return s

def normalize_block_text(block: str) -> str:
    """Unescape leading '\-' '\*' etc in narrative sections and fix mojibake."""
    if not block:
        return ""
    lines = []
    for ln in fix_mojibake(block).splitlines():
        # If a line starts with an escaped bullet, drop the backslash so it renders cleanly
        ln = re.sub(r'^[ \t]*\\(?=[-*+])', "", ln)
        lines.append(ln)
    return "\n".join(lines).strip()

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
        secs = slice_sections(t)

        # narrative sections (normalize escaped bullets + mojibake)
        for k in ["Summary", "Decisions", "Risks", "Dependencies", "Notes"]:
            if secs.get(k):
                acc[k].append(normalize_block_text(secs[k]))

        # actions
        actions_block = secs.get("Actions", "")
        bullets = collect_bullets(actions_block)

        # Fallback: if no bullets but priority tags exist, treat non-empty lines as items
        if not bullets and actions_block:
            lines = [L.strip() for L in actions_block.splitlines() if L.strip()]
            if any(re.search(r"\[(?:high|medium|low)\]", L, re.I) for L in lines):
                bullets = lines

        for line in bullets:
            tag, rank = detect_priority(line)
            action_items.append((rank, tag or "", clean_item_text(line)))

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
        items = [x for x in acc[name] if x]
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
            for rank, tag, text in sorted(action_items, key=lambda t: (t[0], t[2])):
                key = (tag or "other").lower()
                if key not in buckets:
                    key = "other"
                buckets[key].append(f"- {text}")
            for head in ["high", "medium", "low", "other"]:
                if not buckets[head]:
                    continue
                label = "Other" if head == "other" else head.capitalize()
                out.append(f"### {label} priority")
                out.extend(buckets[head])
                out.append("")
        else:
            for _, __, text in sorted(action_items, key=lambda t: (t[0], t[2])):
                out.append(f"- {text}")
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
