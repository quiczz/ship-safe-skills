# Alert catalog

Thresholds are starting points. Tune them after one week of real data. "Day one" alerts are the minimum set.

| Alert | Day one | Default threshold | Severity | Why it matters |
|-------|:------:|-------------------|----------|----------------|
| Site/API down | yes | `/readyz` fails 2 checks in a row (1 min interval) | page | Users cannot use the product |
| HTTP 5xx rate | yes | above 2% of requests for 5 min | page | Server errors users see |
| New error type / error spike | yes | Sentry: new issue in production, or 10x baseline in 10 min | ticket (page if paired with 5xx) | Regressions after deploys |
| Latency (p95) | yes | above 1.5x normal, or above 2 s, for 10 min | ticket | Slowness drives users away |
| Backup age | yes | newest backup older than 26 h (daily job) | page | Silent backup failure means data loss later |
| Backup restore test | | last successful test older than 35 days | ticket | Backups that are never restored are unproven |
| Disk space | yes | above 80% warn, above 90% page | ticket / page | Databases and logs fill disks |
| TLS certificate expiry | yes | under 14 days | ticket (page under 3 days) | Expired certificates take the site down |
| Failed login spike | | above 10x baseline for 10 min | ticket | Credential stuffing or an attack |
| Rate-limit hits | | above 5% of requests returning 429 for 10 min | ticket | Abuse, or limits set too low |
| Password-reset volume | | above 5x baseline for 10 min | ticket | Account takeover attempts or email abuse |
| Queue depth / age | | oldest job older than 5 min, or depth growing 15 min | ticket | Workers stuck |
| Database connections | | above 80% of max for 10 min | ticket | Pool exhaustion causes outages |
| Database replication lag / slow queries | | lag above 30 s; query over 2 s | ticket | Stale reads and timeouts |
| Third-party API failures | | above 5% errors for 10 min | ticket | Payment, email, SMS, LLM outages |
| Usage / spend | yes | provider budget at 50%, 80%, 100% | ticket / page | Runaway cost from loops or abuse |
| Deploy failed / rollback used | | any | ticket | Team should know |
| Memory / restart loops | | more than 3 restarts in 15 min | page | Crash loops |
| Cron / scheduled job missed | | no success heartbeat in 2x interval | ticket | Silent job failure (use a heartbeat ping) |
| Credential stuffing | | one source fails logins on more than 20 accounts in 10 min | page | Account takeover in progress |
| Object probing (BOLA/IDOR) | | one caller gets 403/404 on more than 30 distinct object IDs in 5 min | page | Someone is enumerating other users' data |
| Request to unknown route | | 2xx on a route not in the API inventory | ticket | Shadow or forgotten endpoint is live |
| Audit logging stopped or silent | | trail disabled, or a log source sends nothing for 15 min | page | Attackers hide evidence first |
| Admin grant / MFA removed / root used | | any | page | Privilege escalation or account takeover |
| Public exposure opened | | security group `0.0.0.0/0` on admin/DB port, bucket made public | page | Instant data-exposure risk |
| Mobile crash-free sessions | | below 99% for a release | ticket | Bad app release |

## Notification channels

- Page: phone push or SMS (PagerDuty, Opsgenie, or Telegram bot to a person's phone).
- Ticket: a team chat channel that someone reads daily, or the issue tracker.
- Email alone is not a channel for pages.

## Message format

```
[PAGE] api-prod: 5xx rate 6.4% (threshold 2%) for 5 min
Impact: some API requests are failing
Since: 14:02 UTC   Release: 2026.11.05-3
Dashboard: <link>   Runbook: <link>
```

## After an alert fires

Record: time detected, time fixed, cause, what would have caught it earlier. Add or tune one alert per incident.
