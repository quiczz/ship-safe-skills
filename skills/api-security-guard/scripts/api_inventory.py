#!/usr/bin/env python3
"""Inventory API endpoints in a codebase and flag common API-security gaps (stdlib only, read-only).

usage: api_inventory.py PROJECT_ROOT [--format markdown|json]

Finds routes (Express/Fastify/Koa, FastAPI/Flask, Django, Go, Next.js app+pages routers, NestJS), then for each:
auth evidence, version in path, object-ID parameter (needs an ownership check), and public-by-design guess.
Also flags: tokens in URLs, plain http:// endpoints, long-lived tokens, spec/code drift (OpenAPI), and
data-exposure leads. Everything is a LEAD to verify by reading the code, not a verdict.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

SKIP = {".git", "node_modules", "dist", "build", ".next", "out", "venv", ".venv", "env", "__pycache__", "vendor",
        "target", "coverage", ".cache", "site-packages"}
CODE_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".go", ".rb", ".php", ".java", ".kt", ".cs"}
MAX_BYTES = 800_000

ROUTE_PATTERNS = [
    # (style, regex, group of method, group of path)
    ("express-like", re.compile(r"""(?<![@\w])(?:app|router|server|api|fastify|r|route)\.(get|post|put|patch|delete|all|options)\(\s*['"`](/[^'"`]*)['"`]"""), 1, 2),
    ("fastapi/flask", re.compile(r"""@\w+\.(get|post|put|patch|delete|route|websocket)\(\s*['"](/[^'"]*)['"]"""), 1, 2),
    ("nestjs", re.compile(r"""@(Get|Post|Put|Patch|Delete)\(\s*(?:['"]([^'"]*)['"])?\s*\)"""), 1, 2),
    ("go-http", re.compile(r"""\.(GET|POST|PUT|PATCH|DELETE|Handle|HandleFunc)\(\s*"(/[^"]*)\""""), 1, 2),
    ("django", re.compile(r"""\b(?:re_)?path\(\s*r?['"]([^'"]*)['"]"""), None, 1),
]
AUTH_WORDS = re.compile(
    r"(?i)authenticate|requireauth|require_auth|isauthenticated|is_authenticated|ensureauth|verifytoken|verify_token|"
    r"verifyjwt|checkjwt|jwtauth|jwt_required|login_required|permission_required|@UseGuards|AuthGuard|"
    r"Depends\(\s*(?:get_current|require|verify|auth|current)|Security\(|HTTPBearer|OAuth2PasswordBearer|"
    r"\bprotect\b|withAuth|auth\(\)|getServerSession|getSession|currentUser|clerk|requireUser|authorize\(|"
    r"permission_classes|IsAuthenticated|@PreAuthorize|\[Authorize\]|before_action\s*:authenticate|passport\.authenticate")
TYPED_PRINCIPAL = re.compile(
    r"(?i)\b(?:current_?user|user|principal|actor|identity|claims|caller|me|account|auth(?:_?ctx)?|ctx)\s*:\s*(?:Annotated\[\s*)?[\w.\[]*(?:Auth|User|Principal|Actor|Identity|Claims|Caller)\w*|"
    r"require_?permission|requires?_?(?:role|scope|permission)|has_?permission|check_?permission|user\.require_|\.require_permission|@PreAuthorize|@RolesAllowed|\bcan\(")
FILE_AUTH_USE = re.compile(
    r"(?i)\.use\(\s*(?:\w+\.)?(?:authenticate|requireauth|auth|verifytoken|protect|jwt|passport\.authenticate|checkjwt)\b|"
    r"addHook\(\s*['\"]onRequest|dependencies\s*=\s*\[\s*Depends|router\s*=\s*APIRouter\([^)]*dependencies|"
    r"APP_GUARD|DEFAULT_PERMISSION_CLASSES|MIDDLEWARE.*Authentication|middleware\.ts|authMiddleware")
PUBLIC_PATH = re.compile(r"(?i)/(login|logout|signin|sign-in|signup|sign-up|register|health|healthz|ready|readyz|livez|ping|status|"
                         r"webhooks?|callback|oauth|auth|public|forgot|reset|verify-email|csrf|metrics|docs|openapi|swagger|favicon|robots)\b")
ID_PARAM = re.compile(r":(\w*[iI]d|\w*Id)\b|\{(\w*_?[iI]d|id)\}|\[(\w*[iI]d|id)\]|<(?:int:|str:|uuid:)?(\w*id)>|\(\?P<(\w*id)>")
VERSION = re.compile(r"/v(\d+)(?:/|$)|/api/v(\d+)\b")
TOKEN_IN_URL = re.compile(r"""(?i)[?&](access_?token|token|api_?key|apikey|key|secret|password|auth|jwt|session_?id)=|"""
                          r"""req\.query\.(token|api_?key|access_?token|key|secret|password)|"""
                          r"""request\.args\.get\(\s*['"](token|api_?key|access_token|key|secret|password)['"]|"""
                          r"""request\.GET\.get\(\s*['"](token|api_?key|access_token|key|password)['"]""")
HTTP_URL = re.compile(r"""['"`]http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|host\.docker\.internal|[\w.-]*\.local\b|[\w-]+:\d|example\.|schemas?\.|www\.w3\.org)[\w.\-/:%?=&]+""")
LONG_TOKEN = re.compile(r"""(?i)expiresIn\s*:\s*['"]?(\d+)\s*(d|w|y|days?|weeks?|years?)\b|expires_delta\s*=\s*timedelta\(\s*(days|weeks)\s*=\s*(\d+)|"""
                        r"""ACCESS_TOKEN_(?:EXPIRE|LIFETIME)[A-Z_]*\s*[=:]\s*(\d{4,})|exp\s*[:=]\s*[^,\n]*\b(\d{6,})\b""")
