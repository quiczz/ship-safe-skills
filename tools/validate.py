#!/usr/bin/env python3
"""Check the repo before publishing. Stdlib only. Exit code 1 if anything fails.

    python3 tools/validate.py

Checks: skill front matter (name == folder, description length), JSON files parse,
manifests agree with each other and with skills/, python scripts compile,
healthcheck self-test passes, no leftover placeholders in shipped manifests (warning).
"""
import json
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors, warnings = [], []


def err(msg):
    errors.append(msg)
    print(f"  FAIL  {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"  warn  {msg}")


def ok(msg):
    print(f"  ok    {msg}")


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    data = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip()
    return data


def check_skill_dir(d, label):
    skill_md = d / "SKILL.md"
    if not skill_md.exists():
        err(f"{label}: missing SKILL.md")
        return
    fm = frontmatter(skill_md)
    if fm is None:
        err(f"{label}: SKILL.md has no front matter")
        return
    name, desc = fm.get("name", ""), fm.get("description", "")
    if name != d.name:
        err(f"{label}: front matter name '{name}' != folder '{d.name}'")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name or ""):
        err(f"{label}: name '{name}' must be lowercase letters, digits, hyphens")
    if not desc:
        err(f"{label}: empty description")
    elif len(desc) > 1024:
        err(f"{label}: description is {len(desc)} chars (max 1024)")
    if "<" in desc or ">" in desc:
        err(f"{label}: description contains angle brackets")
    lines = skill_md.read_text(encoding="utf-8").count("\n")
    if lines > 500:
        warn(f"{label}: SKILL.md is {lines} lines (consider moving detail to references/)")
    # relative links inside SKILL.md must exist
    body = skill_md.read_text(encoding="utf-8")
    for target in re.findall(r"`((?:references|scripts|templates)/[^`\s]+)`", body):
        if not (d / target).exists():
            err(f"{label}: SKILL.md mentions `{target}` but the file does not exist")


