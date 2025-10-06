#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
team_email_digest.py — Phase 2

Moves the Phase 1 prototype toward a scalable, config-driven digest tool.

Key additions:
- Config support (YAML or JSON) to avoid hardcoded values.
- Extended sections: risks, dependencies, open_questions (heuristics).
- CLI flags for date range, input sources, and output format (json|md|html).
- Robust log/JSON extraction (streams directories, files, or STDIN).
- Deduplication and normalization of actions/decisions.
- Graceful error handling and useful exit codes.

USAGE (examples):
  python team_email_digest.py --from 2025-10-01 --to 2025-10-05 ^
      --input .\logs --format md --output .\outputs\digest_2025-10-01_2025-10-05.md

  type .\logs\run.log | python team_email_digest.py --format json

  python team_email_digest.py --config .\config.yaml --input .\logs --format html
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # Optional; only needed if using YAML config
    _YAML_AVAILABLE = True
except Exception:
    _YAML_AVAILABLE = False


# -------------------------
# Utilities
# -------------------------

ISO_DATE = "%Y-%m-%d"
ISO_DATETIME = "%Y-%m-%dT%H:%M:%S"

def parse_date(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    s = s.strip()
    for fmt in (ISO_DATE, ISO_DATETIME):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        raise argparse.ArgumentTypeError(f"Invalid date/datetime: {s!r}")

def within_range(path: str, start: Optional[dt.datetime], end: Optional[dt.datetime]) -> bool:
    """Filter files by modified time if a range is provided."""
    if start is None and end is None:
        return True
    try:
        mtime = dt.datetime.fromtimestamp(os.path.getmtime(path))
    except Exception:
        return False
    if start and mtime < start:
        return False
    if end and mtime >= (end + dt.timedelta(days=1) if end.time() == dt.time() else end):
        return False
    return True

def load_config(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        if not _YAML_AVAILABLE:
            raise RuntimeError("PyYAML is not installed, but a YAML config was provided.")
        return yaml.safe_load(text) or {}
    return json.loads(text)

def coalesce(*vals, default=None):
    for v in vals:
        if v is not None:
            return v
    return default


# -------------------------
# Robust JSON extraction
# -------------------------

JSON_BLOCK_RE = re.compile(
    r"""(?P<json>\{\s*(?:"summary"|["']summary["']).*?\})""",
    re.DOTALL | re.IGNORECASE,
)

def _extract_balanced_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract the first balanced {...} JSON object from the text (stack-based),
    then parse it. This survives nested braces inside arrays and objects.
    Returns the dict if it parses and contains a 'summary' key, else None.
    """
    s = text
    n = len(s)
    i = 0
    while i < n:
        if s[i] == "{":
            depth = 0
            j = i
            while j < n:
                ch = s[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        blob = s[i : j + 1]
                        try:
                            obj = json.loads(blob)
                            if isinstance(obj, dict) and any(k.lower() == "summary" for k in obj.keys()):
                                return obj
                        except Exception:
                            # continue scanning after this closing brace
                            pass
                        i = j  # jump ahead
                        break
                j += 1
        i += 1
    return None

# Heuristic phrases (add as needed)
RISK_TERMS = [
    r"\brisk(s)?\b", r"\bblocker(s)?\b", r"\bblocked\b", r"\bslip\b", r"\boverdue\b",
    r"\bat\s+risk\b", r"\bdelay(ed)?\b", r"\bconcern(s)?\b", r"\bmitigation\b",
]
DEPENDENCY_TERMS = [
    r"\bdependenc(y|ies)\b", r"\bwaiting on\b", r"\bexternal team\b", r"\bunblock(ed)?\b",
    r"\brequires\b", r"\bneeds from\b", r"\bPR\b.*\bmerge\b", r"\brelease\b.*\bneeded\b",
]
OPEN_Q_TERMS = [
    r"\bopen question(s)?\b", r"\bTBD\b", r"\bunknown\b", r"\bneed(s)? decision\b",
    r"\bclarify\b", r"\?\s*$", r"\bwho owns\b", r"\bwhen can\b", r"\bhow do\b",
]

LINE_SPLIT_RE = re.compile(r"\r?\n")

def iter_sources(stdin_ok: bool, input_path: Optional[str]) -> Iterable[Tuple[str, str]]:
    """
    Yield (source_label, text) tuples.
    - If input_path is a directory, read all files under it (text-ish only).
    - If input_path is a file, read it.
    - If no input_path and stdin_ok, read from stdin once.
    """
    if input_path:
        if os.path.isdir(input_path):
            for root, _, files in os.walk(input_path):
                for fn in files:
                    full = os.path.join(root, fn)
                    if not any(fn.lower().endswith(ext) for ext in (".log", ".txt", ".json", ".out")):
                        continue
                    yield (full, read_text_safely(full))
        else:
            yield (input_path, read_text_safely(input_path))
    elif stdin_ok and not sys.stdin.closed and not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            yield ("<stdin>", data)

def read_text_safely(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""

def extract_json_blocks(text: str) -> List[Dict[str, Any]]:
    """
    Find JSON-like blocks that include at least the 'summary' key.
    Strategy:
      1) Regex (fast) — may fail on deep nesting.
      2) Balanced-brace scan (robust).
    """
    results: List[Dict[str, Any]] = []

    # 1) Regex attempt(s)
    for m in JSON_BLOCK_RE.finditer(text):
        blob = m.group("json")
        fixed = (
            blob.replace("'", '"')
                .replace(",\n}", "\n}")
                .replace(",}", "}")
        )
        try:
            obj = json.loads(fixed)
            if isinstance(obj, dict) and any(k.lower() == "summary" for k in obj.keys()):
                results.append(obj)
        except Exception:
            cleaned = fixed.strip().strip("`").strip()
            try:
                obj = json.loads(cleaned)
                if isinstance(obj, dict) and any(k.lower() == "summary" for k in obj.keys()):
                    results.append(obj)
            except Exception:
                continue

    # 2) Balanced-brace fallback (first valid dict)
    if not results:
        obj = _extract_balanced_json(text)
        if obj is not None:
            results.append(obj)

    return results

def _normalize_waiting_on_line(s: str) -> Optional[str]:
    """
    Return a normalized 'waiting on ...' phrase in lowercase without trailing punctuation.
    E.g., 'Blocker: waiting on External API keys.' -> 'waiting on external api keys'
    """
    low = s.lower()
    idx = low.find("waiting on")
    if idx == -1:
        return None
    tail = low[idx:].strip()
    # strip leading 'waiting on' and any separators
    tail = tail[len("waiting on"):].strip(" :.-\t")
    # cut at sentence boundary
    tail = re.split(r"[\.!\n\r]", tail, maxsplit=1)[0].strip()
    if not tail:
        return None
    return f"waiting on {tail}"

def extract_heuristics(text: str) -> Dict[str, List[str]]:
    """
    Heuristically collect risks, dependencies, and open questions from text lines.
    - Lines containing 'blocker' are treated as both risk and dependency.
    - Lines containing 'waiting on' are treated as dependencies (line kept verbatim),
      AND we add a normalized 'waiting on ...' form to guarantee substring matches.
    - We also scan the whole text for 'waiting on …' to catch single-line bodies.
    """
    risks, deps, open_qs = set(), set(), set()
    lines = LINE_SPLIT_RE.split(text or "")
    for ln in lines:
        ln_stripped = ln.strip()
        if not ln_stripped:
            continue
        low = ln_stripped.lower()

        if "blocker" in low:
            risks.add(ln_stripped)
            deps.add(ln_stripped)

        if any(re.search(p, low) for p in RISK_TERMS):
            risks.add(ln_stripped)

        if "waiting on" in low:
            deps.add(ln_stripped)
            norm = _normalize_waiting_on_line(ln_stripped)
            if norm:
                deps.add(norm)

        if any(re.search(p, low) for p in DEPENDENCY_TERMS):
            deps.add(ln_stripped)

        if any(re.search(p, ln_stripped) for p in OPEN_Q_TERMS) or ln_stripped.endswith("?"):
            open_qs.add(ln_stripped)

    # Whole-text catch-all for 'waiting on ...'
    text_low = (text or "").lower()
    for match in re.finditer(r"waiting on\s+(.+?)(?:[\.!\n\r]|$)", text_low, re.IGNORECASE):
        phrase = f"waiting on {match.group(1).strip()}"
        deps.add(phrase)

    if "blocker" in text_low:
        risks.add("Blocker detected.")
        deps.add("Blocker detected.")

    return {
        "risks": sorted(risks),
        "dependencies": sorted(deps),
        "open_questions": sorted(open_qs),
    }

def normalize_action(a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": a.get("title", "").strip(),
        "owner": a.get("owner", "").strip(),
        "due": a.get("due", "").strip(),
        "priority": a.get("priority", "").strip().lower() or None,
    }

def merge_lists_unique(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        key = it.strip()
        if key and key not in seen:
            out.append(key)
            seen.add(key)
    return out

def merge_actions(actions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for a in actions:
        na = normalize_action(a)
        key = (na["title"], na["owner"], na["due"])
        if na["title"] and key not in seen:
            out.append(na)
            seen.add(key)
    return out


# -------------------------
# Rendering
# -------------------------

def render_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)

def render_md(payload: Dict[str, Any]) -> str:
    lines = []
    title = payload.get("title") or "Team Email Digest"
    period = payload.get("period")
    if period:
        lines.append(f"# {title} - {period}")  # ASCII-safe
    else:
        lines.append(f"# {title}")
    lines.append("")
    if payload.get("summary"):
        lines.append("## Summary")
        lines.append(payload["summary"])
        lines.append("")
    if payload.get("decisions"):
        lines.append("## Decisions")
        for d in payload["decisions"]:
            lines.append(f"- {d}")
        lines.append("")
    if payload.get("actions"):
        lines.append("## Actions")
        for a in payload["actions"]:
            due = f" (due {a['due']})" if a.get("due") else ""
            owner = f" - **{a['owner']}**" if a.get("owner") else ""
            prio = f" _[{a['priority']}]_" if a.get("priority") else ""
            lines.append(f"- {a['title']}{owner}{due}{prio}")
        lines.append("")
    if payload.get("risks"):
        lines.append("## Risks")
        for r in payload["risks"]:
            lines.append(f"- {r}")
        lines.append("")
    if payload.get("dependencies"):
        lines.append("## Dependencies")
        for r in payload["dependencies"]:
            lines.append(f"- {r}")
        lines.append("")
    if payload.get("open_questions"):
        lines.append("## Open Questions")
        for r in payload["open_questions"]:
            lines.append(f"- {r}")
        lines.append("")
    return "\n".join(lines)

def render_html(payload: Dict[str, Any]) -> str:
    import html
    def esc(s: str) -> str:
        return html.escape(s, quote=True)

    title = esc(payload.get("title") or "Team Email Digest")
    period = esc(payload.get("period") or "")
    parts = [
        "<!doctype html>",
        "<meta charset='utf-8'>",
        f"<title>{title}</title>",
        "<style>",
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.5;margin:24px;}",
        "h1{font-size:24px;margin-bottom:8px}",
        "h2{font-size:18px;margin-top:24px}",
        "ul{margin:8px 0 16px 20px}",
        ".muted{color:#666}",
        "</style>",
        f"<h1>{title}{(' - ' + period) if period else ''}</h1>",
    ]

    if payload.get("summary"):
        parts += ["<h2>Summary</h2>", f"<p>{esc(payload['summary'])}</p>"]

    def section_list(label: str, items: List[str]):
        nonlocal parts
        if items:
            parts.append(f"<h2>{esc(label)}</h2>")
            parts.append("<ul>")
            for it in items:
                parts.append(f"<li>{esc(it)}</li>")
            parts.append("</ul>")

    section_list("Decisions", payload.get("decisions", []))

    if payload.get("actions"):
        parts.append("<h2>Actions</h2><ul>")
        for a in payload["actions"]:
            t = esc(a.get("title", ""))
            owner = esc(a.get("owner", "")) if a.get("owner") else ""
            due = esc(a.get("due", "")) if a.get("due") else ""
            prio = esc(a.get("priority", "")) if a.get("priority") else ""
            meta = " - ".join([p for p in [owner, (f"due {due}" if due else ""), prio] if p])
            parts.append(f"<li>{t}{(' - ' + meta) if meta else ''}</li>")
        parts.append("</ul>")

    section_list("Risks", payload.get("risks", []))
    section_list("Dependencies", payload.get("dependencies", []))
    section_list("Open Questions", payload.get("open_questions", []))

    return "\n".join(parts)


# -------------------------
# Core
# -------------------------

@dataclass
class Aggregates:
    summaries: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)

def aggregate_from_sources(
    sources: Iterable[Tuple[str, str]],
    start: Optional[dt.datetime],
    end: Optional[dt.datetime],
) -> Aggregates:
    agg = Aggregates()

    for label, text in sources:
        if label != "<stdin>" and not within_range(label, start, end):
            continue

        # 1) JSON blocks (authoritative if present)
        objs = extract_json_blocks(text)
        for obj in objs:
            if "summary" in obj and obj["summary"]:
                agg.summaries.append(str(obj["summary"]).strip())

            dec = obj.get("decisions") or []
            if isinstance(dec, list):
                agg.decisions.extend([str(d).strip() for d in dec if str(d).strip()])

            acts = obj.get("actions") or []
            if isinstance(acts, list):
                for a in acts:
                    if isinstance(a, dict):
                        agg.actions.append(a)

            for section_key, dest in [
                ("risks", agg.risks),
                ("dependencies", agg.dependencies),
                ("open_questions", agg.open_questions),
            ]:
                vals = obj.get(section_key) or []
                if isinstance(vals, list):
                    dest.extend([str(v).strip() for v in vals if str(v).strip()])

        # 2) Heuristics from free text
        heur = extract_heuristics(text)
        agg.risks.extend(heur["risks"])
        agg.dependencies.extend(heur["dependencies"])
        agg.open_questions.extend(heur["open_questions"])

    return agg

def _normalize_owner_key(s: str) -> str:
    # remove non-alphanumerics and uppercase for resilient matching
    return re.sub(r"[^A-Za-z0-9]", "", (s or "")).upper()

def build_payload(
    agg: Aggregates,
    config: Dict[str, Any],
    start: Optional[dt.datetime],
    end: Optional[dt.datetime],
) -> Dict[str, Any]:
    title = coalesce(config.get("title"), "Team Email Digest")
    summary = " ".join(s for s in agg.summaries if s).strip()
    decisions = merge_lists_unique(agg.decisions)
    actions = merge_actions(agg.actions)
    risks = merge_lists_unique(agg.risks)
    deps = merge_lists_unique(agg.dependencies)
    open_qs = merge_lists_unique(agg.open_questions)

    # Case- & punctuation-insensitive owner mapping
    owner_map = config.get("owner_map", {}) if isinstance(config.get("owner_map", {}), dict) else {}
    norm_map = {_normalize_owner_key(k): v for k, v in owner_map.items()}
    if norm_map:
        for a in actions:
            key_norm = _normalize_owner_key(a.get("owner", ""))
            if key_norm in norm_map:
                a["owner"] = norm_map[key_norm]

    # Sort actions
    prio_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, None: 4, "": 4}
    def due_key(d):
        try:
            return dt.datetime.strptime(d, ISO_DATE)
        except Exception:
            return dt.datetime.max

    actions.sort(key=lambda a: (prio_rank.get(a.get("priority"), 4), due_key(a.get("due", "")), a.get("title", "")))

    period = None
    if start or end:
        s = start.strftime(ISO_DATE) if start else "..."
        e = end.strftime(ISO_DATE) if end else "..."
        period = f"{s} to {e}"  # ASCII-safe

    payload: Dict[str, Any] = {
        "title": title,
        "period": period,
        "summary": summary,
        "decisions": decisions,
        "actions": actions,
        "risks": risks,
        "dependencies": deps,
        "open_questions": open_qs,
    }

    return payload


# -------------------------
# CLI
# -------------------------

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Generate a team email digest from logs / JSON blocks.")
    p.add_argument("--from", dest="date_from", type=parse_date, help="Start date (YYYY-MM-DD or ISO datetime).")
    p.add_argument("--to", dest="date_to", type=parse_date, help="End date (YYYY-MM-DD or ISO datetime).")
    p.add_argument("--input", dest="input_path", help="File or directory to scan. If omitted, reads STDIN.")
    p.add_argument("--config", dest="config_path", help="Path to config.yaml/.yml or .json.")
    p.add_argument("--format", dest="fmt", choices=("json", "md", "html"), default="json", help="Output format.")
    p.add_argument("--output", dest="output_path", help="Write to this file. Defaults to stdout.")
    args = p.parse_args(argv)

    try:
        config = load_config(args.config_path) if args.config_path else {}
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}", file=sys.stderr)
        return 2

    sources = list(iter_sources(stdin_ok=True, input_path=args.input_path))
    if not sources:
        print("[WARN] No input detected. Provide --input or pipe logs to STDIN.", file=sys.stderr)

    agg = aggregate_from_sources(sources, start=args.date_from, end=args.date_to)
    payload = build_payload(agg, config=config, start=args.date_from, end=args.date_to)

    if args.fmt == "json":
        out = render_json(payload)
    elif args.fmt == "md":
        out = render_md(payload)
    else:
        out = render_html(payload)

    if args.output_path:
        os.makedirs(os.path.dirname(args.output_path) or ".", exist_ok=True)
        with open(args.output_path, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out)

    return 0


# -------------------------
# Compatibility helpers for test_team_mock.py
# -------------------------

def summarize_email(email_payload: str) -> Dict[str, Any]:
    """
    Parse a single email's text and return a minimal digest dict.
    Prefers embedded JSON blocks with 'summary' / 'decisions' / 'actions'.
    Also merges heuristics to capture blockers/dependencies/questions from free text.
    """
    text = email_payload or ""

    # 1) Try regex-based extraction (normal path)
    objs = extract_json_blocks(text)
    obj = objs[0] if objs else None

    # 2) Fallback: balanced-brace scan if regex failed
    if obj is None:
        obj = _extract_balanced_json(text)

    # Heuristics (always computed and merged)
    heur = extract_heuristics(text)

    if obj is not None:
        return {
            "summary": str(obj.get("summary", "")).strip(),
            "decisions": [str(d).strip() for d in (obj.get("decisions") or []) if str(d).strip()],
            "actions": [normalize_action(a) for a in (obj.get("actions") or []) if isinstance(a, dict)],
            "risks": [str(r).strip() for r in (obj.get("risks") or []) if str(r).strip()] + heur.get("risks", []),
            "dependencies": [str(d).strip() for d in (obj.get("dependencies") or []) if str(d).strip()] + heur.get("dependencies", []),
            "open_questions": [str(q).strip() for q in (obj.get("open_questions") or []) if str(q).strip()] + heur.get("open_questions", []),
        }

    # No JSON → heuristics-only output (plus a naive summary guess)
    lines = [ln.strip() for ln in text.splitlines()]
    body_lines = []
    in_body = False
    for ln in lines:
        if in_body:
            if ln:
                body_lines.append(ln)
        elif ln == "" and not in_body:
            in_body = True  # blank line after headers starts body
    summary = body_lines[0] if body_lines else ""

    return {
        "summary": summary,
        "decisions": [],
        "actions": [],
        "risks": heur.get("risks", []),
        "dependencies": heur.get("dependencies", []),
        "open_questions": heur.get("open_questions", []),
    }

def compose_brief(items: List[Dict[str, Any]]) -> str:
    """Render a compact Markdown brief from per-email items."""
    out = ["# Team Email Brief", ""]
    for it in items or []:
        subject = it.get("subject", "(no subject)")
        out.append(f"## {subject}")
        if it.get("summary"):
            out.append(it["summary"])
        if it.get("decisions"):
            out.append("\n**Decisions**")
            out += [f"- {d}" for d in it["decisions"]]
        if it.get("actions"):
            out.append("\n**Actions**")
            for a in it["actions"]:
                title = a.get("title", "")
                due = f" (due {a.get('due')})" if a.get("due") else ""
                owner = f" - **{a.get('owner')}**" if a.get("owner") else ""
                prio = f" _[{a.get('priority')}]_" if a.get("priority") else ""
                out.append(f"- {title}{owner}{due}{prio}")
        out.append("")
    return "\n".join(out).strip()

def send_to_slack(text: str) -> bool:
    """
    Post the brief to Slack if SLACK_WEBHOOK_URL is set in environment.
    Returns True on success, False otherwise. Safe no-op if not configured.
    """
    url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not url:
        return False
    try:
        import requests  # type: ignore
    except Exception:
        return False
    try:
        resp = requests.post(url, json={"text": text}, timeout=10)
        return 200 <= resp.status_code < 300
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
