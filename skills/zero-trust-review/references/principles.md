# The 12 principles: evidence, quick wins, monitoring

Format: what it means, evidence in the repo, what only the owner knows, quick wins, and the signal to monitor.

## 1. Verify every request
Meaning: no implicit trust from network location or a prior login. Each request is authenticated and authorized against policy, internal calls included.
Repo evidence: auth middleware on all routes (default deny), authorization policies (OPA, Cerbos, Casbin, Istio AuthorizationPolicy), API gateway authorizers.
Ask: is there an enforcement point in front of internal services? Are there "trusted network" bypasses?
Quick wins: default-deny at the router or gateway; remove IP-allow-list-only protection for sensitive services; run the `api-security-guard` inventory.
Monitor: requests that reach services without an identity attached; denied-request rate; routes with no auth.

## 2. Strong identity
Meaning: every human and machine has one authoritative, verifiable identity.
Repo evidence: SSO/OIDC/SAML integration, CI federation (OIDC) instead of static keys. Risks: static cloud keys, shared logins, default credentials.
Ask: which identity provider is the source of truth? Are there local accounts or shared admin logins?
Quick wins: SSO for every internal tool; replace CI cloud keys with OIDC role assumption; delete unused accounts; no shared credentials.
Monitor: logins outside SSO; new local accounts; dormant accounts that suddenly sign in.

## 3. MFA everywhere
Meaning: a password alone is never enough. Prefer phishing-resistant factors (passkeys, FIDO2 security keys) over SMS.
Repo evidence: MFA/TOTP/WebAuthn code or IdP policy as code; IAM policies requiring `aws:MultiFactorAuthPresent`.
Ask: is MFA enforced (not just available) for all users, admins, break-glass accounts, and API/CLI access?
Quick wins: enforce MFA in the IdP; hardware keys for admins; require MFA for console and CLI role assumption.
Monitor: sign-ins without MFA; MFA disabled or factor reset; new MFA device registered followed by sensitive action.

## 4. Device health
Meaning: access depends on the device being managed, patched, encrypted and compliant.
Repo evidence: rarely in code. Look for device posture checks (Cloudflare Access/WARP, Tailscale posture, BeyondCorp/Access Context Manager, Intune/Jamf integration).
Ask: is there MDM/EDR? Does conditional access use compliance state?
Quick wins: conditional access rule "managed and compliant device for admin apps"; disk encryption and OS-update baselines.
Monitor: access from unmanaged devices; compliance state changes; EDR alerts correlated with sessions.

## 5. Least privilege (JEA, Just Enough Administration)
Meaning: each identity gets only the permissions its task needs, scoped to specific resources.
Repo evidence (risks): `Action: "*"`, `Resource: "*"`, AdministratorAccess, cluster-admin, `GRANT ALL`, containers as root or privileged, CI `permissions: write-all`. Good: scoped roles, permissions boundaries, `runAsNonRoot`, read-only CI tokens.
Ask: results of an IAM access review; unused permissions (cloud "access advisor").
Quick wins: replace wildcards with listed actions/resources; CI default `contents: read`; per-service database users; remove unused roles.
Monitor: new admin grants; policy changes; use of high-risk permissions; permissions unused for 90 days (report).

## 6. Just-in-time access
Meaning: elevated access is requested, approved, time-limited (an hour, not forever), and removed automatically.
Repo evidence: assume-role patterns with short session durations, PIM/Teleport/Vault dynamic credentials, break-glass procedures. Risk: permanent admin attachments, long-lived IAM user keys.
Ask: how do admins get elevated rights today? Do grants expire? Is there an approval trail?
Quick wins: role assumption with 1-hour sessions; time-boxed group membership; break-glass account sealed and alerted.
Monitor: elevation requests and approvals; elevation outside business hours; break-glass use (always page).

