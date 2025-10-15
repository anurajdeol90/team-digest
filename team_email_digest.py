#!/usr/bin/env python3
"""
Team Digest Generator

Parses team updates (logs, emails, meeting notes) into structured digests,
and prints JSON (default) or Markdown.

Modes:
- Single file / stdin:
    team-digest [path|-] [--format json|md] [-o OUTPUT]
    python -m team_email_digest [path|-] [--format json|md] [-o OUTPUT]

- Aggregator (directory) mode:
    python -m team_email_digest --config CONFIG.json --from YYYY-MM-DD --to YYYY-MM-DD --input LOGS_DIR --format json

Notes:
- If --config is omitted or the file is missing, defaults are used (no crash).
- --from/--to filter by file modified time (local timezone) when in aggregator mode.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Iterable, Tuple

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

# Bullet formats: -, *, â€¢, "1. ", "(1) ", checkbox "[ ]", "[x]"
BULLET_RE = re.compile(r"^\s*(?:[-*â€¢]\s+|\d+\.\s+|\(\d+\)\s+|\[\s*\]\s+|\[\s*x\s*\]\s+)")

# Loose "KV" action parser: "Title | owner: X | due: 2025-10-08 | priority: high"
ACTION_KV_RE = re.compile(
    r"(?i)^\s*(?P<title>[^|;:\u2014]+?)\s*(?:[|;:â€”-]{1,2}\s*)?"
    r"(?:owner\s*[:\-]\s*(?P<owner>[^|;]+))?\s*(?:[|;]\s*)?"
    r"(?:due\s*[:\-]\s*(?P<due>\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}))?\s*(?:[|;]\s*)?"
    r"(?:priority\s*[:\-]\s*(?P<priority>p?\d|low|medium|high))?\s*$"
)

# Phrases that imply dependencies/risks even without headers
WAITING_PAT = re.compile(r"\b(waiting on|waiting for|blocked by|blocked on)\b", re.I)


# ---------- Noise filtering (keep junk out of digests) ----------

# Lines like "2025-10-06 16:55:28,092 INFO ..." (or WARNING/ERROR)
LOG_NOISE_RE = re.compile(
    r"^\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:[,.:]\d{3})?\s+(INFO|ERROR|WARN(?:ING)?)\b",
    re.I,
)
# Python traceback stack frames like: File "C:\path\weekly_digest.py", line 74, in func
STACK_FRAME_RE = re.compile(r'^\s*File\s+".+",\s+line\s+\d+,\s*(?:in\s+\w+)?', re.I)
# Lines showing CLI usage options in square brackets (snippets from argparse help)
CLI_BRACKETS_RE = re.compile(r'\[--(?:input|config|format|output|from|to|start|end)\b', re.I)
# Traceback code lines like: main(), run_cmd(cmd), md_path = generate_digest_for_range(...)
CODE_LINE_RE = re.compile(
    r'^\s*(?:[A-Za-z_]\w*\s*=\s*)?[A-Za-z_][\w\.]*\s*\([^()]*\)\s*$'
)
# Lines that are just caret pointers ^^^^^
CARET_LINE_RE = re.compile(r'^\s*\^{2,}\s*$')

NOISE_CONTAINS = (
    "weekly window:",
    "running:",
    "digest generated:",
    "posted digest:",
    "generator attempt failed:",
    "done.",
    "traceback (most recent call last):",
    "calledprocesserror",
    "usage: team_email_digest.py",
    "error: unrecognized arguments",
    "slack http error",
    "[stderr]",
    "subprocess.py",
    "subprocess.run(",
)

def _is_noise_line(s: str) -> bool:
    low = s.strip().lower()
    if not low:
        return True
    return (
        bool(LOG_NOISE_RE.match(s)) or
        bool(STACK_FRAME_RE.match(s)) or
        bool(CLI_BRACKETS_RE.search(s)) or
        bool(CODE_LINE_RE.match(s)) or
        bool(CARET_LINE_RE.match(s)) or
        any(k in low for k in NOISE_CONTAINS)
    )


# ---------- Small helpers ----------

def _vprint(enabled: bool, *args, **kwargs) -> None:
    if enabled:
        print(*args, file=sys.stderr, **kwargs)

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
    Parse plain text into canonical sections (lists of strings).
    - Recognizes headers + inline trailing content: "Summary: Foo"
    - Bullets/numbering normalized
    - Text before first header -> Summary
    - Filters out noisy log/trace lines
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
        if not line.strip() or _is_noise_line(line):
            continue

        # Fast-path robust header detection
        low = line.lower().lstrip("#*â€¢ ").strip()
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
            # Standard regex header
            h = _match_header(line)
            if h:
                key, trailing = h
                current = key
                if trailing:
                    content = _norm_space(_strip_bullet(trailing))
                    if content:
                        result[current].append(content)
                continue

            # Not a header, attribute to current (or Summary)
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
    """Human-friendly Markdown. Summary becomes bullets if >1 item, else a single line."""
    def hdr(name: str) -> str:
        return f"## {name}\n"
    def bullets(items: List[str]) -> str:
        return "\n".join(f"- {x}" for x in items) + ("\n" if items else "")

    out: List[str] = []

    out.append(hdr("Summary"))
    summary: List[str] = d.get("summary", []) or []
    if len(summary) <= 1:
        out.append((summary[0] if summary else "â€”") + "\n")
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
        out.append(bullets(items) if items else "â€”\n")

    out.append(hdr("Actions"))
    actions = d.get("actions", []) or []
    if not actions:
        out.append("â€”\n")
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
    """Pull out risks/dependencies/open_questions from free text cues (skips noise lines)."""
    risks: List[str] = []
    deps: List[str] = []
    oqs: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _is_noise_line(line):
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
    - If a JSON block is embedded, parse & normalize it.
    - Otherwise, use header parsing + heuristics (risks/deps/oq).
    """
    data = _extract_json_block(text)
    if data is None:
        d = build_digest(text)
        pulls = _heuristic_pullouts(text)
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


