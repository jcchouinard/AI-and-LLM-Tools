#!/usr/bin/env python3
"""Render a design.json into a visual HTML page + Confluence-friendly Markdown.

Usage: render.py design.json --mode public|internal [--out DIR]

Public mode swaps every sensitive field for its `public_*` twin, hides code
paths, then scans the output for any internal term and fails if one leaks.
"""
import argparse, html, json, re, sys
from pathlib import Path

WARNINGS = []


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def sid(s):
    """Mermaid-safe identifier."""
    return re.sub(r"[^A-Za-z0-9_]", "_", s) or "x"


def mq(s):
    """Mermaid-safe label text."""
    return re.sub(r"[\"#;`]", "'", str(s))


class Ctx:
    def __init__(self, data, public):
        self.d, self.public = data, public

    def name(self, item, key="name", prefix="Item", idx=0):
        if not self.public:
            return item.get(key, f"{prefix} {idx}")
        v = item.get("public_" + key)
        if v:
            return v
        WARNINGS.append(f"missing public_{key} on {item.get(key)!r}; used placeholder")
        return f"{prefix} {chr(65 + idx % 26)}"

    def title(self):
        d = self.d
        return d.get("public_title") or d["title"] if self.public else d["title"]

    def text(self, item, key="desc"):
        if self.public:
            if "public_" + key in item:
                return item["public_" + key]
            return item.get(key, "")
        return item.get(key, "")


def items(c, lst):
    out = []
    for x in lst or []:
        if isinstance(x, str):
            out.append(x)
        else:
            t = c.text(x, "text")
            if t:
                out.append(t)
    return out


