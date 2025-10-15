import subprocess, sys

def test_cli_version():
    out = subprocess.check_output([sys.executable, "-m", "team_email_digest", "-V"]).decode()
    assert "team-digest" in out and any(ch.isdigit() for ch in out)

def test_cli_runs_md_stub():
    out = subprocess.check_output([sys.executable, "-m", "team_email_digest", "--format", "md"]).decode()
    assert "# Team Digest" in out