# ---------- CLI helpers ----------

def _read_input(path: str) -> str:
    if path == "-" or path == "":
        return sys.stdin.read()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return p.read_text(encoding="utf-8", errors="ignore")

def _parse_iso_date(s: str) -> Optional[_dt.date]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(s)
    except Exception:
        return None

def _load_config(path: str, *, strict: bool, verbose: bool) -> dict:
    """
    Load JSON or YAML (by extension). If missing and not strict: return defaults.
    If YAML is requested but PyYAML is not installed, warn & return defaults.
    """
    defaults = {"title": "Team Digest", "owner_map": {}}
    if not path:
        _vprint(verbose, "[info] no --config provided; using defaults")
        return defaults

    p = Path(path)
    if not p.exists():
        if strict:
            raise FileNotFoundError(f"Config file not found: {path}")
        _vprint(verbose, f"[warn] config not found: {path} â€” using defaults")
        return defaults

    text = p.read_text(encoding="utf-8")
    ext = p.suffix.lower()
    if ext in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception:
            _vprint(verbose, "[warn] PyYAML not installed; cannot parse YAML. Using defaults.")
            return defaults
        try:
            data = yaml.safe_load(text) or {}
        except Exception as e:
            if strict:
                raise ValueError(f"Invalid YAML in config {path}: {e}") from e
            _vprint(verbose, f"[warn] invalid YAML in {path}: {e} â€” using defaults")
            return defaults
    else:
        try:
            data = json.loads(text) or {}
        except Exception as e:
            if strict:
                raise ValueError(f"Invalid JSON in config {path}: {e}") from e
            _vprint(verbose, f"[warn] invalid JSON in {path}: {e} â€” using defaults")
            return defaults

    # normalize
    cfg = {
        "title": str(data.get("title") or defaults["title"]),
        "owner_map": dict(data.get("owner_map") or {}),
    }
    return cfg

def _iter_text_files(root: Path) -> Iterable[Path]:
    # Deterministic order
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

def _within_range(path: Path, since: Optional[_dt.date], until: Optional[_dt.date]) -> bool:
    if not since and not until:
        return True
    try:
        ts = path.stat().st_mtime
        dt = _dt.datetime.fromtimestamp(ts).date()  # local date
    except Exception:
        return True
    if since and dt < since:
        return False
    if until and dt > until:
        return False
    return True

def _aggregate_from_dir(input_dir: str, cfg: dict, since: Optional[_dt.date], until: Optional[_dt.date], verbose: bool) -> Tuple[dict, int]:
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

    seen_files = 0
    for fp in _iter_text_files(root):
        if not _within_range(fp, since, until):
            _vprint(verbose, f"[skip] {fp} (mtime out of range)")
            continue
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            _vprint(verbose, f"[warn] cannot read {fp}: {e}")
            continue
        d = summarize_email(content)  # JSON blocks & heuristics
        seen_files += 1
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

    return agg, seen_files


# ---------- CLI ----------

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
    parser.add_argument("-o", "--output", default="", help="Output file path (default: stdout)")
    parser.add_argument("--config", default="", help="Path to JSON/YAML config (title, owner_map)")
    parser.add_argument("--from", dest="since", default="", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="until", default="", help="End date (YYYY-MM-DD)")
    parser.add_argument("--input", dest="input_dir", default="", help="Directory of logs/notes (aggregator mode)")
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics to stderr")
    parser.add_argument("--fail-on-empty", action="store_true", help="Exit non-zero if no content found")
    parser.add_argument(
        "--require-config", action="store_true",
        help="If set, missing/invalid --config is an error (default: soft fallback)."
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show version and exit",
    )

    args = parser.parse_args(argv)
    verbose = bool(args.verbose)

    # Aggregator mode
    if args.input_dir:
        cfg = _load_config(args.config, strict=args.require_config, verbose=verbose)
        since = _parse_iso_date(args.since)
        until = _parse_iso_date(args.until)

        agg, seen = _aggregate_from_dir(args.input_dir, cfg, since, until, verbose=verbose)
        if args.format == "json":
            payload = json.dumps(agg, indent=2, ensure_ascii=False)
        else:
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

        # Optional failure on empty
        empty = (seen == 0) or (
            not agg["summary"] and not agg["decisions"] and not agg["risks"]
            and not agg["dependencies"] and not agg["open_questions"] and not agg["actions"]
        )
        if args.fail_on_empty and empty:
            _vprint(verbose, "[fail-on-empty] no content produced")
            return 2
        return 0

    # Single file / stdin mode
    raw = _read_input(args.path)
    digest = build_digest(raw)
    payload = json.dumps(digest, indent=2, ensure_ascii=False) if args.format == "json" else render_markdown(digest)

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
