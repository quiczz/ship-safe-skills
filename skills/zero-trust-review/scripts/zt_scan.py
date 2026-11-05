#!/usr/bin/env python3
"""Collect Zero Trust evidence from code and infrastructure files (stdlib only, read-only).

usage: zt_scan.py PROJECT_ROOT [--format markdown|json]

Looks at Terraform/CloudFormation, Kubernetes, Docker/Compose, CI workflows, web server and app config.
For each of the 12 principles it reports EVIDENCE (good signs found) and RISKS (bad patterns found).
No evidence does not mean the control is missing: many controls live outside the repo (identity provider,
MDM, cloud console). Those are listed as 'ask the owner'.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

SKIP = {".git", "node_modules", "dist", "build", ".next", "out", "venv", ".venv", "__pycache__", "vendor", "target",
        ".terraform", "coverage", ".cache", "site-packages"}
EXT = {".tf", ".tfvars", ".yml", ".yaml", ".json", ".toml", ".conf", ".cfg", ".ini", ".env", ".js", ".ts", ".tsx", ".jsx",
       ".py", ".go", ".rb", ".java", ".kt", ".cs", ".php", ".sh", ".hcl", ".bicep", ".template", ".properties", ""}
MAX_BYTES = 600_000

PRINCIPLES = {
    1: "Verify every request", 2: "Strong identity", 3: "MFA everywhere", 4: "Device health", 5: "Least privilege (JEA)",
    6: "Just-in-time access", 7: "Microsegmentation", 8: "Encrypt internally", 9: "Continuous checks",
    10: "Log everything", 11: "Assume breach", 12: "Service identity",
}
ASK = {
    1: "Is there a gateway/policy layer that authorizes each request, and does it apply to internal traffic too?",
    2: "Which identity provider is the source of truth? Are there shared or local accounts left?",
    3: "Is MFA enforced in the IdP for ALL users (admins first), and are phishing-resistant methods (passkeys, FIDO2) offered?",
    4: "Is there an MDM/EDR posture check (Intune, Jamf, Kandji, CrowdStrike) feeding access decisions?",
    5: "Are cloud IAM roles reviewed? Any wildcard or owner/admin roles in the console that are not in code?",
    6: "How do admins get elevated rights (PIM, Teleport, break-glass, approval flow)? Do grants expire?",
    7: "Are there VPC/subnet/security-group and cluster network policies beyond what is in this repo?",
    8: "Is internal traffic (service to service, DB, cache, queue) TLS/mTLS? Are disks, DBs and backups encrypted with managed keys?",
    9: "Are sessions, tokens and access re-evaluated on risk changes, and can access be revoked in real time?",
    10: "Where do audit logs go (SIEM)? Are they immutable, retained, and alerted on? Is anything NOT logged?",
    11: "Is there an incident plan, tested restore, isolated backups, and a way to contain a compromised host/agent quickly?",
    12: "Does every service and automation/agent have its own identity and credentials with its own audit trail?",
}

# (principle, label, regex, file-name regex or None)
GOOD = [
    (1, "auth middleware / policy engine", r"(?i)authenticate|requireAuth|jwt_required|Depends\(get_current|AuthGuard|opa\b|open policy agent|authorizer|envoy.*ext_authz|oauth2-proxy|cerbos|casbin|oso\b", None),
    (1, "authorization policy (k8s/istio)", r"(?i)kind:\s*AuthorizationPolicy|aws_api_gateway_authorizer|aws_apigatewayv2_authorizer", None),
    (2, "SSO / OIDC / SAML", r"(?i)\boidc\b|openid|\bsaml\b|\bsso\b|keycloak|auth0|okta|cognito|azure[_ ]?ad|entra|clerk|workos|authentik", None),
    (2, "OIDC federation in CI (no static cloud keys)", r"id-token:\s*write|role-to-assume|workload_identity_provider|azure/login.*client-id|aws_iam_openid_connect_provider", None),
    (3, "MFA / WebAuthn / TOTP", r"(?i)\bmfa\b|multi[-_ ]?factor|\btotp\b|webauthn|passkey|fido2|\b2fa\b|two[-_ ]?factor|aws:MultiFactorAuthPresent|mfa_configuration", None),
    (4, "device posture / MDM / conditional access", r"(?i)intune|jamf|kandji|crowdstrike|device[_ ]?posture|beyondcorp|access_context_manager|conditional[_ ]?access|tailscale.*posture|cloudflare.*(warp|device)|zscaler|okta.*device", None),
    (5, "scoped IAM / RBAC / non-root", r"(?i)kind:\s*(Role|RoleBinding)\b|runAsNonRoot:\s*true|least[_ ]?privilege|permissions_boundary|aws_iam_policy_document|readOnlyRootFilesystem:\s*true|permissions:\s*\n\s+contents:\s*read", None),
    (6, "just-in-time / short-lived access", r"(?i)\bpim\b|privileged identity|teleport|sts:AssumeRole|assume_role|boundary\b|vault.*(dynamic|lease)|break[-_ ]?glass|access[_ ]?request|expires?_(in|at)|session_duration|max_session_duration", None),
    (7, "network policies / segmentation", r"(?i)kind:\s*NetworkPolicy|aws_security_group_rule|aws_network_acl|private_subnet|internal:\s*true|networks:\s*\n|calico|cilium|istio|linkerd|PeerAuthentication", None),
    (8, "TLS/mTLS inside + encryption at rest", r"(?i)mtls|mutual tls|ssl_?mode\s*[=:]\s*['\"]?(require|verify|full)|storage_encrypted\s*=\s*true|encrypted\s*=\s*true|kms_key_id|sse_algorithm|PeerAuthentication|mode:\s*STRICT|tls:\s*\n|require_secure_transport|ssl\s*[=:]\s*true", None),
    (9, "token revocation / re-evaluation / short TTL", r"(?i)revoke|introspect|token_?blacklist|denylist|session[_ ]?revalidat|continuous[_ ]?access|risk[_ -]?based|step[-_ ]?up|expiresIn:\s*['\"]?\d+\s*(m|min|s)\b|ACCESS_TOKEN_EXPIRE_MINUTES", None),
    (10, "audit logging / SIEM", r"(?i)aws_cloudtrail|cloudtrail|audit[_ ]?(log|policy|trail)|auditd|kind:\s*Policy\b.*audit|flow[_ ]?logs?|aws_flow_log|azurerm_monitor_diagnostic|datadog|splunk|elastic|loki|siem|wazuh|sentinel", None),
    (11, "container/host hardening, backups, isolation", r"(?i)allowPrivilegeEscalation:\s*false|drop:\s*\[?\s*['\"]?ALL|seccompProfile|readOnlyRootFilesystem:\s*true|no-new-privileges|apparmor|gvisor|firecracker|sandbox|object[_ ]?lock|immutable|aws_backup|versioning", None),
    (12, "workload/service identity", r"(?i)spiffe|spire\b|eks\.amazonaws\.com/role-arn|iam\.gke\.io/gcp-service-account|azure\.workload\.identity|serviceAccountName|aws_iam_role|managed[_ ]?identity|workload[_ ]?identity|irsa\b|mtls", None),
]
RISK = [
    (2, "high", "static cloud access keys in CI/IaC/config", r"AKIA[0-9A-Z]{16}|aws_access_key_id\s*[=:]\s*['\"]?[A-Z0-9]{16,}|AWS_SECRET_ACCESS_KEY\s*[:=]\s*(?!\$\{\{|\$\{|\"?\$)\S{20,}", None),
    (2, "medium", "AWS keys from CI secrets instead of OIDC federation", r"aws-access-key-id:\s*\$\{\{\s*secrets\.", r"\.ya?ml$"),
    (2, "medium", "long-lived IAM access key resource", r"resource\s+\"aws_iam_access_key\"", r"\.tf$"),
    (2, "medium", "default/admin credentials in config", r"(?i)(admin|root|postgres)\s*[:=]\s*['\"]?(admin|password|changeme|root|postgres|123456)['\"]?\s*$", r"\.(ya?ml|env|conf|tf|properties)$"),
    (5, "high", "wildcard IAM action", r"(?i)\"?Action\"?\s*[:=]\s*(\[\s*)?\"\*\"|actions\s*=\s*\[\s*\"\*\"\s*\]|Action:\s*['\"]?\*['\"]?\s*$", r"\.(tf|json|ya?ml|template)$"),
    (5, "high", "wildcard IAM resource with allow", r"(?i)\"?Resource\"?\s*[:=]\s*(\[\s*)?\"\*\"|resources\s*=\s*\[\s*\"\*\"\s*\]|Resource:\s*['\"]?\*['\"]?\s*$", r"\.(tf|json|ya?ml|template)$"),
    (5, "high", "admin policy attached (AdministratorAccess / cluster-admin / Owner)", r"AdministratorAccess|cluster-admin|roles/owner|\"Owner\"", r"\.(tf|json|ya?ml|template|bicep)$"),
    (5, "medium", "CI workflow with write-all or no minimal permissions", r"permissions:\s*write-all", r"\.ya?ml$"),
    (5, "medium", "container runs as root / privileged", r"privileged:\s*true|runAsUser:\s*0\b|allowPrivilegeEscalation:\s*true|^USER\s+root\s*$", None),
    (5, "high", "database GRANT ALL / superuser for app", r"(?i)GRANT\s+ALL\s+PRIVILEGES|\bSUPERUSER\b", r"\.(sql|sh|ya?ml|tf)$"),
    (6, "medium", "permanent admin role assignment pattern (no expiry)", r"(?i)aws_iam_user_policy_attachment|aws_iam_group_policy_attachment.*Administrator", r"\.tf$"),
    (7, "high", "ingress open to the whole internet", r"0\.0\.0\.0/0|::/0", r"\.(tf|json|ya?ml|template|bicep)$"),
    (7, "high", "datastore port published to the host/internet", r"^\s*-\s*['\"]?(?:0\.0\.0\.0:)?(?:5432|3306|6379|27017|9200|11211|5672|2379):\d+['\"]?\s*$", r"(?i)compose.*\.ya?ml$|docker-compose"),
    (7, "medium", "host networking", r"network_mode:\s*['\"]?host|hostNetwork:\s*true|hostPID:\s*true", None),
    (8, "high", "TLS verification disabled", r"rejectUnauthorized\s*:\s*false|verify\s*=\s*False|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0|InsecureSkipVerify:\s*true|sslmode\s*=\s*disable|ssl\s*[:=]\s*false|--insecure\b|curl\s+-k\b", None),
    (8, "medium", "plain http:// between services", r"['\"`]http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|host\.docker\.internal)[\w.\-]+(:\d+)?", r"\.(ya?ml|env|conf|tf|json|py|js|ts|go)$"),
    (8, "high", "storage/database encryption disabled", r"(?i)storage_encrypted\s*=\s*false|\bencrypted\s*=\s*false|encryption_enabled\s*=\s*false|kms_master_key_id\s*=\s*\"\"", r"\.(tf|json|ya?ml|template)$"),
    (8, "high", "public storage bucket / ACL", r"(?i)acl\s*=\s*\"public-read(-write)?\"|block_public_acls\s*=\s*false|restrict_public_buckets\s*=\s*false|AllUsers", r"\.(tf|json|ya?ml|template)$"),
    (9, "medium", "very long token/session lifetime", r"(?i)expiresIn\s*:\s*['\"]?\d+\s*(d|w|y|days?)\b|ACCESS_TOKEN_EXPIRE_MINUTES\s*=\s*\d{4,}|max_age\s*=\s*\d{7,}|SESSION_COOKIE_AGE\s*=\s*\d{7,}", None),
    (10, "high", "logging/auditing explicitly disabled", r"(?i)enable_logging\s*=\s*false|is_multi_region_trail\s*=\s*false|logging\s*[:=]\s*(false|off)\b|audit\s*[:=]\s*(false|off)\b", r"\.(tf|json|ya?ml|conf|template)$"),
    (11, "high", "secrets baked into images / compose / manifests", r"(?i)^\s*(ENV|ARG)\s+\w*(SECRET|PASSWORD|TOKEN|API_?KEY)\w*\s*=?\s*\S{6,}", r"(?i)dockerfile"),
    (11, "medium", "container image uses mutable 'latest' tag", r"(?i)^\s*(FROM\s+\S+:latest\b|image:\s*\S+:latest\b)", None),
    (11, "medium", "unpinned third-party CI actions (supply-chain)", r"uses:\s*[\w\-]+/[\w\-.]+@(main|master|v?\d+(\.\d+)*)\s*$", r"\.ya?ml$"),
    (12, "medium", "shared credentials across services (same secret name used widely)", r"(?i)\b(SHARED|COMMON|GLOBAL)_(API_?KEY|SECRET|TOKEN|PASSWORD)\b", None),
]
GOOD = [(p, l, re.compile(r), (re.compile(f) if f else None)) for p, l, r, f in GOOD]
RISK = [(p, s, l, re.compile(r, re.M), (re.compile(f) if f else None)) for p, s, l, r, f in RISK]
K8S_KIND = re.compile(r"^kind:\s*(\w+)", re.M)


def walk(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP)
        for fn in sorted(fns):
            p = Path(dp) / fn
            low = fn.lower()
            if p.suffix.lower() not in EXT and "dockerfile" not in low and not low.startswith("docker-compose"):
                continue
            if low.endswith((".md", ".lock")) or low in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
                continue
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            yield p


def scan(root):
    good = defaultdict(lambda: defaultdict(list))
    risks = []
    k8s_kinds = defaultdict(int)
    has_iac, has_k8s, has_docker, has_ci = False, False, False, False
    nfiles = 0
    for p in walk(root):
        rel = str(p.relative_to(root))
        if any(x in "/" + rel.lower() for x in ("/test", "tests/", "__tests__", "/examples/", "/fixtures/", "testdata", "/detections/",
                                          "/semgrep", "/sigma", "/yara", "/signatures", "/corpus", "/rules/", "/samples/", "/vendor/",
                                          "gitleaks", "trufflehog", ".security/", "/catalog", "/marketplace")):
            continue
        try:
            b = p.read_bytes()
            if b"\0" in b[:2048]:
                continue
            t = b.decode("utf-8", "replace")
        except OSError:
            continue
        nfiles += 1
        low = p.name.lower()
        is_tf = low.endswith((".tf", ".hcl", ".bicep"))
        has_iac |= is_tf or ("AWSTemplateFormatVersion" in t)
        has_docker |= "dockerfile" in low or low.startswith(("docker-compose", "compose."))
        has_ci |= rel.startswith((".github/workflows", ".gitlab-ci", ".circleci"))
        if re.search(r"^apiVersion:", t, re.M):
            for k in K8S_KIND.findall(t):
                k8s_kinds[k] += 1
                has_k8s = True
        for pr, label, rx, fre in GOOD:
            if fre and not fre.search(rel):
                continue
            if len(good[pr][label]) < 3:
                m = rx.search(t)
                if m:
                    good[pr][label].append(f"{rel}:{t.count(chr(10), 0, m.start()) + 1}")
        for pr, sev, label, rx, fre in RISK:
            if fre and not fre.search(rel) and not fre.search(low):
                continue
            m = rx.search(t)
            if m:
                risks.append({"principle": pr, "severity": sev, "message": label, "where": f"{rel}:{t.count(chr(10), 0, m.start()) + 1}"})
    # structural checks
    if has_k8s:
        wl = sum(k8s_kinds.get(k, 0) for k in ("Deployment", "StatefulSet", "DaemonSet", "Pod", "CronJob"))
        if wl and not k8s_kinds.get("NetworkPolicy"):
            risks.append({"principle": 7, "severity": "high", "message": f"{wl} Kubernetes workload(s) but no NetworkPolicy: all pods can talk to all pods", "where": "kubernetes manifests"})
        if wl and not k8s_kinds.get("ServiceAccount"):
            risks.append({"principle": 12, "severity": "medium", "message": "Kubernetes workloads but no dedicated ServiceAccount defined: they use the namespace default", "where": "kubernetes manifests"})
    if has_ci and not good[2].get("OIDC federation in CI (no static cloud keys)") and any(r["message"].startswith("AWS keys from CI") for r in risks):
        pass
    grouped = {}
    for r in risks:                                   # one line per (principle, message) with a count
        k = (r["principle"], r["message"])
        g = grouped.setdefault(k, {**r, "locations": []})
        if r["where"] not in g["locations"]:
            g["locations"].append(r["where"])
    uniq = []
    for g in grouped.values():
        g["count"] = len(g["locations"])
        g["where"] = ", ".join(g["locations"][:3]) + (f" (+{g['count'] - 3} more)" if g["count"] > 3 else "")
        del g["locations"]
        uniq.append(g)
    order = {"high": 0, "medium": 1, "low": 2}
    uniq.sort(key=lambda r: (order[r["severity"]], r["principle"]))
    per = {}
    for pr, name in PRINCIPLES.items():
        ev = {l: v for l, v in good.get(pr, {}).items() if v}
        rk = [r for r in uniq if r["principle"] == pr]
        status = "RISKS FOUND" if rk else ("EVIDENCE FOUND" if ev else "NO EVIDENCE IN REPO")
        per[pr] = {"name": name, "status": status, "evidence": ev, "risks": rk, "ask_the_owner": ASK[pr]}
    return {"root": str(root), "files_scanned": nfiles,
            "surfaces": {"terraform_or_cloudformation": has_iac, "kubernetes": has_k8s, "docker": has_docker, "ci": has_ci},
            "k8s_kinds": dict(k8s_kinds), "principles": per}


def to_markdown(R):
    sf = R["surfaces"]
    L = [f"# Zero Trust evidence scan: `{R['root']}`", "",
         f"Files scanned: {R['files_scanned']}  |  Surfaces found: " + ", ".join(k for k, v in sf.items() if v or False) + ("" if any(sf.values()) else "none (app code only)"),
         "", "> Evidence = good signs matched by pattern. Risks = bad patterns matched. 'No evidence in repo' means ask the owner, not 'fail'.", "",
         "| # | Principle | Result | Evidence | Risks |", "|---|-----------|--------|:-:|:-:|"]
    for pr, d in R["principles"].items():
        L.append(f"| {pr} | {d['name']} | {d['status']} | {len(d['evidence'])} | {len(d['risks'])} |")
    for pr, d in R["principles"].items():
        L += ["", f"## {pr}. {d['name']}", ""]
        for l, locs in d["evidence"].items():
            L.append(f"- + {l}: " + ", ".join(f"`{x}`" for x in locs))
        for r in d["risks"][:12]:
            L.append(f"- ! [{r['severity']}] {r['message']} ({r['count']}x): {r['where']}")
        if not d["evidence"] and not d["risks"]:
            L.append("- nothing matched")
        L.append(f"- ask the owner: {d['ask_the_owner']}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")
    R = scan(root)
    print(json.dumps(R, indent=2) if a.format == "json" else to_markdown(R))


if __name__ == "__main__":
    main()
