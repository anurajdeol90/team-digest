from team_email_digest import build_digest, render_markdown

SAMPLE = """Summary: Alpha budget approved
Decisions:
- Increase budget by $15k
Actions:
- Update plan | owner: Priya | due: 11/01/2023 | priority: high
"""

def test_build_digest_basic():
    d = build_digest(SAMPLE)
    assert "Alpha budget approved" in d["summary"][0]
    assert d["decisions"] == ["Increase budget by $15k"]
    a = d["actions"][0]
    assert a["owner"] == "Priya" and a["due"] == "2023-11-01" and a["priority"] == "high"

def test_markdown_renders():
    md = render_markdown(build_digest(SAMPLE))
    assert "## Summary" in md and "## Actions" in md
