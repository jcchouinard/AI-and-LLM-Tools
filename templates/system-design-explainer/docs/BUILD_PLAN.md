# Build plan

Follow in order. Each step has a done-check. The files in `skeleton/` are a working reference for every step.

## 1. Create the skill folder
Create `~/.claude/skills/system-design-explainer/` with `scripts/`, `references/`, `examples/`.
Done when: the folder exists and contains an empty `SKILL.md`.

## 2. Define the design.json schema
Write `references/schema.md`. Include: title, tagline, stats, summary, goals, models, stack, components (id, name, kind, tech, path, desc), edges, flows with steps, data_model with fields, relations, api, deploy, decisions, security, risks, video_script, plus `sensitive_terms` and `scan_ignore`. Every sensitive field gets a `public_<field>` twin.
Done when: a small example `examples/example.json` follows the schema.

## 3. Build the block model and Markdown output
In `scripts/render.py` add a context class that resolves fields per mode, then `build_blocks` producing hero, sections and tables, then `to_md`.
Rules: public hides paths, drops `security`, titles risks "Limitations". Items in lists may be strings or objects with `text` and `public_text`. An empty `public_text` drops the item.
Done when: both modes write Markdown and the public Markdown shows no path and no security text.

## 4. Build the shared HTML document
Add `to_html_doc`: a light, plain document with a sticky bar, a "Copy all for Confluence" button (rich text, excludes explorer and buttons), tables, lists, and collapsible Mermaid source (internal only).
Done when: opening the internal HTML shows clean tables and the copy button puts headings and tables on the clipboard.

## 5. Add the leak scan
Collect every internal value that has a twin, every `path`, and `sensitive_terms`, minus `scan_ignore`. Match whole words, case-insensitive, over the Markdown and HTML. Exit non-zero with the list.
Done when: a deliberately leaked term makes the public render fail, and the example passes.

## 6. Build the explorer (public only)
Write `scripts/public_template.html` as JavaScript that reads injected data and builds into `#xp`: column layout from edges, arcs for long edges, hover and click detail, flow tabs with step list and animated pulse, labels on a top layer. Inject it from `render.py` with anonymous node ids.
Done when: in a browser you can click a part, play a flow, step with the next button, and the console has no errors.

## 7. Write SKILL.md
Include: a pushy description (when to trigger), the workflow (scope, explore, write model, render both modes, fix leaks, view, hand over), writing rules (short text, title is the app name, security never public, always list AI models), and how to use each output.
Done when: a fresh Claude session triggers the skill from "document how this app is built".

## 8. Test on a real repository
Run the skill on a small real project. Check: models table present, public output has no names, tables, paths or security text, internal output has them, layout holds with 8 to 10 components.
Done when: the public leak scan is clean and a human skim finds nothing sensitive.

## 9. Browser verification
Serve the output over HTTP. Measure rendered font size, overflow and overlaps by DOM query. Do not rely on screenshots alone.
Done when: node text renders at 14px or larger in a 1000px wide window and no text overflows its node.
