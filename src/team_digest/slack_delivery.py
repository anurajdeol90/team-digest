#!/usr/bin/env python
# Simple Slack webhook helper (text-only; safe default)
from __future__ import annotations
import json, os, urllib.request

def post_markdown(text: str, webhook: str | None = None, *, timeout: int = 20) -> int:
    """
    Posts up to ~39k chars to a Slack incoming webhook.
    Returns HTTP status code (200 on success). Raises on network errors.
    """
    hook = (webhook or os.environ.get("SLACK_WEBHOOK_URL", "")).strip()
    if not hook:
        # No-op if not configured
        return 0
    payload = {"text": text[:39000]}
    req = urllib.request.Request(
        hook,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return int(resp.status)