RESPONSE_LEAK = re.compile(r"""(?i)(password_?hash|passwordHash|hashed_?password|\bsalt\b|reset_?token|api_?secret|private_?key|ssn|card_?number)""")
RAW_RETURN = re.compile(r"""res\.(?:json|send)\(\s*(user|users|account|accounts|rows|result|results|doc|docs|record|records)\s*\)|"""
                        r"""return\s+(user|account)\s*$|jsonify\(\s*(user|account)\s*\)""", re.M)
SELECT_ALL = re.compile(r"""(?i)select\s+\*\s+from|\.findAll\(\s*\)|\.find\(\s*\{\s*\}\s*\)|\.objects\.all\(\)""")
RATE_LIMIT = re.compile(r"(?i)rate-?limit|ratelimit|throttl|slowapi|limiter|upstash/ratelimit")
HTTPS_FORCE = re.compile(r"(?i)strict-transport-security|hsts|force_https|forceSSL|SECURE_SSL_REDIRECT|redirect.*https|helmet\(|x-forwarded-proto")
VALIDATION = re.compile(r"(?i)\bzod\b|\bjoi\b|\byup\b|pydantic|BaseModel|class-validator|express-validator|marshmallow|ajv|ValidationPipe|@Valid\b|serializers\.")
VERSIONING_HINT = re.compile(r"(?i)deprecat|sunset|api-version|apiVersion|Accept-Version")
ERROR_LOG_AUTH = re.compile(r"(?i)(unauthori[sz]ed|forbidden|401|403|invalid[ _]token|auth(entication)?[ _](failed|failure|error)|login[ _]failed)")


def walk(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP)
        for fn in sorted(fns):
            p = Path(dp) / fn
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            yield p


def text(p):
    try:
        b = p.read_bytes()
        return None if b"\0" in b[:2048] else b.decode("utf-8", "replace")
    except OSError:
        return None


def is_test(rel):
    s = str(rel).lower()
    return any(x in s for x in ("test", "spec", "__tests__", "e2e", "fixture", "mock", "example", "demo", "docs/"))


def nextjs_routes(rel):
    parts = rel.parts
    if "app" in parts and rel.stem == "route":
        i = parts.index("app")
        seg = [s for s in parts[i + 1:-1] if not (s.startswith("(") and s.endswith(")"))]
        return "/" + "/".join(seg)
    if len(parts) >= 2 and "pages" in parts and "api" in parts[parts.index("pages") + 1:]:
        i = parts.index("pages")
        return "/" + "/".join(parts[i + 1:-1] + (rel.stem,)).replace("/index", "")
    return None


def openapi_paths(p, t):
    out = set()
    if p.suffix == ".json":
        try:
            out = set((json.loads(t).get("paths") or {}).keys())
        except Exception:
            pass
    else:
        m = re.search(r"^paths:\s*$", t, re.M)
        if m:
            for line in t[m.end():].splitlines():
                if re.match(r"^\S", line) and not line.startswith("#"):
                    break
                mm = re.match(r"^  ['\"]?(/[^'\":\s]*)['\"]?:\s*$", line)
                if mm:
                    out.add(mm.group(1))
    return out


def norm(path):
    p = re.sub(r"\{[^}]+\}|:[A-Za-z_]\w*|\[[^\]]+\]|<[^>]+>", "{}", path.split("?")[0])
    return p.rstrip("/") or "/"


IMPORT_LINE = re.compile(r"^\s*(import\s|from\s+\S+\s+import|const\s+.*=\s*require\(|let\s+.*=\s*require\(|var\s+.*=\s*require\(|using\s|#include|use\s)")


