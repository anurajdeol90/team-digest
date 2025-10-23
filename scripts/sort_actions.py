#!/usr/bin/env python3
import io, re, sys, os


def sort_actions(md_path: str) -> None:
    if not os.path.exists(md_path):
        return
    with io.open(md_path, "r", encoding="utf-8") as f:
        t = f.read()

    # Find the "## Actions" section
    m_start = re.search(r"^##\s*Actions\s*$", t, re.M)
    if not m_start:
        return
    start = m_start.end()
    m_next = re.search(r"^##\s+\S+", t[start:], re.M)
    end = start + (m_next.start() if m_next else len(t) - start)
    block = t[start:end]

    lines = block.splitlines()
    bullets = [ln for ln in lines if re.match(r"^\s*[-*]\s+", ln)]
    others = [ln for ln in lines if ln not in bullets]

    def key(ln: str) -> int:
        s = ln.lower()
        if "[high]" in s:
            return 0
        if "[medium]" in s:
            return 1
        if "[low]" in s:
            return 2
        return 3

    bullets_sorted = sorted(bullets, key=key)
    joined = "\n".join(
        bullets_sorted
        + ([""] if bullets_sorted and (others and others[0].strip()) else [])
        + others
    )

    new_text = t[:start] + "\n" + joined.strip("\n") + "\n" + t[end:]
    with io.open(md_path, "w", encoding="utf-8") as f:
        f.write(new_text)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "outputs/weekly.md"
    sort_actions(path)
