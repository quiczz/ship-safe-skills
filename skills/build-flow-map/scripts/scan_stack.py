#!/usr/bin/env python3
"""Scan a project and report how it is built and connected (stdlib only, read-only).

usage: scan_stack.py PROJECT_ROOT [--format markdown|json]

Reports: languages, frameworks, services, commands, entry points, env var NAMES (never values),
HTTP routes, CI/CD, and a rough internal module graph. Everything is heuristic: verify before relying on it.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import tomllib  # py3.11+
except ImportError:  # pragma: no cover
    tomllib = None

SKIP = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "out", "venv", ".venv", "env", "__pycache__",
        "vendor", "target", "coverage", ".gradle", "Pods", ".dart_tool", ".idea", ".turbo", ".cache", "site-packages"}
LANG = {".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript",
        ".tsx": "TypeScript", ".py": "Python", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
        ".java": "Java", ".kt": "Kotlin", ".swift": "Swift", ".dart": "Dart", ".cs": "C#", ".vue": "Vue",
        ".svelte": "Svelte", ".sql": "SQL"}
FRAMEWORKS = {
    "next": "Next.js", "react": "React", "react-dom": "React", "vue": "Vue", "nuxt": "Nuxt", "svelte": "Svelte",
    "@sveltejs/kit": "SvelteKit", "@angular/core": "Angular", "astro": "Astro", "remix": "Remix", "@remix-run/react": "Remix",
    "express": "Express", "fastify": "Fastify", "koa": "Koa", "@nestjs/core": "NestJS", "hono": "Hono",
    "react-native": "React Native", "expo": "Expo", "electron": "Electron", "tailwindcss": "Tailwind CSS",
    "vite": "Vite", "webpack": "Webpack", "typescript": "TypeScript", "prisma": "Prisma", "@prisma/client": "Prisma",
    "drizzle-orm": "Drizzle", "typeorm": "TypeORM", "sequelize": "Sequelize", "mongoose": "Mongoose", "jest": "Jest",
    "vitest": "Vitest", "playwright": "Playwright", "@playwright/test": "Playwright", "cypress": "Cypress",
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI", "sqlalchemy": "SQLAlchemy", "celery": "Celery",
    "pydantic": "Pydantic", "pytest": "pytest", "gunicorn": "Gunicorn", "uvicorn": "Uvicorn", "alembic": "Alembic",
    "rails": "Ruby on Rails", "sinatra": "Sinatra", "laravel/framework": "Laravel", "symfony/symfony": "Symfony",
    "gin-gonic/gin": "Gin", "labstack/echo": "Echo", "gofiber/fiber": "Fiber", "gorm.io/gorm": "GORM",
    "flutter": "Flutter", "spring-boot": "Spring Boot", "actix-web": "Actix Web", "axum": "Axum", "tokio": "Tokio",
}
SERVICES = {  # dependency/import/env fragment -> service label
    "pg": "PostgreSQL", "postgres": "PostgreSQL", "psycopg": "PostgreSQL", "asyncpg": "PostgreSQL",
    "mysql": "MySQL", "mysql2": "MySQL", "pymysql": "MySQL", "mongodb": "MongoDB", "mongoose": "MongoDB", "pymongo": "MongoDB",
    "redis": "Redis", "ioredis": "Redis", "@upstash/redis": "Upstash Redis", "better-sqlite3": "SQLite", "sqlite3": "SQLite",
    "@supabase/supabase-js": "Supabase", "supabase": "Supabase", "firebase": "Firebase", "firebase-admin": "Firebase",
    "@aws-sdk": "AWS", "boto3": "AWS", "aws-sdk": "AWS", "@google-cloud": "Google Cloud", "@azure": "Azure",
    "stripe": "Stripe", "@stripe/stripe-js": "Stripe", "paypal": "PayPal", "@clerk": "Clerk", "next-auth": "NextAuth",
    "auth0": "Auth0", "@auth0": "Auth0", "better-auth": "Better Auth", "passport": "Passport",
    "@sentry": "Sentry", "sentry-sdk": "Sentry", "@datadog": "Datadog", "dd-trace": "Datadog", "newrelic": "New Relic",
    "openai": "OpenAI API", "@anthropic-ai/sdk": "Anthropic API", "anthropic": "Anthropic API", "@google/generative-ai": "Gemini API",
    "sendgrid": "SendGrid", "@sendgrid": "SendGrid", "resend": "Resend", "nodemailer": "SMTP email", "twilio": "Twilio",
    "kafkajs": "Kafka", "kafka-python": "Kafka", "amqplib": "RabbitMQ", "pika": "RabbitMQ", "bullmq": "BullMQ (Redis queue)",
    "posthog": "PostHog", "mixpanel": "Mixpanel", "@segment": "Segment", "algoliasearch": "Algolia", "elasticsearch": "Elasticsearch",
    "cloudinary": "Cloudinary", "socket.io": "WebSockets (Socket.IO)", "ws": "WebSockets", "graphql": "GraphQL",
    "@apollo": "Apollo GraphQL", "@trpc": "tRPC", "@vercel": "Vercel", "wrangler": "Cloudflare Workers",
}
ENV_USE = re.compile(
    r"""(?:process\.env\.([A-Z][A-Z0-9_]+)|process\.env\[['"]([A-Z][A-Z0-9_]+)['"]\]|import\.meta\.env\.([A-Z][A-Z0-9_]+)|"""
    r"""os\.environ(?:\.get)?\(?\[?['"]([A-Z][A-Z0-9_]+)['"]|os\.getenv\(['"]([A-Z][A-Z0-9_]+)['"]|"""
    r"""ENV\[['"]([A-Z][A-Z0-9_]+)['"]\]|(?<![\w.])getenv\(['"]([A-Z][A-Z0-9_]+)['"]|System\.getenv\(['"]([A-Z][A-Z0-9_]+)['"]|"""
    r"""Deno\.env\.get\(['"]([A-Z][A-Z0-9_]+)['"])""")
ROUTE_RX = [
    ("express-like", re.compile(r"""\b(?:app|router|server|api)\.(get|post|put|patch|delete|all)\(\s*['"`](/[^'"`]*)['"`]""")),
    ("fastapi/flask", re.compile(r"""@(?:\w+)\.(get|post|put|patch|delete|route)\(\s*['"](/[^'"]*)['"]""")),
    ("django", re.compile(r"""\b(?:re_)?path\(\s*r?['"]([^'"]*)['"]""")),
    ("go-http", re.compile(r"""(?:HandleFunc|Handle|GET|POST|PUT|DELETE|PATCH)\(\s*"(/[^"]*)\"""")),
]
IMPORT_JS = re.compile(r"""(?:import\s+(?:[^'"]*?\s+from\s+)?|require\(|import\()\s*['"](\.{1,2}/[^'"]+)['"]""")
IMPORT_PY = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w]*)[\w.]*\s+import|import\s+([A-Za-z_][\w]*))", re.M)
MAX_BYTES = 800_000


