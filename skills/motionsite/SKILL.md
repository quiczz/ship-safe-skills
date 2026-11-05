---
name: motionsite
description: Build an animated, video-driven landing page or hero section - full-bleed looping video background with a gradient overlay, glass cards, animated headline and call-to-action buttons, scroll reveals - that stays fast and accessible (poster image, lazy video, reduced-motion and mobile fallbacks). Includes a site template, ffmpeg asset script and a motion audit script. Use proactively when asked for an animated website, motion site, cinematic landing page, video hero, or to make a page feel alive.
---

# Motionsite

Builds the "motion site" look: a full-screen looping video hero, a dark gradient overlay for readable text, glass-effect cards, words that animate in, buttons that react, and sections that reveal on scroll. The difference between a good one and a slow, inaccessible one is the checklist below, so this skill builds the page and then audits it.

Not affiliated with motionsites.ai. This skill contains no third-party prompts or assets.

**Runs on its own:** when you ask for a landing page, hero or animated site, Claude picks this skill, builds from the template and runs the audit before it reports back.

## Procedure

1. **Get the brief in one pass.** Brand name, one-line promise, main call to action, 3 to 6 sections (features, proof, pricing, FAQ), tone (calm, bold, playful, luxury), and any logo, colors or fonts they already own. If the user gave none, choose a direction yourself and say which one.
2. **Pick the stack from the project.** Existing React/Next/Vue/Svelte project: build components in that stack. Empty folder with no preference: use the single-file `templates/site.html` (no build step, opens by double-click). If they ask for React, Vite, TypeScript and Tailwind, use `templates/Hero.tsx` and `templates/useReveal.ts`.
3. **Get the video honest and light.** See `references/assets.md`. Use the user's own footage or a generated or licensed clip, never hotlink someone else's CDN. Until real footage exists, ship the CSS animated gradient background the template includes so the page already looks finished. Real footage is switched on by filling three data attributes on `.hero-media` (`data-video-mp4`, `data-video-webm`, `data-poster`). Make web versions with `scripts/make_video_assets.sh` (mp4 + webm + poster).
4. **Build the page from the template.** Keep these parts: hero (video + overlay + headline + CTA), a glass navigation bar, 3 to 6 content sections with reveal animations, footer. Apply the design recipes in `references/design-recipes.md` (type scale, spacing, palette, glass cards, button states, timing).
5. **Wire the performance and accessibility rules** (below). They are not optional extras; they are what makes the page usable on a phone.
6. **Audit.** Run `python3 <skill-dir>/scripts/check_motion.py <site-folder>` and fix every FAIL. Then look at it in a browser: desktop and phone width, reduced motion on, JavaScript disabled for the first paint. Details in `references/performance-accessibility.md`.
7. **Report** the files made, how to replace the placeholder video, what the audit said, and one thing to look at.

## Rules that decide quality

- **Video**: `muted`, `loop`, `playsinline` (without these mobile browsers refuse to play it in the page), `poster` set, `preload="metadata"`, no audio track. Start playback from script after checking reduced motion and data saver, as the template does, so those visitors never download the video. Target 2 to 4 MB for the hero clip, 1080p at most, 6 to 12 seconds that loop cleanly.
- **Poster is the first paint.** The poster image (or the gradient) is what the visitor sees and what Largest Contentful Paint measures. Give it `fetchpriority="high"` and exact dimensions.
- **Respect the visitor.** Under `prefers-reduced-motion: reduce`, or when data saver is on, show the poster instead of playing video and turn off animations. Pause the video when it is scrolled off screen.
- **Animate only `transform` and `opacity`.** Never animate `top`, `left`, `width`, `height` or `margin`; they force layout and jank on phones.
- **Text stays readable over video.** Put a gradient overlay between video and text, keep body text at least 4.5:1 contrast against the darkest and lightest frame, and never put small text directly on moving footage.
- **One idea per section, one motion per element.** Stagger within 60 to 100 ms steps, durations 400 to 800 ms, ease-out. If everything moves, nothing leads the eye.
- **Mobile first.** Hero uses `100svh`, not `100vh`. Test at 375 px width; no horizontal scroll. Consider a lighter or still hero on small screens.
- **Real content structure.** One `h1`, landmarks (`header`, `main`, `footer`), buttons are `<button>` or `<a>`, links have text, images have `alt`.
- **Own your assets.** No third-party CDN video, fonts self-hosted or from a font provider, licenses recorded in `assets/README.md`.

## Files

| File | Purpose |
|------|---------|
| `templates/site.html` | Complete one-file landing page: video hero (switched on with data attributes) with CSS gradient fallback, glass nav, animated headline, reveal-on-scroll, cards, CTA, footer |
| `templates/Hero.tsx`, `templates/useReveal.ts` | React versions of the hero and the scroll-reveal hook |
| `references/design-recipes.md` | Type, color, spacing, glass, buttons, motion timing, section patterns |
| `references/performance-accessibility.md` | Budgets, reduced motion, video behavior, testing steps |
| `references/assets.md` | Where video comes from, licensing, generating a clip, encoding |
| `scripts/make_video_assets.sh` | ffmpeg: input clip to web mp4, webm, poster |
| `scripts/check_motion.py` | Audit a site folder for the problems above |
