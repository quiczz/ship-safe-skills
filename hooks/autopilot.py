#!/usr/bin/env python3
"""ship-safe-skills autopilot: lets the skills work without being called. Stdlib only.

Used by Claude Code hooks (see hooks/hooks.json, or `install.py autopilot on`):

    autopilot.py session-start    SessionStart       standing instructions + project warnings
    autopilot.py prompt           UserPromptSubmit   one-line skill hint when the request matches
    autopilot.py post-edit        PostToolUse        check the file Claude just wrote/edited
    autopilot.py session-end      SessionEnd/PreCompact  save the masked transcript

You can also run it by hand:

    autopilot.py status
    autopilot.py off journal      (features: context, hints, secrets, journal, or all)
    autopilot.py on  journal

Rules this script keeps:
  * It never blocks, never fails a session (always exits 0), and finishes in well under a second.
  * It never prints a secret value; findings give the type, file and line only.
  * It writes only to ~/.claude/ship-safe-skills/ (settings, throttle state) and, for the journal,
    <project>/.claude/journal/ (git-ignored by its own .gitignore).
Environment: SHIP_SAFE_DISABLE=all or a comma list (context,hints,secrets,journal) switches features off;
SHIP_SAFE_HOME overrides the settings folder.
"""
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

FEATURES = ("context", "hints", "secrets", "journal")
HOME_DIR = Path(os.environ.get("SHIP_SAFE_HOME") or (Path.home() / ".claude" / "ship-safe-skills"))
CONFIG = HOME_DIR / "config.json"
STATE = HOME_DIR / "state.json"
SELF = Path(__file__).resolve()

# --------------------------------------------------------------------------- config / state


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def enabled(feature):
    env = {x.strip() for x in os.environ.get("SHIP_SAFE_DISABLE", "").split(",") if x.strip()}
    if "all" in env or feature in env:
        return False
    return bool(load_json(CONFIG, {}).get(feature, True))


def throttled(key, days):
    """True if this hint was shown within `days`. Records the show time when it was not."""
    state = load_json(STATE, {})
    now = time.time()
    if now - state.get(key, 0) < days * 86400:
        return True
    state[key] = now
    save_json(STATE, state)
    return False


def session_seen(session_id, key):
    """Per-session dedupe so the same finding or hint is not repeated every edit."""
    if not session_id:
        return False
    path = HOME_DIR / "sessions" / f"{re.sub(r'[^A-Za-z0-9_-]', '', session_id)[:64]}.json"
    seen = set(load_json(path, []))
    if key in seen:
        return True
    seen.add(key)
    save_json(path, sorted(seen))
    return False


