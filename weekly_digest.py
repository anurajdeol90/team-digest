#!/usr/bin/env python3
"""
Weekly digest runner for CI or local use.

Key improvement:
- Preselects last week's logs into a temp folder by matching an ISO date
  in the filename (YYYY-MM-DD-...) OR as the first non-empty line of the file.
  Then runs team_email_digest.py against ONLY those files.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional

REPO = Path(__file__).resolve().parent
LOGS = REPO / "logs"
OUT = REPO / "outputs"
TMP = REPO / ".weekly_inputs"
PYEXE = sys.executable

DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def last_week_window(today: Optional[dt.date] = None) -> tuple[str, str]:
    """Return previous Monday..Sunday as ISO strings (YYYY-MM-DD)."""
    if today is None:
        today = dt.date.today()
    dow = today.weekday()                 # 0=Mon..6=Sun
    start = today - dt.timedelta(days=dow + 7)  # previous Monday
    end = start + dt.timedelta(days=6)
    return start.isoformat(), end.isoformat()


def run_cmd(cmd: List[str], *, cwd: Optional[Path] = None) -> str:
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
        raise subprocess.CalledProcessError(p.returncode, cmd, p.stdout, p.stderr)
    return p.stdout


def parse_iso_date(s: str) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None


def date_in_window(d: dt.date, start: dt.date, end: dt.date) -> bool:
    return start <= d <= end


def first_nonempty_line(path: Path, max_chars: int = 4096) -> str:
    try:
        chunk = path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        for line in chunk.splitlines():
            if line.strip():
                return line.strip()
    except Exception:
        pass
    return ""


def should_include_file(path: Path, start_s: str, end_s: str) -> bool:
    """
    Heuristic to decide if a file belongs to last week's window:
    - If filename contains YYYY-MM-DD, use that.
    - Else if the first non-empty line contains YYYY-MM-DD, use that.
    - Else: exclude (we keep the weekly run precise).
    """
    start_d = dt.date.fromisoformat(start_s)
    end_d = dt.date.fromisoformat(end_s)

    m = DATE_RE.search(path.name)
    if m:
        d = parse_iso_date(m.group(1))
        if d and date_in_window(d, start_d, end_d):
            return True

    header = first_nonempty_line(path)
    m2 = DATE_RE.search(header)
    if m2:
        d2 = parse_iso_date(m2.group(1))
        if d2 and date_in_window(d2, start_d, end_d):
            return True

    return False


def collect_last_week_inputs(start_s: str, end_s: str) -> int:
    """
    Create TMP folder containing only files that match the last-week window.
    Returns the number of files copied.
    """
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)

    base = LOGS if LOGS.exists() else REPO
    candidates: Iterable[Path] = (p for p in base.rglob("*") if p.is_file())

    copied = 0
    for p in candidates:
        # Consider only text-like files
        if p.suffix.lower() not in {".md", ".txt", ".log", ".rst"}:
            continue
        if should_include_file(p, start_s, end_s):
            shutil.copy2(p, TMP / p.name)
            copied += 1

    print(f"Selected {copied} file(s) into {TMP}", flush=True)
    return copied


def generate_digest_for_range(start_s: str, end_s: str) -> Path:
    """
    Run team_email_digest.py on the curated TMP inputs to build the weekly MD.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    md_path = OUT / f"weekly_{start_s}_{end_s}.md"

    # Prefer JSON config; if absent, omit --config and use defaults.
    cfg_json = REPO / "config.json"
    cfg_arg: List[str] = ["--config", str(cfg_json)] if cfg_json.exists() else []

    # Ensure we have inputs for the week
    selected = collect_last_week_inputs(start_s, end_s)
    if selected == 0:
        # Still generate a minimal file so the workflow succeeds
        md_path.write_text(
            f"# Team Email Brief\n## Weekly Team Digest\n\n"
            f"_No notes found for {start_s}..{end_s}_\n",
            encoding="utf-8",
        )
        print(f"No inputs; wrote placeholder digest: {md_path}", flush=True)
        return md_path

    cmd = [
        PYEXE,
        str(REPO / "team_email_digest.py"),
        "--from", start_s,
        "--to", end_s,
        "--format", "md",
        "--input", str(TMP),
        "--output", str(md_path),
        *cfg_arg,
    ]
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
        try:
            run_cmd([PYEXE, str(helper), "--file", str(md_path), "--title", title], cwd=REPO)
        except subprocess.CalledProcessError as e:
            print("[post_digest] ERROR:", e, flush=True)
    else:
        print("post_digest.py not found; skipping Slack post.", flush=True)


def main() -> None:
    start_s, end_s = last_week_window()
    print(f"Weekly window: {start_s} .. {end_s}", flush=True)
    title = f"Weekly Team Digest ({start_s} → {end_s})"
    md_path = generate_digest_for_range(start_s, end_s)
    post_with_helper(md_path, title)


if __name__ == "__main__":
    main()
