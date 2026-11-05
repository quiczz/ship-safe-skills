---
name: app-readiness-audit
description: Audit an application before launch for mobile support, secret keys, database safety, rate limiting, password reset, rollbacks, backups, usage limits, analytics, input sanitizing, error handling, log flow and monitoring/alerts. Use when asked to check if an app is production-ready, do a launch review, or find security and reliability gaps. Use proactively, without being asked, before you tell the user a feature or app is ready to ship.
---

# App Readiness Audit

Checks a codebase against 13 launch-readiness areas and produces an evidence-based report with a fix list. It reads the code; it does not attack a live system.

**Runs on its own:** before Claude calls a feature or app ready to ship, it skims the change against these areas and fixes what it broke. A full audit still runs when you ask.

## What it covers

| # | Area | Question it answers |
|---|------|---------------------|
| 1 | Mobile | Does it work on phones (responsive web, PWA, or native build config)? |
| 2 | Secret keys | Are keys out of the code, out of git, rotatable, and not shipped to the browser? |
| 3 | Database | Constraints, indexes, least-privilege user, migrations, connection limits? |
| 4 | Rate limiting | Are login, signup, reset, and expensive endpoints throttled? |
| 5 | Password reset | Single-use, expiring, hashed tokens; no account enumeration? |
| 6 | Rollbacks | Can a bad deploy or migration be undone quickly? |
| 7 | Backups | Automated, off-site, encrypted, and restore-tested? |
| 8 | Usage limits | Per-user quotas, upload/size caps, cost caps on paid APIs? |
| 9 | Analytics | Are key events tracked without leaking personal data? |
| 10 | Input cleaning | Server-side validation, output encoding, upload checks? |
| 11 | Error handling | Safe messages to users, full detail in logs, no stack traces leaked? |
| 12 | Log flow | Structured logs, request IDs, no secrets in logs, retention? |
| 13 | Monitor and alerts | Someone is told within minutes when it breaks? (build with `monitor-alerts-builder`) |

The criteria, how to verify each one, and severity guidance are in `references/checklist.md`. Read it before judging.

## Procedure

1. **Scope.** Identify the stack and what the app does (web, mobile, API, worker). Ask only if you cannot tell from the repo. Note what is out of reach (production infra, cloud console, third-party dashboards) so those items are marked UNKNOWN rather than guessed.
2. **Run the scanner** for fast evidence (it is heuristic, so treat hits as leads, not verdicts):
   ```bash
   python3 <skill-dir>/scripts/scan.py <project-root> --format markdown > /tmp/readiness-scan.md
   ```
   Add `--format json` if you want to process it. The scanner never prints full secret values.
3. **Verify by reading code.** For every area, open the real files behind the scanner's leads and look for what the scanner cannot see: is the rate limiter actually applied to the login route, does the reset token get invalidated after use, does the backup have a restore test. Use `references/checklist.md` as the guide.
4. **Rate each area** with one of:
   - `PASS` evidence shows it is handled
   - `WARN` partly handled or handled inconsistently
   - `FAIL` missing or clearly broken
   - `UNKNOWN` cannot be determined from the repo (say what to check and where)
5. **Report** using `references/report-template.md`. Order fixes by severity: anything that can leak data or take over accounts first, then data loss, then abuse and cost, then polish.
6. **Offer to fix**, one finding at a time, and re-run the scanner after fixes.

## Rules

- Report only what you saw in the files. Quote the path and line for each finding.
- Never paste a real secret into the report or chat; show the first 4 characters and the file location.
- If you find a committed live secret, say it must be **rotated**, not just removed from the file, because git history keeps it.
- Do not run load tests, port scans, or exploit attempts against anything you do not own.
- A passing scan is not a security audit. Say so in the report summary.