def walk(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP)
        for fn in sorted(fns):
            p = Path(dp) / fn
            try:
                if p.stat().st_size <= MAX_BYTES:
                    yield p
            except OSError:
                pass


def txt(p):
    try:
        b = p.read_bytes()
        return None if b"\0" in b[:2048] else b.decode("utf-8", "replace")
    except OSError:
        return None


def unit_of(rel: Path):
    parts = rel.parts
    if len(parts) == 1:
        return "."
    if parts[0] in ("src", "app", "lib", "apps", "packages", "services", "pages", "server", "client") and len(parts) > 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def scan(root: Path):
    R = {"root": str(root), "languages": {}, "frameworks": [], "services": [], "commands": {}, "entry_points": [],
         "env_vars": [], "routes": [], "ci": [], "docker": {}, "deploy_configs": [], "module_graph": [], "manifests": [],
         "layout": []}
    lang_lines = Counter()
    deps = {}            # name -> manifest
    env_example, env_used = set(), defaultdict(list)
    routes, entry = [], []
    graph = Counter()
    sources = []
    top_dirs = sorted(d.name for d in root.iterdir() if d.is_dir() and d.name not in SKIP and not d.name.startswith(".")) if root.is_dir() else []

    for p in walk(root):
        rel = p.relative_to(root)
        name = p.name
        ext = p.suffix.lower()
        if ext in LANG:
            t = txt(p)
            if t is not None:
                lang_lines[LANG[ext]] += t.count("\n") + 1
                sources.append((p, rel, t))
        low = name.lower()
        if low in (".env.example", ".env.sample", ".env.template", "env.example", ".env.dist"):
            for line in (txt(p) or "").splitlines():
                m = re.match(r"\s*(?:export\s+)?([A-Z][A-Z0-9_]+)\s*=", line)
                if m:
                    env_example.add(m.group(1))
            R["manifests"].append(str(rel))
        elif name == "package.json" and len(rel.parts) <= 3:
            try:
                j = json.loads(txt(p) or "{}")
            except json.JSONDecodeError:
                continue
            R["manifests"].append(str(rel))
            for k in ("dependencies", "devDependencies", "peerDependencies"):
                for d in (j.get(k) or {}):
                    deps[d] = str(rel)
            prefix = "" if len(rel.parts) == 1 else f"{rel.parent}: "
            for sname, cmd in (j.get("scripts") or {}).items():
                R["commands"][f"{prefix}npm run {sname}"] = cmd
            for key in ("main", "module"):
                if j.get(key):
                    entry.append(f"{rel.parent / j[key]}".lstrip("./"))
            b = j.get("bin")
            if isinstance(b, str):
                entry.append(b)
            elif isinstance(b, dict):
                entry.extend(b.values())
            if j.get("engines"):
                R.setdefault("runtime", {}).update(j["engines"])
        elif low.startswith("requirements") and low.endswith(".txt"):
            R["manifests"].append(str(rel))
            for line in (txt(p) or "").splitlines():
                m = re.match(r"\s*([A-Za-z0-9_.\-]+)", line)
                if m and not line.strip().startswith(("#", "-")):
                    deps[m.group(1).lower().replace("_", "-")] = str(rel)
        elif name == "pyproject.toml":
            R["manifests"].append(str(rel))
            t = txt(p) or ""
            if tomllib:
                try:
                    d = tomllib.loads(t)
                    for item in (d.get("project", {}).get("dependencies") or []):
                        deps[re.split(r"[<>=!~\[ ;]", item)[0].lower()] = str(rel)
                    for k in (d.get("tool", {}).get("poetry", {}).get("dependencies") or {}):
                        deps[k.lower()] = str(rel)
                    for sname, tgt in (d.get("project", {}).get("scripts") or {}).items():
                        R["commands"][sname] = tgt
                except Exception:
                    pass
            else:
                for m in re.finditer(r'^\s*"?([A-Za-z0-9_.\-]+)"?\s*[=<>~]', t, re.M):
                    deps[m.group(1).lower()] = str(rel)
        elif name == "go.mod":
            R["manifests"].append(str(rel))
            for m in re.finditer(r"^\s*(?:require\s+)?([\w.\-]+\.[\w.\-]+/[\w./\-]+)\s+v", txt(p) or "", re.M):
                deps[m.group(1)] = str(rel)
        elif name in ("Gemfile", "composer.json", "pubspec.yaml", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts"):
            R["manifests"].append(str(rel))
            t = txt(p) or ""
            for m in re.finditer(r"""(?:gem\s+['"]|"|^\s{2}|\bartifactId>|implementation\(?\s*['"]|^)([A-Za-z0-9_.\-/]+)""", t, re.M):
                deps.setdefault(m.group(1).lower(), str(rel))
        elif name == "Makefile":
            R["manifests"].append(str(rel))
            for m in re.finditer(r"^([a-zA-Z][\w\-]*):(?!=)", txt(p) or "", re.M):
                R["commands"][f"make {m.group(1)}"] = "Makefile target"
        elif name in ("Dockerfile",) or low.startswith("dockerfile"):
            t = txt(p) or ""
            R["docker"]["dockerfile"] = {"from": re.findall(r"^FROM\s+(\S+)", t, re.M),
                                         "expose": re.findall(r"^EXPOSE\s+(\S+)", t, re.M),
                                         "cmd": (re.findall(r"^(?:CMD|ENTRYPOINT)\s+(.+)$", t, re.M) or [""])[-1][:120]}
        elif low in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            t = txt(p) or ""
            R["docker"]["compose_services"] = re.findall(r"^  ([A-Za-z0-9_\-]+):\s*$", t.split("services:", 1)[-1], re.M)[:20]
            R["docker"]["compose_images"] = sorted(set(re.findall(r"^\s+image:\s*(\S+)", t, re.M)))
            for img in R["docker"]["compose_images"]:
                for frag, svc in (("postgres", "PostgreSQL"), ("mysql", "MySQL"), ("mariadb", "MySQL"), ("mongo", "MongoDB"),
                                  ("redis", "Redis"), ("rabbitmq", "RabbitMQ"), ("kafka", "Kafka"), ("elasticsearch", "Elasticsearch")):
                    if frag in img.lower():
                        deps.setdefault(f"docker:{frag}", str(rel))
        elif rel.parts[:2] == (".github", "workflows") and ext in (".yml", ".yaml"):
            t = txt(p) or ""
            on = re.search(r"^on:\s*(.*)$", t, re.M)
            jobs = re.findall(r"^  ([A-Za-z0-9_\-]+):\s*$", t.split("\njobs:", 1)[-1], re.M) if "jobs:" in t else []
            runs = [r.strip() for r in re.findall(r"^\s*-?\s*run:\s*(.+)$", t, re.M) if r.strip() not in ("|", ">", "|-", ">-")][:8]
            R["ci"].append({"file": str(rel), "triggers": (on.group(1).strip() if on else "see file")[:80],
                            "jobs": jobs, "commands": runs})
        elif name in ("vercel.json", "netlify.toml", "fly.toml", "render.yaml", "railway.json", "wrangler.toml", "wrangler.jsonc",
                      "Procfile", "app.yaml", "serverless.yml", "firebase.json", "amplify.yml", ".gitlab-ci.yml", "Jenkinsfile",
                      "azure-pipelines.yml", "bitbucket-pipelines.yml") or name.endswith(".tf"):
            R["deploy_configs"].append(str(rel))
        if name in ("manage.py", "main.py", "app.py", "server.js", "server.ts", "index.js", "index.ts", "main.go", "main.rs", "wsgi.py", "asgi.py") \
                and len(rel.parts) <= 4:
            entry.append(str(rel))

    # per-source analysis
    for p, rel, t in sources:
        for m in ENV_USE.finditer(t):
            n = next(g for g in m.groups() if g)
            if rel.name.startswith("test") or "/test" in str(rel) or "__tests__" in str(rel):
                continue
            if len(env_used[n]) < 3 and str(rel) not in env_used[n]:
                env_used[n].append(str(rel))
        if len(routes) < 80:
            for kind, rx in ROUTE_RX:
                for m in rx.finditer(t):
                    g = m.groups()
                    method, path = (g[0].upper(), g[1]) if len(g) == 2 else ("PATH", g[0])
                    routes.append({"method": method, "path": path, "file": str(rel), "style": kind})
        # Next.js file-based routes
        parts = rel.parts
        if "app" in parts and rel.stem in ("route", "page"):
            i = parts.index("app")
            seg = [s for s in parts[i + 1:-1] if not (s.startswith("(") and s.endswith(")"))]
            routes.append({"method": "API" if rel.stem == "route" else "PAGE", "path": "/" + "/".join(seg), "file": str(rel), "style": "next-app"})
        if len(parts) > 2 and parts[-3:-1] == ("pages", "api") or (parts[:2] == ("pages", "api")):
            routes.append({"method": "API", "path": "/api/" + str(Path(*parts[2:]).with_suffix("")).replace("\\", "/").replace("/index", ""),
                           "file": str(rel), "style": "next-pages"})
        # internal imports (test code is excluded so it does not dominate the graph)
        if any(x in ("tests", "test", "__tests__", "spec", "e2e") for x in rel.parts):
            continue
        if rel.suffix.lower() in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".vue", ".svelte"):
            for m in IMPORT_JS.finditer(t):
                tgt = (p.parent / m.group(1)).resolve()
                try:
                    trel = tgt.relative_to(root)
                except ValueError:
                    continue
                a, b = unit_of(rel), unit_of(trel)
                if a != b:
                    graph[(a, b)] += 1
        elif rel.suffix == ".py":
            for m in IMPORT_PY.finditer(t):
                mod = m.group(1) or m.group(2)
                if mod in top_dirs or (root / mod).with_suffix(".py").exists():
                    a, b = unit_of(rel), mod
                    if a != b:
                        graph[(a, b)] += 1

    # frameworks + services from dependency names
    fw, svc = set(), set()
    for d in deps:
        key = d.lower()
        for frag, label in FRAMEWORKS.items():
            if key == frag or key.startswith(frag + "/") or (frag.count("/") and frag in key):
                fw.add(label)
        for frag, label in SERVICES.items():
            if key == frag or key.startswith(frag + "/") or key.startswith(frag + "-") and frag.startswith("@") or key == "docker:" + frag:
                svc.add(label)
    for k in list(deps):
        if k.startswith("docker:"):
            svc.add({"postgres": "PostgreSQL", "mysql": "MySQL", "mongo": "MongoDB", "redis": "Redis", "rabbitmq": "RabbitMQ",
                     "kafka": "Kafka", "elasticsearch": "Elasticsearch"}.get(k[7:], k[7:]))
    for n in list(env_example) + list(env_used):
        u = n.upper()
        for frag, label in (("DATABASE_URL", "Database (see DATABASE_URL)"), ("STRIPE_", "Stripe"), ("SUPABASE_", "Supabase"),
                            ("SENTRY_", "Sentry"), ("OPENAI_", "OpenAI API"), ("ANTHROPIC_", "Anthropic API"), ("REDIS_", "Redis"),
                            ("AWS_", "AWS"), ("CLERK_", "Clerk"), ("AUTH0_", "Auth0"), ("SMTP_", "SMTP email"), ("TWILIO_", "Twilio"),
                            ("SENDGRID_", "SendGrid"), ("RESEND_", "Resend"), ("MONGO", "MongoDB")):
            if u.startswith(frag) or u == frag:
                svc.add(label)

    all_env = sorted(set(env_example) | set(env_used))
    R["env_vars"] = [{"name": n, "in_example": n in env_example, "used_in": env_used.get(n, [])} for n in all_env]
    R["languages"] = dict(lang_lines.most_common())
    R["frameworks"] = sorted(fw)
    R["services"] = sorted(svc)
    seen, uniq = set(), []
    for r in routes:
        k = (r["method"], r["path"], r["file"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    R["routes"] = uniq[:80]
    R["entry_points"] = sorted(set(e for e in entry if e))[:15]
    R["module_graph"] = [{"from": a, "to": b, "imports": n} for (a, b), n in graph.most_common(25)]
    R["layout"] = top_dirs
    return R


def md_id(s):
    return re.sub(r"[^A-Za-z0-9]", "_", s) or "root"


def to_markdown(R):
    L = [f"# Stack scan: `{R['root']}`", "",
         "> Heuristic scan. Verify against the code; unknowns belong under 'Unverified'. Env var values are never read.", ""]
    langs = ", ".join(f"{k} ({v:,} lines)" for k, v in list(R["languages"].items())[:6]) or "none detected"
    L += ["## Stack", f"- Languages: {langs}", f"- Frameworks / tools: {', '.join(R['frameworks']) or 'none detected'}",
          f"- Services / integrations: {', '.join(R['services']) or 'none detected'}",
          f"- Runtime requirements: {R.get('runtime') or 'not declared'}",
          f"- Manifests: {', '.join(R['manifests'][:10]) or 'none'}", ""]
    L += ["## Commands (from package scripts / Makefile)"]
    for k, v in list(R["commands"].items())[:25]:
        L.append(f"- `{k}` : {v[:90]}")
    if not R["commands"]:
        L.append("- none found")
    L += ["", "## Entry points"] + ([f"- `{e}`" for e in R["entry_points"]] or ["- none found"])
    L += ["", "## Routes"] + ([f"- {r['method']} `{r['path']}` ({r['file']})" for r in R["routes"][:40]] or ["- none found"])
    L += ["", "## Environment variables (names only)", "", "| Name | In .env.example | Used in |", "|---|:-:|---|"]
    for e in R["env_vars"][:60]:
        L.append(f"| `{e['name']}` | {'yes' if e['in_example'] else 'no'} | {', '.join('`'+u+'`' for u in e['used_in']) or '-'} |")
    if not R["env_vars"]:
        L.append("| none found | | |")
    L += ["", "## Docker / deploy / CI"]
    if R["docker"]:
        L.append(f"- Docker: {json.dumps(R['docker'])[:300]}")
    L += [f"- Deploy configs: {', '.join(R['deploy_configs']) or 'none found'}"]
    for c in R["ci"]:
        L.append(f"- CI `{c['file']}`: on {c['triggers']}; jobs: {', '.join(c['jobs']) or '?'}; runs: " + "; ".join(f"`{x[:50]}`" for x in c["commands"][:4]))
    if not R["ci"]:
        L.append("- No GitHub Actions workflows found")
    L += ["", "## Runtime diagram (draft)", "```mermaid", "flowchart LR", "  client[Browser / Client] --> app[App]"]
    for i, s in enumerate(R["services"][:10]):
        shape = f"{md_id(s)}[({json.dumps(s)})]" if any(x in s for x in ("SQL", "Mongo", "Redis", "Database", "SQLite")) else f"{md_id(s)}[{json.dumps(s)}]"
        L.append(f"  app --> {shape}")
    L += ["```", "", "## Internal module graph (imports between folders)"]
    if R["module_graph"]:
        L += ["```mermaid", "flowchart LR"]
        for g in R["module_graph"][:20]:
            L.append(f"  {md_id(g['from'])}[{json.dumps(g['from'])}] -->|{g['imports']}| {md_id(g['to'])}[{json.dumps(g['to'])}]")
        L.append("```")
    else:
        L.append("- none detected (flat project, or imports not relative)")
    L += ["", "## Top-level folders", ", ".join(f"`{d}/`" for d in R["layout"]) or "(none)"]
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
