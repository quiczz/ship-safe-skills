#!/usr/bin/env python3
"""Audit a motion-heavy site for performance and accessibility problems. Stdlib only, read-only.

    python3 check_motion.py SITE_DIR [--json]

Checks HTML/JSX/Vue/Svelte/CSS/JS for: video attributes, video file size/audio, reduced-motion support,
layout-property animation, scroll listeners, 100vh heroes, headings/alt/lang/viewport, focus outlines,
content hidden until JS runs, hotlinked video. Exit code 1 if any FAIL (usable in CI).
These are heuristics: open the file before you change it.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKIP = {"node_modules", ".git", ".next", ".nuxt", "dist", "build", "out", "coverage", ".svelte-kit", "vendor", "__pycache__"}
MARKUP = {".html", ".htm", ".tsx", ".jsx", ".vue", ".svelte", ".astro"}
STYLE = {".css", ".scss", ".sass", ".less"}
SCRIPT = {".js", ".mjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte", ".astro", ".html", ".htm"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v", ".ogv"}
LAYOUT_PROPS = r"(?:top|left|right|bottom|width|height|min-width|min-height|max-width|max-height|margin(?:-[a-z]+)?|padding(?:-[a-z]+)?|font-size|border-width)"

results = []


def add(level, check, where, msg):
    results.append({"level": level, "check": check, "where": where, "message": msg})


def walk(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP and not d.startswith(".")]
        for fn in fns:
            yield Path(dp) / fn


def blank_comments(text, suffix):
    def keep_lines(m):
        return "\n" * m.group(0).count("\n")
    text = re.sub(r"/\*.*?\*/", keep_lines, text, flags=re.S)
    if suffix in MARKUP:
        text = re.sub(r"<!--.*?-->", keep_lines, text, flags=re.S)
    return text


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def has_attr(tag, name):
    return re.search(r"(?i)(?<![\w-])" + name + r"(?![\w-])", tag) is not None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = Path(a.site).resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    files = [p for p in walk(root)]
    css_text_all, js_text_all = "", ""
    anim_found = False
    reduced_css = False
    reduced_js = False
    video_tags = 0
    backdrop_count = 0
    willchange_count = 0
    html_pages = 0

    for p in files:
        suf = p.suffix.lower()
        rel = p.relative_to(root).as_posix()

        if suf in VIDEO_EXT:
            size = p.stat().st_size
            mb = size / 1048576
            if mb > 6:
                add("FAIL", "video-size", rel, f"{mb:.1f} MB. Keep the hero clip at 2 to 4 MB (lower resolution, shorter, higher CRF).")
            elif mb > 4:
                add("WARN", "video-size", rel, f"{mb:.1f} MB. Target 2 to 4 MB.")
            if shutil.which("ffprobe"):
                try:
                    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", str(p)],
                                         capture_output=True, text=True, timeout=30).stdout
                    streams = json.loads(out or "{}").get("streams", [])
                    if any(s.get("codec_type") == "audio" for s in streams):
                        add("WARN", "video-audio", rel, "Has an audio track. Background video should have none (-an).")
                    vs = [s for s in streams if s.get("codec_type") == "video"]
                    if vs and vs[0].get("width", 0) > 1920:
                        add("WARN", "video-resolution", rel, f"{vs[0]['width']}x{vs[0].get('height')} is larger than 1080p.")
                except Exception:
                    pass
            continue

        if suf not in MARKUP | STYLE | SCRIPT:
            continue
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if len(raw) > 1_500_000:
            continue
        text = blank_comments(raw, suf)

        # ---- CSS (also <style> blocks inside markup) ----
        css = text if suf in STYLE else "\n".join(re.findall(r"(?is)<style[^>]*>(.*?)</style>", text)) if suf in MARKUP else ""
        if suf in {".vue", ".svelte", ".astro"}:
            css = css or text
        if css:
            css_text_all += "\n" + css
            if re.search(r"@keyframes|animation\s*:|transition\s*:", css):
                anim_found = True
            if "prefers-reduced-motion" in css:
                reduced_css = True
            backdrop_count += len(re.findall(r"(?<!-webkit-)backdrop-filter\s*:", css))
            willchange_count += len(re.findall(r"will-change\s*:", css))
            for m in re.finditer(r"@keyframes\s+([\w-]+)\s*\{((?:[^{}]|\{[^{}]*\})*)\}", css):
                bad = sorted(set(re.findall(r"(?<![\w-])(" + LAYOUT_PROPS + r")\s*:", m.group(2))))
                if bad:
                    add("FAIL", "layout-animation", f"{rel}:{line_of(text, text.find(m.group(0)))}",
                        f"@keyframes {m.group(1)} animates {', '.join(bad)}. Animate transform and opacity instead (layout properties cause jank).")
            for m in re.finditer(r"transition\s*:\s*([^;}{]+)", css):
                val = m.group(1)
                if re.search(r"(?<![\w-])all(?![\w-])", val):
                    add("WARN", "transition-all", f"{rel}:{line_of(text, text.find(m.group(0)))}", "transition: all animates everything, including layout. List the properties.")
                elif re.search(r"(?<![\w-])" + LAYOUT_PROPS + r"(?![\w-])", val):
                    add("WARN", "layout-transition", f"{rel}:{line_of(text, text.find(m.group(0)))}", f"Transition on a layout property ({val.strip()[:50]}). Prefer transform/opacity.")
            for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
                sel, body = m.group(1).strip(), m.group(2)
                if re.search(r"outline\s*:\s*(none|0)\b", body) and "focus-visible" not in sel and "focus-within" not in sel:
                    if ":focus" in sel and not re.search(r"box-shadow|border|outline-offset|background", body.replace("outline: none", "")):
                        add("WARN", "focus-outline", rel, f"{sel[:60]} removes the focus outline without a replacement.")
                if re.search(r"(reveal|fade-?in|appear|animate-in)", sel) and re.search(r"opacity\s*:\s*0(?![.\d])", body):
                    if not re.search(r"(^|[\s,])(html)?\.js\b|\.no-js|\[data-js", sel):
                        add("WARN", "hidden-until-js", rel, f"{sel[:60]} starts at opacity 0 for everyone. Scope it under .js so content shows without JavaScript.")
            if re.search(r"(?<![\w-])100vh(?![\w])", css) and not re.search(r"100[sd]vh", css):
                add("WARN", "100vh", rel, "Uses 100vh. On phones the browser bar makes that taller than the screen; use 100svh (with 100vh fallback).")

        # ---- JS ----
        js = text if suf in {".js", ".mjs", ".ts"} else "\n".join(re.findall(r"(?is)<script[^>]*>(.*?)</script>", text)) if suf in MARKUP else ""
        if suf in {".tsx", ".jsx", ".vue", ".svelte", ".astro"}:
            js = js or text
        if js:
            js_text_all += "\n" + js
            if "prefers-reduced-motion" in js:
                reduced_js = True
            for m in re.finditer(r"addEventListener\(\s*['\"]scroll['\"]\s*,", js):
                if "passive" not in js[m.start(): m.start() + 400]:
                    add("WARN", "scroll-listener", f"{rel}:{line_of(text, text.find(js[m.start(): m.start() + 40]))}",
                        "Scroll listener without { passive: true }. For reveals use IntersectionObserver; for effects use CSS scroll-driven animation or requestAnimationFrame.")
            if re.search(r"\.(offsetTop|offsetHeight|getBoundingClientRect)\b", js) and re.search(r"['\"]scroll['\"]", js):
                add("WARN", "layout-read-on-scroll", rel, "Reads layout (getBoundingClientRect/offset*) in a scroll handler. Cache values or use IntersectionObserver.")

        # ---- Markup ----
        if suf in MARKUP:
            is_page = suf in {".html", ".htm"} and re.search(r"(?i)<html\b", text)
            if is_page:
                html_pages += 1
                if not re.search(r"(?i)<html[^>]*\blang=", text):
                    add("WARN", "html-lang", rel, "<html> has no lang attribute.")
                if not re.search(r'(?i)<meta[^>]+name=["\']viewport', text):
                    add("FAIL", "viewport", rel, "Missing <meta name=viewport>. The page will not scale on phones.")
                n_h1 = len(re.findall(r"(?i)<h1\b", text))
                if n_h1 != 1:
                    add("WARN", "h1-count", rel, f"{n_h1} <h1> elements; use exactly one.")
                if not re.search(r"(?i)<main\b", text):
                    add("WARN", "landmarks", rel, "No <main> landmark.")
            for m in re.finditer(r"(?is)<img\b[^>]*>", text):
                if not re.search(r"(?i)(?<![\w-])alt\s*=", m.group(0)):
                    add("FAIL", "img-alt", f"{rel}:{line_of(text, m.start())}", "<img> without alt. Use alt text, or alt=\"\" for decoration.")
            for m in re.finditer(r"(?is)<video\b[^>]*>", text):
                video_tags += 1
                tag = m.group(0)
                where = f"{rel}:{line_of(text, m.start())}"
                auto = has_attr(tag, "autoplay")
                muted = has_attr(tag, "muted")
                plays = has_attr(tag, "playsinline")
                if auto and not muted:
                    add("FAIL", "video-muted", where, "autoplay without muted. Browsers block it, and sound on load is hostile.")
                if (auto or muted) and not plays:
                    add("FAIL", "video-playsinline", where, "Missing playsinline. iOS will open the video full screen instead of playing it in the page.")
                if not has_attr(tag, "poster"):
                    add("FAIL", "video-poster", where, "No poster. The poster is the first paint and the fallback for reduced motion.")
                if re.search(r"(?i)preload\s*=\s*[\"']?auto", tag):
                    add("WARN", "video-preload", where, "preload=auto downloads the whole video. Use preload=\"metadata\".")
                if not (has_attr(tag, "width") and has_attr(tag, "height")) and not has_attr(tag, "style") and "class" not in tag.lower():
                    add("WARN", "video-size-attrs", where, "No width/height; reserve space to avoid layout shift.")
            for m in re.finditer(r"(?is)<(?:video|source)\b[^>]*\bsrc\s*=\s*[\"'](https?://[^\"']+)", text):
                add("WARN", "video-hotlink", f"{rel}:{line_of(text, m.start())}", f"Video loaded from {m.group(1)[:60]}. Host your own copy; do not hotlink.")

    # ---- Cross-file checks ----
    if anim_found and not (reduced_css or reduced_js):
        add("FAIL", "reduced-motion", "(site)", "Animations exist but nothing handles prefers-reduced-motion. Add the media query (see references/performance-accessibility.md).")
    if video_tags and not (reduced_js or reduced_css):
        add("FAIL", "video-reduced-motion", "(site)", "Video exists but reduced motion / data saver are not handled. Show the poster instead of playing.")
    if backdrop_count > 4:
        add("WARN", "backdrop-filter", "(site)", f"{backdrop_count} backdrop-filter rules. Blur is expensive on phones; keep 2 or 3 surfaces visible at once.")
    if willchange_count > 6:
        add("WARN", "will-change", "(site)", f"{willchange_count} will-change declarations. Use it only on elements that animate continuously.")
    if video_tags and not re.search(r"IntersectionObserver", js_text_all):
        add("WARN", "video-offscreen", "(site)", "Video is never paused off screen (no IntersectionObserver found).")
    if html_pages == 0 and not any(p.suffix.lower() in MARKUP for p in files):
        add("WARN", "no-markup", "(site)", "No HTML/JSX/Vue/Svelte files found in this folder.")

    fails = [r for r in results if r["level"] == "FAIL"]
    warns = [r for r in results if r["level"] == "WARN"]
    if a.json:
        print(json.dumps({"site": str(root), "fail": len(fails), "warn": len(warns), "results": results}, indent=2))
    else:
        print(f"Motion audit: {root}")
        print(f"{len(fails)} FAIL, {len(warns)} WARN | video tags: {video_tags}, animation found: {'yes' if anim_found else 'no'}, reduced-motion handled: {'yes' if (reduced_css or reduced_js) else 'no'}\n")
        for lvl in ("FAIL", "WARN"):
            for r in [x for x in results if x["level"] == lvl]:
                print(f"  {lvl}  [{r['check']}] {r['where']}\n        {r['message']}")
        if not results:
            print("  PASS  Nothing found by these checks. Still look at it on a phone with reduced motion on.")
        print("\nHeuristic checks, not a full audit. Run Lighthouse and test by hand too.")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
