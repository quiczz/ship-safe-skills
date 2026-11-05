#!/usr/bin/env python3
"""Build upload-ready zips into ./dist. Stdlib only.

    python3 tools/build_release.py            # version read from .claude-plugin/plugin.json

Creates:
  dist/<skill>.zip                  one per skill, the skill folder at the zip root
                                    (upload in Claude.ai / Claude Desktop: Settings > Capabilities > Skills)
  dist/ship-safe-skills-all-skills-<version>.zip
                                    all skill folders at the root (for unzipping into ~/.claude/skills/)
  dist/SHA256SUMS.txt
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".DS_Store"}
FIXED_TIME = (2020, 1, 1, 0, 0, 0)  # reproducible zips


def files_in(folder):
    for p in sorted(folder.rglob("*")):
        if p.is_file() and not (set(p.relative_to(folder).parts) & SKIP_DIRS) and p.suffix not in SKIP_SUFFIX and p.name != ".DS_Store":
            yield p


def add(z, path, arcname):
    info = zipfile.ZipInfo(arcname, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o755 if path.suffix in {".py", ".sh"} else 0o644
    info.external_attr = (mode | 0o100000) << 16
    z.writestr(info, path.read_bytes())


def main():
    version = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"]
    DIST.mkdir(exist_ok=True)
    for old in DIST.glob("*.zip"):
        old.unlink()
    skills = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
    outputs = []

    for s in skills:
        out = DIST / f"{s.name}.zip"
        with zipfile.ZipFile(out, "w") as z:
            for f in files_in(s):
                add(z, f, f"{s.name}/{f.relative_to(s).as_posix()}")
        outputs.append(out)

    allzip = DIST / f"ship-safe-skills-all-skills-{version}.zip"
    with zipfile.ZipFile(allzip, "w") as z:
        for s in skills:
            for f in files_in(s):
                add(z, f, f"{s.name}/{f.relative_to(s).as_posix()}")
    outputs.append(allzip)

    sums = []
    for o in outputs:
        sums.append(f"{hashlib.sha256(o.read_bytes()).hexdigest()}  {o.name}")
        print(f"  {o.name:55s} {o.stat().st_size/1024:7.1f} KB")
    (DIST / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    print(f"\n{len(outputs)} zips written to {DIST}")


if __name__ == "__main__":
    sys.exit(main())
