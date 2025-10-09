#!/usr/bin/env python3
"""
Weekly digest runner for CI or local use.

- Computes the previous Monday..Sunday window
- Runs team_email_digest.py in aggregator mode to generate a Markdown file
- (Optionally) posts via post_digest.py if SLACK_WEBHOOK_URL is set

This script is CI-safe:
- Ensures outputs/ exists
- Prints full stdout/stderr if a child command fails
"""

from __future__ import annotations

import datetime as dt
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
OUT = REPO / "outputs"
PYEXE = sys.executable


def last_week_window(today: dt.date | None = None) -> tuple[str, str]:
    """
    Return previous Monday..Sunday (ISO date strings).
    If today is Monday, we still return the *previous* week.
    """
    if today is None:
        today = dt.date.today()
    # 0=Mon..6=Sun
    dow = today.weekday()
    start = today - dt.timedelta(days=dow + 7)  # previous Monday
    end = start + dt.timedelta(days=6)          # following Sunday
    return start.isoformat(), end.isoformat()


def run_cmd(cmd: list[str], *, cwd: Path | None = None) -> str:
    """Run a command, echo, capture, and raise with full context on error."""
    print("Running:", " ".join(shlex.quote(c) for c in cmd), flush=True)
    p = subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if p.stdout:
        print("[stdout]\n" + p.stdout, flush=True)
    if p.stderr:
        print("[stderr]\n" + p.stderr, flush=True)
    if p.returncode != 0:
        # Raise with captured output preserved in the exception
        raise subprocess.CalledProcessError(p.returncode, cmd, p.stdout, p.stderr)
    return p.stdout


def generate_digest_for_range(start_s: str, end_s: str) -> Path:
    """Run team_email_digest.py to build the weekly MD into outputs/."""
    OUT.mkdir(parents=True, exist_ok=True)

    # Prefer YAML, fallback to JSON, or omit if neither exists (team_email_digest handles defaults).
    cfg = REPO / "config.yaml"
    if not cfg.exists():
        alt = REPO / "config.json"
        cfg = alt if alt.exists() else None

    md_path = OUT / f"weekly_{start_s}_{end_s}.md"

    cmd = [
        PYEXE,
        str(REPO / "team_email_digest.py"),
        "--from", start_s,
        "--to", end_s,
        "--format", "md",
        "--input", str(REPO),
        "--output", str(md_path),
        "--verbose",
    ]
    if cfg is not None:
        cmd.extend(["--config", str(cfg)])

    run_cmd(cmd, cwd=REPO)
    print(f"Digest generated: {md_path}", flush=True)
    return md_path


def post_with_helper(md_path: Path, title: str) -> None:
    """
    Optional Slack post via post_digest.py if SLACK_WEBHOOK_URL is present.
    If no webhook is set, this is a no-op.
    """
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook:
        print("No SLACK_WEBHOOK_URL set; skipping post.", flush=True)
        return

    helper = REPO / "post_digest.py"
    if helper.exists():
        cmd = [
            PYEXE, str(helper),
            "--file", str(md_path),
            "--title", title,
        ]
        run_cmd(cmd, cwd=REPO)
    else:
        # Fallback inline post if helper is absent
        import json
        import requests  # available in CI per workflow
        text = md_path.read_text(encoding="utf-8")
        payload = {"text": f"*{title}*\n```{text}```"}
        r = requests.post(webhook, json=payload, timeout=10)
        r.raise_for_status()
        print("Posted digest via inline webhook.", flush=True)


def main() -> None:
    start_s, end_s = last_week_window()
    print(f"Weekly window: {start_s} .. {end_s}", flush=True)

    title = f"Weekly Team Digest ({start_s} → {end_s})"
    md_path = generate_digest_for_range(start_s, end_s)

    # Optional Slack post
    try:
        post_with_helper(md_path, title)
    except subprocess.CalledProcessError as e:
        print("[post_digest] ERROR:", e, flush=True)
        # Do not fail the job due to Slack issues
    except Exception as e:
        print("[post_digest] ERROR:", e, flush=True)


if __name__ == "__main__":
    main()
