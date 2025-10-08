#!/usr/bin/env python3
"""
Team Digest Generator

Parses team updates (logs, emails, meeting notes) into structured digests,
and prints JSON (default) or Markdown.

Recognized sections (case-insensitive, "##" and ":" optional):
  Summary, Decisions, Actions, Risks, Dependencies, Open Questions

Usage (file/stdin):
  team-digest [path|-] [--format json|md] [-o OUTPUT]
  python -m team_email_digest [path|-] [--format json|md] [-o OUTPUT]

Usage (aggregator mode used by CI tests):
  python -m team_email_digest --config CONFIG.json --from YYYY-MM-DD --to YYYY-MM-DD --input LOGS_DIR --format json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Iterable

# Version handling: prefer the version module; fall back for dev environments.
try:
    from team_digest_version import __version__
except Exception:
    __version__ = "0.0.0"  # fallback only; real version should come from team_digest_version.py

# ---------- Configuration ----------

SECTION_ALIASES: Dict[str, List[str]] = {
    "summary": ["summary"],
    "decisions": ["decision", "decisions"],
    "actions": ["action", "actions", "todo", "todos", "to-dos"],
    "risks": ["risk", "risks", "blocker", "blockers"],
    "dependencies": ["dependency", "dependencies", "deps"],
    "open_questions": ["open question", "open questions", "questions", "oq"],
}

# Header like "Summary", "## Summary", "Summary:", or "Summary: inline text"
HEADER_RE = re.compile(r"^\s*(?:#+\s*)?([A-Za-z][A-Za-z\s_-]+?)\s*:?\s*(.*)$")

# Bullet formats: -, *, •, "1. ", "(1) ", checkbox "[ ]", "[x]"
BULLET_RE = re.compile(r"^\s*(?:[-*•]\s+|\d+\.\s+|\(\d+\)\s+|\[\s*\]\s+|\[\s*x\s*\]\s+)")

# Loose "KV" action parser: "Title | owner: X | due: 2025-10-08 | priority: high"
ACTION_KV_RE = re.compile(
    r"(?i)^\s*(?P<title>[^|;:\u2014]+?)\s*(?:[|;:—-]{1,2}\s*)?"
    r"(?:owner\s*[:\-]\s*(?P<owner>[^|;]+))?\s*(?:[|;]\s*)?"
    r"(?:due\s*[:\-]\s*(?P<due>\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}))?\s*(?:[|;]\s*)?"
    r"(?:priority\s*[:\-]\s*(?P<priority>p?\d|low|medium|high))?\s*$"
)

# Phrases that imply dependencies/risks even without headers
WAITING_PAT = re.compile(r"\b(waiting on|waiting for|blocked by|blocked on)\b", re.I)

# ---------- Helpers ----------

def _section_key(name: str) -> Optional[str]:
    n = name.strip().lower()
    for key, aliases in SECTION_ALIASES.items():
        if n in aliases:
            return key
    return None

def _match_header(line: str) -> Optional[tuple[str, str]]:
    m = HEADER_RE.match(line)
    if not m:
        return None
    header, trailing = m.groups()
    key = _section_key(header.lower().strip())
    return (key, trailing) if key else None

def _strip_bullet(s: str) -> str:
    return BULLET_RE.sub("", s).strip()

def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _unique_preserve_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in items:
        k = str(x).strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out

def _normalize_date(s: str) -> str:
    """
    Accepts YYYY-MM-DD or MM/DD[/YY|YYYY]; returns YYYY-MM-DD if parseable.
    If invalid/ambiguous, returns original string.
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
        text = _norm_space(_strip_bullet(raw))
        if not text:
            continue
        m = ACTION_KV_RE.match(text)
        if m:
            d = {k: (v.strip() if v else "") for k, v in m.groupdict().items()}
            if d.get("due"):
                d["due"] = _normalize_date(d["due"])
            out.append({
                "title": d.get("title", ""),
                **({"owner": d["owner"]} if d.get("owner") else {}),
                **({"due": d["due"]} if d.get("due") else {}),
                **({"priority": d["priority"].lower()} if d.get("priority") else {}),
            })
        else:
            out.append({"title": text})
    return out

# ---------- Core parsing ----------

