# Autopilot

Autopilot is how the skills in this repo work **without being called**. It is a small set of [Claude Code hooks](https://code.claude.com/docs/en/hooks) backed by one Python file, [`hooks/autopilot.py`](../hooks/autopilot.py).

It exists because skills normally wait: Claude loads one only when it decides the description matches. That works most of the time, but "most of the time" is not good enough for "did Claude check this file for a leaked key?". Autopilot adds reminders and a few cheap checks at the moments that matter.

## What runs, and when

| Hook event | Command | What it does |
|------------|---------|--------------|
| `SessionStart` | `autopilot.py session-start` | Prints standing instructions for Claude (which skill to use in which situation) and project warnings: `.env` present but not git-ignored; no `docs/BUILD_FLOW.md` (at most once every 14 days per project); a one-time note that the journal is on |
| `UserPromptSubmit` | `autopilot.py prompt` | If your prompt matches a skill's topic, prints one line pointing Claude to it. At most two hints per prompt; the same hint is not repeated in a session |
| `PostToolUse` (`Write`, `Edit`, `MultiEdit`) | `autopilot.py post-edit` | Checks the file Claude just wrote (see below) and returns a short note to Claude if something is found |
| `PreCompact`, `SessionEnd` | `autopilot.py session-end` | Runs `session-journal`'s exporter to save the transcript as Markdown with secrets masked |

All hooks exit 0, even on bad input or an internal error, so they cannot break a session. Each has a timeout (5 to 30 seconds) far above what it needs.

### What the file check looks for

- **Secrets** (code files only; docs, tests and examples are skipped): private key blocks, AWS access keys, Stripe live keys, GitHub tokens, Slack tokens, Google API keys, OpenAI/Anthropic-style keys, database URLs that contain a password, and generic `api_key = "..."` style assignments with a high-entropy value. Placeholders (`your-key-here`, `example`, `process.env...`, `${...}`) are ignored.
- **Risky settings:** TLS verification turned off (`verify=False`, `rejectUnauthorized: false`, `InsecureSkipVerify`), wildcard CORS (`Access-Control-Allow-Origin: *`), and secrets in URL query strings.
- **`.env` files:** a `.env` or `.env.local` that git does not ignore.
- **Loading UI:** when an edit to a `.tsx`, `.jsx`, `.vue` or `.svelte` file adds a bare spinner or "Loading..." outside a button, Claude is reminded about the `skeletonizer` skill.

The note names the finding, file and line, and the fix. **It never contains the secret value.**

See real examples in [`docs/examples/autopilot.txt`](examples/autopilot.txt).

## Switching things off

Four features can be switched on or off independently: `context` (session-start text), `hints` (prompt hints and the spinner reminder), `secrets` (file checks) and `journal` (transcript saving).

```bash
python3 hooks/autopilot.py status
python3 hooks/autopilot.py off journal
python3 hooks/autopilot.py off all
python3 hooks/autopilot.py on all
```

Settings live in `~/.claude/ship-safe-skills/config.json`. For one session only, set an environment variable: `SHIP_SAFE_DISABLE=journal,hints claude` (or `all`).

To remove the hooks entirely: `/plugin uninstall ship-safe-skills@ship-safe-skills` (plugin install) or `python3 install.py autopilot off`.

## Where things are written

| What | Where |
|------|-------|
| Settings | `~/.claude/ship-safe-skills/config.json` |
| Throttle state (when a project hint was last shown) | `~/.claude/ship-safe-skills/state.json` |
| Per-session de-duplication (deleted after 7 days) | `~/.claude/ship-safe-skills/sessions/` |
| Transcripts (journal on) | `<project>/.claude/journal/transcripts/<date>_<session>.md`, with a `.gitignore` containing `*` in `.claude/journal/` |

Nothing is sent over the network.

## Installing autopilot

- **Plugin install:** hooks come with the plugin (`hooks/hooks.json`); nothing else to do.
- **Without the plugin:** `python3 install.py autopilot on` copies `autopilot.py` to `~/.claude/ship-safe-skills/` and merges the hooks into `~/.claude/settings.json`. It keeps your other settings and hooks, saves a one-time backup (`settings.json.ship-safe-backup`), and refuses to touch a settings file that is not valid JSON. Add `--project` to use `.claude/settings.local.json` for one project instead.
- **Both at once** would run every check twice. Use one.

## Privacy

The journal saves your whole conversation, including what you pasted and what tools returned. The exporter masks common secret formats (keys, tokens, JWTs, passwords in assignments, database URLs) but cannot recognise every secret. The folder is git-ignored by its own `.gitignore`. If that is not acceptable for a project, run `python3 hooks/autopilot.py off journal`.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Nothing seems to run | In Claude Code run `/hooks` and confirm the hooks are listed; restart after installing. Run `python3 hooks/autopilot.py status` |
| "python3: command not found" | Install Python 3.8+ and make sure `python3` is on your PATH (on Windows you may need to edit the command to `python` or `py -3`; Windows is untested) |
| Findings repeat | They should not within a session. If they do, check that the session id is passed (`~/.claude/ship-safe-skills/sessions/`) |
| Too noisy | `python3 hooks/autopilot.py off hints`, or `off secrets` |
| Transcript missing | Journal may be off (`status`), or the `session-journal` skill is not installed beside the hooks |

## Extending

Everything is in one readable file. Add a secret format to `SECRET_PATTERNS`, a risky setting to `RISKY`, or a skill hint to `HINTS`. `python3 tools/validate.py` runs the autopilot self-checks.
