---
name: monitor-alerts-builder
description: Design and build monitoring and alerting for an application - health endpoint, uptime checks, error tracking, alert rules (errors, latency, auth abuse, rate limits, backups, spend, certificates), notification channels and runbooks. Use when asked to add monitoring, set up alerts, or fix the "monitor and alerts" gap from app-readiness-audit. Use proactively when an app is about to be deployed or launched with no alerting.
---

# Monitor and Alerts Builder

Goal: a human is told within minutes when something important breaks, with enough context to act, and is not woken up by noise.

**Runs on its own:** when a deploy or launch is being prepared and there is no health check or alerting, Claude offers to build it.

## Procedure

1. **Discover what exists.** Look for: a health endpoint, an error-tracking SDK (Sentry etc.), a metrics library, logs, a cron or CI that could run checks, and where the app is hosted. Run `app-readiness-audit` scan if available. Do not add a second tool if one is already wired in.
2. **Ask three things only if the repo cannot answer them:** where alerts should go (Slack, Discord, Telegram, email, PagerDuty), who owns them, and the hosting platform.
3. **Pick the lightest stack that fits** (see table). Prefer the host's built-in monitoring plus one error tracker over running your own Prometheus.
4. **Build in this order** (each step is useful on its own):
   1. Health endpoint (`/healthz` for "process is up", `/readyz` for "database and dependencies reachable").
   2. Uptime check hitting `/readyz` from outside, every 1 minute, alerting after 2 failures.
   3. Error tracking with release and environment tags, user ID but no email or tokens.
   4. Alert rules from `references/alert-catalog.md` (start with the "Day one" set).
   5. Notification channel wired and **tested by firing a fake alert**.
   6. One runbook per alert, from `templates/runbook-template.md`.
5. **Write out what you built**: where each alert is defined, the threshold and why, who gets it, and the runbook link.

## Choosing a stack

| Situation | Suggested setup |
|-----------|-----------------|
| Small app, one server or PaaS | Hosted uptime check + Sentry + `templates/healthcheck.py` on cron for backups/disk/certs |
| Kubernetes or many services | Prometheus + Alertmanager using `templates/alert-rules.prometheus.yml`, Grafana for dashboards |
| Serverless | Provider metrics (CloudWatch, Vercel, Cloudflare) + Sentry + external uptime check |
| Mobile app | Crash reporting (Crashlytics or Sentry) + backend alerts above + release health |

## Alert design rules

- **Alert on symptoms users feel** (errors, slowness, downtime) and on **things that silently rot** (backup age, certificate expiry, queue growth, spend). Do not alert on raw CPU unless it predicts an outage.
- Every alert needs: a name, a threshold with a duration (`for: 5m`), a severity, an owner, and a runbook link. If you cannot write what the person should do, delete the alert.
- Two severities are enough: **page** (act now, customers affected) and **ticket** (fix this week).
- Use a duration or multiple failures before firing, so one blip does not page anyone.
- Group and de-duplicate; send "resolved" messages; repeat reminders for unacknowledged pages only.
- Never put secrets, tokens, or personal data in alert text.
- Test alerts after any change. An untested alert is a guess.

## Templates in this skill

- `templates/healthcheck.py`: dependency-free script. Checks URLs, disk space, TLS certificate expiry, and backup freshness; posts to a Slack/Discord/Telegram/generic webhook. Run with cron or a scheduler. Try `--help` and `--selftest`.
- `templates/alert-rules.prometheus.yml`: ready-to-adapt Prometheus rules.
- `templates/runbook-template.md`: one-page runbook format.
- `references/alert-catalog.md`: what to alert on, default thresholds, and why.
- Security alert sets from sibling skills (use them when the user asks for API or Zero Trust monitoring): `../api-security-guard/references/monitoring.md` (auth failures, credential stuffing, object probing, unknown routes, deprecated versions) and `../zero-trust-review/references/monitoring.md` plus `../zero-trust-review/templates/aws-eventbridge-patterns.json` (logging tampering, MFA, admin grants, exposure, service identity). If those skills are not installed, use the security rows in `references/alert-catalog.md`.
