#!/usr/bin/env python3
"""Heuristic readiness scanner (stdlib only). Finds evidence and risky patterns; it does not rate or fix.

usage: scan.py PROJECT_ROOT [--format markdown|json] [--max-hits N]

Every hit is a lead for a human or an AI to verify by reading the code. Secret values are redacted.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "out", "venv", ".venv", "env",
             "__pycache__", "vendor", "target", "coverage", ".gradle", "Pods", ".dart_tool", ".idea",
             ".turbo", ".cache", "site-packages", "bower_components"}
TEXT_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".rs", ".java", ".kt", ".swift",
            ".php", ".cs", ".dart", ".vue", ".svelte", ".html", ".htm", ".css", ".scss", ".json", ".yml", ".yaml",
            ".toml", ".ini", ".cfg", ".conf", ".env", ".sh", ".bash", ".sql", ".md", ".xml", ".plist", ".gradle",
            ".tf", ".txt", ".properties", ".dockerfile", ""}
MAX_BYTES = 1_000_000

# area -> list of (label, regex). A hit means "evidence present".
SIGNALS = {
    "1 Mobile": [
        ("viewport meta", r'<meta[^>]+name=["\']viewport'),
        ("responsive CSS", r"@media\s*\([^)]*(max|min)-width|@container|\bsm:|\bmd:|\blg:"),
        ("PWA manifest", r'"(short_name|start_url|display)"\s*:'),
        ("native/hybrid framework", r"\breact-native\b|\bexpo\b|\bflutter\b|\bcapacitor\b|\bcordova\b|\bionic\b|\bSwiftUI\b|\bjetpack\b"),
        ("android permissions", r"<uses-permission"),
        ("ios usage strings", r"NS[A-Za-z]+UsageDescription"),
    ],
    "2 Secret keys": [
        ("env loaded from environment", r"process\.env\.|os\.environ|os\.getenv|ENV\[|System\.getenv|dotenv"),
        ("secrets manager", r"secretsmanager|SecretManager|vault|doppler|1password|infisical"),
    ],
    "3 Database": [
        ("ORM / client", r"prisma|sequelize|typeorm|drizzle|sqlalchemy|django\.db|activerecord|gorm|knex|mongoose|supabase|psycopg|pg\b|mysql2?"),
        ("migrations", r"migrations?[/\\]|alembic|flyway|liquibase|prisma migrate|knex migrate"),
        ("pooling", r"pool(ing)?\b|pgbouncer|max_connections|connection_limit"),
        ("index / constraint", r"CREATE\s+(UNIQUE\s+)?INDEX|@@index|@unique|unique=True|db_index|FOREIGN KEY|REFERENCES\s"),
    ],
    "4 Rate limiting": [
        ("rate limit library", r"express-rate-limit|rate-limiter-flexible|@upstash/ratelimit|slowapi|flask-limiter|django-ratelimit|throttler|rack-attack|limiter\b|ratelimit|rate_limit|rateLimit"),
        ("429 response", r"\b429\b|Too Many Requests"),
    ],
    "5 Password reset": [
        ("reset flow", r"reset[-_ ]?password|forgot[-_ ]?password|password[-_ ]?reset|resetToken|reset_token"),
        ("token expiry", r"expires?(At|_at|In|_in)|expiresAt|ttl|exp\b"),
        ("token hashing", r"sha256|createHash|hashlib|bcrypt|argon2"),
    ],
    "6 Rollbacks": [
        ("down / rollback migration", r"downgrade\(|def down\b|\.down\(|rollback|migrate:undo|revert"),
        ("CI/CD deploy config", r"deploy|release"),
        ("versioned artifacts", r"docker\s+(build|tag|push)|--tag|image:\s*\S+:\S+"),
    ],
    "7 Backups": [
        ("dump / backup tooling", r"pg_dump|mysqldump|mongodump|litestream|pgbackrest|barman|wal-g|restic|borg"),
        ("backup/restore wording", r"\bbackup|\brestore\b|snapshot"),
    ],
    "8 Usage limits": [
        ("size/upload caps", r"maxFileSize|fileSize\s*:|limits\s*:\s*\{|max_content_length|MAX_UPLOAD|client_max_body_size|bodyLimit|limit:\s*['\"]\d+\s*(kb|mb)"),
        ("quota / plan limits", r"\bquota\b|usage[_-]?limit|monthly[_-]?limit|credits?\b|max_requests|plan[_-]?limit"),
        ("pagination cap", r"Math\.min\([^)]*limit|max_page_size|MAX_PAGE|le=\d+"),
    ],
    "9 Analytics": [
        ("analytics SDK", r"posthog|mixpanel|amplitude|segment\.|analytics\.track|gtag\(|plausible|fathom|google-analytics|firebase/analytics|umami|@vercel/analytics"),
        ("event tracking call", r"\.track\(|\.capture\(|logEvent\(|trackEvent\("),
    ],
    "10 Input cleaning": [
        ("validation library", r"\bzod\b|\bjoi\b|\byup\b|pydantic|class-validator|express-validator|marshmallow|valibot|ajv|cerberus|FormRequest|strong_parameters"),
        ("sanitizer / escaper", r"DOMPurify|sanitize-html|bleach|html\.escape|escapeHtml|xss\b"),
        ("CSRF protection", r"csrf|csurf|xsrf"),
    ],
    "11 Error handling": [
        ("global error handler", r"app\.use\(\s*\(?\s*err|errorhandler|@app\.errorhandler|ErrorBoundary|exception_handler|rescue_from|ExceptionFilter|process\.on\(['\"](unhandledRejection|uncaughtException)"),
        ("error tracking SDK", r"sentry|bugsnag|rollbar|honeybadger|raygun"),
    ],
    "12 Log flow": [
        ("structured logger", r"winston|pino|bunyan|structlog|loguru|logging\.getLogger|zerolog|zap\.|slog\.|serilog|logrus"),
        ("request id", r"x-request-id|request[_-]?id|correlation[_-]?id|trace[_-]?id|AsyncLocalStorage"),
    ],
    "13 Monitor and alerts": [
        ("health endpoint", r"['\"/](healthz?|health[-_]?check|ready|readyz|livez|ping|status)['\"/]"),
        ("metrics / tracing", r"prometheus|prom-client|opentelemetry|otel|datadog|dd-trace|newrelic|statsd|grafana"),
        ("alert rules", r"alert:|alertmanager|PagerDuty|Opsgenie|uptimerobot|betteruptime|statuspage"),
        ("error tracking SDK", r"sentry|bugsnag|rollbar|honeybadger"),
    ],
}
SIGNALS = {k: [(l, re.compile(p, re.I)) for l, p in v] for k, v in SIGNALS.items()}

# Risky patterns -> (id, severity, area, message, regex, file-extension filter or None)
RISKS = [
    ("sql-concat", "high", "3 Database", "SQL built with string concatenation/interpolation",
     re.compile(r"""(query|execute|raw)\s*\(\s*(f["']|[`"'][^`"']*(\$\{|["'`]\s*\+)|["'][^"']*%s?["']\s*%)\s*.*\b(SELECT|INSERT|UPDATE|DELETE)\b|\b(SELECT|INSERT|UPDATE|DELETE)\b[^;\n]*(\$\{|\"\s*\+\s*\w|'\s*\+\s*\w)""", re.I), None),
    ("html-sink", "medium", "10 Input cleaning", "Raw HTML sink (check input is sanitized)",
     re.compile(r"dangerouslySetInnerHTML|\.innerHTML\s*=|v-html|\|\s*safe\b|html_safe|\{\{\{"), None),
    ("eval-exec", "high", "10 Input cleaning", "eval/exec/shell with possible user input",
     re.compile(r"\beval\s*\(|new Function\(|child_process\.exec\(|os\.system\(|subprocess\.[a-z]+\([^)]*shell\s*=\s*True|\bpickle\.loads\("), None),
    ("debug-on", "high", "11 Error handling", "Debug mode enabled (must be off in production)",
     re.compile(r"^\s*DEBUG\s*=\s*True|app\.run\([^)]*debug\s*=\s*True|NODE_ENV\s*[:=]\s*['\"]development['\"]", re.M), None),
    ("err-leak", "high", "11 Error handling", "Error stack/message sent back to the client",
     re.compile(r"res\.(send|json|status\([^)]*\)\.(send|json))\([^)]*\b(err|error|e)\.(stack|message)"), None),
    ("empty-catch", "medium", "11 Error handling", "Swallowed exception (empty catch/except)",
     re.compile(r"catch\s*(\([^)]*\))?\s*\{\s*\}|except[^:\n]*:\s*\n\s*pass\b"), None),
    ("log-secrets", "high", "12 Log flow", "Logging request bodies/headers or credentials",
     re.compile(r"(console\.log|logger\.\w+|logging\.\w+|print)\(.*(req\.body|request\.(body|json|form)|headers|password|passwd|token|authorization)", re.I), None),
    ("weak-reset-token", "high", "5 Password reset", "Predictable randomness in a file that handles tokens/resets",
     re.compile(r"Math\.random\(|random\.random\(|rand\(\)"), "reset"),
    ("cors-star", "medium", "10 Input cleaning", "CORS allows any origin (fine for public APIs only)",
     re.compile(r"Access-Control-Allow-Origin['\"]?\s*[:,]\s*['\"]\*|origin\s*:\s*['\"]\*['\"]|allow_origins\s*=\s*\[\s*['\"]\*"), None),
    ("tls-off", "high", "2 Secret keys", "TLS verification disabled",
     re.compile(r"rejectUnauthorized\s*:\s*false|verify\s*=\s*False|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0|InsecureSkipVerify:\s*true"), None),
]

SECRET_PATTERNS = [
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Stripe live key", re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{16,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("OpenAI/Anthropic-style key", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_\-]{32,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("DB URL with password", re.compile(r"\b(postgres(ql)?|mysql|mongodb(\+srv)?|redis)://[^:/\s]+:[^@\s'\"]{4,}@")),
    ("hardcoded credential", re.compile(r"""(?i)\b(secret|passw(or)?d|api[_-]?key|auth[_-]?token|access[_-]?token)\b["']?\s*[:=]\s*["']([^"'\s]{12,})["']""")),
]
PLACEHOLDER = re.compile(r"(?i)example|your[_-]|xxx|changeme|placeholder|<[^>]+>|\$\{|%\(|process\.env|os\.environ|dummy|sample|test|fake|redacted|\*{3}|\.{3}|todo|replace")
PUBLIC_PREFIX = re.compile(r"\b(NEXT_PUBLIC|VITE|REACT_APP|EXPO_PUBLIC|NUXT_PUBLIC|PUBLIC)_[A-Z0-9_]*(SECRET|PRIVATE|SERVICE_ROLE|PASSWORD|TOKEN)[A-Z0-9_]*\b")


def redact(s: str) -> str:
    s = s.strip()
    return (s[:4] + "***") if len(s) > 4 else "***"


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if fn.endswith(("-lock.json", ".lock", ".min.js", ".map")) or fn in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
                continue
            ext = p.suffix.lower()
            if ext not in TEXT_EXT and fn not in ("Dockerfile", "Makefile", "Procfile", ".gitignore") and not fn.startswith(".env"):
                continue
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            yield p


def read(p: Path):
    try:
        data = p.read_bytes()
        if b"\0" in data[:2048]:
            return None
        return data.decode("utf-8", errors="replace")
    except OSError:
        return None


def git_tracked(root: Path, names):
    if not (root / ".git").exists():
        return None
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, timeout=20).stdout.splitlines()
    except Exception:
        return None
    return [f for f in out if Path(f).name in names or re.match(r"\.env(\..+)?$", Path(f).name)]


def scan(root: Path, max_hits: int):
    signals = defaultdict(lambda: defaultdict(list))   # area -> label -> [loc]
    risks = []                                           # dicts
    secrets = []
    stats = {"files": 0}
    tech = set()
    env_files, ignore_text = [], ""

    for p in iter_files(root):
        text = read(p)
        if text is None:
            continue
        stats["files"] += 1
        rel = str(p.relative_to(root))
        name = p.name
        if name == ".gitignore":
            ignore_text += text + "\n"
        if re.match(r"\.env(\.|$)", name) and not re.search(r"example|sample|template|dist$", name):
            env_files.append(rel)
        for pk, tl in (("package.json", "node"), ("requirements.txt", "python"), ("pyproject.toml", "python"),
                       ("go.mod", "go"), ("Gemfile", "ruby"), ("composer.json", "php"), ("pubspec.yaml", "flutter"),
                       ("Cargo.toml", "rust"), ("pom.xml", "java"), ("build.gradle", "java/android")):
            if name == pk:
                tech.add(tl)
        lines = text.splitlines()
        file_has_reset = bool(re.search(r"reset|forgot|token", text, re.I))
        for area, sigs in ([] if name.lower().endswith((".md", ".txt")) else SIGNALS.items()):
            for label, rx in sigs:
                if len(signals[area][label]) >= max_hits:
                    continue
                m = rx.search(text)
                if m:
                    ln = text.count("\n", 0, m.start()) + 1
                    signals[area][label].append(f"{rel}:{ln}")
        for rid, sev, area, msg, rx, need in RISKS:
            if need == "reset" and not file_has_reset:
                continue
            if name.endswith((".md", ".txt")) or "test" in rel.lower() or "spec" in rel.lower():
                continue
            for m in rx.finditer(text):
                ln = text.count("\n", 0, m.start()) + 1
                risks.append({"id": rid, "severity": sev, "area": area, "message": msg, "where": f"{rel}:{ln}"})
                break
        if not name.endswith((".md",)) and "node_modules" not in rel:
            for lineno, line in enumerate(lines, 1):
                if len(line) > 600:
                    continue
                for label, rx in SECRET_PATTERNS:
                    m = rx.search(line)
                    if not m:
                        continue
                    value = m.group(m.lastindex) if label == "hardcoded credential" and m.lastindex else m.group(0)
                    if label == "DB URL with password":
                        pw = re.search(r"://[^:/\s]+:([^@\s'\"]+)@", value)
                        value = pw.group(1) if pw else value
                    elif PLACEHOLDER.search(line) and label in ("hardcoded credential", "JWT"):
                        continue
                    if PLACEHOLDER.search(value):
                        continue
                    secrets.append({"type": label, "where": f"{rel}:{lineno}", "preview": redact(value)})
                    break
        for m in PUBLIC_PREFIX.finditer(text):
            risks.append({"id": "public-secret-name", "severity": "high", "area": "2 Secret keys",
                          "message": f"Variable '{m.group(0)}' is exposed to the browser by its prefix yet looks secret",
                          "where": f"{rel}:{text.count(chr(10), 0, m.start()) + 1}"})
            break

    # .env hygiene
    env_tracked = git_tracked(root, {".env"})
    ignored = bool(re.search(r"(^|\n)\s*/?\.env(\*|\.\*|\b)", ignore_text))
    hygiene = {"env_files_present": env_files, "gitignore_covers_env": ignored,
               "env_tracked_by_git": env_tracked if env_tracked is not None else "no git repo"}
    if env_tracked:
        risks.append({"id": "env-tracked", "severity": "critical", "area": "2 Secret keys",
                      "message": "A .env file is tracked by git: treat every key in it as leaked and rotate",
                      "where": ", ".join(env_tracked[:3])})
    elif env_files and not ignored:
        risks.append({"id": "env-not-ignored", "severity": "high", "area": "2 Secret keys",
                      "message": ".env file exists but .gitignore does not clearly ignore it",
                      "where": ", ".join(env_files[:3])})
    for s in secrets:
        risks.append({"id": "secret-in-code", "severity": "critical", "area": "2 Secret keys",
                      "message": f"{s['type']} found in code (starts '{s['preview']}'): rotate it and move it to the environment",
                      "where": s["where"]})
    return {"root": str(root), "files_scanned": stats["files"], "stack_hint": sorted(tech),
            "env_hygiene": hygiene,
            "signals": {a: {k: v for k, v in l.items() if v} for a, l in signals.items()},
            "risks": dedupe(risks), "areas": list(SIGNALS)}


def dedupe(risks):
    seen, out = set(), []
    for r in risks:
        k = (r["id"], r["where"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(out, key=lambda r: (order.get(r["severity"], 9), r["area"]))


def to_markdown(res):
    L = [f"# Readiness scan: `{res['root']}`", "",
         f"Files scanned: {res['files_scanned']}  |  Stack hint: {', '.join(res['stack_hint']) or 'unknown'}", "",
         "> Heuristic leads only. Verify each by reading the code. Absence of a signal means 'not found by pattern', not 'missing'.", "",
         "## Risky patterns", ""]
    if res["risks"]:
        L += ["| Severity | Area | Problem | Where |", "|---|---|---|---|"]
        for r in res["risks"]:
            L.append(f"| {r['severity']} | {r['area']} | {r['message']} | `{r['where']}` |")
    else:
        L.append("None matched.")
    h = res["env_hygiene"]
    L += ["", "## .env hygiene", "",
          f"- .env files present: {h['env_files_present'] or 'none'}",
          f"- .gitignore covers .env: {h['gitignore_covers_env']}",
          f"- tracked by git: {h['env_tracked_by_git']}", "", "## Evidence by area", ""]
    for area in res["areas"]:
        sigs = res["signals"].get(area, {})
        L.append(f"### {area}")
        if not sigs:
            L.append("- no signals found: check by hand")
        for label, locs in sigs.items():
            L.append(f"- {label}: {', '.join('`'+x+'`' for x in locs[:3])}")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--max-hits", type=int, default=3)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")
    res = scan(root, a.max_hits)
    print(json.dumps(res, indent=2) if a.format == "json" else to_markdown(res))


if __name__ == "__main__":
    main()
