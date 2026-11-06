# <PROJECT_NAME>: System Design Explainer (Claude Code skill)

## Project purpose
A Claude Code skill that turns any code directory into a visual technical design for engineers and PMs. It outputs two versions from one model:
- **Internal**: real names, tables and code paths, as a clean document that pastes into Confluence.
- **Public**: anonymized, with no security content, as the same clean document plus one interactive architecture explorer. Safe to share, guarded by an automated leak scan.
Both versions list the AI models used. Markdown is produced for both.

## Tech stack
- Python 3 standard library only (renderer and leak scanner). No pip installs.
- Vanilla JS and inline SVG for the explorer. No frameworks, no CDN, no network at view time.
- Output is static HTML and Markdown.

## Directory layout
```
system-design-explainer/
  SKILL.md                  workflow and writing rules for the agent
  scripts/render.py         design.json to HTML and Markdown, plus the leak scan
  scripts/public_template.html   explorer JS (injected into a script tag by render.py)
  references/schema.md      the design.json schema
  examples/example.json     small complete example
```
Install by copying this folder to `~/.claude/skills/system-design-explainer/` (see `skeleton/`).

## Commands
```
python3 scripts/render.py design.json --mode internal --out OUT_DIR
python3 scripts/render.py design.json --mode public   --out OUT_DIR
```
Public exits non-zero and lists every leaked term if the scan fails.

## Conventions
- The agent reads the code and writes `design.json`. The script renders. Never hand-write the HTML.
- Every sensitive value has a `public_<field>` twin written at the same time as the plain value.
- The app title is the app's real name in both modes.
- Descriptions are one short phrase or sentence (6 to 12 words). Flow messages are 2 to 5 words.
- Never use em dashes in generated text.

## Architecture decisions (with why)
- **Model plus renderer, not free-form HTML.** Enforcing redaction in code is reliable. A prompt that says "remember to hide names" is not.
- **Twin fields (`public_*`) instead of regex redaction.** Generic words stay meaningful (`provider_ref`, not `field_3`).
- **Leak scan on the final output.** Whole-word, case-insensitive match of every internal name, path and extra term. It catches what the author forgot.
- **One shared document for both modes.** Users preferred the plain Confluence-style page. The public page keeps only one interactive element, the explorer.
- **Security is a hard rule, not a setting.** The renderer never emits the `security` list in public mode.
- **Anonymous diagram ids.** Internal ids never reach diagram source or page data.

## Known gotchas
- A 9-digit hex color (`#0e7490449`) is invalid CSS and silently drops the whole rule, which turned a dark page white. Validate colors.
- Scroll-reveal sections (opacity 0 until visible) make element screenshots blank. Avoid reveal animations.
- Some browser tools block `file:` URLs. Serve the output folder with `python3 -m http.server`.
- Browser tool viewports can desync from the requested size. If screenshots come back blank or cropped, close the browser and measure with DOM queries instead of retrying images.
- Diagram text shrinks with the SVG scale. Check rendered pixels (font size times scale), not source font sizes.
- Short generic words used as column names (for example `MODEL`, `TIMESTAMP`) trigger the scan on ordinary prose. Use `scan_ignore` for those, deliberately.
- Fan-out edges clump their labels. Draw labels on a top layer and show them only for the hovered or selected part.

## Do and Don't
- Do read at least two real flows end to end before writing the model.
- Do list every AI model, including ones only selectable in the UI. Mark configured-but-unused ones internal-only.
- Do tell the user about real security problems found in the code (committed secrets, keys printed to a UI). Put them under `security`, internal only, and never copy secret values anywhere.
- Don't add reassuring public claims you have not verified (for example "credentials are injected at runtime").
- Don't put secrets, internal URLs or account ids in any file you share.
- Don't weaken the leak scan to get a render through. Fix the data.

## How to start (new agent)
1. Read `docs/BUILD_PLAN.md` and follow it in order.
2. Read `docs/LEARNINGS.md` before changing layout or styles.
3. Copy `skeleton/` into the skills folder and render `examples/example.json` in both modes to confirm the baseline.