def build_blocks(c):
    d, B = c.d, []
    comps = d.get("components", [])
    cname = {x["id"]: c.name(x, prefix="Component", idx=i) for i, x in enumerate(comps)}
    # anonymous node ids so internal ids never reach diagram source
    nid = {x["id"]: f"n{i}" for i, x in enumerate(comps)}
    nid = type("N", (dict,), {"__missing__": lambda self, k: self.setdefault(k, f"n{len(self)}")})(nid)

    B.append(("hero", {
        "title": c.title(),
        "tagline": c.text(d, "tagline"),
        "stats": d.get("stats", []),
        "mode": "Public overview" if c.public else "Internal technical design",
    }))

    if d.get("summary") or d.get("goals"):
        B.append(("section", "overview", "What it is and why it exists"))
        if d.get("summary"):
            B.append(("p", c.text(d, "summary")))
        if d.get("goals"):
            B.append(("cards", [(g.get("title", ""), c.text(g, "desc"), "Goal") for g in d["goals"]]))

    models = [m for m in d.get("models", []) if not (c.public and "public_name" in m and not m["public_name"])]
    if models:
        B.append(("section", "models", "AI models used"))
        B.append(("table", ["Model", "Provider", "Used for", "Notes"],
                  [[m.get("public_name") or m["name"] if c.public else m["name"], m.get("provider", ""), c.text(m, "role"), c.text(m, "note")] for m in models]))

    if d.get("stack"):
        B.append(("section", "stack", "Tech stack"))
        B.append(("cards", [(s["layer"], ", ".join((s.get("public_items") if c.public and s.get("public_items") else s["items"])), "Layer") for s in d["stack"]]))

    if comps:
        B.append(("section", "architecture", "Architecture"))
        lines = ["flowchart LR"]
        for x in comps:
            lines.append(f'  {nid[x["id"]]}["{mq(cname[x["id"]])}"]')
        for e in d.get("edges", []):
            lab = f'|{mq(e["label"])}|' if e.get("label") else ""
            lines.append(f'  {nid[e["from"]]} -->{lab} {nid[e["to"]]}')
        B.append(("mermaid", "\n".join(lines), "System architecture"))
        hdr = ["Component", "Kind", "Tech", "Responsibility"] + ([] if c.public else ["Path"])
        rows = []
        for x in comps:
            r = [cname[x["id"]], x.get("kind", ""), c.text(x, "tech"), c.text(x)]
            if not c.public:
                r.append(x.get("path", ""))
            rows.append(r)
        B.append(("table", hdr, rows))
        if d.get("edges"):
            B.append(("table", ["From", "To", "Interaction"],
                      [[cname.get(e["from"], e["from"]), cname.get(e["to"], e["to"]), e.get("label", "")] for e in d["edges"]]))

    flows = d.get("flows", [])
    if flows:
        B.append(("section", "flows", "Key flows"))
        for i, f in enumerate(flows):
            lines = ["sequenceDiagram", "  autonumber"]
            seen = []
            for s in f["steps"]:
                for k in ("from", "to"):
                    if s[k] not in seen:
                        seen.append(s[k])
            for p in seen:
                lines.append(f'  participant {nid[p]} as {mq(cname.get(p, p))}')
            for s in f["steps"]:
                arrow = "-->>" if s.get("reply") else "->>"
                lines.append(f'  {nid[s["from"]]}{arrow}{nid[s["to"]]}: {mq(c.text(s, "msg"))}')
            title = c.text(f, "name")
            B.append(("h3", title))
            if c.text(f):
                B.append(("p", c.text(f)))
            B.append(("table", ["#", "From", "To", "Message"],
                      [[n + 1, cname.get(st["from"], st["from"]), cname.get(st["to"], st["to"]), c.text(st, "msg")] for n, st in enumerate(f["steps"])]))
            B.append(("mermaid", "\n".join(lines), title))

    dm = d.get("data_model", [])
    if dm:
        B.append(("section", "data", "Data model"))
        ename = {x["name"]: sid(c.name(x, prefix="Entity", idx=i)) for i, x in enumerate(dm)}
        lines = ["erDiagram"]
        for i, x in enumerate(dm):
            lines.append(f"  {ename[x['name']]} {{")
            for j, fl in enumerate(x.get("fields", [])):
                fname = sid(c.name(fl, prefix="field", idx=j))
                ftype = sid(fl.get("type", "string")) or "string"
                lines.append(f"    {ftype} {fname}")
            lines.append("  }")
        for r in d.get("relations", []):
            if r["from"] in ename and r["to"] in ename:
                lines.append(f'  {ename[r["from"]]} {r.get("card", "||--o{")} {ename[r["to"]]} : "{mq(r.get("label", "has"))}"')
        B.append(("mermaid", "\n".join(lines), "Data model"))
        rows = []
        for i, x in enumerate(dm):
            fields = ", ".join(c.name(fl, prefix="field", idx=j) for j, fl in enumerate(x.get("fields", [])))
            rows.append([c.name(x, prefix="Entity", idx=i), c.text(x, "purpose"), fields])
        B.append(("table", ["Entity", "Purpose", "Fields"], rows))

    api = d.get("api", [])
    if api:
        B.append(("section", "api", "API surface"))
        rows = []
        for i, a in enumerate(api):
            path = a.get("path", "") if not c.public else (a.get("public_path") or f"/resource-{chr(65 + i % 26)}")
            if c.public and not a.get("public_path"):
                WARNINGS.append(f"missing public_path on {a.get('path')!r}")
            rows.append([a.get("method", ""), path, c.text(a, "purpose")])
        B.append(("table", ["Method", "Endpoint", "Purpose"], rows))

    if d.get("deploy"):
        B.append(("section", "deploy", "Deployment and infrastructure"))
        B.append(("bullets", items(c, d["deploy"])))

    if d.get("decisions"):
        B.append(("section", "decisions", "Key decisions and trade-offs"))
        B.append(("table", ["Decision", "Chosen", "Why", "Trade-off"],
                  [[x["title"], x.get("choice", ""), x.get("why", ""), x.get("tradeoff", "")] for x in d["decisions"]]))

    risk = items(c, d.get("risks")) if c.public else items(c, d.get("security")) + items(c, d.get("risks"))
    if risk:
        B.append(("section", "risks", "Limitations" if c.public else "Security, scale and risks"))
        B.append(("bullets", risk))

    if d.get("video_script"):
        B.append(("section", "script", "Video walkthrough script"))
        B.append(("table", ["Scene", "Show on screen", "Say"],
                  [[x["scene"], x.get("show", ""), x.get("say", "")] for x in d["video_script"]]))
    return B


