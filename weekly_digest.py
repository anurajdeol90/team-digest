#!/usr/bin/env python3
"""
Weekly digest runner for CI or local use.

- Computes the previous Monday..Sunday window
- Runs team_email_digest.py to generate a Markdown digest
- Saves to outputs/weekly_YYYY-MM-DD_YYYY-MM-DD.md
- Optionally posts to Slack if SLACK_WEBHOOK_URL is set

Notes:
- We intentionally pass ONLY config.json (if present). This avoids YAML
  parsing surprises in environments where the digest script expects JSON.
- If a logs/ directory exists, we scan that; otherwise we scan the repo root.
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
    """Return previous Monday..Sunday as ISO date strings (YYYY-MM-DD)."""
    if today is None:
        today = dt.date.today()
    # 0=Mon..6=Sun
    dow = today.weekday()
    start = today - dt.timedelta(days=dow + 7)  # previous Monday
    end = start + dt.timedelta(days=6)          # following Sunday
    return start.isoformat(), end.isoformat()


def run_cmd(cmd: list[str], *, cwd: Path | None = None) -> str:
    """Run a command, echo it, capture output, and raise with context on error."""
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
        raise subprocess.CalledProcessError(p.returncode, cmd, p.stdout, p.stderr)
    return p.stdout


def generate_digest_for_range(start_s: str, end_s: str) -> Path:
    """
    Run team_email_digest.py to build the weekly Markdown into outputs/.
    Prefers scanning logs/ if it exists; otherwise scans the repo root.
    """
    OUT.mkdir(parents=True, exist_ok=True)

    # Prefer JSON config; if it doesn't exist, omit --config and use defaults.
    cfg_json = REPO / "config.json"
    cfg_path: Path | None = cfg_json if cfg_json.exists() else None

    # Prefer logs/ as input if present; otherwise use the repo root.
    src_dir = REPO / "logs" if (REPO / "logs").exists() else REPO
    print(f"Input directory: {src_dir}", flush=True)

    md_path = OUT / f"weekly_{start_s}_{end_s}.md"

    cmd = [
        PYEXE,
        str(REPO / "team_email_digest.py"),
        "--from", start_s,
        "--to", end_s,
        "--format", "md",
        "--input", str(src_dir),
        "--output", str(md_path),
    ]
    if cfg_path is not None:
        cmd.extend(["--config", str(cfg_path)])

    run_cmd(cmd, cwd=REPO)
    print(f"Digest generated: {md_path}", flush=True)
    return md_path


def post_with_helper(md_path: Path, title: str) -> None:
    """
    Optional Slack post via post_digest.py if SLACK_WEBHOOK_URL is present.
    If the helper isn't present, we do nothing (no failure in CI).
    """
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook:
        print("No SLACK_WEBHOOK_URL set; skipping Slack post.", flush=True)
        return

    helper = REPO / "post_digest.py"
    if helper.exists():
        cmd = [
            PYEXE, str(helper),
            "--file", str(md_path),
            "--title", title,
        ]
        try:
            run_cmd(cmd, cwd=REPO)
        except subprocess.CalledProcessError as e:
            print("[post_digest] ERROR:", e, flush=True)
    else:
        print("post_digest.py not found; skipping Slack post.", flush=True)


def main() -> None:
    start_s, end_s = ("1900-01-01", "2100-01-01")
    print(f"Weekly window: {start_s} .. {end_s}", flush=True)

    title = f"Weekly Team Digest ({start_s} → {end_s})"
    md_path = generate_digest_for_range(start_s, end_s)
    post_with_helper(md_path, title)


if __name__ == "__main__":
    main()
