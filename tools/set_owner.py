#!/usr/bin/env python3
"""Replace the YOUR-NAME placeholder with your GitHub username (and optional display name).

    python3 tools/set_owner.py YOUR_GITHUB_USERNAME
    python3 tools/set_owner.py YOUR_GITHUB_USERNAME --name "Your Name"

Edits README, docs, CONTRIBUTING, SECURITY, issue templates and .claude-plugin/*.json. Safe to run again.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ["README.md", "THIRD_PARTY.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "LICENSE",
           ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", ".github/ISSUE_TEMPLATE/config.yml"]
TARGETS += sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "docs").glob("*.md"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("username", help="GitHub username or organization")
    ap.add_argument("--name", help="display name for author/owner/license (default: username)")
    a = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", a.username):
        sys.exit("That does not look like a GitHub username (letters, digits, hyphens).")
    display = a.name or a.username
    changed = 0
    for rel in TARGETS:
        p = ROOT / rel
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        # URLs and github paths get the username; everything else gets the display name
        n = re.sub(r"github\.com/(YOUR-NAME|OWNER)", f"github.com/{a.username}", t)
        n = re.sub(r"(?<![A-Za-z0-9/-])OWNER/ship-safe-skills", f"{a.username}/ship-safe-skills", n)
        n = n.replace("YOUR-NAME", display)
        if n != t:
            p.write_text(n, encoding="utf-8")
            changed += 1
            print(f"  updated {rel}")
    print(f"Done: {changed} file(s) changed. Repo URL: https://github.com/{a.username}/ship-safe-skills")


if __name__ == "__main__":
    main()
