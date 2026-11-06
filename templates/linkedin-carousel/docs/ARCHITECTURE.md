# Architecture

## Components
- **spec.json**: input. Brand handle, slide list, thumbnail config, optional twitter config.
- **build.py**: orchestrator. Stages images into `build/img` (spaces replaced by underscores), measures aspect ratios with `sips`, fills HTML templates, drives headless Chrome, assembles the PDF.
- **HTML templates (strings in build.py)**: CAROUSEL (JS renders all slides into one strip), THUMB, TWITTER.
- **PDF writer**: `build_pdf` writes raw PDF objects, one JPEG per page, MediaBox 1080x1350.

## Data flow
spec.json -> stage images + aspect ratios -> carousel.html (per slide: open with `?p=<i>`, screenshot at 1x for PNG and 2x for JPEG) -> JPEGs -> carousel.pdf.
Thumbnail: spec.thumbnail -> thumbnail.html -> screenshots at 1x and 2x.
Twitter: pick up to 4 slides (explicit list or auto: first, two evenly spaced, last) -> one HTML per image -> 1600x900 PNG, plus tweet.txt.

## Layout constants
Slide 1080x1350. Card band top 280, band height 820 (600 for chips slides), card max height 900/aspect. Chips: 2 columns, max 6. Footer avatar at y 1258.
