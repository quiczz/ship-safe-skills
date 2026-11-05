#!/usr/bin/env python3
"""Find where a project needs loading skeletons. Stdlib only, read-only.

    python3 find_loading_candidates.py PROJECT_DIR [--json] [--all] [--max N]

Groups (leads, not verdicts - open the file before changing it):
  spinner-for-content        a spinner or "Loading..." where content will appear
  blank-while-loading        returns null/empty while a loading flag is true (blank flash)
  no-loading-state           fetches data on the client but has no loading handling at all
  route-missing-loading      Next.js App Router page with data but no loading.* up the tree
  async-component-no-suspense  async server component with no <Suspense> around its usage
  already-skeleton           has a skeleton already (leave alone)
--all also lists low-priority items (static routes). Exit code is always 0.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {
    "node_modules", ".git", ".next", ".nuxt", ".output", ".svelte-kit", "dist", "build", "out", "coverage",
    "vendor", "__pycache__", ".dart_tool", "Pods", "DerivedData", ".turbo", ".cache", ".venv", "venv",
    ".gradle", ".idea", ".vscode", "storybook-static", "android", "ios", ".expo", "public", "static",
    "cypress", "e2e", "playwright", "__tests__", "__mocks__", "tests", "test",
}
EXTS = {".tsx", ".jsx", ".ts", ".js", ".mjs", ".vue", ".svelte", ".astro", ".html", ".dart", ".swift", ".kt"}
SKIP_NAME = re.compile(r"(\.d\.ts$|\.min\.|\.stories\.|\.story\.|\.test\.|\.spec\.|\.config\.|_test\.dart$|Tests?\.swift$)")
NON_UI_DIRS = {"hooks", "api", "lib", "services", "service", "utils", "util", "store", "stores", "server", "models",
               "types", "schemas", "repositories", "repository", "providers", "middleware", "actions", "queries"}
MAX_BYTES = 400_000

R = lambda p: re.compile(p)
FETCH = R(r"\b(useQuery|useInfiniteQuery|useSWR|useSWRInfinite|useFetch|useLazyFetch|useAsyncData|useLazyAsyncData|createResource|FutureBuilder|StreamBuilder|AsyncValue|URLSession|HttpClient)\b|\bfetch\(|\baxios\.|\$fetch\(|\bonMounted\b|\bngOnInit\b|\binitState\b")
CLIENT_FETCH = R(r"\b(useQuery|useInfiniteQuery|useSWR|useSWRInfinite|useFetch|useLazyFetch|useAsyncData|useLazyAsyncData|createResource|FutureBuilder|StreamBuilder|HttpClient|URLSession)\b|\baxios\.|\$fetch\(|\bfetch\(")
EFFECT = R(r"\buseEffect\b|\bonMounted\b|\bonMount\b|\bngOnInit\b|\binitState\b|\buseQuery\b|\buseSWR\b|\buseFetch\b|\buseAsyncData\b|FutureBuilder|StreamBuilder|HttpClient|\.task\s*\{")
LOADING_FLAG = R(r"\b(isLoading|isPending|isFetching|isInitialLoading|isValidating|loading|pending|isLoaded|hasData|fetching)\b|status\s*===?\s*['\"](pending|loading)|ConnectionState\.waiting|\{#await|\.when\(|AsyncLoading|\.redacted\(|\bSuspense\b|v-if=\"[^\"]*(loading|pending)|\*ngIf=\"[^\"]*(loading|pending)|@if\s*\([^)]*(loading|pending)")
SPINNER = R(r"<(Spinner|Loader2?|Loading|LoadingSpinner|CircularProgress|LinearProgress|ActivityIndicator|ClipLoader|BeatLoader|PulseLoader|ScaleLoader|CgSpinner|ImSpinner\d*|ProgressView|q-spinner[\w-]*|b-spinner|mat-spinner|mat-progress-spinner|v-progress-circular|ion-spinner|Loader)\b|\bCircularProgressIndicator\b|\banimate-spin\b|class(Name)?=[\"'][^\"']*\bspinner\b|ProgressView\(|\bngx-spinner\b|react-spinners")
LOADING_TEXT = R(r">\s*(Loading|Please wait)[^<{]{0,20}<|[\"'`](Loading|Please wait)(\.\.\.|…)?[\"'`]|\bLoading(\.\.\.|…)")
SKELETON = R(r"[Ss]keleton|[Ss]himmer|\bBone\b|\.redacted\(|placeholder-glow|\banimate-pulse\b|ion-skeleton-text|\bsk-o\b|class(Name)?=[\"'][^\"']*\bsk\b|ContentLoader|react-loading-skeleton")
SUSPENSE = R(r"<Suspense\b")
BLANK_ON_LOAD = R(r"if\s*\(\s*(isLoading|loading|isPending|isFetching|!data|!isLoaded)\s*\)\s*\{?\s*return\s*(null|<>\s*</>|false|undefined)\s*;?")
BUTTONISH = R(r"<button|<Button|\bbtn\b|[Ss]ubmit|disabled|isSubmitting|isSaving|isMutating|isDeleting|isUploading|mutation|loadingIndicator|<IconButton|ElevatedButton|FilledButton|TextButton|Pressable|TouchableOpacity")
DATA_CALL = R(r"\bawait\s+(?!params\b|searchParams\b|cookies\(|headers\()|\bfetch\(|\bprisma\.|\bdb\.|\bsupabase\.")
DYNAMIC_API = R(r"\bcookies\(\)|\bheaders\(\)|\bsearchParams\b|dynamic\s*=\s*['\"]force-dynamic")
ASYNC_COMPONENT = R(r"(?:export\s+default\s+)?async\s+function\s+([A-Z]\w*)\s*\(|export\s+const\s+([A-Z]\w*)\s*=\s*async\s*\(")
JSXISH = R(r"return\s*\(?\s*<|<[A-Z][A-Za-z]*[\s/>]|=>\s*\(?\s*<")
SPECIAL_STEMS = {"opengraph-image", "twitter-image", "icon", "apple-icon", "sitemap", "robots", "manifest", "route", "middleware", "instrumentation"}
PAGE_FILE = R(r"^page\.(tsx|jsx|js|ts)$")
LOADING_FILE = R(r"^loading\.(tsx|jsx|js|ts)$")


def walk(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            p = Path(dp) / fn
            if p.suffix in EXTS and not SKIP_NAME.search(fn):
                try:
                    if p.stat().st_size <= MAX_BYTES:
                        yield p
                except OSError:
                    pass


def read(p):
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


COMMENT_START = ("//", "*", "/*", "<!--", "///")


def blank_comments(text):
    """Blank out whole-line comments so words in comments do not match. Line numbers stay the same."""
    return "\n".join("" if l.lstrip().startswith(COMMENT_START) else l for l in text.splitlines())


def first_line(lines, rx, start=0):
    for i in range(start, len(lines)):
        if rx.search(lines[i]):
            return i + 1, lines[i].strip()[:110]
    return None, ""


def detect_frameworks(root):
    found = []
    pjs = [root / "package.json"] + sorted(root.glob("*/package.json")) + sorted(root.glob("*/*/package.json"))
    pjs = [x for x in pjs if x.exists() and "node_modules" not in x.parts]
    for pj in pjs:
        try:
            d = json.loads(pj.read_text())
            deps = {**d.get("dependencies", {}), **d.get("devDependencies", {})}
            for k, label in [("next", "Next.js"), ("react", "React"), ("react-native", "React Native"), ("vue", "Vue"), ("nuxt", "Nuxt"),
                             ("svelte", "Svelte"), ("@sveltejs/kit", "SvelteKit"), ("@angular/core", "Angular"), ("@remix-run/react", "Remix"),
                             ("react-router", "React Router"), ("@tanstack/react-query", "TanStack Query"), ("swr", "SWR"), ("astro", "Astro"),
                             ("tailwindcss", "Tailwind"), ("react-loading-skeleton", "react-loading-skeleton (already installed)")]:
                if k in deps and label not in found:
                    found.append(label)
        except Exception:
            pass
    ps = root / "pubspec.yaml"
    if ps.exists():
        t = read(ps)
        found.append("Flutter" if "flutter:" in t else "Dart")
        if "skeletonizer" in t:
            found.append("skeletonizer (already installed)")
    if list(root.glob("*.xcodeproj")) or (root / "Package.swift").exists():
        found.append("Swift/SwiftUI")
    return found


def app_dirs(root):
    """Next.js App Router roots: any folder named app (depth <= 4) that has a layout.* or page.* directly inside."""
    found = []
    base = len(root.parts)
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
        if len(Path(dp).parts) - base > 4:
            dns[:] = []
            continue
        if Path(dp).name == "app" and any(re.match(r"^(layout|page)\.(tsx|jsx|js|ts)$", f) for f in fns):
            found.append(Path(dp))
    return found


def next_route_checks(root, add):
    for app in app_dirs(root):
        for dp, dns, fns in os.walk(app):
            dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith("_") and not d.startswith("@")]
            page = next((f for f in fns if PAGE_FILE.match(f)), None)
            if not page:
                continue
            d = Path(dp)
            covered = False
            cur = d
            while True:
                if any(LOADING_FILE.match(f.name) for f in cur.iterdir() if f.is_file()):
                    covered = True
                    break
                if cur == app:
                    break
                cur = cur.parent
            if covered:
                continue
            text = read(d / page)
            lines = text.splitlines()
            server = "use client" not in text[:200]
            data_call = server and bool(DATA_CALL.search(text))
            dyn_api = server and bool(DYNAMIC_API.search(text))
            client_fetch = bool(CLIENT_FETCH.search(text))
            rel = (d / page).relative_to(root).as_posix()
            if SKELETON.search(text) or SUSPENSE.search(text):
                continue  # the page handles its own loading
            if data_call:
                n, ev = first_line(lines, DATA_CALL)
                add("route-missing-loading", rel, n, "high", ev,
                    "Server page awaits data and has no loading.* in this folder or any parent. Add loading.tsx (mirror mode) or a <Suspense> around the slow part.")
            elif dyn_api:
                n, ev = first_line(lines, DYNAMIC_API)
                add("route-missing-loading", rel, n, "medium", ev,
                    "Page renders per request (cookies/headers/searchParams). Navigation waits on the server, so a loading.tsx makes it feel instant.")
            elif client_fetch:
                n, ev = first_line(lines, CLIENT_FETCH)
                add("route-missing-loading", rel, n, "medium", ev,
                    "Client page fetches data; check its own loading state. A loading.tsx still helps for navigation.")
            else:
                add("route-missing-loading", rel, None, "low", "no data access found",
                    "Probably static, so no skeleton needed.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="include low-priority leads")
    ap.add_argument("--max", type=int, default=40, help="max leads shown per group (default 40)")
    a = ap.parse_args()

    root = Path(a.project).resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    leads = defaultdict(list)

    def add(group, rel, line, prio, evidence, hint):
        leads[group].append({"file": rel, "line": line, "priority": prio, "evidence": evidence, "hint": hint})

    files = list(walk(root))
    texts = {p: blank_comments(read(p)) for p in files}
    async_components = {}  # name -> file

    for p in files:
        text = texts[p]
        if not text.strip():
            continue
        rel = p.relative_to(root).as_posix()
        parts = set(p.relative_to(root).parts[:-1])
        stem = p.stem.lower()
        lines = text.splitlines()
        has_skeleton = bool(SKELETON.search(text))
        has_flag = bool(LOADING_FLAG.search(text))
        # Dart/Swift/Kotlin keep their UI under lib/ or similar, so only skip clearly non-UI folders there
        non_ui = NON_UI_DIRS - {"lib", "models", "providers", "services", "service", "repositories", "repository"} if p.suffix in {".dart", ".swift", ".kt"} else NON_UI_DIRS
        is_ui_dir = not (parts & non_ui) and not p.name.startswith("use")
        is_primitive = bool(re.search(r"(spinner|loader|loading|progress|skeleton|shimmer)", stem))
        is_page_like = bool(re.search(r"(page|screen|view|route)", stem) or parts & {"pages", "screens", "views", "routes", "app"})
        is_markup = p.suffix in {".tsx", ".jsx", ".vue", ".svelte", ".astro", ".html", ".dart", ".swift", ".kt"}

        if is_primitive and re.search(r"skeleton|shimmer", stem):
            continue
        if stem in SPECIAL_STEMS:
            continue
        if has_skeleton and not is_primitive:
            n, ev = first_line(lines, SKELETON)
            add("already-skeleton", rel, n, "info", ev, "Has a skeleton already. Check it matches the layout; otherwise leave it.")
        if not is_markup or not is_ui_dir:
            continue

        # spinner / "Loading..." used where content will appear
        if not is_primitive:
            sp_hits = [i for i, l in enumerate(lines) if SPINNER.search(l) or LOADING_TEXT.search(l)]
            content_hits = []
            for i in sp_hits:
                window = "\n".join(lines[max(0, i - 1): i + 2])
                if not BUTTONISH.search(window):
                    content_hits.append(i)
            if content_hits and (has_flag or FETCH.search(text)):
                i = content_hits[0]
                add("spinner-for-content", rel, i + 1, "high" if is_page_like else "medium", lines[i].strip()[:110],
                    "Replace with a skeleton of the content that will appear (keep spinners for button actions).")

        # blank flash
        if BLANK_ON_LOAD.search(text) and not has_skeleton:
            n, ev = first_line(lines, BLANK_ON_LOAD)
            add("blank-while-loading", rel, n, "high" if is_page_like else "medium", ev,
                "Renders nothing while loading, so the area is blank then jumps. Render a skeleton instead.")
        # client fetch with no handling at all
        elif (CLIENT_FETCH.search(text) and EFFECT.search(text) and not has_flag and not has_skeleton and not SPINNER.search(text)
              and not LOADING_TEXT.search(text)):
            n, ev = first_line(lines, CLIENT_FETCH)
            add("no-loading-state", rel, n, "high" if is_page_like else "medium", ev,
                "Fetches on the client but never handles the loading phase. Find where the data is stored and add a skeleton for 'no data yet'.")

        # async server components
        if p.suffix in {".tsx", ".jsx"} and "use client" not in text[:200] and not PAGE_FILE.match(p.name) and p.stem not in {"layout", "template", "loading", "error", "not-found", "route"}:
            for m in ASYNC_COMPONENT.finditer(text):
                name = m.group(1) or m.group(2)
                body = text[m.end(): m.end() + 1500]
                if re.search(r"\bawait\b", body):
                    async_components[name] = (rel, text[:m.start()].count("\n") + 1, lines[text[:m.start()].count("\n")].strip()[:110])
            if p.stem and p.stem[0].isupper() and re.search(r"export\s+default\s+async\s+function\s*\(", text) and re.search(r"\bawait\b", text):
                async_components[p.stem] = (rel, 1, "export default async function")

    # Suspense check for async components
    for name, (rel, line, ev) in async_components.items():
        use_rx = re.compile(r"<" + re.escape(name) + r"\b")
        usages, wrapped = 0, 0
        for p, t in texts.items():
            if p.relative_to(root).as_posix() == rel:
                continue
            tl = t.splitlines()
            for i, l in enumerate(tl):
                if use_rx.search(l):
                    usages += 1
                    if any(SUSPENSE.search(x) for x in tl[max(0, i - 5): i + 1]):
                        wrapped += 1
        if wrapped == 0:
            add("async-component-no-suspense", rel, line, "high" if usages else "medium", ev,
                f"{name} awaits data and is {'used' if usages else 'not found in JSX'} without a <Suspense> boundary nearby ({usages} usage(s)). "
                "Wrap it in <Suspense fallback={<...Skeleton />}> so the rest of the page renders first.")

    next_route_checks(root, add)

    # filter + order
    order = ["spinner-for-content", "blank-while-loading", "no-loading-state", "route-missing-loading", "async-component-no-suspense", "already-skeleton"]
    prio_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    result = {}
    for g in order:
        items = leads.get(g, [])
        if not a.all:
            items = [x for x in items if x["priority"] != "low"]
        items.sort(key=lambda x: (prio_rank[x["priority"]], x["file"]))
        result[g] = items

    frameworks = detect_frameworks(root)
    if a.json:
        print(json.dumps({"project": str(root), "frameworks": frameworks, "files_scanned": len(files), "leads": result}, indent=2))
        return

    print(f"Skeleton candidates for {root}")
    print(f"Frameworks: {', '.join(frameworks) or 'not detected'} | files scanned: {len(files)}")
    total = sum(len(v) for g, v in result.items() if g != "already-skeleton")
    print(f"{total} lead(s) to look at, {len(result['already-skeleton'])} file(s) already have skeletons.\n")
    for g in order:
        items = result[g]
        if not items:
            continue
        print(f"== {g} ({len(items)})")
        for x in items[: a.max]:
            loc = f"{x['file']}:{x['line']}" if x["line"] else x["file"]
            print(f"  [{x['priority']}] {loc}")
            print(f"        {x['evidence']}")
            if g != "already-skeleton":
                print(f"        -> {x['hint']}")
        if len(items) > a.max:
            print(f"  ... {len(items) - a.max} more (use --max or --json)")
        print()
    if total == 0:
        print("Nothing obvious found. Name the screen you want skeletons for and read it directly.")
    print("These are leads from pattern matching, not verdicts. Open each file before changing it.")


if __name__ == "__main__":
    main()