# ---------- Markdown ----------
def to_md(B):
    out = []
    for b in B:
        k = b[0]
        if k == "hero":
            h = b[1]
            out.append(f"# {h['title']}\n\n_{h['tagline']}_\n")
            if h["stats"]:
                out.append(" | ".join(f"**{s['value']}** {s['label']}" for s in h["stats"]) + "\n")
        elif k == "section":
            out.append(f"\n## {b[2]}\n")
        elif k == "h3":
            out.append(f"\n### {b[1]}\n")
        elif k == "p":
            out.append(b[1] + "\n")
        elif k == "cards":
            out.append("\n".join(f"- **{t}**: {body}" for t, body, _ in b[1]) + "\n")
        elif k == "bullets":
            out.append("\n".join(f"- {x}" for x in b[1]) + "\n")
        elif k == "table":
            esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
            out.append("| " + " | ".join(b[1]) + " |")
            out.append("|" + "---|" * len(b[1]))
            out.extend("| " + " | ".join(esc(x) for x in r) + " |" for r in b[2])
            out.append("")
        elif k == "mermaid":
            out.append(f"**Diagram: {b[2]}** (paste into a Confluence Mermaid macro, or render at mermaid.live)\n\n```mermaid\n{b[1]}\n```\n")
    return "\n".join(out)


# ---------- HTML ----------
E = html.escape


def explorer_model(c):
    d = c.d
    comps = d.get("components", [])
    key = {x["id"]: f"n{i}" for i, x in enumerate(comps)}
    cn = {x["id"]: c.name(x, prefix="Component", idx=i) for i, x in enumerate(comps)}
    return {
        "components": [{"id": key[x["id"]], "name": cn[x["id"]], "kind": x.get("kind", "service"), "tech": c.text(x, "tech"), "desc": c.text(x)} for x in comps],
        "edges": [{"from": key.get(e["from"], ""), "to": key.get(e["to"], ""), "label": e.get("label", "")} for e in d.get("edges", [])],
        "flows": [{"name": c.text(f, "name"), "desc": c.text(f),
                   "steps": [{"from": key.get(st["from"], ""), "to": key.get(st["to"], ""), "msg": c.text(st, "msg"), "reply": bool(st.get("reply"))} for st in f["steps"]]}
                  for f in d.get("flows", [])],
    }


