#!/usr/bin/env python3
"""Convert a Claude Code session transcript (JSONL) to readable Markdown, masking common secrets.

Hook mode (no arguments): reads the hook JSON on stdin ({"session_id", "transcript_path", "cwd", ...})
and writes <cwd>/.claude/journal/transcripts/<date>_<session>.md.
Manual mode: export_transcript.py --input FILE.jsonl [--out DIR]

Standard library only. Never fails the hook: problems go to stderr and the exit code is 0 in hook mode.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

MASKS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[PRIVATE KEY REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[AWS KEY REDACTED]"),
    (re.compile(r"\b[sr]k_(live|test)_[0-9A-Za-z]{10,}\b"), "[STRIPE KEY REDACTED]"),
    (re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}\b"), "[GITHUB TOKEN REDACTED]"),
    (re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"), "[SLACK TOKEN REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "[GOOGLE KEY REDACTED]"),
    (re.compile(r"\bsk-(ant-)?[A-Za-z0-9_\-]{32,}\b"), "[API KEY REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[JWT REDACTED]"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{16,}"), r"\1 [REDACTED]"),
    (re.compile(r"(?i)\b((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^:/\s]+:)[^@\s'\"]+@"), r"\1[REDACTED]@"),
    (re.compile(r"(?i)\b([A-Z0-9_]*(?:SECRET|PASSWORD|PASSWD|TOKEN|API_?KEY|PRIVATE_?KEY)[A-Z0-9_]*)(\s*[=:]\s*)(['\"]?)[^\s'\"]{6,}\3"),
     r"\1\2[REDACTED]"),
]


def mask(text: str) -> str:
    for rx, rep in MASKS:
        text = rx.sub(rep, text)
    return text


def block_to_md(b) -> str:
    if isinstance(b, str):
        return b
    t = b.get("type")
    if t == "text":
        return b.get("text", "")
    if t == "tool_use":
        inp = json.dumps(b.get("input", {}), ensure_ascii=False)
        return f"`[tool: {b.get('name')}]` {inp[:600]}{'...' if len(inp) > 600 else ''}"
    if t == "tool_result":
        c = b.get("content")
        if isinstance(c, list):
            c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
        c = str(c or "")
        return f"`[tool result]` {c[:800]}{'...' if len(c) > 800 else ''}"
    if t == "thinking":
        return ""
    return ""


def convert(lines, skipped):
    out, n = [], 0
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            skipped.append(i)
            continue
        msg = rec.get("message") if isinstance(rec.get("message"), dict) else None
        role = (msg or {}).get("role") or rec.get("type")
        if role not in ("user", "assistant") or msg is None:
            continue
        content = msg.get("content")
        if isinstance(content, list):
            body = "\n\n".join(x for x in (block_to_md(b) for b in content) if x.strip())
        else:
            body = str(content or "")
        if not body.strip():
            continue
        ts = rec.get("timestamp", "")
        who = "User" if role == "user" else "Claude"
        out.append(f"### {who}" + (f"  <sub>{ts}</sub>" if ts else "") + "\n\n" + mask(body).strip() + "\n")
        n += 1
    return out, n


def write_transcript(src: Path, out_dir: Path, session_id: str):
    skipped = []
    with src.open(encoding="utf-8", errors="replace") as f:
        parts, n = convert(f, skipped)
    out_dir.mkdir(parents=True, exist_ok=True)
    gi = out_dir.parent / ".gitignore"
    if out_dir.parent.name == "journal" and not gi.exists():
        gi.write_text("*\n")
    name = f"{datetime.now().strftime('%Y-%m-%d_%H%M')}_{(session_id or src.stem)[:12]}.md"
    dest = out_dir / name
    header = (f"# Session transcript\n\nSession: `{session_id or src.stem}`  |  Exported: {datetime.now().isoformat(timespec='seconds')}"
              f"  |  Messages: {n}\n\n> Secrets are masked on a best-effort basis. Review before sharing.\n\n---\n\n")
    dest.write_text(header + "\n".join(parts), encoding="utf-8")
    if skipped:
        print(f"export_transcript: skipped {len(skipped)} unreadable line(s)", file=sys.stderr)
    return dest, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input")
    ap.add_argument("--out")
    ap.add_argument("--session-id", default="")
    a = ap.parse_args()
    hook_mode = not a.input
    try:
        if hook_mode:
            data = json.loads(sys.stdin.read().strip() or "{}")
            tp = data.get("transcript_path")
            if not tp or not Path(tp).expanduser().exists():
                print("export_transcript: no transcript_path in hook input", file=sys.stderr)
                return 0
            cwd = Path(data.get("cwd") or ".")
            dest, n = write_transcript(Path(tp).expanduser(), cwd / ".claude" / "journal" / "transcripts", data.get("session_id", ""))
        else:
            dest, n = write_transcript(Path(a.input), Path(a.out or "./transcripts"), a.session_id)
        print(f"export_transcript: wrote {n} messages to {dest}", file=sys.stderr if hook_mode else sys.stdout)
    except Exception as e:  # never break the user's session
        print(f"export_transcript: failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 0 if hook_mode else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
