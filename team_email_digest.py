#!/usr/bin/env python3
"""
Team Digest Generator

Parses team updates (logs, emails, meeting notes) into structured digests,
and prints JSON (default) or Markdown.

Sections recognized (case-insensitive, with optional "##" and ":"):
  Summary, Decisions, Actions, Risks, Dependencies, Open Questions

Usage:
  team-digest [-] [--format json|md] [--output PATH]
  python -m team_email_digest [-] [--format json|md] [--output PATH]

Examples:
  team-digest updates.txt
  type updates.txt | team-digest - --format md
"""

from __future__ import annotations
import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Version handling: prefer version module; fall back to a literal (keep this indented)
try:
    from team_digest_version import __version__
except Exception:
    __version__ = "0.0.0"  # fallback only; real version comes from team_digest_version.py

# ---------- Config ----------

SECTION_ALIASES: Dict[str, List[str]] = {
    "summary": ["summary"],
    "decisions": ["decision", "decisions"],
    "actions": ["action", "actions", "todo", "todos", "to-dos"],
    "risks": ["risk", "risks"],
    "dependencies": ["dependency", "dependencies", "deps"],
    "open_questions": ["open question", "open questions", "questions", "oq"],
}

HEADER_RE = re.compile(r"^\s*(?:#+\s*)?([A-Za-z][A-Za-z\s_-]+?)\s*:?\s*(.*)$")
BULLET_RE = re.compile(r"^\s*(?:[-*•]\s+|\d+\.\s+|\(\d+\)\s+|\[\s*\]\s+|\[\s*x\s*\]\s+)")
ACTION_KV_RE = re.compile(
    r"(?i)^\s*(?P<title>[^|;:\u2014]+?)\s*(?:[|;:—-]{1,2}\s*)?"
    r"(?:owner\s*[:\-]\s*(?P<owner>[^|;]+))?\s*(?:[|;]\s*)?"
    r"(?:due\s*[:\-]\s*(?P<due>\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}))?\s*(?:[|;]\s*)?"
    r"(?:priority\s*[:\-]\s*(?P<priority>p?\d|low|medium|high))?\s*$"
)

# ---------- Helpers ----------

def _section_key(name: str) -> Optional[str]:
    n = name.strip().lower()
    for key, aliases in SECTION_ALIASES.items():
        if n in aliases:
            return key
    return None

def _is_header(line: str) -> Optional[re.Match]:
    m = HEADER_RE.match(line)
    if not m:
        return None
    header, trailing = m.groups()
    key = _section_key(header.lower().strip())
    return (key, trailing) if key else None

def _strip_bullet(s: str) -> str:
    return BULLET_RE.sub("", s).strip()

