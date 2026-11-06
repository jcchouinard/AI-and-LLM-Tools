# Build plan

1. **Create the project folder** with `img/` and copy `skeleton/build.py` and `skeleton/spec.example.json` (rename to `spec.json`). Done when: both files exist.
2. **Check requirements**: `ls "/Applications/Google Chrome.app"` and `which sips`. Done when: both found (else set `CHROME`).
3. **Collect inputs**: screenshots into `img/`, avatar image, handle, post text. Read every screenshot. Done when: every spec image path exists.
4. **Write spec.json**: cover, one slide per step, optional chips slide, CTA slide, thumbnail, twitter. Done when: valid JSON (`python3 -m json.tool spec.json`) and headlines are under about 28 chars.
5. **Build**: `python3 build.py spec.json --out build`. Done when: it prints OK and `build/carousel.pdf`, `build/slides/`, `build/thumbnail.png`, `build/twitter/` exist.
6. **Verify visually**: view cover, a middle slide, the CTA, thumbnail, two Twitter images. Done when: no headline/subtitle overlap, no overlap with arrow or footer, CTA button clear of arrow.
7. **Check PDF**: page size 1080x1350 pt, under about 10 MB. Done when: confirmed.
8. **Report** paths, page count, and text baked into screenshots that cannot change. Save new builds under a new version name.
