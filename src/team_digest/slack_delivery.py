#!/usr/bin/env python
# Simple Slack webhook helper (text-only; safe default)
import json
import os
import urllib.request
from typing import Optional


def post_markdown(
    text: str, webhook: Optional[str] = None, *, timeout: int = 20
) -> int:
    """
    Posts up to ~39k chars to a Slack incoming webhook.
    Returns HTTP status code (200 on success). No-op if webhook missing.
    """
    hook = (webhook or os.environ.get("SLACK_WEBHOOK_URL", "")).strip()
    if not hook:
        return 0
    payload = {"text": text[:39000]}
    req = urllib.request.Request(
        hook,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return int(resp.status)
