# scripts/ci_verify_examples.py
import sys, subprocess, tempfile, os, shlex
from importlib.resources import files, as_file
from contextlib import ExitStack
from importlib import metadata

def run(cmd, check=True):
    print(f"\n$ {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    if check and res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, cmd, res.stdout, res.stderr)
    return res

def resolve_examples_logs():
    es = ExitStack()
    p = files("team_digest").joinpath("examples", "logs")
    fp = es.enter_context(as_file(p))
    # keep ExitStack alive
    resolve_examples_logs._es = es  # type: ignore
    return str(fp)

def main():
    # 1) Version sanity
    dist_ver = metadata.version("team-digest")
    try:
        import team_digest
        mod_ver = getattr(team_digest, "__version__", "0+unknown")
    except Exception as e:
        print("Failed to import team_digest:", e, file=sys.stderr)
        sys.exit(2)

    print(f"dist version: {dist_ver}")
    print(f"module __version__: {mod_ver}")
    if dist_ver != mod_ver:
        print(f"WARNING: version drift (dist={dist_ver}, module={mod_ver})", file=sys.stderr)

    # 2) Ensure packaged examples exist
    logs = resolve_examples_logs()
    print("Packaged examples logs path:", logs)
    if not os.path.isdir(logs):
        print("ERROR: examples/logs not found in installed package", file=sys.stderr)
        sys.exit(3)

    # 3) Run CLI against packaged examples
    tmpdir = tempfile.mkdtemp(prefix="td-ci-")
    daily_out   = os.path.join(tmpdir, "daily.md")
    weekly_out  = os.path.join(tmpdir, "weekly.md")
    monthly_out = os.path.join(tmpdir, "monthly.md")

    # Weekly (supports KPIs/owner breakdown on 1.1.12)
    run(
        f'team-digest weekly --logs-dir "{logs}" '
        f'--start 2025-10-13 --end 2025-10-19 '
        f'--output "{weekly_out}" --group-actions --emit-kpis --owner-breakdown'
    )

    # Daily
    run(
        f'team-digest daily --logs-dir "{logs}" '
        f'--date 2025-10-17 --output "{daily_out}" --group-actions'
    )

    # Monthly (try with KPIs; if not supported, retry without)
    monthly_cmd_with = (
        f'team-digest monthly --logs-dir "{logs}" '
        f'--output "{monthly_out}" --group-actions --emit-kpis --owner-breakdown'
    )
    monthly_cmd_plain = (
        f'team-digest monthly --logs-dir "{logs}" '
        f'--output "{monthly_out}" --group-actions'
    )
    try:
        run(monthly_cmd_with, check=True)
    except subprocess.CalledProcessError as e:
        # If monthly doesn't support --emit-kpis/--owner-breakdown yet, fallback
        if "unrecognized arguments" in (e.stderr or "") or "unrecognized arguments" in (e.stdout or ""):
            print("Monthly flags not supported on this version; retrying without KPI flags...", file=sys.stderr)
            run(monthly_cmd_plain, check=True)
        else:
            raise

    # 4) Basic content assertions
    for path in (daily_out, weekly_out, monthly_out):
        print(f"\n--- Preview {os.path.basename(path)} ---")
        with open(path, "r", encoding="utf-8") as fh:
            txt = fh.read()
        print("\n".join(txt.splitlines()[:40]))
        if "# Team Digest" not in txt:
            print(f"ERROR: {path} missing title", file=sys.stderr)
            sys.exit(4)

    print("\nAll checks passed ✅")

if __name__ == "__main__":
    main()
