#!/usr/bin/env python
# scripts/post_to_slack.py
import os, sys, io, json, urllib.request


def main():
    if len(sys.argv) != 2:
        print("Usage: post_to_slack.py PATH_TO_MD", file=sys.stderr)
        sys.exit(2)
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook:
        print("No SLACK_WEBHOOK_URL; skipping Slack post.")
        return
    md_path = sys.argv[1]
    text = io.open(md_path, "r", encoding="utf-8").read()
    payload = {"text": text[:39000]}  # Slack guard
    req = urllib.request.Request(
        webhook,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        print("Slack response:", resp.status)


if __name__ == "__main__":
    main()
