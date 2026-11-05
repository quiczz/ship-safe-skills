# API security monitoring

Build these with the `monitor-alerts-builder` skill. Thresholds are starting points; tune after a week of real traffic. Alert text must never contain tokens, passwords, or full personal data.

## Log fields you need (rule 9)

One JSON line per request or auth event: `timestamp, request_id, method, route_template (not raw URL), status, user_id or key_id, tenant_id, source_ip, user_agent, latency_ms, api_version, auth_result (ok/fail/expired/revoked)`.
Log the **route template** (`/orders/:id`), not the raw URL, so IDs and any stray tokens do not pollute logs and aggregation works.

## Alert catalog

| Alert | Rule | Detection | Default threshold | Severity |
|-------|------|-----------|-------------------|----------|
| Auth failure spike | 1, 6, 9 | count of 401 | above 10x the same hour last week, for 10 min | ticket (page if paired with a success after many failures) |
| Credential stuffing | 3, 9 | one IP or ASN failing logins across many accounts | more than 20 distinct accounts failed from one IP in 10 min | page |
| Brute force on one account | 3, 9 | failed logins per account | more than 10 in 10 min | ticket (and lock or step-up) |
| Success after many failures | 9 | login ok following 10+ failures for same account | any | page |
| Object probing (BOLA) | 2 | one caller gets many 403/404 on ID routes, or requests many distinct IDs | more than 30 distinct object IDs with 403/404 in 5 min | page |
| Forbidden spike by function | 2 | 403 on admin or privileged routes by non-admin users | any burst of 5+ in 5 min | ticket |
| Rate-limit pressure | 3 | share of 429 responses | above 5% for 10 min, or one key above 50% of its own traffic | ticket |
| Unknown route traffic | 12 | requests to routes not in the inventory/spec | any 2xx on an unknown route; 404 flood from one IP is ticket | ticket / page |
| Deprecated version in use | 10 | traffic on versions past their sunset date | any after sunset; weekly report before | ticket |
| Token in URL | 8 | query string matching `token|api_key|password|secret` in access logs | any | ticket (rotate the leaked value) |
| Plain HTTP request | 5 | requests on port 80 or `X-Forwarded-Proto: http` | any non-redirect response | ticket |
| Long-lived token issued | 6 | token with lifetime above policy | any | ticket |
| New or changed API key | 7 | key created, scope widened, admin scope granted | any admin-scope grant | page for admin, ticket otherwise |
| Large response / bulk read | 11 | response bytes or rows per caller | above 10x that caller's daily norm | ticket |
| Mass data export | 11 | export routes or pagination crawl by one caller | above norm, or full-table crawl pattern | page |
| Webhook signature failures | 1 | failed signature checks | more than 5 in 10 min | ticket |
| Spec drift | 12 | CI check: routes in code but not in spec | any | block the merge |
| Error-rate on auth service | availability | 5xx from the auth/token endpoint | above 1% for 5 min | page (nobody can log in) |

## Example queries (adapt to your log store)

Credential stuffing (SQL-like):
```sql
SELECT source_ip, COUNT(DISTINCT user_id_attempted) AS accounts, COUNT(*) AS failures
FROM auth_events
WHERE auth_result = 'fail' AND ts > now() - interval '10 minutes'
GROUP BY source_ip HAVING COUNT(DISTINCT user_id_attempted) > 20;
```

BOLA probing:
```sql
SELECT caller_id, COUNT(DISTINCT object_id) AS ids
FROM access_log
WHERE status IN (403, 404) AND route_template LIKE '%:id%' AND ts > now() - interval '5 minutes'
GROUP BY caller_id HAVING COUNT(DISTINCT object_id) > 30;
```

Unknown routes: export the route list from `api_inventory.py --format json`, load it as a lookup, and alert on `route_template NOT IN inventory` with status below 400.

Token in URL (grep-style): `?(access_)?token=|[?&]api_?key=|[?&]password=` on raw access logs; also strip these values before storing logs.

## Prometheus-style counters to expose

`http_requests_total{route,method,status,version}`, `auth_failures_total{reason}`, `rate_limited_total{route}`, `authz_denied_total{route}`. Keep labels low-cardinality: never label by user ID, IP, or raw URL.

## After an alert

Check the request IDs, block or step-up the source, rotate any credential involved, add a regression test, then record what would have caught it sooner.
