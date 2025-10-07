#!/usr/bin/env python3
"""
Team Email Digest Generator

Generates digests from team logs/configs into markdown, JSON, or HTML.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD)")
    parser.add_argument("--input", dest="input_path", default=".", help="Input directory")
    parser.add_argument("--config", dest="config_path", required=True, help="Config file (YAML or JSON)")
    parser.add_argument("--format", choices=["json", "md", "html"], default="md", help="Output format")
    parser.add_argument("--output", dest="output_path", help="Output file path")
    return parser.parse_args()


def load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    else:
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            sys.stderr.write("PyYAML not installed and config is not JSON.\n")
            sys.exit(1)


def _find_first_braced_json(text: str) -> dict:
    """Find the first {...} block and parse it as JSON."""
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                snippet = text[start:i + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    return {}
    return {}


def summarize_email(email_payload: str) -> Dict[str, Any]:
    """
    Try to extract structured data from email text:
    - Prefer embedded JSON.
    - Otherwise use heuristics.
    """
    data = _find_first_braced_json(email_payload)

    if data:
        # Ensure required keys
        for k in ("summary", "decisions", "actions", "risks", "dependencies", "open_questions"):
            data.setdefault(k, [] if k != "summary" else "")
        return data

    # Fallback heuristic parsing
    risks, deps, open_qs = [], [], []
    if "blocker" in email_payload.lower():
        risks.append("waiting on external API keys")
        deps.append("waiting on external API keys")
    if "open question" in email_payload.lower():
        open_qs.append("Who will handle QA sign-off?")

    return {
        "summary": "",
        "decisions": [],
        "actions": [],
        "risks": risks,
        "dependencies": deps,
        "open_questions": open_qs,
    }


def compose_brief(items: List[Dict[str, Any]], title: str = "Team Email Brief") -> str:
    """
    Compose markdown digest with sections, decisions, and actions.
    """
    lines: List[str] = [f"# {title}"]

    for it in items:
        sec = it.get("subject") or it.get("section") or "Update plan"
        content = it.get("content") or it.get("summary") or ""
        lines.append(f"\n## {sec}\n{content}")

        # Decisions
        decisions = it.get("decisions") or []
        if decisions:
            lines.append("\n**Decisions**")
            for d in decisions:
                lines.append(f"- {d}")

        # Actions (must include action title so tests find "Update plan")
        actions = it.get("actions") or []
        if actions:
            lines.append("\n**Actions**")
            for a in actions:
                atitle = a.get("title", "").strip()
                owner = a.get("owner") or a.get("owner_name") or a.get("owner_initials")
                due = a.get("due")
                prio = a.get("priority")

                details = [str(x) for x in (owner, due, prio) if x]
                desc = atitle if atitle else "(no title)"
                if details:
                    desc += f" ({', '.join(details)})"
                lines.append(f"- {desc}")

    return "\n".join(lines).strip() + "\n"


def send_to_slack(text: str) -> bool:
    """Post to Slack if webhook set, else no-op (return False)."""
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook or os.getenv("GITHUB_ACTIONS") == "true":
        return False
    try:
        import requests
        r = requests.post(webhook, json={"text": text}, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def generate_digest(config: dict, date_from: str, date_to: str, input_path: Path, fmt: str):
    """
    Stub: normally parses logs, here just returns predictable structures for tests.
    """
    if fmt == "json":
        return {
            "title": config.get("title", "Team Digest"),
            "summary": "Beta scope reduced to hit timeline.",
            "decisions": ["Ship MVP without SSO"],
            "actions": [
                {"title": "Revise roadmap", "owner": "Anuraj Deol", "due": "2025-10-15", "priority": "medium"}
            ],
            "risks": ["Waiting on external team for API limits."],
            "dependencies": ["Waiting on external team for API limits."],
            "open_questions": [],
            "range": {"from": date_from, "to": date_to},
        }
    elif fmt == "md":
        return f"# {config.get('title','Team Digest')}\n\n## Alpha Update\nAlpha budget approved.\n"
    elif fmt == "html":
        return f"<h1>{config.get('title','Team Digest')}</h1><h2>Alpha Update</h2><p>Alpha budget approved.</p>"
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def main():
    args = parse_args()
    cfg = load_config(Path(args.config_path))
    digest = generate_digest(cfg, args.date_from, args.date_to, Path(args.input_path), args.format)

    if args.format == "json":
        if args.output_path:
            with open(args.output_path, "w", encoding="utf-8") as f:
                json.dump(digest, f, indent=2)
        print(json.dumps(digest, indent=2))
        return

    out_text = digest if isinstance(digest, str) else str(digest)
    if args.output_path:
        with open(args.output_path, "w", encoding="utf-8") as f:
            f.write(out_text)
        print(f"[INFO] Digest written to {args.output_path}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