def main():
    print("Skills")
    skills_dir = ROOT / "skills"
    skill_names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
    for n in skill_names:
        check_skill_dir(skills_dir / n, f"skills/{n}")
    wrapper = ROOT / "wrappers" / "awesome-design-md"
    if wrapper.exists():
        check_skill_dir(wrapper, "wrappers/awesome-design-md")
    ok(f"{len(skill_names)} skills checked: {', '.join(skill_names)}")

    print("JSON")
    json_files = [p for p in ROOT.rglob("*.json") if ".git" not in p.parts and "dist" not in p.parts]
    parsed = {}
    for p in json_files:
        try:
            parsed[p.relative_to(ROOT).as_posix()] = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            err(f"{p.relative_to(ROOT)}: invalid JSON ({e})")
    ok(f"{len(json_files)} JSON files parsed")

    print("Manifests")
    plugin = parsed.get(".claude-plugin/plugin.json")
    market = parsed.get(".claude-plugin/marketplace.json")
    skills_json = parsed.get("skills.json")
    if plugin and market:
        pname = plugin.get("name", "")
        if re.match(r"^(claude-|anthropic-|anthropics-|cc-plugin-)", pname):
            err(f"plugin name '{pname}' uses a reserved prefix")
        mp = [x.get("name") for x in market.get("plugins", [])]
        if pname not in mp:
            err(f"plugin.json name '{pname}' not listed in marketplace.json plugins {mp}")
        if market.get("name", "").startswith(("claude-", "anthropic-")):
            err(f"marketplace name '{market.get('name')}' uses a reserved prefix")
        versions = {plugin.get("version")} | {x.get("version") for x in market.get("plugins", [])}
        if len(versions) != 1:
            err(f"version mismatch between plugin.json and marketplace.json: {versions}")
        else:
            ok(f"plugin '{pname}' version {versions.pop()}")
        for field in ("homepage", "repository"):
            if "YOUR-NAME" in str(plugin.get(field, "")):
                warn(f"plugin.json {field} still contains YOUR-NAME (run tools/set_owner.py)")
        if "YOUR-NAME" in json.dumps(market.get("owner", {})):
            warn("marketplace.json owner still YOUR-NAME (run tools/set_owner.py)")
    if skills_json:
        own = skills_json.get("own", [])
        if sorted(own) != skill_names:
            err(f"skills.json 'own' {sorted(own)} != skills/ folders {skill_names}")
        else:
            ok("skills.json 'own' matches skills/ folders")
        for u in skills_json.get("upstream", []):
            sha = u.get("pinned", "")
            if u.get("kind") != "corpus" and not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
                warn(f"skills.json upstream '{u.get('id')}' has no full 40-char pinned commit")
            w = u.get("wrapper")
            if w and not (ROOT / w / "SKILL.md").exists():
                err(f"skills.json upstream '{u.get('id')}' wrapper '{w}' has no SKILL.md")

    print("Python")
    py_files = [p for p in ROOT.rglob("*.py") if ".git" not in p.parts and "dist" not in p.parts]
    with tempfile.TemporaryDirectory() as tmp:
        for p in py_files:
            try:
                py_compile.compile(str(p), cfile=str(Path(tmp) / (p.name + "c")), doraise=True)
            except py_compile.PyCompileError as e:
                err(f"{p.relative_to(ROOT)}: {e.msg.strip()}")
    ok(f"{len(py_files)} Python files compile")

    hc = ROOT / "skills/monitor-alerts-builder/templates/healthcheck.py"
    if hc.exists():
        r = subprocess.run([sys.executable, "-I", str(hc), "--selftest"], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            err("healthcheck.py --selftest failed:\n" + (r.stdout + r.stderr)[-600:])
        else:
            ok("healthcheck.py --selftest passed")

    print("Autopilot")
    hj = ROOT / "hooks" / "hooks.json"
    ap = ROOT / "hooks" / "autopilot.py"
    if hj.exists() and ap.exists():
        try:
            hooks = json.loads(hj.read_text(encoding="utf-8")).get("hooks", {})
            for ev, groups in hooks.items():
                for g in groups:
                    for h in g.get("hooks", []):
                        if "autopilot.py" not in h.get("command", ""):
                            err(f"hooks.json {ev}: command does not call autopilot.py")
            ok(f"hooks.json declares {len(hooks)} events: {', '.join(hooks)}")
        except Exception as e:
            err(f"hooks/hooks.json: {e}")
        import os as _os
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(_os.environ, SHIP_SAFE_HOME=str(Path(tmp) / "home"), PYTHONDONTWRITEBYTECODE="1")
            proj = Path(tmp) / "proj"
            proj.mkdir()
            fake = "ghp_" + "Ab3dE6gH9jK2mN5pQ8sT1vW4yZ7bC0eF3hJ6"  # fake token, built at runtime
            (proj / "bad.js").write_text(f'const t = "{fake}";\n')
            (proj / "good.js").write_text("const t = process.env.TOKEN;\n")

            def run(event, rel):
                payload = json.dumps({"session_id": "v", "cwd": str(proj), "tool_input": {"file_path": rel}, "prompt": "add a skeleton and make it production ready"})
                return subprocess.run([sys.executable, "-I", str(ap), event], input=payload, capture_output=True, text=True, env=env, timeout=30)

            r = run("post-edit", "bad.js")
            if "GitHub token" not in r.stdout or fake in r.stdout:
                err("autopilot post-edit did not flag the fake token (or leaked its value)")
            elif run("post-edit", "good.js").stdout.strip():
                err("autopilot post-edit flagged a clean file")
            else:
                ok("autopilot post-edit: flags a secret without printing it, ignores clean code")
            r = run("prompt", "x")
            if "skeletonizer" not in r.stdout or "app-readiness-audit" not in r.stdout:
                err("autopilot prompt hints did not match expected skills")
            else:
                ok("autopilot prompt hints match skills")
            r = run("session-start", "x")
            if r.returncode != 0 or "autopilot is on" not in r.stdout:
                err("autopilot session-start failed")
            else:
                ok("autopilot session-start prints standing instructions")
    else:
        warn("hooks/hooks.json or hooks/autopilot.py missing")

    print("Skill scripts")
    cm = ROOT / "skills/motionsite/scripts/check_motion.py"
    if cm.exists():
        r = subprocess.run([sys.executable, "-I", str(cm), str(ROOT / "skills/motionsite/templates")], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            err("motionsite template fails its own audit:\n" + r.stdout[-500:])
        else:
            ok("motionsite template passes check_motion.py")
    fl = ROOT / "skills/skeletonizer/scripts/find_loading_candidates.py"
    if fl.exists():
        r = subprocess.run([sys.executable, "-I", str(fl), str(ROOT / "skills/skeletonizer/templates")], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            err("find_loading_candidates.py failed")
        else:
            ok("find_loading_candidates.py runs")

    print("Placeholders")
    left = []
    for f in list(ROOT.glob("*.md")) + list((ROOT / "docs").glob("*.md")) + list((ROOT / ".github").rglob("*.yml")):
        t = f.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"OWNER/ship-safe-skills|github\.com/OWNER|YOUR-NAME", t):
            left.append(f.relative_to(ROOT).as_posix())
    if left:
        warn("OWNER / YOUR-NAME placeholders remain in: " + ", ".join(left) + " (run tools/set_owner.py YOUR_GITHUB_USERNAME)")
    else:
        ok("no placeholders left")

    print("Hygiene")
    for p in ROOT.rglob("*"):
        if p.is_file() and ".git" not in p.parts and "dist" not in p.parts and p.suffix in {".py", ".md", ".json", ".yml", ".yaml", ".sh"}:
            t = p.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"(AKIA[0-9A-Z]{16}|sk_live_[0-9a-zA-Z]{20,}|ghp_[0-9A-Za-z]{30,}|-----BEGIN (RSA |EC )?PRIVATE KEY-----)", t):
                # scanner pattern tables legitimately contain regex text, not literal keys; flag literals only
                err(f"{p.relative_to(ROOT)}: looks like a real secret literal")
    ok("no secret literals found")

    print()
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