DOC_CSS = """
:root{--ink:#172b4d;--mute:#5e6c84;--line:#dfe1e6;--bg:#fff;--soft:#f4f5f7;--acc:#4f46e5;
--frontend:#0891b2;--service:#7c3aed;--database:#059669;--external:#d97706;--queue:#db2777;--job:#2563eb}
*{box-sizing:border-box}
body{font:16px/1.55 -apple-system,Segoe UI,Arial,sans-serif;max-width:1040px;margin:0 auto;padding:0 24px 80px;color:var(--ink);background:var(--bg)}
#bar{position:sticky;top:0;z-index:5;background:#fffffff2;backdrop-filter:blur(6px);padding:10px 0;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center}
#bar .mode{color:var(--mute);font-size:13px;text-transform:uppercase;letter-spacing:.08em;flex:1}
button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:8px 16px;cursor:pointer;font-size:14px}button:hover{filter:brightness(1.1)}
h1{font-size:34px;margin:28px 0 4px}.tagline{color:var(--mute);font-size:19px;margin:0 0 14px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 8px}.stats span{background:var(--soft);border:1px solid var(--line);border-radius:99px;padding:3px 14px;font-size:14px}.stats b{color:var(--acc)}
h2{font-size:24px;margin:40px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--line)}
h3{font-size:18px;margin:22px 0 6px}h4{font-size:15px;margin:16px 0 4px;color:var(--mute)}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:15px}
th,td{border:1px solid var(--line);padding:7px 11px;text-align:left;vertical-align:top}th{background:var(--soft);font-size:13px;text-transform:uppercase;letter-spacing:.04em}
tbody tr:nth-child(even) td{background:#fafbfc}td:first-child{font-weight:600}
ul{padding-left:22px}li{margin:3px 0}
pre{background:var(--soft);padding:10px;overflow:auto;font-size:12px;border-radius:6px}
details{margin:10px 0}summary{cursor:pointer;color:var(--acc);font-size:14px}
p.note{color:var(--mute);font-size:14px;margin:4px 0}
/* interactive explorer (public only) */
.xp{margin:14px 0}
.tabs{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.tab{background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:99px;padding:7px 16px;font-size:15px}
.tab.on{background:var(--acc);color:#fff;border-color:var(--acc)}.tab:hover{filter:none;border-color:var(--acc)}
.stage{background:#f8f9fc;border:1px solid var(--line);border-radius:12px;padding:8px;position:relative}
.xp svg{width:100%;height:auto;display:block}
.node{cursor:pointer;transition:opacity .25s}.node rect{fill:#fff;stroke-width:2.5;transition:.2s}
.node text{fill:#172b4d;font-size:24px;font-weight:600;text-anchor:middle;pointer-events:none}
.node .k{font-size:17px;font-weight:500;fill:#5e6c84;letter-spacing:.08em;text-transform:uppercase}
.node:hover rect{filter:brightness(.96)}.node.sel rect{stroke-width:5}
.dim{opacity:.2}.edge{fill:none;stroke:#97a0af;stroke-width:2;transition:.25s}.edge.hot{stroke:var(--acc);stroke-width:3.5}
.elab{opacity:0;transition:.2s;pointer-events:none;fill:#172b4d;font-size:22px;text-anchor:middle;paint-order:stroke;stroke:#f8f9fc;stroke-width:6px}.elab.show{opacity:1}
.pulse{fill:var(--acc)}
.legend{display:flex;gap:16px;flex-wrap:wrap;padding:6px 12px;font-size:14px;color:var(--mute)}.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px}
.cap{position:absolute;left:50%;bottom:12px;transform:translateX(-50%);background:#fff;border:1px solid var(--acc);border-radius:8px;padding:8px 16px;font-size:17px;max-width:92%;text-align:center}
.side{border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-top:10px;min-height:90px}
.side h3{margin:0 0 4px;font-size:20px}.side p{margin:6px 0;color:var(--mute)}
.badge{display:inline-block;font-size:12px;text-transform:uppercase;letter-spacing:.08em;border-radius:99px;padding:1px 10px;border:1px solid;margin-bottom:6px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.chip{font-size:14px;background:var(--soft);border:1px solid var(--line);border-radius:99px;padding:2px 12px;color:var(--ink)}
.side button.chip{cursor:pointer}.side button.chip:hover{border-color:var(--acc);filter:none}
.steps{list-style:none;margin:8px 0;padding:0;columns:2;column-gap:20px}@media(max-width:760px){.steps{columns:1}}
.steps li{break-inside:avoid;margin:0;padding:7px 10px;border-radius:8px;border:1px solid transparent;cursor:pointer;color:var(--mute);display:flex;gap:10px}
.steps li b{color:var(--acc);min-width:18px}.steps li.on{background:#eef0ff;border-color:var(--acc);color:var(--ink)}
.ctl{display:flex;gap:8px;margin-top:8px}.btn{background:#fff;color:var(--ink);border:1px solid var(--line);padding:7px 16px}.btn:hover{border-color:var(--acc);filter:none}
@media print{#bar{display:none}}
"""

DOC_JS = """
function plain(){
  const c=document.getElementById('doc').cloneNode(true);
  c.querySelectorAll('.xp,button').forEach(n=>n.remove());
  c.querySelectorAll('details').forEach(d=>{d.querySelector('summary')?.remove();d.replaceWith(...d.childNodes)});
  return c;
}
document.getElementById('copy').onclick=async function(){
  const el=plain(),h=el.innerHTML,t=el.innerText;
  try{await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([h],{type:'text/html'}),'text/plain':new Blob([t],{type:'text/plain'})})])}
  catch(e){await navigator.clipboard.writeText(t)}
  this.textContent='Copied. Paste into Confluence.';setTimeout(()=>this.textContent='Copy all for Confluence',1800)};
"""


