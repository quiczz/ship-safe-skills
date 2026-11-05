---
name: session-journal
description: Keep a written history of your work sessions - a running journal of goals, decisions, files changed and open items, plus an optional hook that saves the full chat transcript (with secrets masked) to a file. Use when asked to save, log, note or remember the session, keep chat history, or resume where we left off. Use proactively at the end of a substantial piece of work.
---

# Session Journal

Two layers, because they do different jobs:

| Layer | What it gives you | How |
|-------|-------------------|-----|
| **Journal** (this skill) | A short, readable record: goal, decisions and why, files changed, commands that mattered, open items | You (Claude) write it during the session |
| **Transcript export** (optional hook) | The complete verbatim chat, saved automatically | `scripts/export_transcript.py` run by a Claude Code hook |

A skill on its own cannot capture raw chat text. It can only write notes from what you did. For the full verbatim history, set up the hook (see below). Say this to the user if they ask for "all the chat".

**Runs on its own:** with autopilot on, the full transcript is saved (secrets masked) at the end of every session and before context is compacted. The written journal is added after substantial work.

## Where files go

```
<project>/.claude/journal/
  JOURNAL.md              index + entries, newest at the bottom
  transcripts/            full chats from the hook (one file per session)
  .gitignore              contains "*" so nothing here is committed by accident
```

On first use, create the folder and the `.gitignore` (content: `*`). Tell the user once that chat history can contain secrets and personal data, so it stays out of git unless they choose otherwise.

## Journal entry format

Append (never rewrite old entries) to `JOURNAL.md`:

```markdown
## 2026-11-06 14:20 - short title of the session
**Goal:** one sentence
**Done:**
- what changed and why (file paths)
**Decisions:**
- decision - reason - alternatives rejected
**Commands worth remembering:** `...`
**Open items / next steps:**
- [ ] ...
**Gotchas:** things that surprised us
```

Keep each entry under about 25 lines. Link to files instead of pasting code.

## When to write

- At the start of a session: read the last 2 entries of `JOURNAL.md` and the "Open items" so you can resume. Tell the user in one line what you picked up.
- At natural stopping points (a feature finished, a decision made, before a long break) and whenever the user says save, log, note, remember, or wrap up.
- Before the context gets long enough to be summarized: write the entry first so detail is not lost.

## Never write into the journal

Passwords, API keys, tokens, private keys, full personal data, or customer records. Write "uses STRIPE_SECRET_KEY from the environment" instead of the value.

## Optional: save the full transcript with a hook

1. Copy or install this skill to `~/.claude/skills/session-journal/`.
2. Add to `~/.claude/settings.json` (all projects) or `.claude/settings.json` (one project):

```json
{
  "hooks": {
    "SessionEnd": [
      { "hooks": [ { "type": "command",
        "command": "python3 \"$HOME/.claude/skills/session-journal/scripts/export_transcript.py\"" } ] }
    ],
    "PreCompact": [
      { "hooks": [ { "type": "command",
        "command": "python3 \"$HOME/.claude/skills/session-journal/scripts/export_transcript.py\"" } ] }
    ]
  }
}
```

`SessionEnd` saves when the session closes; `PreCompact` saves just before old messages are summarized away. The script reads the hook's JSON from stdin, converts the session transcript to Markdown, **masks common secret patterns**, and writes it to `.claude/journal/transcripts/`. Masking is best-effort, so review before sharing a transcript.

Manual use: `python3 scripts/export_transcript.py --input path/to/session.jsonl --out ./transcripts`

Check that hook field names and the transcript format still match your Claude Code version if the export looks empty; the script prints what it could not read to stderr.
