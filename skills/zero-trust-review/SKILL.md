---
name: zero-trust-review
description: Review a system against 12 Zero Trust principles - verify every request, strong identity, MFA, device health, least privilege, just-in-time access, microsegmentation, internal encryption, continuous checks, full logging, assume breach, service identity - then build the missing controls and the monitoring for them. Includes an infrastructure evidence scanner. Use when asked for a zero trust assessment, to harden cloud/Kubernetes/CI setup, or to secure AI agents and service accounts. Use proactively whenever you touch IAM, service accounts, CI secrets, network or cloud configuration.
---

# Zero Trust Review

Assesses how well a system follows Zero Trust, produces a prioritized roadmap, and builds detection for the controls that matter. Zero Trust means: never trust a request because of where it comes from; verify identity, device and context every time; give the least access for the shortest time; and assume something is already compromised.

Aligned with NIST SP 800-207 (Zero Trust Architecture) and the CISA Zero Trust Maturity Model (pillars: Identity, Devices, Networks, Applications and Workloads, Data; cross-cutting: Visibility and Analytics, Automation and Orchestration, Governance; stages: Traditional, Advanced, Optimal).

**Runs on its own:** when Claude touches IAM, service accounts, CI secrets or network config, it applies the 12 principles to that change.

## The 12 principles

| # | Principle | CISA pillar | One-line test |
|---|-----------|-------------|---------------|
| 1 | Verify every request | Applications | Does each request get authenticated and authorized, even from inside the network? |
| 2 | Strong identity | Identity | Can you say exactly who or what is connecting, from one trusted source? |
| 3 | MFA everywhere | Identity | Is a second factor (ideally phishing-resistant) required for all users, admins first? |
| 4 | Device health | Devices | Is the device known, patched and compliant before access is granted? |
| 5 | Least privilege (JEA) | Identity / Apps | Does each identity have only what the task needs, no wildcards, no standing admin? |
| 6 | Just-in-time access | Identity | Are elevated rights requested, approved, time-boxed and revoked automatically? |
| 7 | Microsegmentation | Networks | If one workload is breached, how far can it reach? |
| 8 | Encrypt internally | Data / Networks | Is data encrypted in transit (even service to service) and at rest? |
| 9 | Continuous checks | Visibility / Automation | Is trust re-evaluated during a session and revocable in real time? |
| 10 | Log everything | Visibility and Analytics | Can you reconstruct who did what, when, from where, for every access attempt? |
| 11 | Assume breach | All | Is the blast radius small, backups isolated, and containment rehearsed? |
| 12 | Service identity | Identity / Workloads | Does every service, job and AI agent have its own verifiable identity and audit trail? |

What each means in practice, what evidence to look for, quick wins and monitoring signals: `references/principles.md`. Detection and alert patterns: `references/monitoring.md`. Applying 11 and 12 to AI agents: `references/agents.md`.

## Procedure

1. **Scope.** Is this one application, a cloud account, a cluster, a company? Zero Trust spans the repo and things outside it (identity provider, device management, cloud console). Say which parts you can see.
2. **Collect evidence** from the repo:
   ```bash
   python3 <skill-dir>/scripts/zt_scan.py <project-root> > /tmp/zt-scan.md
   ```
   It reads Terraform/CloudFormation, Kubernetes, Docker/Compose, CI workflows and app config and reports, per principle, good signs and risky patterns. It is heuristic: confirm each lead in the file. For rule 1, also run the `api-security-guard` inventory if installed.
3. **Ask the owner** the out-of-repo questions the scan lists (identity provider, MFA enforcement, device management, SIEM). Mark principles you cannot verify as `UNKNOWN` and write the exact question and who can answer.
4. **Rate each principle** `PASS / WARN / FAIL / UNKNOWN` with evidence, and place it on the maturity scale: Traditional (static, perimeter-based), Advanced (automated, risk-aware), Optimal (continuous, dynamic).
5. **Prioritize** the roadmap. Default order, because it reduces the most risk per effort:
   1. Phishing-resistant MFA on admins and all remote access (3)
   2. Remove standing admin and wildcard permissions; add JIT for the rest (5, 6)
   3. Central audit logging with alerts on identity and permission changes (10, 9)
   4. Workload identity instead of static keys; per-service credentials (12, 2)
   5. Network segmentation and default-deny between workloads (7)
   6. Internal TLS/mTLS and encryption at rest (8)
   7. Device posture in access decisions (4)
   8. Containment drills and isolated backups (11)
6. **Build** the first items with the user (policy files, IaC changes, CI OIDC, NetworkPolicies, alert rules). One change at a time, each with a way to verify it works and a rollback.
7. **Monitor** with `references/monitoring.md` via the `monitor-alerts-builder` skill. Zero Trust without logging and alerts is only configuration.

## Output

A report with: scorecard (12 rows), top 5 risks with `path:line`, roadmap in 30/60/90-day batches, UNKNOWN questions with owners, and what was not covered. Be plain: say what is wrong, why it matters, and the exact fix.

## Rules

- Read-only on infrastructure unless the user asks for a change. Never run scans or probes against systems they do not own, and never apply IaC to a live account without explicit approval and a plan/diff.
- Zero Trust is a direction, not a product. Do not declare a system "zero trust"; rate it per principle.
- Never print secrets. For exposed keys, require rotation.
- A passing scan is not an audit.