## 7. Microsegmentation
Meaning: small zones with explicit allow rules, so a breach in one place cannot spread freely (limits lateral movement).
Repo evidence: Kubernetes NetworkPolicy, security groups per tier, private subnets, service mesh policies. Risks: `0.0.0.0/0` ingress, published database ports, host networking, no NetworkPolicy.
Ask: can the web tier reach the database directly? Can any pod reach the metadata service or other namespaces?
Quick wins: default-deny NetworkPolicy plus explicit allows; databases only reachable from their app; block instance metadata from workloads that do not need it; remove public ingress on SSH/DB ports.
Monitor: new `0.0.0.0/0` rules; denied connections spikes; unexpected east-west connections (flow logs).

## 8. Encrypt internally
Meaning: encryption in transit and at rest even between internal services; the internal network is not trusted.
Repo evidence: TLS/mTLS (service mesh `STRICT`), `sslmode=require/verify-full`, encrypted storage and KMS keys. Risks: `rejectUnauthorized: false`, `sslmode=disable`, internal `http://`, `encrypted = false`, public buckets.
Ask: is internal traffic TLS? Who manages keys, and is rotation automated? Are backups encrypted?
Quick wins: enforce TLS to databases and caches; mesh mTLS in STRICT mode; default encryption on storage; remove TLS-skip flags.
Monitor: plaintext connections; certificate expiry; KMS key policy changes and unusual decrypt volume.

## 9. Continuous checks
Meaning: trust is re-evaluated during use and can be revoked immediately when context changes (new location, risky behavior, device falls out of compliance).
Repo evidence: short token lifetimes, refresh rotation, revocation or introspection endpoints, step-up auth, risk-based rules. Risk: tokens or sessions lasting days or weeks.
Ask: can you cut off one user, device or token within minutes? Does anything re-check posture mid-session?
Quick wins: access tokens of 5 to 15 minutes; server-side session revocation; step-up for sensitive actions; session kill switch runbook.
Monitor: impossible travel; new device plus sensitive action; token reuse after revocation; revocation latency (time from request to effect).

## 10. Log everything
Meaning: complete, tamper-resistant audit trail of every access attempt, success and failure, with identity, resource, decision and source.
Repo evidence: CloudTrail/audit logs enabled and multi-region, Kubernetes audit policy, flow logs, structured app logs shipped to a SIEM. Risk: logging disabled, logs on the same host as the workload.
Ask: where do logs go, who can delete them, how long are they kept, which systems are not covered?
Quick wins: organization-wide trail to a separate, write-once account; log retention policy; log auth success and failure; time sync.
Monitor: logging stopped or reconfigured (always page); log volume drop from a source (silence is a signal); log deletion attempts.

## 11. Assume breach
Meaning: design so a compromise of one account, host or agent is contained and recoverable.
Repo evidence: container hardening (`allowPrivilegeEscalation: false`, drop capabilities, read-only filesystem, seccomp), sandboxes, immutable or versioned backups, no secrets baked into images, pinned CI dependencies. Risks: secrets in images, `latest` tags, unpinned CI actions.
Ask: tested restore? isolated backups? incident plan and contacts? ability to isolate a host in minutes?
Quick wins: pin actions and images by digest; short-lived CI credentials; isolated backup account with object lock; tabletop exercise.
Monitor: unusual process or egress from workloads; new credentials created; backup deletion; canary token triggers.

## 12. Service identity
Meaning: machines, jobs and autonomous agents have first-class verifiable identities (not shared secrets) so actions can be proven and traced.
Repo evidence: workload identity (IRSA, GKE Workload Identity, Azure managed identity), SPIFFE/SPIRE, dedicated Kubernetes ServiceAccounts, mTLS. Risks: one shared API key for many services, default service account, static keys.
Ask: does each service have its own credentials and permissions? Can you list every non-human identity and its owner?
Quick wins: inventory service accounts and owners; one identity per service; short-lived credentials from the platform; rotate or delete stale keys.
Monitor: service identity used from a new location; key age above policy; new service account or key creation; actions by a service identity outside its normal pattern.
