# CLAUDE.md: LinkedIn carousel builder

## Project purpose
Turn screenshots and short copy into social assets from one command:
- LinkedIn carousel PDF (1080x1350, 4:5) plus one PNG per slide
- Newsletter thumbnail (1200x630, plus @2x)
- X/Twitter post: up to 4 images (1600x900) plus tweet text

## Tech stack
- Python 3 standard library only (no pip packages)
- Headless Google Chrome renders HTML to PNG
- macOS `sips` converts PNG to JPEG and reads image sizes
- PDF is written by hand (raw PDF objects) from JPEGs

## Directory layout
```
<PROJECT_NAME>/
  build.py            # the builder (see skeleton/)
  spec.json           # slides, brand, thumbnail, twitter config
  img/                # input screenshots + avatar
  build/              # output: carousel.pdf, slides/, thumbnail*.png, twitter/
```

## Commands
- Build: `python3 build.py spec.json --out build`
- Override Chrome: `CHROME=/path/to/chrome python3 build.py spec.json`
- Preview one slide: open `build/carousel.html?p=<zero-based-index>` in Chrome

## Conventions
- Image paths in the spec are relative to the spec file.
- Headline: 2-5 words, one phrase wrapped in `<em>` (rendered in the accent color). Max about 28 chars so it stays on one line at 66px.
- Subtitle: one line, under about 45 chars, or omit.
- Flow: cover (value + "Swipe"), one idea per slide, optional "what you get" slide with `chips` and `band: 600`, final CTA slide with `cta`. Keep 5-12 slides, ideally 10 or fewer.
- Name new builds by version (`carousel-v2`, `-v3`). Do not overwrite older ones.

## Architecture decisions (with why)
- Whole carousel is one wide HTML strip (N x 1080 px). Each page is the same strip shifted with `translateX`. Why: lets elements cross slide seams (arrow, line, card peek) for a swipe effect.
- Each card starts 120 px inside the previous slide on an empty padded edge. Why: invites the swipe and never clips annotations on the screenshot.
- PDF is built from per-slide JPEGs at exactly 1080x1350 pt. Why: Chrome `--print-to-pdf` produced 810x1012.5 pt pages with black offset space and a hidden strip in LinkedIn's preview. Do not regress this.
- Thumbnail keeps content within x 150-1050. Why: the newsletter platform crops the feed card to about 3:2 (about 125 px off each side).
- Twitter images are 16:9 with content inside x 160-1440 and y 90-810. Why: X center-crops 4-image grid tiles.
- Max 4 Twitter images. Tweet text under 280 chars (a URL counts as 23).

## Known gotchas
- macOS screenshot filenames contain a narrow no-break space before AM/PM. Copy with a glob, for example `cp Screenshot\ 2026-01-01\ at\ 9.14.17*.png img/`.
- Screenshots with the author's own red annotations are content. Never crop them.
- Text baked into screenshots cannot be changed by the spec. If a product name must be hidden, drop it from all copy, warn about the screenshots, and offer to blur or crop.
- All pages must have identical dimensions (LinkedIn requirement). PDF should be under about 10 MB (about 0.5 MB per slide).
- A low-resolution avatar looks soft at 76 px. Ask for a higher-res photo if available.
- Only claim what is visible in the screenshots or in the user's text. Verify numbers against the image. Never invent "free", stats, links or CTAs.

## Do and Don't
Do: read every screenshot before writing copy; build, then view cover, one middle slide, CTA, thumbnail, and two Twitter images; report paths, page count, and what cannot be changed.
Don't: use Chrome print-to-pdf for the deliverable; exceed 4 Twitter images; put important content outside the safe zones; overwrite previous versions.

## How to start
1. Read README.md, docs/BUILD_PLAN.md, and docs/LEARNINGS.md.
2. Ask the user (one short message) for: screenshots, post text or steps, brand handle, avatar, and whether any product name must be hidden. Skip what you can infer.
3. Copy `skeleton/build.py` and `skeleton/spec.example.json` into the new project, then follow the build plan.
