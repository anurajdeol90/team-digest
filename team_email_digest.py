#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
team_email_digest.py — Phase 2 final + risk promotion & summary bullets

Key features:
- Extracts ALL JSON blocks with balanced braces.
- Heuristics ignore JSON-like lines and strip JSON blocks before scanning.
- Blockers appear ONLY in Risks (not Dependencies).
- Auto-promotion: risky dependency lines (blocker/blocked/delay/slip/threat/overdue) are ALSO added to Risks.
- Strips redundant prefixes "Risk:", "Dependency:", "Open question:" from bullets.
- De-duplicates case-insensitively while preserving first-seen casing.
- Owner map applied from config (e.g., AD -> Anuraj Deol).
- Auto-save to outputs/digest_<from>_<to>.<fmt> when --output is not provided.
- NEW: Summary bullets rule — 1 item = single line, 2+ items = bullets (MD/HTML). JSON includes both "summary" and "summary_items".
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
    import yaml
    _YAML_AVAILABLE = True
except Exception:
    _YAML_AVAILABLE = False

ISO_DATE = "%Y-%m-%d"
ISO_DATETIME = "%Y-%m-%dT%H:%M:%S"

# -------------------------
# Config / date utils
# -------------------------

def parse_date(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    for fmt in (ISO_DATE, ISO_DATETIME):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        raise argparse.ArgumentTypeError(f"Invalid date: {s!r}")

def within_range(path: str, start: Optional[dt.datetime], end: Optional[dt.datetime]) -> bool:
    if not start and not end:
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
            raise RuntimeError("PyYAML is not installed")
        return yaml.safe_load(text) or {}
    return json.loads(text)

def coalesce(*vals, default=None):
    for v in vals:
        if v is not None:
            return v
    return default

# -------------------------
# Source iterator
# -------------------------

def iter_sources(stdin_ok: bool = False, input_path: Optional[str] = None):
    """Yield (label, text) pairs from stdin, file, or directory."""
    if stdin_ok and not input_path:
        text = sys.stdin.read()
        if text:
            yield "<stdin>", text
        return
    if not input_path:
        return
    if os.path.isfile(input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            yield input_path, f.read()
        return
    if os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for fn in files:
                if fn.lower().endswith((".log", ".txt")):
                    path = os.path.join(root, fn)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            yield path, f.read()
                    except Exception:
                        continue

# -------------------------
# JSON extraction (multi-block)
# -------------------------

def extract_json_blocks(text: str) -> List[Dict[str, Any]]:
    """
    Collect ALL balanced {...} JSON objects in the text that parse successfully
    and contain a 'summary' key.
    """
    results: List[Dict[str, Any]] = []
    s = text or ""
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
                        blob = s[i:j+1]
                        try:
                            obj = json.loads(blob)
                            if isinstance(obj, dict) and any(k.lower() == "summary" for k in obj.keys()):
                                results.append(obj)
                        except Exception:
                            pass
                        i = j  # jump to end of this object
                        break
                j += 1
        i += 1
    return results

# -------------------------
# Heuristics & cleanup
# -------------------------

# Patterns
RISK_TERMS = [
    r"\brisk(s)?\b",
    r"\bblocker(s)?\b",
    r"\bblocked\b",
    r"\bdelay(ed|s|ing)?\b",
    r"\bslip(s|ped|page)?\b",
    r"\bthreat\b",
    r"\boverdue\b",
]
DEPENDENCY_TERMS = [
    r"\bdependenc(y|ies)\b",
    r"\bwaiting on\b",
    r"\bexternal team\b",
    r"\brequires\b",
    r"\bneeds from\b",
    r"\breview needed\b",
]
OPEN_Q_TERMS = [
    r"\bopen question(s)?\b",
    r"\bTBD\b",
    r"\bunknown\b",
    r"\bneed(s)? decision\b",
    r"\bclarify\b",
    r"\?\s*$",
]

LINE_SPLIT_RE = re.compile(r"\r?\n")
_JSONISH_LINE_RE = re.compile(r'^\s*[\{\[]|("\s*:\s*")')

# Prefixes to strip from bullets inside sections
PREFIX_STRIP_RE = re.compile(
    r"^\s*(risk|risks|dependency|dependencies|open\s*question[s]?)\s*:\s*", re.IGNORECASE
)

def _is_jsonish_line(s: str) -> bool:
    return bool(_JSONISH_LINE_RE.search(s))

def _strip_json_blocks(text: str) -> str:
    s = text or ""
    out, depth = [], 0
    for ch in s:
        if ch == "{":
            depth += 1
        if depth == 0:
            out.append(ch)
        if ch == "}":
            depth = max(0, depth - 1)
    return "".join(out)

def _dedupe_casefold(items: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for it in items:
        key = it.casefold().strip()
        if key and key not in seen:
            out.append(it.strip())
            seen.add(key)
    return out

def _strip_prefix(s: str) -> str:
    return PREFIX_STRIP_RE.sub("", s).strip()

def extract_heuristics(text: str) -> Dict[str, List[str]]:
    """
    Extract Risks/Dependencies/Open Questions from *free-text* only.
    - Strips JSON blocks first and skips JSON-ish lines.
    - Blockers go ONLY to Risks (not Dependencies).
    - Promotion: dependency lines that include risky terms are also added to Risks.
    - De-duplicates case-insensitively while preserving first seen casing.
    - Strips redundant prefixes from bullets.
    """
    if not text:
        return {"risks": [], "dependencies": [], "open_questions": []}

    text_wo_json = _strip_json_blocks(text)
    risks, deps, open_qs = [], [], []
    explicit_blocker_found = False

    for ln in LINE_SPLIT_RE.split(text_wo_json):
        ln = ln.strip()
        if not ln or _is_jsonish_line(ln):
            continue
        low = ln.lower()

        # Strip redundant prefixes early
        ln_clean = _strip_prefix(ln)
        low_clean = ln_clean.lower()

        # Blockers: ONLY Risks
        if "blocker" in low_clean or re.search(r"\bblocked\b", low_clean):
            explicit_blocker_found = True
            risks.append(ln_clean)

        # Generic risk terms
        if any(re.search(p, low_clean) for p in RISK_TERMS):
            risks.append(ln_clean)

        # Dependencies (do NOT add blockers here)
        is_dependency_line = ("waiting on" in low_clean) or any(re.search(p, low_clean) for p in DEPENDENCY_TERMS)
        if is_dependency_line and ("blocker" not in low_clean and "blocked" not in low_clean):
            deps.append(ln_clean)
            # Promotion: if dependency contains risky language, also add to Risks
            if any(re.search(p, low_clean) for p in RISK_TERMS):
                risks.append(ln_clean)

        # Open questions
        if any(re.search(p, ln_clean) for p in OPEN_Q_TERMS):
            open_qs.append(ln_clean)

    # Generic blocker only if mentioned but no explicit blocker line was captured
    if "blocker" in text_wo_json.lower() and not explicit_blocker_found:
        risks.append("Blocker detected.")  # only Risks

    return {
        "risks": _dedupe_casefold(risks),
        "dependencies": _dedupe_casefold(deps),
        "open_questions": _dedupe_casefold(open_qs),
    }

# -------------------------
# Aggregation / normalization
# -------------------------

@dataclass
class Aggregates:
    summaries: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)

def normalize_action(a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": a.get("title", "").strip(),
        "owner": a.get("owner", "").strip(),
        "due": a.get("due", "").strip(),
        "priority": a.get("priority", "").strip().lower() or None,
    }

def merge_actions(actions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for a in actions:
        na = normalize_action(a)
        key = (na["title"], na["owner"], na["due"])
        if na["title"] and key not in seen:
            out.append(na); seen.add(key)
    return out

# -------------------------
# Rendering
# -------------------------

def render_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)

def render_md(payload: Dict[str, Any]) -> str:
    lines = [f"# {payload.get('title','Team Email Digest')} - {payload.get('period','')}"]

    # Summary: 1 item -> single line; 2+ -> bullets
    summary_items = payload.get("summary_items", [])
    if summary_items:
        lines += ["", "## Summary"]
        if len(summary_items) == 1:
            lines.append(summary_items[0])
        else:
            lines += [f"- {s}" for s in summary_items]
    elif payload.get("summary"):  # fallback for safety
        lines += ["", "## Summary", payload["summary"]]

    if payload.get("decisions"):
        lines += ["", "## Decisions"] + [f"- {d}" for d in payload["decisions"]]
    if payload.get("actions"):
        lines += ["", "## Actions"]
        for a in payload["actions"]:
            due = f" (due {a['due']})" if a.get("due") else ""
            owner = f" - **{a['owner']}**" if a.get("owner") else ""
            prio = f" _[{a['priority']}]_" if a.get("priority") else ""
            lines.append(f"- {a['title']}{owner}{due}{prio}")
    if payload.get("risks"):
        lines += ["", "## Risks"] + [f"- {r}" for r in payload["risks"]]
    if payload.get("dependencies"):
        lines += ["", "## Dependencies"] + [f"- {d}" for d in payload["dependencies"]]
    if payload.get("open_questions"):
        lines += ["", "## Open Questions"] + [f"- {q}" for q in payload["open_questions"]]
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

    # Summary: 1 item -> single paragraph; 2+ -> bullets
    summary_items = payload.get("summary_items", [])
    if summary_items:
        parts.append("<h2>Summary</h2>")
        if len(summary_items) == 1:
            parts.append(f"<p>{esc(summary_items[0])}</p>")
        else:
            parts.append("<ul>")
            for s in summary_items:
                parts.append(f"<li>{esc(s)}</li>")
            parts.append("</ul>")
    elif payload.get("summary"):
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
# Build digest
# -------------------------

@dataclass
class Aggregates:
    summaries: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)

def aggregate_from_sources(sources: Iterable[Tuple[str,str]], start, end) -> Aggregates:
    agg = Aggregates()
    for label,text in sources:
        if label != "<stdin>" and not within_range(label,start,end):
            continue
        # JSON blocks (authoritative)
        objs = extract_json_blocks(text)
        for obj in objs:
            if obj.get("summary"): agg.summaries.append(str(obj["summary"]).strip())
            agg.decisions += [str(d).strip() for d in obj.get("decisions", []) if str(d).strip()]
            agg.actions += [a for a in obj.get("actions", []) if isinstance(a, dict)]
            agg.risks += [str(x).strip() for x in obj.get("risks", []) if str(x).strip()]
            agg.dependencies += [str(x).strip() for x in obj.get("dependencies", []) if str(x).strip()]
            agg.open_questions += [str(x).strip() for x in obj.get("open_questions", []) if str(x).strip()]
        # Heuristics from free text
        heur = extract_heuristics(text)
        agg.risks += heur["risks"]
        agg.dependencies += heur["dependencies"]
        agg.open_questions += heur["open_questions"]
    return agg

def build_payload(agg: Aggregates, config: Dict[str,Any], start, end) -> Dict[str,Any]:
    title = config.get("title","Team Email Digest")

    # Build summary_items (list) and a fallback "summary" string for JSON compatibility
    summary_items = [s for s in agg.summaries if s]
    # (Optional) Bold project names in summary items — tweak as needed
    for i, s in enumerate(summary_items):
        for proj in ("Alpha", "Beta", "Gamma"):
            s = s.replace(proj, f"**{proj}**")
        summary_items[i] = s
    summary = " ".join(summary_items).strip()

    decisions = _dedupe_casefold(agg.decisions)
    actions = merge_actions(agg.actions)
    risks = _dedupe_casefold(agg.risks)
    deps = _dedupe_casefold(agg.dependencies)
    open_qs = _dedupe_casefold(agg.open_questions)

    # Owner mapping
    owner_map = config.get("owner_map",{}) if isinstance(config.get("owner_map",{}),dict) else {}
    for a in actions:
        if a["owner"] in owner_map:
            a["owner"] = owner_map[a["owner"]]

    period = f"{start.strftime(ISO_DATE) if start else '...'} to {end.strftime(ISO_DATE) if end else '...'}" if start or end else None

    return {
        "title": title,
        "period": period,
        "summary": summary,               # keep for JSON compatibility
        "summary_items": summary_items,   # used by MD/HTML to decide bullets vs single line
        "decisions": decisions,
        "actions": actions,
        "risks": risks,
        "dependencies": deps,
        "open_questions": open_qs
    }

# -------------------------
# CLI
# -------------------------

def main(argv: Optional[List[str]]=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="date_from", type=parse_date)
    p.add_argument("--to", dest="date_to", type=parse_date)
    p.add_argument("--input", dest="input_path")
    p.add_argument("--config", dest="config_path")
    p.add_argument("--format", dest="fmt", choices=("json","md","html"), default="json")
    p.add_argument("--output", dest="output_path")
    args = p.parse_args(argv)

    try:
        config = load_config(args.config_path) if args.config_path else {}
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}", file=sys.stderr); return 2

    sources = list(iter_sources(stdin_ok=True,input_path=args.input_path))
    if not sources:
        print("[WARN] No input detected. Provide --input or pipe logs to STDIN.", file=sys.stderr)

    agg = aggregate_from_sources(sources,args.date_from,args.date_to)
    payload = build_payload(agg,config,args.date_from,args.date_to)

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
        os.makedirs("outputs", exist_ok=True)
        start_str = args.date_from.strftime(ISO_DATE) if args.date_from else "..."
        end_str = args.date_to.strftime(ISO_DATE) if args.date_to else "..."
        ext = args.fmt
        fname = f"outputs/digest_{start_str}_{end_str}.{ext}"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"[INFO] Digest written to {fname}")

    return 0

