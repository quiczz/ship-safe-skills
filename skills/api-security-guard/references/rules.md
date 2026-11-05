# The 12 API rules: verify and fix

For each rule: what to look for, the typical failure, and the fix. Severity in brackets is a default; raise it for payments, health, or children's data.

## 1. Authenticate every call [critical]
Look for: a default-deny setup (auth applied to the whole router/app, with an explicit public allow-list) rather than per-route opt-in. Check debug, admin, export, metrics, health-detail, GraphQL, websocket and webhook routes.
Failure: a new route is added and forgotten; `/internal/*` or `/debug/*` reachable from the internet; webhooks accepted without signature check.
Fix: global auth middleware or router-level dependency; explicit `@public` marker for the few open routes; verify webhook signatures (HMAC) and timestamps.

## 2. Check object access [critical]
Look for: every route with an ID (`/orders/:id`, `?user_id=`, body `accountId`) and the line that ties the record to the caller. Also function-level checks: can a normal user call `DELETE`, `/admin/*`, role changes?
Failure: `Order.findById(req.params.id)` with no owner filter (BOLA/IDOR); trusting `userId` from the request body; admin routes only hidden in the UI.
Fix: query by `{ id, ownerId: caller.id }` (or tenant); central policy function; deny by default; use unguessable IDs as defense in depth, never as the control. Test: user B requests user A's object, expect 403/404.

## 3. Rate limit [high]
Look for: limits on login, signup, password reset, OTP/SMS/email sends, search, exports, expensive queries, and business flows (checkout, coupon redeem, ticket purchase).
Failure: limiter exists but is not attached to auth routes; only per-IP limit (bypassed by many IPs) with no per-account limit; in-memory limiter behind many instances.
Fix: per-IP and per-account limits in a shared store; stricter on auth; `429` with `Retry-After`; per-key quotas; cost caps on paid APIs; bot protection on sensitive flows.

## 4. Validate input [high]
Look for: a schema (zod, pydantic, joi, DTO validators) on body, query, params and headers; max lengths, array sizes, page sizes; allow-listed enums; file type and size checks; any server-side request to a user-supplied URL (SSRF); parameterized queries.
Failure: validation only in the front end; mass assignment (`User.update(req.body)` lets callers set `role`); unbounded `limit`; fetching user URLs without an allow-list.
Fix: strict schemas that reject unknown fields; explicit field allow-lists for writes; URL allow-list and block private ranges (169.254.169.254, 10/8, 172.16/12, 192.168/16, localhost); reject, do not "clean", malformed input.

## 5. HTTPS only [high]
Look for: HTTP to HTTPS redirect or no port 80 at all; HSTS header; `http://` base URLs in clients and config; cookies with `Secure`, `HttpOnly`, `SameSite`; TLS 1.2+.
Failure: API reachable on plain HTTP; mobile app allows cleartext; internal services talking plain HTTP carrying tokens.
Fix: terminate TLS at the edge; HSTS; reject cleartext; cert expiry alert.

## 6. Short-lived tokens [high]
Look for: access token lifetime (target 5 to 15 minutes), refresh token rotation with reuse detection, server-side revocation, `aud` and `iss` checked, strong signing algorithm pinned (no `alg: none`), logout that really revokes.
Failure: 30-day or non-expiring access tokens; tokens stored in `localStorage` with an XSS-prone app; no way to revoke after a leak.
Fix: short access tokens plus rotating refresh tokens; deny-list or session table for revocation; bind tokens to audience; rotate signing keys.

## 7. Least-privilege keys [high]
Look for: scopes on API keys; separate keys per client and per environment; database users and cloud roles with only needed permissions; keys with expiry; admin keys not used by the app.
Failure: one all-powerful key shared by every service; service account with owner/admin rights; no way to see what a key can do.
Fix: scoped keys (read-only by default), per-service identities, expiry and rotation, inventory of keys with owners.

## 8. No secrets in URLs [high]
Look for: `?token=`, `?api_key=`, `?password=` in routes, client code, emails, redirects; secrets in path segments.
Failure: tokens land in access logs, browser history, proxies, referrer headers, analytics.
Fix: send secrets in the `Authorization` header or a POST body; one-time, short-lived, single-use tokens where a link is unavoidable (email verification, magic link); scrub query strings from logs.

## 9. Log auth failures [medium to high]
Look for: logging of 401, 403, failed login, token verification errors, lockouts, with timestamp, IP, user or key ID, route, user agent (never the password or token).
Failure: failures are swallowed; logs lack IP or route; no alert, so credential stuffing runs for weeks.
Fix: structured auth-failure events; alert on spikes and on one source trying many accounts or many object IDs (see `monitoring.md`).

## 10. Version your API [medium]
Look for: `/v1/`, `/v2/` or header versioning; a deprecation policy with dates; `Deprecation` and `Sunset` response headers; traffic metrics per version.
Failure: old versions linger with weaker auth; nobody knows who still uses v1; breaking changes shipped silently.
Fix: version from day one; document and announce sunset dates; measure per-version traffic; remove old versions on schedule, and apply security fixes to all live versions until then.

## 11. Limit response data [high]
Look for: explicit response schemas/serializers; no `res.json(user)` of a raw database row; no password hashes, tokens, internal flags, other users' emails; pagination with a max page size; field filtering by role.
Failure: the API returns the whole row and the UI hides fields (BOPLA / excessive data exposure); list endpoints return other tenants' data; error bodies include stack traces.
Fix: response DTOs with allow-listed fields; separate admin and public shapes; maximum page size; test that sensitive fields never appear.

## 12. Inventory endpoints [medium, but it enables everything else]
Look for: an up-to-date OpenAPI spec or generated inventory; list of hosts, environments, versions, owners; shadow and zombie APIs (old, undocumented, debug); third-party APIs you call and what data you send them.
Failure: staging or v0 endpoints still public; nobody owns an endpoint; the spec drifted from the code.
Fix: generate the spec from code; CI fails when code routes are missing from the spec; quarterly review of the inventory, with owner and data classification per endpoint; periodically compare against gateway/access logs for undocumented routes.
