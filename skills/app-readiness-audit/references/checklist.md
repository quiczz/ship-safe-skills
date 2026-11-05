# Readiness checklist

For each area: what good looks like, how to check it in a repo, and what usually goes wrong. Severity in brackets is the default; raise it if the app handles money, health, or children's data.

## 1. Mobile
Good: viewport meta tag; layouts work at 360px width; touch targets at least 44px; no hover-only actions; PWA manifest and icons if installable; native apps declare only the permissions they use, handle offline/poor network, and support deep links.
Check: `<meta name="viewport">`, CSS media/container queries or a responsive framework, `manifest.json`, `AndroidManifest.xml` permissions, `Info.plist` usage strings, React Native/Flutter/Capacitor config.
Common failures: fixed pixel widths, 100vh bugs on mobile browsers, tiny tap targets, API base URL pointing at localhost in the mobile build, missing privacy strings (store rejection). [medium]

## 2. Secret keys
Good: secrets only from environment or a secrets manager; `.env` in `.gitignore`; a `.env.example` with fake values; no secret in client bundles (anything prefixed `NEXT_PUBLIC_`, `VITE_`, `REACT_APP_`, `EXPO_PUBLIC_` is public); separate keys per environment; a documented rotation step.
Check: scanner hits, `git log -p -S"sk_live"` style searches for history leaks, build config that inlines env vars into the client.
Common failures: service-role or admin keys in frontend env, keys in `docker-compose.yml`, secrets in CI logs, same key in dev and prod. [critical]

## 3. Database
Good: least-privilege app user (not superuser); migrations in version control; primary keys and foreign keys; NOT NULL and unique constraints; indexes on foreign keys and common filters; connection pooling; no raw string-built SQL; row-level access checks per user.
Check: migration folder, schema files, ORM models, any `query(` or `execute(` with string concatenation or template literals.
Common failures: missing indexes, N+1 queries, SQL built with string concatenation, one user can read another user's rows by changing an ID (IDOR). [high]

## 4. Rate limiting
Good: limits on login, signup, password reset, OTP/SMS/email sending, search, file upload, and any paid-API call; limits keyed by IP and by account; `429` with `Retry-After`; a shared store (Redis) when running more than one instance.
Check: limiter middleware and where it is mounted; per-route config.
Common failures: limiter exists but is not attached to auth routes; in-memory limiter behind multiple instances; trusting `X-Forwarded-For` without a trusted proxy setting. [high]

## 5. Password reset
Good: token is random (at least 128 bits), stored hashed, expires in 15 to 60 minutes, single use, invalidated when the password changes; same response whether or not the email exists; rate limited; all sessions revoked after reset; user notified by email; reset link uses HTTPS.
Check: reset handler, token model, email template, session handling.
Common failures: predictable tokens (timestamp, user id), tokens not expiring, "no such user" message (account enumeration), reset link contains the password or email in a loggable URL. [high]

## 6. Rollbacks
Good: previous release artifact kept and redeployable in one command; database migrations are backward compatible (expand, then contract) or have tested down-migrations; feature flags for risky changes; a written rollback step; deploys tagged by commit.
Check: CI/CD config, deploy scripts, migration tool settings, README/runbook.
Common failures: destructive migrations (drop column) in the same release as the code change; no way to redeploy the last good build; secrets/config changes not versioned. [high]

## 7. Backups
Good: automated schedule; stored in a different account/region from the primary; encrypted; retention policy; a restore has been tested and timed; uploads/object storage covered, not just the database; backup failure raises an alert.
Check: managed DB backup settings (usually outside the repo, so often UNKNOWN), cron/CI jobs, backup scripts, restore documentation.
Common failures: backups exist but have never been restored; backups stored next to the database; no alert when a backup silently fails. [critical for data loss]

## 8. Usage limits
Good: per-user and per-plan quotas; maximum request body and upload size; pagination caps; timeouts on outbound calls; spend caps and alerts on paid APIs (LLM, SMS, email, maps); abuse controls on free tiers.
Check: quota middleware, upload config (`limits`, `maxFileSize`), provider billing settings (often UNKNOWN).
Common failures: unlimited LLM calls per user, unbounded `limit` query parameter, no cap on file size, no billing alert. [high, because it becomes a money problem]

## 9. Analytics
Good: a small event plan (signup, activation, key feature use, payment, error); consistent event names; no passwords, tokens, or full personal data in events; consent respected where required; server-side events for critical conversions.
Check: analytics SDK usage, event calls, consent banner logic.
Common failures: PII in event properties, tracking before consent, events fired twice, no way to see the funnel. [medium]

## 10. Input cleaning
Good: server-side validation with a schema library (zod, pydantic, joi, etc.) on every endpoint; length and type limits; output encoding (frameworks escape by default, so look for `dangerouslySetInnerHTML`, `innerHTML`, `v-html`); parameterized queries; upload type checked by content, size limited, stored outside the web root; URL fetches guarded against SSRF; CSRF protection for cookie sessions.
Check: validation at route boundary, raw HTML sinks, file handling, shell/`eval` use.
Common failures: validation only in the browser, trusting client-sent role/price/user id, `eval` or `exec` with user input, path traversal in file downloads. [critical for injection, high otherwise]

## 11. Error handling
Good: a global error handler; users see a friendly message and an error ID; stack traces and SQL errors never reach the client; unhandled promise rejections handled; timeouts and retries with backoff on outbound calls; graceful degradation.
Check: error middleware, `try/catch` around external calls, production `DEBUG` flags.
Common failures: `DEBUG=True` in production, returning `err.message` or `err.stack` to the client, swallowed exceptions (`catch {}`), crash on the first bad request. [high]

## 12. Log flow
Good: structured (JSON) logs with level, timestamp, request ID, user ID (not email); one request ID traced through services; no secrets, tokens, passwords, or full card numbers in logs; logs shipped off the box; retention and access control; audit log for sensitive actions (login, permission changes, deletes).
Check: logger setup, middleware that adds request IDs, grep for logging of `req.body`/headers.
Common failures: `console.log(req.body)` containing passwords, no request ID so incidents cannot be traced, logs lost on restart. [medium to high]

## 13. Monitor and alerts
Good: uptime check on a real health endpoint; error tracking (Sentry or similar); alerts on error rate, latency, failed logins spike, rate-limit spike, queue depth, disk, certificate expiry, backup failure, and spend; alerts go to a channel a human reads, with an owner and a runbook link; alerts are tested.
Check: health endpoint, error-tracking init, alert rule files, on-call docs.
Common failures: dashboards without alerts, alerts to an unread email, alert on every error (noise) so people mute it. [high]
Build these with the `monitor-alerts-builder` skill.
