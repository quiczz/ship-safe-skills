# Runbook: {{alert name}}

Owner: {{person or team}}   Severity: {{page | ticket}}   Last tested: {{date}}

## What this means
One or two sentences in plain language. What are users experiencing?

## Check first (2 minutes)
1. {{dashboard or command}}
2. {{log query}}
3. Was there a deploy or config change in the last hour? ({{where to look}})

## Likely causes and fixes
| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| {{}} | {{}} | {{command or step}} |

## Rollback
{{exact command or button to redeploy the last good version}}

## Escalate if
Not improving after {{20}} minutes, or data may be lost: contact {{person}} at {{channel}}.

## After it is resolved
- Post a short update ("resolved, cause, follow-up").
- Add notes to the incident log: cause, time to detect, time to fix, one improvement.
