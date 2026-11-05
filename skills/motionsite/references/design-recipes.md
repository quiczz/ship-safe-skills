# Design recipes

Starting values, not law. Change them to fit the brand, but change them on purpose.

## Direction presets

| Tone | Background | Accent | Display font | Body font | Motion |
|------|-----------|--------|--------------|-----------|--------|
| Calm tech | `#0b0d12` | `#7c9cff` | Inter Tight 600 | Inter 400 | slow fades, 700 ms |
| Bold launch | `#07070a` | `#ff4d2e` | Space Grotesk 700 | Inter 400 | quick, 450 ms, bigger stagger |
| Luxury | `#0a0908` | `#d9b779` | Fraunces 500 (serif) | Inter 400 | very slow, 900 ms, little movement |
| Playful | `#12091f` | `#ff7ad9` | Bricolage Grotesque 700 | DM Sans 400 | springy, small overshoot |

Self-host fonts or load them with `font-display: swap`. Never block the first paint on a font file.

## Type scale (desktop, then phone)

| Role | Desktop | Phone |
|------|---------|-------|
| Hero headline | `clamp(2.6rem, 6vw, 5.5rem)`, line-height 1.02, letter-spacing -0.03em | same clamp |
| Section title | `clamp(1.8rem, 3.5vw, 3rem)`, 1.1 | same clamp |
| Lead paragraph | 1.2 to 1.35rem, 1.5 | 1.1rem |
| Body | 1rem, 1.6 | 1rem |

Keep headline to 2 or 3 lines and 12 words or fewer.

## Spacing

Sections: `padding-block: clamp(4rem, 10vw, 8rem)`. Content width: `min(1120px, 100% - 2rem)`. Use an 8 px base grid.

## Hero layout

1. Video (or gradient) fills the section: `position:absolute; inset:0; object-fit:cover`.
2. Overlay: `linear-gradient(180deg, rgb(0 0 0 / .55) 0%, rgb(0 0 0 / .25) 40%, rgb(0 0 0 / .75) 100%)`, darker at the bottom so the next section blends in.
3. Content block aligned to the lower-left or centre, max 40 rem wide.
4. Optional glass card under the headline for a short proof line or email form.
5. A small "scroll" cue at the bottom that fades out after the first scroll.

## Glass card

```css
.glass {
  background: rgb(255 255 255 / .06);
  border: 1px solid rgb(255 255 255 / .14);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border-radius: 20px;
}
@supports not (backdrop-filter: blur(1px)) { .glass { background: rgb(20 22 30 / .85); } }
```

Use blur sparingly: it is expensive on phones. At most 2 or 3 glass surfaces visible at once.

## Buttons

- Primary: solid accent, dark text if the accent is light (check 4.5:1), radius 999px, padding 0.9rem 1.6rem.
- Secondary: glass or 1 px outline.
- States: hover lifts 2 px (`transform`) and brightens; `:active` presses back; `:focus-visible` shows a 2 px outline with offset. Never remove focus outlines.
- Animated CTA: a slow moving highlight inside the button using a pseudo-element and `transform`, paused under reduced motion.

## Motion timing

| Thing | Duration | Easing |
|-------|----------|--------|
| Headline words | 600 ms each, 70 ms stagger | `cubic-bezier(.2,.7,.2,1)` |
| Reveal on scroll | 700 ms, translateY 24 px | same |
| Hover | 180 ms | ease-out |
| Page-load sequence | total under 1.6 s | |

Start the headline animation without waiting for the video, so the hero never looks empty.

## Section patterns that work on top of a video hero

- **Logos strip**: 5 to 6 greyscale logos, low opacity, no animation.
- **Feature trio**: three glass cards with an icon, a 3-word title and one sentence.
- **Big number row**: three metrics, count-up only when visible, final number set in HTML for no-JS.
- **Showcase**: one large rounded image or second looping video that plays only in view.
- **Testimonial**: one quote at a time, large type. Only real quotes; do not invent customers.
- **Pricing**: 3 cards, middle highlighted.
- **Closing CTA**: repeat the hero promise with the same button.
