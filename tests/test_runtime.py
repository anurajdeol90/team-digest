# tests/test_runtime.py
import datetime as dt
from pathlib import Path
from textwrap import dedent

from team_digest.team_digest_runtime import slice_sections, aggregate_range

def write_log(dirpath: Path, datestr: str, body: str):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / f"notes-{datestr}.md").write_text(body, encoding="utf-8")

def test_slice_sections_basic():
    md = dedent("""\
        ## Summary
        Hello

        ## Decisions
        - Do a thing

        ## Actions
        - [high] Alex to ship feature.

        ## Risks
        - Something might slip.

        ## Dependencies
        - Needs design.

        ## Notes
        - misc
    """)
    secs = slice_sections(md)
    assert "Summary" in secs and "Decisions" in secs and "Actions" in secs
    assert "Risks" in secs and "Dependencies" in secs and "Notes" in secs
    assert "Hello" in secs["Summary"]

def test_aggregate_grouped(tmp_path: Path):
    logs = tmp_path / "logs"
    write_log(logs, "2025-10-13", dedent("""\
        ## Summary
        Day summary.

        ## Actions
        - [high] Priya to review artifact output for accuracy.
        - [medium] Alex to update documentation index.md.
        - [low] Sam to explore customer documentation tools.

        ## Decisions
        - Adopt automated digest workflows.

        ## Risks
        - Slack webhook misconfiguration could block delivery.
    """))
    out = aggregate_range(
        logs_dir=logs,
        start=dt.date(2025, 10, 13),
        end=dt.date(2025, 10, 13),
        title="Team Digest (test)",
        group_actions=True,
        flat_by_name=False,
        emit_kpis=True,
        owner_breakdown=True,
        owner_top=8,
    )
    # Bucket headers present; no duplicated priority tags inside lines
    assert "## Actions" in out and "### High priority" in out
    assert "- [high]" not in out  # bucketed mode strips inline tags
    # KPIs present with counts
    assert "## Executive KPIs" in out
    assert "Actions:" in out and "Decisions:" in out and "Risks:" in out

def test_aggregate_flat_by_name_order(tmp_path: Path):
    logs = tmp_path / "logs"
    write_log(logs, "2025-10-14", dedent("""\
        ## Actions
        - [medium] Priya to prepare slides.
        - [high] Alex to configure Slack channel integration.
        - [low] Sam to capture screenshots.
    """))
    out = aggregate_range(
        logs_dir=logs,
        start=dt.date(2025, 10, 14),
        end=dt.date(2025, 10, 14),
        title="Team Digest (test)",
        group_actions=False,
        flat_by_name=True,  # global sort: name → priority → text
        emit_kpis=False,
        owner_breakdown=False,
    )
    # Expect Alex block before Priya before Sam (alphabetical by owner)
    lines = [l for l in out.splitlines() if l.startswith("- [")]
    assert lines[0].startswith("- [high] Alex")
    assert lines[1].startswith("- [medium] Priya")
    assert lines[2].startswith("- [low] Sam")
