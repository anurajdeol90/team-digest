#!/usr/bin/env python3
# post_digest.py
"""
Posts a markdown digest to Slack via Incoming Webhook.
- Reads SLACK_WEBHOOK_URL from env
- Can post a specific file or the newest .md in outputs\
- Splits long posts into safe chunks
- Has a --test mode to quickly verify the webhook
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import glob
from pathlib import Path
from datetime import datetime
from urllib import request, error

REPO = Path(__file__).resolve().parent
OUTPUTS = REPO / "outputs"
MAX_CHARS = 35000  # conservative chunking for Slack webhook payloads

def read_env_webhook() -> str:
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        raise RuntimeError("SLACK_WEBHOOK_URL environment variable is not set.")
    if not url.startswith("https://hooks.slack.com/services/"):
        raise RuntimeError("SLACK_WEBHOOK_URL doesn't look like a Slack Incoming Webhook URL.")
    return url

def post_to_slack(webhook_url: str, text: str) -> None:
    payload = {"text": text}
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace").strip()
            if resp.status < 200 or resp.status >= 300:
                raise RuntimeError(f"Slack responded with HTTP {resp.status}: {body}")
    except error.HTTPError as e:
        raise RuntimeError(f"Slack HTTP error: {e.code} {e.reason}") from e
    except error.URLError as e:
        raise RuntimeError(f"Slack connection error: {e.reason}") from e

def chunk_text(md: str, limit: int = MAX_CHARS) -> list[str]:
    if len(md) <= limit:
        return [md]
    parts = []
    buf = []
    running = 0
    for para in md.split("\n\n"):
        p = (para + "\n\n")
        if running + len(p) > limit and buf:
            parts.append("".join(buf).rstrip())
            buf, running = [p], len(p)
        else:
            buf.append(p)
            running += len(p)
    if buf:
        parts.append("".join(buf).rstrip())
    return parts

def newest_md_in_outputs() -> Path:
    files = sorted(OUTPUTS.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No .md files found in {OUTPUTS}")
    return files[0]

def load_markdown(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()

def post_markdown_file(path: Path, webhook_url: str, title: str | None = None) -> None:
    md = load_markdown(path)
    header = f"*{title.strip()}*\n" if title else ""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    preface = f"{header}```{path.name}```\n_Posted {ts}_\n\n"
    chunks = chunk_text(md)
    # Send preface as first message
    post_to_slack(webhook_url, preface + "```" + chunks[0] + "```")
    # Any remaining chunks
    for i, chunk in enumerate(chunks[1:], start=2):
        post_to_slack(webhook_url, f"(part {i}) of `{path.name}`\n```{chunk}```")

def main():
    ap = argparse.ArgumentParser(description="Post team digest markdown to Slack via webhook.")
    ap.add_argument("--file", type=str, help="Path to a specific markdown file to post.")
    ap.add_argument("--title", type=str, help="Optional title to show above the digest.")
    ap.add_argument("--test", type=str, help="Send a small test message (ignores --file).")
    args = ap.parse_args()

    webhook = read_env_webhook()

    if args.test:
        post_to_slack(webhook, f"🔔 Test: {args.test}")
        print("Posted test message to Slack.")
        return

    if args.file:
        path = Path(args.file).expanduser().resolve()
    else:
        path = newest_md_in_outputs()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    post_markdown_file(path, webhook, title=args.title)
    print(f"Posted digest: {path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[post_digest] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