def route_context(lines, ln, style):
    """Text that can legitimately protect THIS route, with import lines removed."""
    i = ln - 1
    if style in ("fastapi/flask", "nestjs"):
        start = max(0, i - 4)                       # stacked decorators above
        chunk, j = list(lines[start:i + 1]), i + 1
        while j < min(len(lines), i + 9):           # then the function signature
            chunk.append(lines[j])
            if re.match(r"^\s*(async\s+def|def|public|async|\w+\s*\()", lines[j]) and lines[j].rstrip().endswith((":", "{")):
                break
            j += 1
    else:                                           # express-like, go, django: the registration statement itself
        chunk, depth, j = [], 0, i
        while j < min(len(lines), i + 5):
            chunk.append(lines[j])
            depth += lines[j].count("(") - lines[j].count(")")
            if depth <= 0:
                break
            j += 1
    return "\n".join(l for l in chunk if not IMPORT_LINE.match(l))


def scan(root):
    endpoints, findings = [], []
    spec_paths, spec_files = set(), []
    global_flags = {"rate_limit": False, "https_enforced": False, "validation": False, "versioning_policy": False, "auth_failure_logging": False}
    for p in walk(root):
        rel = p.relative_to(root)
        low = p.name.lower()
        if p.suffix not in CODE_EXT and not (low.startswith(("openapi", "swagger")) and p.suffix in (".json", ".yaml", ".yml")):
            continue
        t = text(p)
        if t is None:
            continue
        if low.startswith(("openapi", "swagger")) and p.suffix in (".json", ".yaml", ".yml"):
            ps = openapi_paths(p, t)
            if ps:
                spec_paths |= {norm(x) for x in ps}
                spec_files.append(str(rel))
            continue
        test = is_test(rel)
        if not test:
            global_flags["rate_limit"] |= bool(RATE_LIMIT.search(t))
            global_flags["https_enforced"] |= bool(HTTPS_FORCE.search(t))
            global_flags["validation"] |= bool(VALIDATION.search(t))
            global_flags["versioning_policy"] |= bool(VERSIONING_HINT.search(t))
            if re.search(r"(?i)log(ger)?\.\w+\(|console\.(warn|error)|logging\.", t) and ERROR_LOG_AUTH.search(t):
                global_flags["auth_failure_logging"] = True
        if test:
            continue
        lines = t.splitlines()
        file_auth = bool(FILE_AUTH_USE.search(t))
        # next.js file routes
        nr = nextjs_routes(rel)
        if nr is not None:
            methods = re.findall(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)|export\s+const\s+(GET|POST|PUT|PATCH|DELETE)", t)
            ms = sorted({a or b for a, b in methods}) or ["ANY"]
            auth = bool(AUTH_WORDS.search(t))
            for m in ms:
                endpoints.append({"method": m, "path": nr, "file": f"{rel}:1", "auth": "yes" if auth else ("file-wide?" if file_auth else "none seen")})
        for style, rx, gm, gp in ROUTE_PATTERNS:
            for m in rx.finditer(t):
                ln = t.count("\n", 0, m.start()) + 1
                method = (m.group(gm) if gm else "ANY").upper()
                path = m.group(gp) or ""
                if style == "django":
                    path = "/" + path
                if style == "nestjs":
                    path = "/" + path.lstrip("/") if path else "/"
                    cls = re.findall(r"@Controller\(\s*['\"]([^'\"]*)['\"]", t)
                    if cls:
                        path = "/" + cls[0].strip("/") + ("" if path == "/" else path)
                ctx = route_context(lines, ln, style)
                if AUTH_WORDS.search(ctx) or TYPED_PRINCIPAL.search(ctx) or (style == "nestjs" and re.search(r"@UseGuards|@Controller", t) and "@UseGuards" in t):
                    auth = "yes"
                elif file_auth:
                    auth = "file-wide?"
                else:
                    auth = "none seen"
                endpoints.append({"method": method, "path": path, "file": f"{rel}:{ln}", "auth": auth})
        # token in URL, http endpoints, long-lived tokens, data leaks
        for rx, kind, sev, msg in (
            (TOKEN_IN_URL, "token-in-url", "high", "Credential or token passed in the URL query string (leaks into logs, history, referrers)"),
            (HTTP_URL, "plain-http", "medium", "Plain http:// URL used for a non-local endpoint"),
            (LONG_TOKEN, "long-lived-token", "medium", "Token lifetime looks long (days or more): prefer minutes for access tokens plus refresh tokens"),
            (RESPONSE_LEAK, "sensitive-field-near-response", "low", "Sensitive-looking field name in API code: confirm it is never returned to clients"),
            (RAW_RETURN, "raw-object-returned", "low", "A whole object/record is returned directly: confirm only needed fields are sent"),
            (SELECT_ALL, "select-all", "low", "Select-all query: confirm the response is filtered to needed fields and paginated"),
        ):
            m = rx.search(t)
            if m and (nr is not None or any(e["file"].startswith(str(rel) + ":") for e in endpoints) or kind in ("token-in-url", "plain-http", "long-lived-token")):
                findings.append({"kind": kind, "severity": sev, "message": msg, "where": f"{rel}:{t.count(chr(10), 0, m.start()) + 1}"})

    # enrich endpoints
    rank = {"yes": 0, "file-wide?": 1, "none seen": 2}
    best = {}
    for e in endpoints:                     # same route matched twice: keep the strongest auth evidence
        k = (e["method"], e["path"], e["file"])
        if k not in best or rank[e["auth"]] < rank[best[k]["auth"]]:
            best[k] = e
    uniq = []
    for e in best.values():
        v = VERSION.search(e["path"])
        e["version"] = f"v{v.group(1) or v.group(2)}" if v else "none"
        e["object_id_param"] = bool(ID_PARAM.search(e["path"]))
        e["public_by_design"] = bool(PUBLIC_PATH.search(e["path"]))
        uniq.append(e)
    endpoints = sorted(uniq, key=lambda e: (e["path"], e["method"]))

    code_paths = {norm(e["path"]) for e in endpoints}
    versions = sorted({e["version"] for e in endpoints if e["version"] != "none"})
    unauth = [e for e in endpoints if e["auth"] == "none seen" and not e["public_by_design"]]
    summary = {
        "endpoints": len(endpoints),
        "no_auth_seen_not_public": len(unauth),
        "with_object_id_param": sum(e["object_id_param"] for e in endpoints),
        "unversioned": sum(e["version"] == "none" for e in endpoints),
        "versions_seen": versions,
        "multiple_versions_live": len(versions) > 1,
        "openapi_files": spec_files,
        "in_code_not_in_spec": sorted(code_paths - spec_paths)[:40] if spec_paths else None,
        "in_spec_not_in_code": sorted(spec_paths - code_paths)[:40] if spec_paths else None,
        "global_signals": global_flags,
    }
    return {"root": str(root), "summary": summary, "endpoints": endpoints, "findings": sorted(findings, key=lambda f: {"high": 0, "medium": 1, "low": 2}[f["severity"]])}