# -------------------------
# Test helpers
# -------------------------

def summarize_email(email_payload: str) -> Dict[str,Any]:
    objs = extract_json_blocks(email_payload)
    obj = objs[0] if objs else None
    heur = extract_heuristics(email_payload)
    if obj:
        return {
            "summary": obj.get("summary",""),
            "decisions": _dedupe_casefold(obj.get("decisions",[])),
            "actions": [normalize_action(a) for a in obj.get("actions",[])],
            "risks": heur["risks"],
            "dependencies": heur["dependencies"],
            "open_questions": heur["open_questions"],
        }
    return {
        "summary": "",
        "decisions": [],
        "actions": [],
        "risks": heur["risks"],
        "dependencies": heur["dependencies"],
        "open_questions": heur["open_questions"],
    }

def compose_brief(items: List[Dict[str,Any]]) -> str:
    out=["# Team Email Brief",""]
    for it in items:
        out.append(f"## {it.get('subject','(no subject)')}")
        if it.get("summary"): out.append(it["summary"])
    return "\n".join(out)

def send_to_slack(text: str) -> bool:
    url=os.getenv("SLACK_WEBHOOK_URL","")
    if not url: return False
    try:
        import requests
        resp=requests.post(url,json={"text":text},timeout=10)
        return 200<=resp.status_code<300
    except Exception:
        return False

if __name__=="__main__":
    raise SystemExit(main())
