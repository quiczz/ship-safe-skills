# Assets

## Where the video comes from (best first)

1. **The user's own footage**: product screen recording, brand film, drone shots.
2. **A generated clip** from an AI video tool the user has an account with, using a prompt like: "slow cinematic dolly through [scene], soft volumetric light, shallow depth of field, no text, no people's faces, seamless loop". Ask for 6 to 10 s, 16:9, 1080p. Check the tool's terms for commercial use.
3. **Stock footage** with a licence that allows web and commercial use (check the licence page of Pexels, Pixabay, Mixkit and similar; terms change). Save the licence link in `assets/README.md`.
4. **Placeholder**: the CSS gradient background in `templates/site.html`. It is a finished look, not a stub.

Never hotlink a third-party video URL or reuse another site's hero footage. Do not scrape.

## Making a loop that loops

- Cut a segment where the first and last frames are similar, or cross-fade the last second over the first (`make_video_assets.sh --loop-fade`).
- Avoid fast camera moves and anything with text.
- Keep the subject away from where the headline sits (usually left or centre).

## Encoding

`scripts/make_video_assets.sh input.mov assets/` produces:

- `hero.mp4`: H.264, High profile, CRF 26, max 1080p, 24 fps, no audio, `+faststart` so playback starts before the download ends
- `hero.webm`: VP9, CRF 34, smaller on Chrome and Firefox
- `hero-poster.jpg`: a frame from 1 second in (convert to WebP or AVIF for production)

If the file is over 4 MB: lower the resolution to 720p, cut to 8 s, raise CRF by 2.

## Images

- AVIF or WebP with a JPEG fallback via `<picture>`.
- `width` and `height` always set; `loading="lazy"` except for the hero poster, which gets `fetchpriority="high"`.

## Record what you used

`assets/README.md` with: file, source, licence and link, date, who made it.
