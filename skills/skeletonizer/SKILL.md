---
name: skeletonizer
description: Turn an existing UI into a loading skeleton - find screens and components that show a spinner, blank space or "Loading..." while data loads, then add skeleton placeholders that match the real layout (no layout shift), wired into the framework's loading state, with accessibility and reduced-motion handled. Works with React, Next.js, Vue/Nuxt, Svelte, Angular, plain HTML/CSS, Flutter, SwiftUI and React Native. Use when asked to add skeleton loading, shimmer placeholders, loading states, or to replace spinners. Use proactively whenever you build UI that fetches data, so the loading state is a skeleton from the start.
---

# Skeletonizer

Makes an existing interface feel fast while data loads by showing grey placeholder shapes that look like the final content. It edits the real UI; it does not redesign it.

**Runs on its own:** when Claude builds UI that loads data it writes the skeleton as part of it, and when it writes a bare spinner or "Loading..." for content it is reminded to use a skeleton.

## Two ways to build a skeleton

| Mode | What it is | Use when |
|------|-----------|----------|
| **Mirror** | A separate `XxxSkeleton` component with the same outer layout as `Xxx`, using placeholder blocks | Content shape is different from its loading shape (lists, cards with images, tables), or the framework has a loading slot (`loading.tsx`, `<Suspense fallback>`, `@placeholder`) |
| **Overlay** | The real component stays; a `data-loading` / `aria-busy` state paints its text and images as grey bars with CSS (`templates/skeleton.css`) | The component already renders fine with empty or fake data and you want zero layout drift with the least code |

Prefer **mirror** for routes and lists. Prefer **overlay** for small components (profile header, stat card, form with prefilled values).

## Procedure

1. **Find candidates.** Run
   `python3 <skill-dir>/scripts/find_loading_candidates.py <project>` and read the groups:
   - `spinner-for-content`: a spinner or "Loading..." where content will appear (best wins)
   - `blank-while-loading`: returns `null` while loading, so the area is blank and then jumps
   - `no-loading-state`: client components that fetch data and never handle the loading phase
   - `route-missing-loading`: Next.js App Router pages with data but no `loading.*` in the folder or a parent
   - `async-component-no-suspense`: async server components used without a `<Suspense>` boundary
   - `already-skeleton`: leave alone
   Priority is `high` for pages, screens and real server data calls, `medium` for smaller components or per-request rendering.
   Treat results as leads; open the file before changing it. If the user named a screen, start there and skip the scan.
2. **Understand the real layout.** Read the component and its styles. Write down for each region: size (width, height, aspect ratio), spacing, radius, how many repeats (list rows, cards). Skeleton blocks must use the same numbers or the page will jump when data arrives. If a Playwright or browser tool is available, screenshot the loaded page first and measure real element boxes.
3. **Pick the loading signal** the code already has (`isLoading`, `isPending`, `status === 'pending'`, Suspense, route transition, `@defer`, `FutureBuilder`, `redacted`). Do not add new fetching logic. `references/frameworks.md` has the exact pattern for each framework.
4. **Add the shared pieces once.** Copy `templates/skeleton.css` (styles, shimmer, dark mode, reduced motion) and, for React/Next, `templates/Skeleton.tsx`. Reuse the project's design tokens (colors, radius) if it has them; otherwise keep the template's CSS variables.
5. **Write the skeleton** per component using the rules below. Keep each skeleton next to its component and export it with the same props that affect layout (for example `rows`).
6. **Wire it in** at the loading signal. Replace the spinner for content areas. Keep a small spinner only for button actions and background refreshes.
7. **Add the timing guard** if the data usually arrives in under about 300 ms: show the skeleton only after a short delay and keep it for a minimum time so it does not flash (`templates/useDelayedLoading.ts`, or the CSS-only delay in `skeleton.css`).
8. **Check it.** See "Verify" below. Report what changed and what to look at.

## Rules for a good skeleton

- **Same box, not same pixels.** Match width, height, spacing and radius of the real elements. Text lines: one block per line at line-height, last line shorter (about 60 percent). Avatars: circle of the real size. Images: reserve the real aspect ratio.
- **Repeat honestly.** Use the number of items that fit the first screen, not 50. Use a stable count (for example 5 rows); do not read data to decide.
- **Skeleton content, not chrome.** Headers, nav, buttons, labels and static text that do not depend on data render normally. Never grey out a control the user can already use.
- **No fake data in the DOM.** Skeleton blocks contain no text, so screen readers and search engines do not read invented values.
- **One animation, calm.** A slow shimmer (about 1.5 s) or a gentle pulse. Never both. Stop animation under `prefers-reduced-motion: reduce` (the template does).
- **Theme aware.** Colors come from CSS variables with a dark-mode override.
- **Accessible.** The loading region gets `aria-busy="true"`; skeleton blocks get `aria-hidden="true"`; provide one visually hidden "Loading" message (`role="status"`). When loaded, remove `aria-busy`.
- **Errors and empty states are different.** A skeleton must end. Make sure a failed fetch shows an error and an empty result shows an empty state, never an endless skeleton.
- **Do not skeleton what is instant.** If content is already in cache or bundled, no skeleton.
- **Avoid layout shift.** Same container, same scroll height. For long lists prefer a fixed-height skeleton container.

## Verify

1. Build or type-check (`tsc`, `npm run build`, `flutter analyze`, etc.) and fix errors.
2. Look at it. With Playwright (if available): throttle the network or delay the API route, screenshot the loading state and the loaded state at the same viewport, and compare element positions. A shift of more than a few pixels means the skeleton does not match.
3. Check reduced motion (`page.emulateMedia({ reducedMotion: 'reduce' })`), dark mode, and a narrow mobile width.
4. Check the error and empty paths still render something.
5. If the project has component tests, add one that renders the loading state and asserts `aria-busy="true"`.

## Output to the user

List each file changed with one line on why, the shared files added, anything skipped and why (for example "route already has loading.tsx"), and how to preview the loading state (the delay or throttle used). Do not paste whole components back into chat.

## Files

| File | Purpose |
|------|---------|
| `scripts/find_loading_candidates.py` | Heuristic scan for where skeletons are missing or spinners are used for content |
| `references/frameworks.md` | Exact patterns for React, Next.js, Vue/Nuxt, SvelteKit, Angular, plain HTML, React Native, Flutter, SwiftUI |
| `references/anatomy.md` | How to turn common UI (list row, card, table, profile, chart, form) into skeleton blocks |
| `templates/skeleton.css` | Shimmer, dark mode, reduced motion, overlay mode, delayed show |
| `templates/Skeleton.tsx` | React primitives: `Skeleton`, `SkeletonText`, `SkeletonAvatar`, `SkeletonRegion` |
| `templates/useDelayedLoading.ts` | Hook that delays showing and enforces a minimum display time |
| `templates/next-loading.tsx` | Example Next.js `loading.tsx` |
| `templates/demo.html` | Open in a browser to preview mirror mode, overlay mode, dark mode |
