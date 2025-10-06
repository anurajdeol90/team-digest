import json
import os
import sys
from pathlib import Path
from subprocess import run, PIPE

from team_email_digest import summarize_email, compose_brief, send_to_slack

PY = sys.executable  # use current Python interpreter

def test_summarize_email_with_json_block():
    email_payload = """
    --- RAW MODEL JSON for: Alpha ---
    {
      "summary": "Alpha budget approved.",
      "decisions": ["Increase Alpha budget by $15k"],
      "actions": [
        {"title": "Update plan for Alpha", "owner": "P", "due": "2025-11-01", "priority": "high"}
      ]
    }
    """
    res = summarize_email(email_payload)
    assert "Alpha budget approved." in res["summary"]
    assert any("Increase Alpha budget" in d for d in res["decisions"])
    assert any(a["title"].startswith("Update plan") for a in res["actions"])

def test_summarize_email_heuristics_without_json():
    email_payload = (
        "Subject: Client needs final draft\nFrom: Client <pm@bigcorp.com>\n\n"
        "Blocker: waiting on external API keys.\n"
        "Open question: Who will handle QA sign-off?\n"
    )
    res = summarize_email(email_payload)
    # No structured JSON, but risks/dependencies/open_questions should be detected
    assert isinstance(res["decisions"], list)
    assert isinstance(res["actions"], list)
    # ✅ needle lowercased to match lowercased haystack
    assert any("waiting on external api keys" in s.lower()
               for s in (res.get("risks", []) + res.get("dependencies", [])))
    assert any("qa sign-off" in s.lower() for s in res.get("open_questions", []))

def test_compose_brief_contains_sections():
    items = [{
        "subject": "Alpha Update",
        "summary": "Alpha budget approved.",
        "decisions": ["Budget increase"],
        "actions": [{"title": "Update plan", "owner": "Priya", "due": "2025-11-01", "priority": "high"}]
    }]
    md = compose_brief(items)
    assert "# Team Email Brief" in md
    assert "Alpha Update" in md
    assert "Update plan" in md

def test_send_to_slack_noop_without_env(monkeypatch):
    # Ensure function becomes a safe no-op if webhook isn't set
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    assert send_to_slack("hello") is False

def test_cli_end_to_end_json(tmp_path: Path):
    """
    Write a sample log + config and call the CLI to produce JSON.
    This validates the full pipeline without touching Slack.
    """
    repo_root = Path.cwd()
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "sample.log").write_text(
        """
        --- RAW MODEL JSON for: Beta ---
        {
          "summary": "Beta scope reduced to hit timeline.",
          "decisions": ["Ship MVP without SSO"],
          "actions": [
            {"title": "Revise roadmap", "owner": "AD", "due": "2025-10-15", "priority": "medium"}
          ]
        }
        Waiting on external team for API limits.
        """,
        encoding="utf-8"
    )

    # Use JSON config so there is no PyYAML dependency needed for this test
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "title": "Weekly Team Digest",
        "owner_map": {"AD": "Anuraj Deol"}
    }), encoding="utf-8")

    cmd = [
        PY, "team_email_digest.py",
        "--config", str(cfg),
        "--from", "2025-10-01",
        "--to", "2025-10-31",
        "--input", str(logs_dir),
        "--format", "json",
    ]
    p = run(cmd, cwd=repo_root, stdout=PIPE, stderr=PIPE, text=True)
    assert p.returncode == 0, f"STDERR:\n{p.stderr}\nSTDOUT:\n{p.stdout}"
    data = json.loads(p.stdout)

    # Basic shape
    for key in ("title", "summary", "decisions", "actions", "risks", "dependencies", "open_questions"):
        assert key in data

    # Owner mapping applied & decisions present
    assert any(a.get("owner") == "Anuraj Deol" for a in data.get("actions", []))
    assert any("Ship MVP without SSO" in d for d in data.get("decisions", []))
