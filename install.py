#!/usr/bin/env python3
"""Installer for the Claude skills pack (Python 3.8+, standard library only).

  python3 install.py list
  python3 install.py install --all                 # everything, into ~/.claude/skills
  python3 install.py install rea hallmark          # only some
  python3 install.py install --own                 # only the skills written in this repo
  python3 install.py install --all --project       # into ./.claude/skills of the current project
  python3 install.py install --all --latest        # newest upstream instead of the reviewed commit
  python3 install.py install --all --with-mcp      # also run `claude mcp add` for MCP servers
  python3 install.py uninstall hallmark
  python3 install.py autopilot on|off|status       # let the skills run on their own (Claude Code hooks)

Third-party skills are downloaded from the authors' GitHub repos (git is required).
Skills are instructions the AI follows with your permissions: read what you install.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "skills.json").read_text(encoding="utf-8"))
SKIP_NAMES = {".git", "node_modules", ".DS_Store", "__pycache__"}


def dest_dir(project: bool) -> Path:
    base = Path.cwd() if project else Path.home()
    return base / ".claude" / "skills"


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def copy_skill(src: Path, dst: Path):
    """Copy a skill folder, following symlinks and skipping VCS/build junk."""
    if dst.exists():
        shutil.rmtree(dst)

    def ignore(_dir, names):
        return [n for n in names if n in SKIP_NAMES]

    shutil.copytree(src, dst, symlinks=False, ignore=ignore)


RECORD = ".skillpack-installed.json"


def record(dest: Path, key: str, folders):
    f = dest / RECORD
    try:
        data = json.loads(f.read_text())
    except Exception:
        data = {}
    data[key] = sorted(set(folders))
    f.write_text(json.dumps(data, indent=2))


def has_skill_md(p: Path) -> bool:
    return p.is_dir() and any(c.name.lower() == "skill.md" for c in p.iterdir())


def fetch(repo: str, sha, latest: bool, workdir: Path) -> Path:
    url = f"https://github.com/{repo}.git"
    target = workdir / repo.replace("/", "__")
    if latest or not sha:
        run(["git", "clone", "--depth", "1", "-q", url, str(target)])
    else:
        target.mkdir(parents=True)
        run(["git", "init", "-q"], cwd=target)
        run(["git", "remote", "add", "origin", url], cwd=target)
        try:
            run(["git", "fetch", "--depth", "1", "-q", "origin", sha], cwd=target)
            run(["git", "checkout", "-q", "FETCH_HEAD"], cwd=target)
        except subprocess.CalledProcessError:
            print(f"   ! could not fetch pinned commit {sha[:10]}; falling back to newest default branch")
            shutil.rmtree(target)
            run(["git", "clone", "--depth", "1", "-q", url, str(target)])
    return target


def install_own(names, dest: Path):
    for name in names:
        src = ROOT / "skills" / name
        if not src.exists():
            print(f"   ! missing own skill folder: {src}")
            continue
        copy_skill(src, dest / name)
        record(dest, name, [name])
        print(f"   + {name}  ->  {dest / name}")


def install_upstream(entry, dest: Path, latest: bool):
    print(f"\n[{entry['id']}] {entry['title']}")
    print(f"   source: https://github.com/{entry['repo']}  license: {entry.get('license', '?')}")
    with tempfile.TemporaryDirectory(prefix="skillpack-") as tmp:
        try:
            repo_dir = fetch(entry["repo"], entry.get("pinned"), latest, Path(tmp))
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            out = getattr(e, "stdout", "") or str(e)
            print(f"   ! download failed: {out.strip()[:300]}")
            return False

        if entry.get("kind") == "corpus":
            skill_dst = dest / entry["id"]
            copy_skill(ROOT / entry["wrapper"], skill_dst)
            corpus_src = repo_dir / entry["corpus_path"]
            shutil.copytree(corpus_src, skill_dst / entry["corpus_path"], ignore=lambda d, n: [x for x in n if x in SKIP_NAMES])
            for lic in repo_dir.glob("LICENSE*"):
                shutil.copy(lic, skill_dst / "UPSTREAM_LICENSE")
                break
            count = len(list((skill_dst / entry["corpus_path"]).glob("*/DESIGN.md")))
            print(f"   + {entry['id']} (wrapper + {count} DESIGN.md files)  ->  {skill_dst}")
            record(dest, entry["id"], [entry["id"]])
            return True

        found = []
        for pattern in entry["paths"]:
            matches = sorted(repo_dir.glob(pattern)) if any(c in pattern for c in "*?[") else [repo_dir / pattern]
            for m in matches:
                if has_skill_md(m):
                    found.append(m)
        if not found:
            print("   ! no SKILL.md found at the expected paths (upstream layout may have changed)")
            return False
        for src in found:
            copy_skill(src, dest / src.name)
            print(f"   + {src.name}  ->  {dest / src.name}")
        record(dest, entry["id"], [src.name for src in found])
        if entry.get("note"):
            print(f"   note: {entry['note']}")
        return True


def install_mcp(entry, with_mcp: bool):
    cmd = entry["claude_command"]
    print(f"\n[{entry['id']}] {entry['title']}  (MCP server, not a skill)")
    print(f"   note: {entry['note']}")
    if with_mcp and shutil.which("claude"):
        try:
            out = run(cmd).stdout.strip()
            print(f"   + registered: {out[:200]}")
        except subprocess.CalledProcessError as e:
            print(f"   ! claude mcp add failed: {e.stdout.strip()[:300]}")
    else:
        why = "claude CLI not found" if with_mcp else "run with --with-mcp to do it automatically"
        print(f"   to register ({why}):  {' '.join(cmd)}")


# ---------------------------------------------------------------- autopilot (Claude Code hooks)

HOOK_MARK = "ship-safe-skills/autopilot.py"
HOOK_EVENTS = [  # (event, matcher, argument, timeout seconds)
    ("SessionStart", None, "session-start", 10),
    ("UserPromptSubmit", None, "prompt", 5),
    ("PostToolUse", "Write|Edit|MultiEdit", "post-edit", 10),
    ("PreCompact", None, "session-end", 30),
    ("SessionEnd", None, "session-end", 30),
]


def autopilot_paths(project: bool):
    base = Path.cwd() if project else Path.home()
    # Project scope uses settings.local.json: it holds a path on this machine, so it must not be committed.
    settings = base / ".claude" / ("settings.local.json" if project else "settings.json")
    return settings, base / ".claude" / "ship-safe-skills" / "autopilot.py"


def _is_ours(group) -> bool:
    return any(HOOK_MARK in h.get("command", "") for h in group.get("hooks", []))


def _load_settings(path: Path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as e:
        sys.exit(f"{path} is not valid JSON ({e}). Fix it first; nothing was changed.")
    if not isinstance(data, dict):
        sys.exit(f"{path} is not a JSON object. Nothing was changed.")
    return data


def autopilot_on(project: bool) -> int:
    settings_path, script = autopilot_paths(project)
    if not shutil.which("python3") and sys.platform != "win32":
        print("Warning: python3 was not found on PATH; the hooks call python3.")
    src = ROOT / "hooks" / "autopilot.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, script)
    script.chmod(0o755)
    settings = _load_settings(settings_path)
    backup = settings_path.with_name(settings_path.name + ".ship-safe-backup")
    if settings_path.exists() and not backup.exists():
        shutil.copy2(settings_path, backup)
    hooks = settings.setdefault("hooks", {})
    for event, matcher, arg, timeout in HOOK_EVENTS:
        groups = [g for g in hooks.get(event, []) if not _is_ours(g)]
        # On Windows "python3" is usually missing or a Microsoft Store stub, so use the interpreter running this installer.
        py = f'"{sys.executable}"' if sys.platform == "win32" else "python3"
        group = {"hooks": [{"type": "command", "command": f'{py} "{script}" {arg}', "timeout": timeout}]}
        if matcher:
            group = {"matcher": matcher, **group}
        groups.append(group)
        hooks[event] = groups
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"Autopilot ON  ->  {settings_path}")
    print(f"  script: {script}")
    if backup.exists():
        print(f"  your previous settings were saved to {backup.name}")
    print("What it does by itself: standing instructions at session start, a skill hint when your request matches,")
    print("a secret/risk check on every file Claude edits, and the masked session transcript saved to .claude/journal/.")
    print(f"Switch parts off:  python3 \"{script}\" off all|context|hints|secrets|journal")
    print("Use ONE of: this, or the plugin install. Both together would run every check twice.")
    print("Restart Claude Code to apply.")
    return 0


def autopilot_off(project: bool) -> int:
    settings_path, script = autopilot_paths(project)
    if settings_path.exists():
        settings = _load_settings(settings_path)
        hooks = settings.get("hooks", {})
        for event in list(hooks):
            hooks[event] = [g for g in hooks[event] if not _is_ours(g)]
            if not hooks[event]:
                del hooks[event]
        if not hooks:
            settings.pop("hooks", None)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    if script.exists():
        script.unlink()
    print(f"Autopilot OFF  ({settings_path}). Your other settings were left as they were.")
    return 0


def autopilot_status(project: bool) -> int:
    settings_path, script = autopilot_paths(project)
    on = False
    if settings_path.exists():
        hooks = _load_settings(settings_path).get("hooks", {})
        on = any(_is_ours(g) for groups in hooks.values() for g in groups)
    print(f"Autopilot is {'ON' if on else 'OFF'} for {'this project' if project else 'your user account'} ({settings_path})")
    if on and script.exists():
        subprocess.run([sys.executable, str(script), "status"])
    return 0


def cmd_autopilot(args):
    return {"on": autopilot_on, "off": autopilot_off, "status": autopilot_status}[args.action](args.project)


def ask_autopilot(args) -> None:
    """After installing the skills in this repo, offer to switch autopilot on (default yes)."""
    settings_path, _ = autopilot_paths(args.project)
    already = False
    if settings_path.exists():
        try:
            already = any(_is_ours(g) for groups in json.loads(settings_path.read_text() or "{}").get("hooks", {}).values() for g in groups)
        except Exception:
            pass
    if already or args.autopilot is False:
        return
    if args.autopilot is None and not args.yes:
        print("\nAutopilot lets the skills work without being called: a safety check on every file Claude edits,")
        print("a skill hint when your request matches, and masked session transcripts saved to .claude/journal/.")
        if input("Turn autopilot on? [Y/n] ").strip().lower() in ("n", "no"):
            print("Skipped. Turn it on later with: python3 install.py autopilot on")
            return
    print()
    autopilot_on(args.project)


def cmd_list(_args):
    print("Skills written in this repo:")
    for n in MANIFEST["own"]:
        print(f"  {n}")
    print("\nDownloaded from the original authors:")
    for e in MANIFEST["upstream"]:
        print(f"  {e['id']:<22} {e['repo']:<42} {e.get('license', '')}")
    print("\nMCP servers (registered, not copied):")
    for e in MANIFEST["mcp"]:
        print(f"  {e['id']:<22} {e['repo']}")
    print("\nNot auto-installed:")
    for e in MANIFEST["manual"]:
        print(f"  {e['id']:<22} {e['repo']}  - {e['note'][:90]}...")


def cmd_install(args):
    dest = dest_dir(args.project)
    dest.mkdir(parents=True, exist_ok=True)
    upstream = {e["id"]: e for e in MANIFEST["upstream"]}
    mcps = {e["id"]: e for e in MANIFEST["mcp"]}
    manual = {e["id"]: e for e in MANIFEST["manual"]}
    own = set(MANIFEST["own"])

    if args.all:
        want_own, want_up, want_mcp, want_manual = list(MANIFEST["own"]), list(upstream), list(mcps), list(manual)
    elif args.own and not args.names:
        want_own, want_up, want_mcp, want_manual = list(MANIFEST["own"]), [], [], []
    else:
        want_own = [n for n in args.names if n in own]
        want_up = [n for n in args.names if n in upstream]
        want_mcp = [n for n in args.names if n in mcps]
        want_manual = [n for n in args.names if n in manual]
        unknown = [n for n in args.names if n not in own | set(upstream) | set(mcps) | set(manual)]
        if unknown:
            sys.exit(f"Unknown name(s): {', '.join(unknown)}. Run: python3 install.py list")
    if not (want_own or want_up or want_mcp or want_manual):
        sys.exit("Nothing selected. Use --all, --own, or give names. Run: python3 install.py list")

    print(f"Install location: {dest}")
    if want_up and not shutil.which("git"):
        sys.exit("git is required to download third-party skills.")
    if want_up:
        mode = "newest default branch (--latest)" if args.latest else "commits reviewed on 2026-11-06 (use --latest for newest)"
        print(f"Third-party skills will be downloaded from GitHub: {mode}")
        if not args.yes:
            if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
                sys.exit("Cancelled.")

    if want_own:
        print("\n[own skills]")
        install_own(want_own, dest)
    failures = 0
    for i in want_up:
        if not install_upstream(upstream[i], dest, args.latest):
            failures += 1
    for i in want_mcp:
        install_mcp(mcps[i], args.with_mcp)
    for i in want_manual:
        print(f"\n[{i}] {manual[i]['title']}  (not auto-installed)\n   {manual[i]['note']}")

    print("\nDone." + (f" {failures} upstream skill(s) failed." if failures else ""))
    if want_own:
        ask_autopilot(args)
    print("Restart Claude Code (or start a new session) so it picks up the new skills.")
    return 1 if failures else 0


def cmd_uninstall(args):
    dest = dest_dir(args.project)
    try:
        rec = json.loads((dest / RECORD).read_text())
    except Exception:
        rec = {}
    for name in args.names:
        targets = rec.get(name, [name])   # fall back to a folder with the same name
        for t in targets:
            p = dest / t
            if p.exists() and p.parent == dest:
                shutil.rmtree(p)
                print(f"removed {p}")
            else:
                print(f"not installed: {p}")
        rec.pop(name, None)
    if rec or (dest / RECORD).exists():
        (dest / RECORD).write_text(json.dumps(rec, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("install")
    p.add_argument("names", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--own", action="store_true", help="only the skills written in this repo")
    p.add_argument("--project", action="store_true", help="install into ./.claude/skills instead of ~/.claude/skills")
    p.add_argument("--latest", action="store_true", help="newest upstream instead of the reviewed commit")
    p.add_argument("--with-mcp", action="store_true", help="also run `claude mcp add` for MCP servers")
    p.add_argument("-y", "--yes", action="store_true", help="skip the confirmation prompt (also turns autopilot on)")
    p.add_argument("--autopilot", dest="autopilot", action="store_true", default=None, help="turn autopilot on without asking")
    p.add_argument("--no-autopilot", dest="autopilot", action="store_false", help="do not set up autopilot")
    p.set_defaults(fn=cmd_install)
    ap_p = sub.add_parser("autopilot", help="let the skills run on their own (Claude Code hooks)")
    ap_p.add_argument("action", choices=["on", "off", "status"])
    ap_p.add_argument("--project", action="store_true", help="this project only (.claude/settings.local.json)")
    ap_p.set_defaults(fn=cmd_autopilot)
    u = sub.add_parser("uninstall")
    u.add_argument("names", nargs="+")
    u.add_argument("--project", action="store_true")
    u.set_defaults(fn=cmd_uninstall)
    args = ap.parse_args()
    sys.exit(args.fn(args) or 0)


if __name__ == "__main__":
    main()
