# LinkedIn carousel builder template

A recipe for an agent to recreate a screenshot-to-carousel pipeline: LinkedIn PDF and slide PNGs, a newsletter thumbnail, and an X/Twitter post.

## How to use
1. Copy this folder into a new project directory.
2. Tell Claude: "Read CLAUDE.md, then follow docs/BUILD_PLAN.md to set this up."
3. Provide your screenshots, post text, handle, and avatar.

## Files
- `CLAUDE.md`: purpose, stack, conventions, decisions, gotchas
- `docs/ARCHITECTURE.md`: components and data flow
- `docs/LEARNINGS.md`: lessons learned
- `docs/BUILD_PLAN.md`: ordered steps with done-checks
- `skeleton/build.py`: the builder (stdlib Python)
- `skeleton/spec.example.json`: example spec with placeholders

## Requirements
macOS (`sips`) and Google Chrome. Set `CHROME=/path` if Chrome is not at the default path.
The default avatar file is not included. Supply your own image and set `brand.avatar` in the spec (the builder falls back to an `assets/avatar.png` next to `build.py`, so create it or always set the field).
