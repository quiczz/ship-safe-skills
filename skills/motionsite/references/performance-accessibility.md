# Performance and accessibility

## Budgets

| Metric | Target |
|--------|--------|
| Hero video | 2 to 4 MB mp4 (H.264), optional WebM, 1080p max, 6 to 12 s loop, no audio |
| Poster image | under 150 KB (AVIF or WebP; JPEG fallback), same aspect ratio as the video |
| Total page weight before video | under 300 KB (HTML, CSS, JS, fonts) |
| Largest Contentful Paint | under 2.5 s on a mid-range phone, 4G |
| Cumulative Layout Shift | under 0.1 |
| JavaScript for motion | under 10 KB without libraries; add GSAP or Motion only for effects CSS cannot do |

## Video element checklist

Preferred: create and play the video from script after checking `prefers-reduced-motion` and `saveData` (see `templates/site.html`), so visitors who should not get video never download it. If you write the tag in HTML instead, use this:

```html
<video class="hero-video" autoplay muted loop playsinline preload="metadata"
       poster="assets/hero-poster.webp" width="1920" height="1080" aria-hidden="true" tabindex="-1">
  <source src="assets/hero.webm" type="video/webm">
  <source src="assets/hero.mp4" type="video/mp4">
</video>
```

- `muted` and `playsinline` are required for autoplay on iOS and Chrome.
- `aria-hidden="true"`: background video is decoration. If the video carries meaning, add a text alternative next to it.
- Do not add controls to a background loop; do add a visible pause button if the loop is longer than 5 seconds and sits next to important text (WCAG 2.2.2 Pause, Stop, Hide).
- Pause when off screen with IntersectionObserver; resume when back.
- Do not autoplay when `prefers-reduced-motion: reduce` or `navigator.connection.saveData` is true; show the poster.
- Handle `play()` rejection (`.catch(() => {})`); some browsers still refuse.

## Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; scroll-behavior: auto !important; }
  .reveal { opacity: 1 !important; transform: none !important; }
}
```

Reveals must have a no-JS and a reduced-motion state where content is visible. Never hide content that only JavaScript can show.

## Colour and text

- Normal text 4.5:1, large text (24 px or 19 px bold) 3:1, against the worst frame behind it. Check by pausing the video on its brightest frame.
- Do not convey meaning by colour alone.
- Overlay strength is a design decision: raise it before shrinking the video.

## Layout

- `100svh` for hero height; `min-height` so large text can grow.
- No horizontal scroll at 320 px.
- Touch targets at least 44 by 44 px.
- Fixed navigation should not cover anchor targets: `scroll-margin-top` on sections.

## Structure

One `h1`. Landmarks. A skip link. Buttons and links with text. `alt` text on content images, empty `alt=""` on decoration. Language set on `<html lang>`.

## Test steps

1. `python3 scripts/check_motion.py <site-folder>` and fix every FAIL.
2. Serve the folder and open it at 1440 px and 375 px wide.
3. With Playwright: `page.emulateMedia({ reducedMotion: 'reduce' })` and confirm the video is not playing and content is visible.
4. Throttle the network (Fast 3G): the poster or gradient and headline must appear before the video.
5. Keyboard only: Tab reaches every control with a visible focus ring; Escape and Enter behave.
6. Lighthouse (or PageSpeed Insights) for LCP, CLS and accessibility score. Treat the score as a hint, not a goal.
