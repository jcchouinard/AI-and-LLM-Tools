---
name: system-design-explainer
description: Turn a project directory or code into a visual, detailed technical design (architecture diagram, key flows, data model, API surface, decisions and trade-offs, plus a video walkthrough script) that engineers and PMs can understand quickly. Two modes: "public" (names, tables, paths, endpoints anonymized, with an automated leak scan, safe to publish) and "internal" (real table names and code paths kept, for Confluence). Both modes output a clean, copy-to-Confluence document with an AI models table; public mode adds an interactive architecture explorer with a step-through flow player. Markdown for both. Use whenever the user wants to explain, document, diagram or present how an app or system is built, asks for a technical design doc, architecture overview, system design write-up, Confluence page about a codebase, or a public/shareable version of how something was built, even if they never say "design doc".
---

# System Design Explainer

Read a codebase, distill it into a structured model (`design.json`), and render it two ways from the same model. The split matters: Claude does the understanding, and a script does the rendering and the public-safety check. A script can enforce redaction reliably, while "please remember to hide table names" in prose is easy to miss.

## Workflow

1. **Pin down the inputs.** Get the target directory (default: cwd) and the mode: `public`, `internal`, or `both` (default `both`, since the model is the same). Ask only if the target is ambiguous. Also ask who the audience is if it is not obvious (engineers vs PMs changes depth, not structure).
2. **Explore the code.** Read the README, manifests (package.json, pyproject, requirements, Dockerfile, compose, terraform), entrypoints, route definitions, schema/migration/model files, config, and CI. For large repos, delegate breadth to an Explore agent and keep the conclusions. Trace two or three real flows end to end (for example a user signup, a payment, a scheduled job) rather than describing files one by one: flows are what make the design click.
3. **Write `design.json`** following `references/schema.md`. Save it next to the outputs (default output dir: `./system-design/`). Fill in the `public_*` twin for every name, table, field, path, route, vendor-revealing tech, and message while you are writing the entry, not afterwards. That is when you know what each thing is.
4. **Render.**
   ```bash
   python3 ~/.claude/skills/system-design-explainer/scripts/render.py system-design/design.json --mode internal --out system-design
   python3 ~/.claude/skills/system-design-explainer/scripts/render.py system-design/design.json --mode public   --out system-design
   ```
   Produces `design-<mode>.html` and `design-<mode>.md`.
5. **Fix leak-scan failures.** The public render exits non-zero and lists every internal term found (project names, table names, paths, anything in `sensitive_terms`). Fix the `public_*` fields or generalize the free text, then re-run. Do not weaken the scan to get it through. Also read the public Markdown once yourself for things a string match cannot catch: unique business logic, customer names, internal metrics, infrastructure that fingerprints the company.
6. **Look at it.** Serve the output folder (`python3 -m http.server`) and open the public HTML. Click a node, play a flow, and check the browser console for errors. File URLs may be blocked in some browser tools, hence the local server. If screenshots come back blank, the sections are probably still fading in or the browser viewport is out of sync: close the browser and measure with DOM queries (font sizes, overlaps) instead of retrying images.
7. **Hand over.** Tell the user the file paths and how to use each (below). Offer a short recording order based on `video_script`.

## What good looks like

- **Always list the AI models** (`models`): exact model ids, provider and what each is used for, in both modes. Model names are not sensitive. Include models that are selectable in the UI as well as the ones hard-coded, and mark configured-but-unused models as internal-only with `"public_name": ""`.
- **Title is the app's name**, in both modes (the repo or product name, not a descriptive rename). Only set `public_title` if the user explicitly wants the name hidden.
- **Write short.** Readers skim, and a video script needs room to talk. Every `desc`, `purpose`, `why` and `tradeoff` is one short phrase or sentence (about 6 to 12 words). Flow messages are 2 to 5 words. If a field needs a second sentence, it belongs in the voice-over, not on the page.
- **Security never appears in public output.** The renderer drops the `security` list in public mode and shows only `risks` as "Limitations". Put vulnerabilities, secrets handling and hardcoded credentials in `security`, and never describe them in public-facing fields. Do not add reassuring public claims about security you have not verified.
- **Diagrams carry the explanation.** Keep the architecture to 6 to 12 components (merge minor pieces) and write 2 to 4 flows that show the interesting decisions. The public explorer lays components out in columns by following `edges`, so make sure edges reflect the real direction of calls. Too many nodes makes a poster nobody reads. Keep component names short (under about 20 characters) so they stay readable inside the nodes.
- **Decisions and trade-offs** separate a design doc from a file listing. Infer them from the code and state the cost of each choice honestly.
- **`video_script`**: 5 to 8 scenes, each tied to a section on the page. The HTML has arrow-key scene navigation so the user can record by pressing the right arrow.
- **Public mode keeps the story, drops the identifiers.** Replace `stripe_customer_id` with `provider_ref`, not with `field_3`. Vendor names in `tech` and `stack` are shown as-is unless a `public_` twin is given, so decide whether the vendor itself is sensitive. Flow names do not need twins.
- Never invent components. If something is unclear from the code, leave it out.
- If you find real security problems while reading the code (committed secrets, keys printed to a UI), tell the user in your reply as well as listing them under `security`, and never copy secret values into any file.

## Using the outputs

Both HTML files are the same clean document (headings, tables, lists), so they look alike and paste the same way. The differences are deliberate.

- **Internal (`design-internal.html`)**: real names, tables, fields and code paths, the Security section, and collapsible Mermaid source under each diagram table.
- **Public (`design-public.html`)**: anonymized names and no code paths, no security content (limitations only), plus an **interactive explorer** in the Architecture section. Click a part to see its role and connections, or play a flow step by step with a moving pulse. The connection and flow tables sit under "Table view" for anyone who prefers reading.
- **Copy button (both)**: "Copy all for Confluence" copies the document as rich text (tables stay tables). The explorer and buttons are left out of the copy.
- **Markdown (`design-<mode>.md`)**: same content as plain Markdown for wikis and repos.
- Share only `design-public.*`. `design.json` holds the real names, so keep it private.

## Files

- `scripts/render.py`: renderer and leak scanner.
- `scripts/public_template.html`: the interactive explorer script injected into the public page (vanilla JS, no dependencies).
- `references/schema.md`: full `design.json` schema with the `public_*` convention.
- `examples/example.json`: a small complete example; render it to see the output shape.
