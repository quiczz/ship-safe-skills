# Anatomy: turning common UI into skeleton blocks

Measure the real thing first (DevTools, or Playwright `locator.boundingBox()`), then copy the numbers.

## Text

A line of text occupies its **line-height**, not its font size. For 14px text at line-height 22px, use a 22px-tall row with a 14px-tall bar centred in it (`SkeletonText lineHeight={22} textSize={14}`). Last line about 60 percent wide. Headings: one bar, about 50 to 70 percent wide, at the heading's line-height.

Width guide when the text is unknown: names 30 to 45 percent, titles 50 to 70 percent, body 100 percent with a shorter last line, labels 20 to 30 percent.

## Patterns

| UI | Skeleton |
|----|----------|
| **List row** (avatar + title + subtitle) | Circle (real avatar size), two text bars; row height equals the real row height; 5 to 8 rows |
| **Card with image** | Image box with the real `aspect-ratio`, then title bar and two body lines; same card padding and border |
| **Card grid** | Same CSS grid with 6 (or one screenful) placeholder cards |
| **Table** | Real header row; N body rows at the real row height; each cell a bar at its column's typical width; keep column widths fixed (`table-layout: fixed`) so they do not jump |
| **Profile header** | Avatar circle, name bar, handle bar, button-sized block; keep the follow/edit button real if it does not depend on data |
| **Article** | Title (2 bars), meta bar, hero image box at real ratio, then 8 to 12 text lines |
| **Stat tile** | Label bar (40 percent), value bar (60 percent, value font height), optional sparkline box |
| **Chart** | One rounded box at the chart's height, optionally 3 faint horizontal gridlines. Never fake bars or lines: they read as real data |
| **Form (edit)** | Labels render normally; each input is a block at the input height; submit button stays real but disabled |
| **Sidebar / nav** | Usually static: render it. Skeleton only data-driven items (projects, channels) |
| **Comment thread** | Avatar, two short bars, one full-width bar; repeat 3 |
| **Image gallery** | Boxes at the real aspect ratio in the real grid |
| **Detail page with tabs** | Real tab bar; skeleton only the active tab's content |
| **Map, video, embed** | A single box at the real size, no shimmer needed if it loads in its own frame |

## Sizes that matter for no layout shift

- Container height: if the loaded content's height varies, give the skeleton a typical height and let it grow; for infinite lists, fix the container (`min-height`).
- Images in the loaded UI should have `width`/`height` or `aspect-ratio` too, otherwise the page shifts when they arrive even with a perfect skeleton.
- Scrollbars: if the loaded page scrolls and the skeleton does not, content shifts by the scrollbar width. Use `scrollbar-gutter: stable` on the scroll container or make the skeleton tall enough.
- Fonts: fallback fonts have different metrics, so text bars use `lineHeight` in px, not `em` of the fallback.

## Measuring in the browser

```js
// Playwright: record boxes in both states and compare
const boxes = async () => page.$$eval("[data-testid]", els =>
  Object.fromEntries(els.map(e => [e.dataset.testid, e.getBoundingClientRect().toJSON()])));
const loaded = await boxes();            // after data arrives
// ...reload with the API delayed, then:
const loading = await boxes();           // while skeleton shows
// Compare top/height of the container and of each item; differences over about 4px are visible jumps.
```

To see the loading state on demand: `page.route("**/api/**", r => setTimeout(() => r.continue(), 3000))` or Chrome DevTools, Network, throttling.
