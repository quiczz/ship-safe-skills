# Readiness report: {{app name}}

Date: {{date}}  |  Reviewed: {{commit or folder}}  |  Stack: {{stack}}

**Summary:** {{one or two sentences: ready / not ready, and the 1 to 3 things that matter most}}

This is a code review plus heuristic scan. It is not a penetration test and cannot see production settings.

## Scorecard

| # | Area | Rating | Evidence |
|---|------|--------|----------|
| 1 | Mobile | PASS / WARN / FAIL / UNKNOWN | path:line or "not found" |
| 2 | Secret keys | | |
| 3 | Database | | |
| 4 | Rate limiting | | |
| 5 | Password reset | | |
| 6 | Rollbacks | | |
| 7 | Backups | | |
| 8 | Usage limits | | |
| 9 | Analytics | | |
| 10 | Input cleaning | | |
| 11 | Error handling | | |
| 12 | Log flow | | |
| 13 | Monitor and alerts | | |

## Fix list (most urgent first)

For each item:

1. **{{title}}** [critical / high / medium / low]
   - Where: `path:line`
   - Problem: one sentence
   - Fix: one or two concrete sentences (or a patch)
   - How to confirm it is fixed: one check

## Needs a human check (UNKNOWN items)

- {{item}}: look in {{place}} for {{what}}

## What was not covered

- {{e.g. production cloud settings, third-party dashboards, load behaviour}}