def to_html_doc(B, title, public, model=None):
    def tbl(b):
        th = "".join(f"<th>{E(x)}</th>" for x in b[1])
        tr = "".join("<tr>" + "".join(f"<td>{E(str(x))}</td>" for x in r) + "</tr>" for r in b[2])
        return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"

    def block(b):
        k = b[0]
        if k == "h3":
            return f"<h3>{E(b[1])}</h3>"
        if k == "p":
            return f"<p>{E(b[1])}</p>"
        if k == "cards":
            return "<ul>" + "".join(f"<li><strong>{E(t)}</strong>: {E(bd)}</li>" for t, bd, _ in b[1]) + "</ul>"
        if k == "bullets":
            return "<ul>" + "".join(f"<li>{E(x)}</li>" for x in b[1]) + "</ul>"
        if k == "table":
            return tbl(b)
        if k == "mermaid":
            if public:
                return ""
            return (f"<details><summary>Mermaid source: {E(b[2])}</summary>"
                    f"<p class='note'>Paste into a Confluence Mermaid macro or mermaid.live.</p><pre><code>{E(b[1])}</code></pre></details>")
        return ""

    body, tv, sec, tables_seen = [], [], None, 0
    has_xp = public and model and model["components"]

    def flush():
        nonlocal tv
        if tv:
            body.append("<details><summary>Table view: connections and flow steps</summary>" + "".join(tv) + "</details>")
            tv = []

    for b in B:
        k = b[0]
        if k == "hero":
            h = b[1]
            body.append(f"<h1>{E(h['title'])}</h1><p class='tagline'>{E(h['tagline'])}</p>")
            if h["stats"]:
                body.append("<div class='stats'>" + "".join(f"<span><b>{E(str(s['value']))}</b> {E(s['label'])}</span>" for s in h["stats"]) + "</div>")
            continue
        if k == "section":
            if sec in ("architecture", "flows") and b[1] not in ("architecture", "flows"):
                flush()
            sec = b[1]
            if has_xp and sec == "architecture":
                body.append("<h2>Architecture and flows</h2><p class='note'>Click a part to inspect it, or play a flow.</p><div class='xp' id='xp'></div>")
                tables_seen = 0
            elif has_xp and sec == "flows":
                pass
            else:
                body.append(f"<h2>{E(b[2])}</h2>")
            continue
        if has_xp and sec == "architecture":
            if k == "mermaid":
                continue
            if k == "table":
                tables_seen += 1
                (body if tables_seen == 1 else tv).append(block(b))
                continue
        if has_xp and sec == "flows":
            if k != "mermaid":
                tv.append(block(b))
            continue
        body.append(block(b))
    flush()

    mode = "Public overview" if public else "Internal technical design"
    xp = ""
    if has_xp:
        tpl = (Path(__file__).parent / "public_template.html").read_text()
        xp = "<script>" + tpl.replace("__DATA__", json.dumps(model).replace("</", "<\\/")) + "</script>"
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{E(title)}</title><style>{DOC_CSS}</style></head><body>'
            f'<div id="bar"><span class="mode">{mode}</span><button id="copy">Copy all for Confluence</button></div>'
            f'<div id="doc">{"".join(body)}</div><script>{DOC_JS}</script>{xp}</body></html>')


def sensitive_terms(d):
    terms = set(d.get("sensitive_terms", []))

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if ("public_" + k) in o and isinstance(v, str):
                    terms.add(v)
                if k == "path" and isinstance(v, str):
                    terms.add(v)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(d)
    # the original title is sensitive if a public title exists
    return sorted({t for t in terms if len(t) >= 3}, key=len, reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--mode", choices=["public", "internal"], required=True)
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    d = json.loads(Path(a.design).read_text())
    public = a.mode == "public"
    c = Ctx(d, public)
    B = build_blocks(c)
    title = c.title()
    md = to_md(B)
    page = to_html_doc(B, title, public, explorer_model(c) if public else None)

    if public:
        # scan visible text only (diagram source is included in md and html)
        hay = (md + "\n" + page).lower()
        ignore = {t.lower() for t in d.get("scan_ignore", [])}
        hits = [t for t in sensitive_terms(d) if t.lower() not in ignore

                if re.search(r"(?<![A-Za-z0-9])" + re.escape(t.lower()) + r"(?![A-Za-z0-9])", hay)]
        # terms that are also public names are fine (author chose to expose them)
        pub_vals = {v.lower() for v in re.findall(r'"public_\w+":\s*"([^"]+)"', json.dumps(d))}
        hits = [t for t in hits if t.lower() not in pub_vals]
        if hits:
            die("public output leaks internal terms: " + ", ".join(hits[:20]) + "\nFix public_* fields or desc text, then re-run.")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"design-{a.mode}.html").write_text(page)
    (out / f"design-{a.mode}.md").write_text(md)
    for w in sorted(set(WARNINGS)):
        print("WARN:", w, file=sys.stderr)
    print(f"wrote {out}/design-{a.mode}.html and .md" + (" (leak scan clean)" if public else ""))


if __name__ == "__main__":
    main()
