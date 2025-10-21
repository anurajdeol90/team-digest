import sys, subprocess, tempfile, os
from importlib.resources import files, as_file
from contextlib import ExitStack
from importlib import metadata

def run(cmd):
    print(f"\n$ {cmd}")
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    r.check_returncode()
    return r

def resolve_logs():
    es = ExitStack()
    p = files("team_digest").joinpath("examples", "logs")
    fp = es.enter_context(as_file(p))
    # keep context alive
    resolve_logs.es = es  # type: ignore
    return str(fp)

def main():
    # versions
    dist_ver = metadata.version("team-digest")
    import team_digest
    mod_ver = getattr(team_digest, "__version__", "0+unknown")
    print("dist version:", dist_ver)
    print("module __version__:", mod_ver)
    if dist_ver != mod_ver:
        print(f"WARNING: version drift (dist={dist_ver}, module={mod_ver})", file=sys.stderr)

    logs = resolve_logs()
    if not os.path.isdir(logs):
        print("ERROR: packaged examples/logs not found", file=sys.stderr)
        sys.exit(2)

    tmp = tempfile.mkdtemp(prefix="td-verify-")
    daily   = os.path.join(tmp, "daily.md")
    weekly  = os.path.join(tmp, "weekly.md")
    monthly = os.path.join(tmp, "monthly.md")

    run(f'team-digest weekly --logs-dir "{logs}" --start 2025-10-13 --end 2025-10-19 --output "{weekly}" --group-actions --emit-kpis --owner-breakdown')
    run(f'team-digest daily  --logs-dir "{logs}" --date  2025-10-17 --output "{daily}"  --group-actions')
    run(f'team-digest monthly --logs-dir "{logs}" --output "{monthly}" --group-actions --emit-kpis --owner-breakdown')

    for path in (daily, weekly, monthly):
        print(f"\n--- Preview {os.path.basename(path)} ---")
        with open(path, "r", encoding="utf-8") as fh:
            head = "\n".join(fh.read().splitlines()[:40])
        print(head)
        if "# Team Digest" not in head:
            print(f"ERROR: {path} missing title", file=sys.stderr)
            sys.exit(3)

    print("\nAll checks passed ✅")

if __name__ == "__main__":
    main()
