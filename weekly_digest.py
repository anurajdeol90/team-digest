#!/usr/bin/env python3
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import subprocess
from datetime import date, timedelta
from pathlib import Path
import sys

# --- Paths ---
REPO = Path(__file__).resolve().parent
PYTHON = sys.executable  # use the same Python that runs this script
LOG_FILE = REPO / "logs" / "weekly_digest.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
(REPO / "outputs").mkdir(parents=True, exist_ok=True)

# --- Logging (rotating) ---
handler = RotatingFileHandler(LOG_FILE, maxBytes=500_000, backupCount=5, encoding="utf-8")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[handler],
)
log = logging.getLogger("weekly_digest")

def run_cmd(cmd: list[str]) -> None:
    """Run a subprocess command, log stdout/stderr, and raise on non-zero exit."""
    log.info("Running: %s", " ".join(str(c) for c in cmd))
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    if p.stdout:
        log.info("[stdout]\n%s", p.stdout.strip())
    if p.stderr:
        log.info("[stderr]\n%s", p.stderr.strip())
    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, cmd, p.stdout, p.stderr)

def last_week_range() -> tuple[str, str]:
    """Return (start_iso, end_iso) for the last full Monday..Sunday window."""
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.isoformat(), last_sunday.isoformat()

def generate_digest_for_range(start_date: str, end_date: str) -> Path:
    """Generate a digest markdown file for the given date range."""
    out_path = REPO / "outputs" / f"weekly_{start_date}_{end_date}.md"
    cmd = [
        PYTHON,
        str(REPO / "team_email_digest.py"),
        "--from", start_date,
        "--to", end_date,
        "--config", str(REPO / "config.yaml"),
        "--format", "md",
        "--input", str(REPO),
        "--output", str(out_path),
    ]
    run_cmd(cmd)
    log.info("Digest generated: %s", out_path)
    return out_path

def post_with_helper(md_path: Path, title: str) -> None:
    """Post the digest markdown file to Slack using post_digest.py."""
    cmd = [
        PYTHON,
        str(REPO / "post_digest.py"),
        "--file", str(md_path),
        "--title", title,
    ]
    run_cmd(cmd)

def main() -> None:
    start_s, end_s = last_week_range()
    log.info("Weekly window: %s .. %s", start_s, end_s)
    md_path = generate_digest_for_range(start_s, end_s)
    title = f"Weekly Team Digest ({start_s} \u2192 {end_s})"  # → arrow
    post_with_helper(md_path, title)
    log.info("Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("FAILED: %s", e)
        raise
s