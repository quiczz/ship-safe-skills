# Zero Trust monitoring

Zero Trust depends on seeing every access decision and reacting when context changes (principles 9 and 10). Build these with the `monitor-alerts-builder` skill. "Page" means a human acts now; "ticket" means fix this week. Tune thresholds after a week of real data.

## The one rule that protects all the others

**Alert when logging itself changes or goes quiet.** An attacker's first move is often to stop the evidence. Page on audit logging disabled, trail deleted or edited, log forwarder down, or a source that normally sends events sending none for 15 minutes.

## Alert catalog

| Alert | Principle | Detection | Default | Severity |
|-------|-----------|-----------|---------|----------|
| Audit logging stopped/changed, or log source silent | 10 | cloud trail stop/delete/update; no events from a source for 15 min | any | page |
| Sign-in without MFA | 3 | IdP/cloud console login with MFA not used | any for admins; ticket for users | page / ticket |
| MFA removed or factor reset | 3 | MFA deactivated, device registered then sensitive action within 1 h | any | page |
| Root / break-glass account used | 5, 6 | root login or break-glass sign-in | any | page |
| New admin grant / policy change | 5, 6 | admin policy attached; wildcard policy created; role trust policy edited | any | page for admin, ticket otherwise |
| Elevation outside window | 6 | JIT role used outside business hours or without an approved request | any | ticket (page for production admin) |
| Long-lived key created | 2, 12 | access key or service-account key created; key age above 90 days | any creation | ticket |
| Service identity from new place | 12 | service principal used from a new IP/ASN/region | any | page |
| Impossible travel / new device + sensitive action | 9, 4 | two sign-ins too far apart in time; unmanaged device accessing admin app | any | ticket / page |
| Session or token reuse after revocation | 9 | revoked token still accepted | any | page |
| Revocation latency | 9 | time from revoke to effective deny | above 5 min | ticket |
| Public exposure opened | 7, 8 | security group `0.0.0.0/0` on admin/DB ports; bucket made public; public-access-block removed | any | page |
| NetworkPolicy / segmentation removed | 7 | policy deleted, namespace without default-deny | any | ticket |
| Denied-connection spike | 7 | flow logs/mesh show many denied east-west connections from one workload | 10x baseline | page (lateral movement) |
| Plaintext or TLS-skipped connection | 8 | non-TLS to datastore; cert verification off in deployed config | any | ticket |
| Encryption key abuse | 8 | key deletion scheduled/disabled; decrypt volume spike | any | page |
| Unusual workload behavior | 11 | new process, new outbound domain, container escape signals, privileged container started | any | page |
| Backup tampered | 11 | backup deleted, retention shortened, object lock removed | any | page |
| Canary triggered | 11 | honeytoken credential or file touched | any | page |
| Agent out of pattern | 11, 12 | AI agent/automation reads in bulk, touches new resource types, changes permissions, or hits repeated denies | any | page |
| Unmanaged device access | 4 | access granted from a device with no compliance record | any admin | page |

## Where each signal comes from

| Signal | Typical source |
|--------|----------------|
| Sign-ins, MFA, device compliance | Identity provider logs (Okta, Entra ID, Google Workspace), cloud sign-in logs |
| Permission and policy changes | Cloud audit logs (CloudTrail, Cloud Audit Logs, Azure Activity Log), Kubernetes audit log |
| Network denies and unexpected flows | VPC/NSG flow logs, service mesh telemetry, Cilium/Hubble |
| Workload behavior | Runtime security (Falco, eBPF agents), EDR |
| Device state | MDM/EDR compliance feed |
| Application authorization | App audit events (see `api-security-guard/references/monitoring.md`) |

## Ready-made patterns

`templates/aws-eventbridge-patterns.json` contains EventBridge event patterns for the AWS items above (console login without MFA, root use, trail tampering, new access keys, admin policy attachment, open security groups, MFA removal, bucket exposure, KMS key deletion). Create one EventBridge rule per pattern, send matches to an SNS topic or chat webhook, and **fire a test event** to confirm delivery. The patterns follow the documented CloudTrail event shapes but have not been run against a live AWS account here; test them in yours.

For other clouds or an IdP, express the same intent as queries over your log store: the table above is the spec.

## Message format

```
[PAGE] zero-trust: admin policy attached
Who: role/ci-deploy  From: 203.0.113.9  When: 14:02 UTC
What: AdministratorAccess attached to user/svc-reports
Why it matters: standing admin on a service identity (principles 5, 12)
Runbook: <link>   Revert: detach policy, rotate svc-reports keys, review CloudTrail for the last 24 h
```
Never include secrets or tokens in alert text.

## Metrics to track (report monthly)

Percent of users with phishing-resistant MFA; count of standing admins; count of long-lived keys and median key age; percent of workloads with default-deny network policy; percent of internal traffic over TLS/mTLS; time to revoke access; percent of services with their own identity; log coverage (sources reporting vs expected).
