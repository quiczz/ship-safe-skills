# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private reporting: the repository's **Security** tab, then **Report a vulnerability** (https://github.com/quiczz/ship-safe-skills/security/advisories/new).

Include what you found, how to reproduce it, and the version (`version` in `.claude-plugin/plugin.json`). You can expect an acknowledgement within a few days. This is a volunteer-maintained project, so there is no fixed response SLA.

## In scope

- Scripts and hooks in this repository that could read, write or send data they should not (for example an unmasked secret in a saved transcript, or a path traversal in the installer).
- Skill instructions that would make Claude do something unsafe by default.

## Out of scope

- Third-party skills the installer can download (report to their authors).
- Findings that need an attacker who already controls your machine or your Claude settings.
- Scanner false negatives: the scanners are heuristic and say so.

## Design notes that matter for security

- Scripts use only the Python standard library and make no network calls.
- Hooks never block a session, never print secret values, and write only to `~/.claude/ship-safe-skills/` and `<project>/.claude/journal/`.
- The installer changes settings only after a JSON validity check, keeps a backup, and touches only the hooks it added.
