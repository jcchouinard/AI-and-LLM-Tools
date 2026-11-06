# Architecture

## Components
| Part | Role |
|---|---|
| SKILL.md | Tells the agent the workflow: scope, explore code, write `design.json`, render, fix leaks, hand over |
| `design.json` | The single source of truth. Plain fields hold real values, `public_*` twins hold safe ones |
| `render.py` | Builds blocks from the model, renders HTML and Markdown, runs the leak scan |
| `public_template.html` | Explorer JavaScript injected into the public page only |
| `schema.md` | Reference for every field |

## Data flow
```
code  -->  agent reads and distills  -->  design.json
                                              |
                          +-------------------+-------------------+
                          v                                       v
                   mode = internal                          mode = public
                   plain names, paths                       twin fields, no paths,
                   security section                         no security, anon ids
                          |                                       |
                          v                                       v
                  design-internal.html/.md              leak scan (whole words)
                                                                  |
                                                    pass --> design-public.html/.md
                                                    fail --> exit 1 with list of terms
```

## Render pipeline inside render.py
1. `Ctx` resolves each field for the chosen mode (`name`, `text`, `title`).
2. `build_blocks` produces an ordered list: hero, sections, tables, text, Mermaid source.
3. `to_md` and `to_html_doc` turn blocks into outputs. The public HTML replaces the architecture section with the explorer and moves connection and flow tables under a "Table view" toggle.
4. `explorer_model` builds the explorer data with anonymous node ids (`n0`, `n1`, ...).
5. `sensitive_terms` collects every internal value that has a twin, every `path`, and `sensitive_terms` from the model, minus `scan_ignore`. The scan runs over the Markdown and HTML.

## Explorer (public only)
- Layers components into columns by following edges (longest path from sources, cycle safe).
- Edges that skip a column arc over the intermediate nodes.
- Explore mode: hover dims unrelated parts, click opens a detail panel with connected parts.
- Flow mode: one tab per flow, step list, prev, play, next, and a moving pulse along each step. Arrow keys work.
- Edge labels sit on a top layer and show only for the focused part.