def to_markdown(R):
    s = R["summary"]
    L = [f"# API inventory: `{R['root']}`", "",
         "> Heuristic leads. Verify by reading the code. 'none seen' means no auth pattern was matched near the route, not that none exists.", "",
         "## Summary", "",
         f"- Endpoints found: **{s['endpoints']}**",
         f"- No authentication seen (excluding login/health/webhook-style paths): **{s['no_auth_seen_not_public']}**",
         f"- Routes with an object-ID parameter (each needs an ownership check): **{s['with_object_id_param']}**",
         f"- Unversioned routes: **{s['unversioned']}**; versions seen: {', '.join(s['versions_seen']) or 'none'}"
         + ("  (several versions live: is there a retirement plan?)" if s["multiple_versions_live"] else ""),
         f"- OpenAPI/Swagger files: {', '.join(s['openapi_files']) or 'none found (rule 12: you have no machine-readable inventory)'}"]
    if s["in_code_not_in_spec"] is not None:
        L.append(f"- In code but not in spec ({len(s['in_code_not_in_spec'])}): {', '.join('`'+x+'`' for x in s['in_code_not_in_spec'][:8]) or 'none'}")
        L.append(f"- In spec but not in code ({len(s['in_spec_not_in_code'])}): {', '.join('`'+x+'`' for x in s['in_spec_not_in_code'][:8]) or 'none'}")
    g = s["global_signals"]
    L += ["", "Global signals (found anywhere in non-test code):", ""]
    for k, label in (("rate_limit", "Rate limiting"), ("https_enforced", "HTTPS/HSTS enforcement"), ("validation", "Input validation library"),
                     ("versioning_policy", "Deprecation / versioning policy wording"), ("auth_failure_logging", "Logging of auth failures")):
        L.append(f"- {label}: {'yes' if g[k] else '**not found**'}")
    L += ["", "## Findings", ""]
    if R["findings"]:
        L += ["| Severity | Issue | Where |", "|---|---|---|"] + [f"| {f['severity']} | {f['message']} | `{f['where']}` |" for f in R["findings"][:40]]
    else:
        L.append("None matched.")
    L += ["", "## Endpoint inventory", "", "| Method | Path | Auth | Version | Object ID | Public? | Where |", "|---|---|---|---|:-:|:-:|---|"]
    for e in R["endpoints"][:300]:
        L.append(f"| {e['method']} | `{e['path']}` | {e['auth']} | {e['version']} | {'yes' if e['object_id_param'] else ''} | {'yes' if e['public_by_design'] else ''} | `{e['file']}` |")
    if len(R["endpoints"]) > 300:
        L.append(f"\n...and {len(R['endpoints']) - 300} more (use --format json)")
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