def prune_sessions():
    d = HOME_DIR / "sessions"
    try:
        cutoff = time.time() - 7 * 86400
        for f in d.glob("*.json"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
    except Exception:
        pass


def read_stdin():
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        return raw, json.loads(raw) if raw.strip() else {}
    except Exception:
        return raw, {}


def emit_context(event, text):
    """Hand text to Claude as additional context (JSON form, works for every event)."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def git_ignored(path, cwd):
    """True if ignored, False if not ignored, None if unknown (not a repo, git missing)."""
    try:
        r = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=cwd, capture_output=True, timeout=3)
        return {0: True, 1: False}.get(r.returncode)
    except Exception:
        return None

# --------------------------------------------------------------------------- session-start


CONTEXT = """[ship-safe-skills autopilot is on]
Use these skills on your own, without waiting to be asked:
- Before you call a feature done or ready to ship: check it against app-readiness-audit (secrets, input validation, errors, rate limits, backups) and fix the gaps you caused.
- When you add or change an API route, auth or a token: apply api-security-guard (12 rules). When you touch IAM, service accounts, CI secrets or network config: apply zero-trust-review.
- When you build UI that loads data: make the loading state a layout-matching skeleton (skeletonizer), not a bare spinner or blank area.
- When asked for a landing page, hero or animated site: use motionsite, then run its check_motion.py audit.
- After a structural change (new service, framework, env var, route group): update docs/BUILD_FLOW.md (build-flow-map).
- When something is about to be deployed with no alerting: offer monitor-alerts-builder.
Already running by themselves: edited files are checked for committed secrets and risky settings; session transcripts are saved with secrets masked to .claude/journal/ (git-ignored).
Mention a finding to the user in one line, fix it, and move on. To switch parts off: python3 "{self}" off all|context|hints|secrets|journal"""

SOURCE_HINT = re.compile(r"\.(py|js|jsx|ts|tsx|go|rb|java|kt|swift|dart|php|rs|vue|svelte)$")


def project_has_source(cwd):
    markers = ("package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml", "pubspec.yaml", "Gemfile", "pom.xml", "composer.json", "Package.swift")
    return any((cwd / m).exists() for m in markers)


def session_start(data):
    if not enabled("context"):
        return
    cwd = Path(data.get("cwd") or os.getcwd())
    lines = [CONTEXT.format(self=SELF)]
    notes = []
    env = cwd / ".env"
    if env.exists() and git_ignored(".env", cwd) is False:
        notes.append("WARNING: .env exists but is NOT git-ignored in this project. Tell the user and add it to .gitignore before anything is committed.")
    if project_has_source(cwd) and not (cwd / "docs" / "BUILD_FLOW.md").exists() and not throttled(f"buildflow:{cwd}", 14):
        notes.append("This project has no docs/BUILD_FLOW.md. When there is a natural pause, offer to create it with build-flow-map.")
    if enabled("journal") and not throttled(f"journalnote:{cwd}", 365):
        notes.append("Tell the user once: session transcripts are saved (secrets masked) to .claude/journal/transcripts/ and are git-ignored; they can switch this off.")
    if notes:
        lines.append("Project notes:\n- " + "\n- ".join(notes))
    prune_sessions()
    print("\n".join(lines))

# --------------------------------------------------------------------------- prompt hints


HINTS = [
    ("app-readiness-audit", r"\b(production[- ]ready|ready to (launch|ship|deploy)|go(ing)? live|launch (review|checklist)|before (we |i )?(launch|release|ship)|pre-?launch|readiness)\b"),
    ("monitor-alerts-builder", r"\b(monitoring|alerting|uptime|health ?checks?|on-?call|pagerduty|runbooks?|set up alerts?|add alerts?)\b"),
    ("api-security-guard", r"\b(bola|idor|owasp|api (security|auth|keys?)|secure (the|my|this) api|rate[- ]limit|endpoint inventory|list (all )?(the )?endpoints)\b"),
    ("zero-trust-review", r"\b(zero[- ]trust|least[- ]privilege|mfa|service accounts?|iam (policy|role)|microsegment\w*|assume breach|harden (the )?(cloud|cluster|infra\w*))\b"),
    ("skeletonizer", r"\b(skeletons?|shimmer|loading (state|spinner|screen|placeholder)s?|spinners?|layout shift|content jump)\b"),
    ("motionsite", r"\b(landing page|hero (section|video)|video (background|hero)|animated (site|website|landing)|motion[- ]?site|cinematic|scroll animation)\b"),
    ("build-flow-map", r"\b(build flow|how (is|does) (this|the) (project|app|repo|codebase) (built|work)s?|onboard(ing)? (a |the )?(new )?dev\w*|architecture (doc|map|overview)|what (stack|frameworks?) )\b"),
    ("session-journal", r"\b(save (the |this )?session|session (history|journal|log)|where we left off|resume where|chat history)\b"),
]


def prompt_hint(data):
    if not enabled("hints"):
        return
    prompt = (data.get("prompt") or "")[:4000].lower()
    if not prompt:
        return
    sid = data.get("session_id", "")
    found = []
    for skill, rx in HINTS:
        if re.search(rx, prompt) and not session_seen(sid, f"hint:{skill}"):
            found.append(skill)
        if len(found) == 2:
            break
    if found:
        print("[ship-safe-skills] This request matches: " + ", ".join(f"the {s} skill" for s in found) + ". Use it.")

# --------------------------------------------------------------------------- post-edit checks


SKIP_PATH = re.compile(r"(^|/)(node_modules|\.git|dist|build|\.next|vendor|__pycache__|coverage|\.venv|venv)/|\.(lock|min\.js|map|png|jpe?g|gif|webp|ico|woff2?|ttf|pdf|zip|mp4|webm|svg)$|(package-lock\.json|yarn\.lock|pnpm-lock\.yaml)$")
DOC_PATH = re.compile(r"\.(md|mdx|txt|rst)$|(^|/)(docs?|tests?|__tests__|fixtures?|examples?)/|\.(test|spec)\.|(^|/)\.env\.(example|sample|template)$")

SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Stripe live key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{16,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Anthropic or OpenAI key", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{32,}\b")),
    ("database URL with password", re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:/\s'\"@]+:([^@\s'\"]{4,})@")),
]
GENERIC_SECRET = re.compile(r"(?i)\b[\w.-]*(?:api[_-]?key|secret|token|passwd|password|private[_-]?key)[\w.-]*['\"]?\s*[:=]\s*['\"]([A-Za-z0-9/+_\-.=]{20,})['\"]")
PLACEHOLDER = re.compile(r"(?i)example|your[_-]|xxx|changeme|change[_-]me|dummy|placeholder|sample|test|fake|redacted|<|\$\{|\{\{|process\.env|os\.environ|getenv|\*\*\*|0000|1234")

RISKY = [
    ("TLS verification turned off", re.compile(r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0|InsecureSkipVerify\s*:\s*true"),
     "Turn certificate checks back on; fix the certificate instead."),
    ("wildcard CORS origin", re.compile(r"(?i)Access-Control-Allow-Origin['\"]?\s*[:,]\s*['\"]\*|\borigin\s*:\s*['\"]\*['\"]"),
     "Allow only the origins that need it, especially if cookies or auth headers are used."),
    ("secret in a URL query string", re.compile(r"(?i)['\"`]https?://[^'\"`\s]*[?&](?:access_)?(?:token|api_?key|apikey|secret|password)=[^'\"`\s&]+"),
     "Send secrets in an Authorization header, not in the URL (URLs end up in logs and history)."),
]

LOADING_UI = re.compile(r">\s*(Loading|Please wait)[^<{]{0,20}<|<(Spinner|Loader2?|CircularProgress|ActivityIndicator|ClipLoader)\b|\bCircularProgressIndicator\b")
BUTTONISH = re.compile(r"(?i)<button|\bbtn\b|submit|disabled|issubmitting|issaving|mutation|<IconButton|Pressable|TouchableOpacity")


def entropy(s):
    if not s:
        return 0.0
    probs = [s.count(c) / len(s) for c in set(s)]
    return -sum(p * math.log2(p) for p in probs)


def scan_text(text, rel, is_doc):
    findings = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if len(line) > 2000:
            continue
        if not is_doc:
            for name, rx in SECRET_PATTERNS:
                m = rx.search(line)
                if m:
                    secret = m.group(1) if m.groups() else m.group(0)
                    if name == "database URL with password" and PLACEHOLDER.search(secret):
                        continue
                    if name != "private key" and PLACEHOLDER.search(line) and "AKIA" not in line:
                        continue
                    findings.append((i, f"{name} written into {rel}", "Move it to an environment variable or secret manager. If it was ever committed or shared, rotate it."))
                    break
            else:
                m = GENERIC_SECRET.search(line)
                if m and not PLACEHOLDER.search(m.group(1)) and not PLACEHOLDER.search(line) and entropy(m.group(1)) > 3.4:
                    findings.append((i, f"hard-coded secret-looking value in {rel}", "Read it from an environment variable instead. If it is real, rotate it."))
            for name, rx, fix in RISKY:
                if rx.search(line):
                    findings.append((i, f"{name} in {rel}", fix))
    return findings


def post_edit(data):
    if not enabled("secrets"):
        return
    ti = data.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("path")
    if not fp:
        return
    cwd = Path(data.get("cwd") or os.getcwd())
    path = Path(fp)
    path = path if path.is_absolute() else cwd / path
    try:
        rel = path.resolve().relative_to(cwd.resolve()).as_posix()
    except Exception:
        rel = path.name
    posix = path.as_posix()
    if SKIP_PATH.search(posix) or not path.is_file():
        return
    try:
        if path.stat().st_size > 300_000:
            return
        text = path.read_text(encoding="utf-8")
    except Exception:
        return
    sid = data.get("session_id", "")
    msgs = []

    name = path.name
    if name == ".env" or (name.startswith(".env.") and not re.search(r"(example|sample|template)$", name)):
        if git_ignored(path, path.parent) is False:
            msgs.append(f"{rel} holds secrets but is NOT git-ignored. Add `{name}` to .gitignore now (and run `git rm --cached {rel}` if it was ever added).")
    else:
        is_doc = bool(DOC_PATH.search(posix))
        for line_no, what, fix in scan_text(text, rel, is_doc):
            if not session_seen(sid, f"find:{rel}:{what}"):
                msgs.append(f"{what} (line {line_no}). {fix}")

    # newly written loading UI -> suggest a skeleton (only when this edit adds it)
    if path.suffix in {".tsx", ".jsx", ".vue", ".svelte"} and enabled("hints"):
        added = ti.get("new_string") or ti.get("content") or ""
        for ln in added.splitlines():
            if LOADING_UI.search(ln) and not BUTTONISH.search(ln):
                if not session_seen(sid, f"skel:{rel}"):
                    msgs.append(f"{rel} now shows a spinner or 'Loading...' for content. If this stands in for data that will appear, use the skeletonizer skill to show a layout-matching skeleton instead.")
                break

    if msgs:
        extra = f"\n- (+{len(msgs) - 8} more in this file)" if len(msgs) > 8 else ""
        emit_context("PostToolUse", "ship-safe-skills check on the file you just wrote:\n- " + "\n- ".join(msgs[:8]) + extra + "\nTell the user in one line and fix it unless they said otherwise.")

# --------------------------------------------------------------------------- session-end


def find_export_script(cwd):
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    candidates = []
    if root:
        candidates.append(Path(root) / "skills/session-journal/scripts/export_transcript.py")
    candidates += [
        SELF.parent.parent / "skills/session-journal/scripts/export_transcript.py",
        Path(cwd) / ".claude/skills/session-journal/scripts/export_transcript.py",
        Path.home() / ".claude/skills/session-journal/scripts/export_transcript.py",
    ]
    return next((c for c in candidates if c.is_file()), None)


def session_end(raw, data):
    if not enabled("journal"):
        return
    script = find_export_script(data.get("cwd") or os.getcwd())
    if not script or not data.get("transcript_path"):
        return
    try:
        subprocess.run([sys.executable, str(script)], input=raw, text=True, capture_output=True, timeout=25)
    except Exception:
        pass

# --------------------------------------------------------------------------- manual commands


def cli(args):
    cfg = load_json(CONFIG, {})
    if not args or args[0] == "status":
        print("ship-safe-skills autopilot")
        for f in FEATURES:
            print(f"  {f:8s} {'on' if enabled(f) else 'off'}")
        print(f"  settings: {CONFIG}")
        return
    if args[0] in {"on", "off"} and len(args) == 2:
        names = FEATURES if args[1] == "all" else (args[1],)
        if any(n not in FEATURES for n in names):
            print(f"Unknown feature '{args[1]}'. Use: all, {', '.join(FEATURES)}")
            return
        for n in names:
            cfg[n] = args[0] == "on"
        save_json(CONFIG, cfg)
        print(f"{args[1]} is now {args[0]}. Takes effect on the next session.")
        return
    print(__doc__)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if cmd in {"session-start", "prompt", "post-edit", "session-end"}:
            raw, data = read_stdin()
            {"session-start": lambda: session_start(data), "prompt": lambda: prompt_hint(data),
             "post-edit": lambda: post_edit(data), "session-end": lambda: session_end(raw, data)}[cmd]()
        else:
            cli(sys.argv[1:])
    except Exception as e:  # a hook must never break the session
        print(f"ship-safe-skills autopilot: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