def _norm_line(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _unique_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        k = x.strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out

def _normalize_date(s: str) -> str:
    """
    Accepts YYYY-MM-DD or MM/DD[/YY|YYYY]; returns YYYY-MM-DD if parseable.
    If ambiguous or invalid, returns the original string untouched.
    """
    s = s.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if not m:
        return s
    mm, dd, yy = m.groups()
    try:
        mm_i, dd_i = int(mm), int(dd)
        yy_i = int(yy)
        if yy_i < 100:
            yy_i += 2000 if yy_i < 70 else 1900
        dt = _dt.date(yy_i, mm_i, dd_i)
        return dt.isoformat()
    except Exception:
        return s

def _parse_actions(lines: List[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for raw in lines:
        text = _norm_line(_strip_bullet(raw))
        if not text:
            continue
        m = ACTION_KV_RE.match(text)
        if m:
            d = {k: (v.strip() if v else "") for k, v in m.groupdict().items()}
            if d.get("due"):
                d["due"] = _normalize_date(d["due"])
            # Always keep title; other keys optional
            out.append({
                "title": d.get("title", ""),
                **({"owner": d["owner"]} if d.get("owner") else {}),
                **({"due": d["due"]} if d.get("due") else {}),
                **({"priority": d["priority"].lower()} if d.get("priority") else {}),
            })
        else:
            # No KV pattern; treat whole line as the title
            out.append({"title": text})
    return out

def parse_sections(text: str) -> Dict[str, List[str]]:
    """
    Parse plain text into canonical sections (all lists of strings).
    - Recognizes headers and inline trailing content: "Summary: Foo"
    - Bullets and numbered items are normalized
    - Text before the first header is treated as Summary
    """
    result: Dict[str, List[str]] = {
        "summary": [],
        "decisions": [],
        "actions": [],
        "risks": [],
        "dependencies": [],
        "open_questions": [],
    }
    current: Optional[str] = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        header = _is_header(line)
        if header:
            key, trailing = header
            current = key
            if trailing:
                # Inline content on header line
                content = _norm_line(_strip_bullet(trailing))
                if content:
                    result[current].append(content)
            continue

        # No header on this line → attribute to current section (or Summary by default)
        bucket = current or "summary"
        content = _norm_line(_strip_bullet(line))
        if content:
            result[bucket].append(content)

    # de-dup & tidy
    for k in list(result.keys()):
        result[k] = _unique_preserve_order(result[k])
    return result

def build_digest(text: str) -> Dict[str, object]:
    """Produce the final digest dict with structured actions and metadata."""
    sec = parse_sections(text)
    actions_struct = _parse_actions(sec["actions"])
    digest = {
        "summary": sec["summary"],           # list[str]
        "decisions": sec["decisions"],       # list[str]
        "actions": actions_struct,           # list[dict]
        "risks": sec["risks"],               # list[str]
        "dependencies": sec["dependencies"], # list[str]
        "open_questions": sec["open_questions"], # list[str]
        "generated_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "version": __version__,
    }
    return digest

def render_markdown(d: Dict[str, object]) -> str:
    """Human-friendly Markdown. Summary becomes bullets if >1 item, else one line."""
    def sec_hdr(name: str) -> str:
        return f"## {name}\n"
    def fmt_list(items: List[str]) -> str:
        return "\n".join(f"- {x}" for x in items) + ("\n" if items else "")
    out = []

    # Summary
    out.append(sec_hdr("Summary"))
    summary: List[str] = d.get("summary", []) or []
    if len(summary) <= 1:
        out.append((summary[0] if summary else "—") + "\n")
    else:
        out.append(fmt_list(summary))

    # Simple list sections
    for key, title in [
        ("decisions", "Decisions"),
        ("risks", "Risks"),
        ("dependencies", "Dependencies"),
        ("open_questions", "Open Questions"),
    ]:
        out.append(sec_hdr(title))
        items: List[str] = d.get(key, []) or []
        out.append(fmt_list(items) if items else "—\n")

    # Actions as a table
    out.append(sec_hdr("Actions"))
    actions = d.get("actions", []) or []
    if not actions:
        out.append("—\n")
    else:
        out.append("| Title | Owner | Due | Priority |\n|---|---|---|---|\n")
        for a in actions:
            out.append(
                f"| {a.get('title','')} | {a.get('owner','')} | {a.get('due','')} | {a.get('priority','')} |\n"
            )
    return "".join(out).rstrip() + "\n"

# ---------- CLI ----------

def _read_input(path: str) -> str:
    if path == "-" or path == "":
        return sys.stdin.read()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return p.read_text(encoding="utf-8", errors="ignore")

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a team digest (JSON default) from updates/notes.",
        prog="team-digest",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help="Input file path or '-' for stdin (default: '-')",
    )
    parser.add_argument(
        "--format",
        choices=["json", "md"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "-o", "--output",
        default="",
        help="Optional output file path. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show version and exit",
    )

    args = parser.parse_args(argv)

    raw = _read_input(args.path)
    digest = build_digest(raw)

    if args.format == "json":
        payload = json.dumps(digest, indent=2, ensure_ascii=False)
    else:
        payload = render_markdown(digest)

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
