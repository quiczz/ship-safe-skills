---
name: api-security-guard
description: Audit, harden and monitor an API against 12 rules - authenticate every call, check object access, rate limit, validate input, HTTPS only, short-lived tokens, least-privilege keys, no secrets in URLs, log auth failures, version the API, limit response data, inventory endpoints. Includes an endpoint inventory scanner and monitoring alerts. Use when asked to review API security, check for BOLA/IDOR, list all endpoints, or build API monitoring. Use proactively whenever you add or change an API route, authentication or a token.
---

# API Security Guard

Checks an API against 12 rules (mapped to the OWASP API Security Top 10, 2023), builds the missing protections, and sets up monitoring so attacks and drift are noticed.

**Runs on its own:** when Claude adds or changes a route, auth or a token, it checks the change against the 12 rules, and edited files are scanned for hard-coded secrets, wildcard CORS, secrets in URLs and turned-off TLS checks.

## The 12 rules

| # | Rule | OWASP API 2023 | Core question |
|---|------|----------------|---------------|
| 1 | Authenticate every call | API2 | Is there any route a stranger can call that should not be public? |
| 2 | Check object access | API1, API5 | Can user A read or change user B's record by changing an ID? Can a normal user call an admin function? |
| 3 | Rate limit | API4, API6 | Are login, reset, search, and costly or business-critical flows throttled? |
| 4 | Validate input | API3, API7 | Is every field type-checked, size-limited, allow-listed at the boundary? Any server-side fetch of user URLs? |
| 5 | HTTPS only | API8 | Redirect or reject plain HTTP? HSTS? No plain-text tokens? |
| 6 | Short-lived tokens | API2 | Access tokens in minutes, refresh tokens rotated and revocable? |
| 7 | Least-privilege keys | API5, API8 | Keys and service accounts scoped to read-only or minimum permissions? |
| 8 | No secrets in URLs | API8 | Any `?token=`, `?api_key=` in routes, links or clients? |
| 9 | Log auth failures | API8 | 401/403/lockouts logged with IP, user, route, and alerted on spikes? |
| 10 | Version your API | API9 | Are old versions tracked, deprecated with dates, and retired? |
| 11 | Limit response data | API3 | Only needed fields returned? No hashes, internal IDs, or other users' data? Pagination caps? |
| 12 | Inventory endpoints | API9, API10 | Is there a current list of every endpoint, including old, internal, debug and third-party ones? |

Details, how to verify and fix each rule: `references/rules.md`. Alerts for each: `references/monitoring.md`.

## Procedure

1. **Inventory first (rule 12).** Run:
   ```bash
   python3 <skill-dir>/scripts/api_inventory.py <project-root> > /tmp/api-inventory.md
   ```
   It lists routes with auth evidence, version, object-ID parameters, and spec/code drift, and flags tokens in URLs, plain `http://`, long-lived tokens and data-exposure leads. Read its limits: it is heuristic. "none seen" means no auth pattern matched near the route. Apps with custom auth wrappers will show false alarms, so check how auth is actually applied (middleware, router-level dependency, gateway) and tell the user.
2. **Verify by reading code.** For every route flagged `none seen`, open it and decide: public by design, protected elsewhere (gateway, router-level), or a real gap. For every route with an object-ID parameter, find the line that proves the record belongs to the caller (a query filtered by the user or tenant, or a policy check). No such line means a probable BOLA/IDOR: rule 2 FAIL.
3. **Walk the 12 rules** using `references/rules.md`; rate each `PASS / WARN / FAIL / UNKNOWN` with `path:line` evidence. Items needing infrastructure access (gateway config, TLS termination, key scopes in a cloud console) are `UNKNOWN`, listing exactly where to look.
4. **Report** in this order: broken access control (rules 1, 2) first, then credentials and transport (5, 6, 7, 8), then abuse and data exposure (3, 4, 11), then visibility (9, 10, 12).
5. **Fix** one finding at a time, smallest safe change, and add a test that proves the fix (for rule 2: a test where user B requests user A's object and gets 403 or 404).
6. **Monitor.** Add the alerts from `references/monitoring.md` using the `monitor-alerts-builder` skill if installed. At minimum: auth-failure spike, 403/404 probing per user, rate-limit hits, traffic on deprecated versions, and requests to routes not in the inventory.
7. **Keep the inventory alive.** Commit the OpenAPI spec (or the inventory output), and fail CI when a route exists in code but not in the spec.

## Rules of engagement

- Read code and configs. Do not send requests to any live system you do not own, and do not run exploit or fuzzing tools unless the user owns the target and asks.
- Never print real tokens or keys; show the first 4 characters and the location.
- If a secret was exposed in a URL or log, say it must be rotated.
- A clean scan is not proof of security. Say so in the summary.