def parse_sections(text: str) -> Dict[str, List[str]]:
    """
    Parse plain text into canonical sections (all lists of strings).
    - Recognizes headers and inline trailing content: "Summary: Foo"
    - Bullets/numbering are normalized
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

        # Robust header detection (works even if regex somehow misses)
        low = line.lower().lstrip("#*• ").strip()
        for alias, key in [
            ("summary", "summary"),
            ("decisions", "decisions"),
            ("decision", "decisions"),
            ("actions", "actions"),
            ("action", "actions"),
            ("risks", "risks"),
            ("risk", "risks"),
            ("blocker", "risks"),
            ("blockers", "risks"),
            ("dependencies", "dependencies"),
            ("dependency", "dependencies"),
            ("open questions", "open_questions"),
            ("open question", "open_questions"),
            ("questions", "open_questions"),
            ("oq", "open_questions"),
        ]:
            if low.startswith(alias + ":") or low == alias:
                current = key
                trailing = line.split(":", 1)[1] if ":" in line else ""
                trailing = _norm_space(_strip_bullet(trailing))
                if trailing:
                    result[current].append(trailing)
                break
        else:
            # Standard header match
            h = _match_header(line)
            if h:
                key, trailing = h
                current = key
                if trailing:
                    content = _norm_space(_strip_bullet(trailing))
                    if content:
                        result[current].append(content)
                continue

            # Not a header, attribute to current (or Summary by default)
            bucket = current or "summary"
            content = _norm_space(_strip_bullet(line))
            if content:
                result[bucket].append(content)

    for k in list(result.keys()):
        result[k] = _unique_preserve_order(result[k])
    return result

def build_digest(text: str) -> Dict[str, object]:
    """Return the final digest with structured actions and metadata."""
    sec = parse_sections(text)
    actions_struct = _parse_actions(sec["actions"])
    digest = {
        "summary": sec["summary"],
        "decisions": sec["decisions"],
        "actions": actions_struct,
        "risks": sec["risks"],
        "dependencies": sec["dependencies"],
        "open_questions": sec["open_questions"],
        "generated_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "version": __version__,
    }
    return digest

# ---------- Rendering ----------

def render_markdown(d: Dict[str, object]) -> str:
    """Human-friendly Markdown. Summary becomes bullets if >1 item, else one line."""
    def hdr(name: str) -> str:
        return f"## {name}\n"
    def bullets(items: List[str]) -> str:
        return "\n".join(f"- {x}" for x in items) + ("\n" if items else "")

    out: List[str] = []

    # Summary
    out.append(hdr("Summary"))
    summary: List[str] = d.get("summary", []) or []
    if len(summary) <= 1:
        out.append((summary[0] if summary else "—") + "\n")
    else:
        out.append(bullets(summary))

    for key, title in [
        ("decisions", "Decisions"),
        ("risks", "Risks"),
        ("dependencies", "Dependencies"),
        ("open_questions", "Open Questions"),
    ]:
        out.append(hdr(title))
        items: List[str] = d.get(key, []) or []
        out.append(bullets(items) if items else "—\n")

    # Actions (table)
    out.append(hdr("Actions"))
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

# ---------- Compatibility shims expected by tests ----------

try:
    __all__  # keep any existing __all__
except NameError:
    __all__ = []
__all__ += [
    "parse_sections",
    "build_digest",
    "render_markdown",
    "summarize_email",
    "compose_brief",
    "send_to_slack",
    "main",
    "__version__",
]

def _extract_json_block(text: str) -> dict | None:
    """
    If text contains a JSON object preceded by a marker like:
        --- RAW MODEL JSON for: Something ---
    try to extract & parse the JSON block. Returns dict or None.
    """
    marker = "--- RAW MODEL JSON"
    if marker not in text:
        return None

    start = text.find(marker)
    brace = text.find("{", start)
    if brace == -1:
        return None

    depth = 0
    end = None
    for i, ch in enumerate(text[brace:], brace):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None

    try:
        return json.loads(text[brace:end])
    except Exception:
        return None

def _heuristic_pullouts(text: str) -> dict:
    """Pull out risks/dependencies/open_questions from free text cues."""
    risks: List[str] = []
    deps: List[str] = []
    oqs: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()

        m = re.match(r"^\s*(blocker|risk)s?\s*[:\-]\s*(.+)$", low, re.I)
        if m:
            risks.append(_norm_space(m.group(2)))
            continue

        m = re.match(r"^\s*(dependency|dependencies)\s*[:\-]\s*(.+)$", low, re.I)
        if m:
            deps.append(_norm_space(m.group(2)))
            continue

        m = re.match(r"^\s*(open question|question|oq)\s*[:\-]\s*(.+)$", low, re.I)
        if m:
            oqs.append(_norm_space(m.group(2)))
            continue

        if WAITING_PAT.search(low):
            # Treat “waiting on/for …” or “blocked by …” as a dependency-ish note.
            # Strip leading “waiting …” / “blocked …” phrasing to keep the meat.
            cleaned = re.sub(r"^\s*(waiting on|waiting for|blocked by|blocked on)\s*[:\-]?\s*", "", low, flags=re.I)
            deps.append(_norm_space(cleaned if cleaned else line))

    return {
        "risks": _unique_preserve_order(risks),
        "dependencies": _unique_preserve_order(deps),
        "open_questions": _unique_preserve_order(oqs),
    }

def summarize_email(text: str) -> dict:
    """
    Return a normalized digest dict from an email-like payload.
    - If a JSON block is embedded, parse and normalize it.
    - Otherwise, use header parsing + extra heuristics for risks/deps/oq.
    """
    data = _extract_json_block(text)
    if data is None:
        d = build_digest(text)
        pulls = _heuristic_pullouts(text)
        # Merge heuristic pulls (dedup)
        d["risks"] = _unique_preserve_order(list(d.get("risks", [])) + pulls["risks"])
        d["dependencies"] = _unique_preserve_order(list(d.get("dependencies", [])) + pulls["dependencies"])
        d["open_questions"] = _unique_preserve_order(list(d.get("open_questions", [])) + pulls["open_questions"])
        return d

    def as_list(x):
        if x is None:
            return []
        if isinstance(x, list):
            return [str(i).strip() for i in x if str(i).strip()]
        return [str(x).strip()] if str(x).strip() else []

    digest = {
        "summary": as_list(data.get("summary")),
        "decisions": as_list(data.get("decisions")),
        "actions": [],
        "risks": as_list(data.get("risks")),
        "dependencies": as_list(data.get("dependencies")),
        "open_questions": as_list(data.get("open_questions")),
        "generated_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "version": __version__,
    }

    acts = data.get("actions") or []
    if isinstance(acts, list):
        for a in acts:
            if isinstance(a, dict):
                title = str(a.get("title", "")).strip()
                owner = (a.get("owner") or "").strip()
                due = (a.get("due") or "").strip()
                if due:
                    due = _normalize_date(due)
                prio = (a.get("priority") or "").strip().lower()
                item = {"title": title}
                if owner:
                    item["owner"] = owner
                if due:
                    item["due"] = due
                if prio:
                    item["priority"] = prio
                digest["actions"].append(item)
            else:
                s = str(a).strip()
                if s:
                    digest["actions"].append({"title": s})

    return digest

def compose_brief(items_or_text, fmt: str = "md") -> str:
    """
    Build a short human brief (Markdown default).
    - If input is a list of items (each with 'subject', 'summary', etc.), render that.
    - If input is raw text, summarize to a digest and render that single item.
    """
    if isinstance(items_or_text, str):
        d = summarize_email(items_or_text)
        item = {
            "subject": "Digest",
            "summary": " ".join(d.get("summary", [])),
            "decisions": d.get("decisions", []),
            "actions": d.get("actions", []),
        }
        items = [item]
    else:
        items = list(items_or_text)

    if fmt.lower() == "json":
        return json.dumps(items, indent=2, ensure_ascii=False)

    out: list[str] = ["# Team Email Brief\n"]
    for it in items:
        subject = str(it.get("subject", "Update")).strip()
        out.append(f"## {subject}\n")

        summary = str(it.get("summary", "")).strip()
        if summary:
            out.append(summary + "\n")

        decisions = it.get("decisions") or []
        if decisions:
            out.append("\n**Decisions**\n")
            out.extend(f"- {str(d).strip()}\n" for d in decisions if str(d).strip())

        actions = it.get("actions") or []
        if actions:
            out.append("\n**Actions**\n")
            for a in actions:
                if isinstance(a, dict):
                    title = a.get("title", "")
                    owner = a.get("owner", "")
                    due = a.get("due", "")
                    prio = a.get("priority", "")
                    line = title
                    if owner:
                        line += f" (owner: {owner})"
                    if due:
                        line += f" (due: {due})"
                    if prio:
                        line += f" (priority: {prio})"
                    out.append(f"- {line}\n")
                else:
                    out.append(f"- {str(a).strip()}\n")

        out.append("\n")
    return "".join(out).rstrip() + "\n"

def send_to_slack(message: str, *, timeout: int = 10) -> bool:
    """
    Post a message to Slack using the SLACK_WEBHOOK_URL environment variable.
    Returns False (no-op) if the variable is unset. Returns True on 2xx response.
    """
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return False
    try:
        import requests  # optional dependency
        resp = requests.post(url, json={"text": message}, timeout=timeout)
        return 200 <= getattr(resp, "status_code", 0) < 300
    except Exception:
        return False

# ---------- CLI ----------

def _read_input(path: str) -> str:
    if path == "-" or path == "":
        return sys.stdin.read()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return p.read_text(encoding="utf-8", errors="ignore")

def _load_config(path: str) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid JSON in config {path}: {e}") from e

def _iter_text_files(root: Path) -> Iterable[Path]:
    # Deterministic order for tests
    for ext in (".log", ".txt", ".md"):
        for f in sorted(root.rglob(f"*{ext}")):
            if f.is_file():
                yield f

def _apply_owner_map(actions: List[dict], owner_map: dict) -> None:
    if not owner_map:
        return
    norm = {str(k).strip().lower(): str(v).strip() for k, v in owner_map.items()}
    for a in actions:
        owner = a.get("owner", "")
        if not owner:
            continue
        key = owner.strip().lower()
        if key in norm:
            a["owner"] = norm[key]

def _aggregate_from_dir(input_dir: str, cfg: dict) -> dict:
    root = Path(input_dir)
    if not root.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    agg = {
        "title": cfg.get("title") or "Team Digest",
        "summary": [],
        "decisions": [],
        "actions": [],
        "risks": [],
        "dependencies": [],
        "open_questions": [],
    }

    for fp in _iter_text_files(root):
        content = fp.read_text(encoding="utf-8", errors="ignore")
        d = summarize_email(content)  # <— use summarize_email so JSON blocks & heuristics work
        agg["summary"].extend(d.get("summary", []))
        agg["decisions"].extend(d.get("decisions", []))
        agg["risks"].extend(d.get("risks", []))
        agg["dependencies"].extend(d.get("dependencies", []))
        agg["open_questions"].extend(d.get("open_questions", []))
        agg["actions"].extend(d.get("actions", []))

    # de-dup while preserving order
    for k in ("summary", "decisions", "risks", "dependencies", "open_questions"):
        agg[k] = _unique_preserve_order(agg[k])

    _apply_owner_map(agg["actions"], cfg.get("owner_map") or {})

    return agg

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

    # Extra args used by phase-2 tests (configurable aggregator mode)
    parser.add_argument("--config", default="", help="Path to JSON config (title, owner_map)")
    parser.add_argument("--from", dest="since", default="", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="until", default="", help="End date (YYYY-MM-DD)")
    parser.add_argument("--input", dest="input_dir", default="", help="Directory of logs/notes")


    args = parser.parse_args(argv)

    # Aggregator mode if --input is provided
    if args.input_dir:
        cfg = _load_config(args.config) if args.config else {}
        agg = _aggregate_from_dir(args.input_dir, cfg)

        if args.format == "json":
            payload = json.dumps(agg, indent=2, ensure_ascii=False)
        else:
            # Convert aggregated dict into a single brief for md rendering
            brief_items = [{
                "subject": agg.get("title", "Team Digest"),
                "summary": " ".join(agg.get("summary", [])),
                "decisions": agg.get("decisions", []),
                "actions": agg.get("actions", []),
            }]
            payload = compose_brief(brief_items, fmt="md")

        if args.output:
            Path(args.output).write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
        return 0

    # Simple single-input mode
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
