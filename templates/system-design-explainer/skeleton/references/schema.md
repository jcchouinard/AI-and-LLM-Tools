# design.json schema

Every field is optional except where noted; empty sections are skipped. The
rule for anything sensitive: write the real value in the plain field and a safe
twin in `public_<field>`. Internal mode uses the plain field, public mode uses
the twin. Anything with no twin is shown as-is in public mode, so only leave
the twin off when the plain value is already safe to publish.

```jsonc
{
  "title": "acme-course-hub",                       // the app's name; used in both modes unless public_title is set explicitly
  "tagline": "...", "public_tagline": "...",
  "sensitive_terms": ["Acme", "acme.com", "/me/access"],   // extra strings the public scan must never find (whole-word, case-insensitive)
  "scan_ignore": ["TIMESTAMP", "MODEL"],                   // generic words that are also real column names; you vouch they are safe
  "stats": [{"label": "services", "value": 3}],            // hero tiles, 3-5 of them
  "summary": "...", "public_summary": "...",
  "goals": [{"title": "...", "desc": "...", "public_desc": "..."}],
  "models": [{"name": "gemini-2.5-flash", "provider": "Google", "role": "Grounded answers", "note": "Selectable, default"},
             {"name": "gpt-4o-mini", "public_name": "", "provider": "OpenAI", "role": "Not used", "note": "internal only: empty public_name hides the row in public"}],
  "stack": [{"layer": "Payments", "items": ["Stripe"], "public_items": ["Hosted payments"]}],

  "components": [{                       // REQUIRED for the architecture diagram
    "id": "api",                         // internal key, never printed (diagram ids are anonymized)
    "name": "access-api", "public_name": "Access API",
    "kind": "frontend|service|database|queue|external|job",
    "tech": "FastAPI", "public_tech": "...",
    "path": "repo/api/main.py",          // internal mode only; never rendered in public mode
    "desc": "...", "public_desc": "..."
  }],
  "edges": [{"from": "hub", "to": "api", "label": "check access"}],

  "flows": [{                            // each becomes a sequence diagram
    "name": "...", "public_name": "...", "desc": "...", "public_desc": "...",
    "steps": [{"from": "hub", "to": "api", "msg": "GET /me/access",
               "public_msg": "Request entitlements", "reply": false}]
  }],

  "data_model": [{
    "name": "users", "public_name": "Account", "purpose": "...", "public_purpose": "...",
    "fields": [{"name": "stripe_customer_id", "public_name": "provider_ref", "type": "string"}]
  }],
  "relations": [{"from": "users", "to": "subscriptions", "card": "||--o{", "label": "has"}],

  "api": [{"method": "GET", "path": "/api/me/access", "public_path": "/access",
           "purpose": "...", "public_purpose": "..."}],
  "deploy": ["plain string", {"text": "internal detail", "public_text": "safe version"}],
  "decisions": [{"title": "...", "choice": "...", "why": "...", "tradeoff": "..."}],
  "security": ["..."], "risks": ["..."],
  "video_script": [{"scene": "1. Big picture", "show": "Architecture diagram", "say": "..."}]
}
```

Notes
- `security` is never rendered in public mode (hard rule). Public mode shows only `risks`, titled "Limitations". `security` and `risks` items, like `deploy`, may be `{"text": "...", "public_text": "..."}`. An empty `public_text` drops the item from the public output (use this for vulnerabilities that belong only in the internal doc); an empty `text` with a `public_text` adds an item to public mode only.
- `from`/`to` in edges, flow steps and relations reference component `id`s (edges, flows) or data_model `name`s (relations).
- Entity and field `type` values must be a single word (`string`, `int`, `date`): they go into a Mermaid ER diagram.
- Free text (`desc`, `why`, `tradeoff`, `risks`, `video_script`) has no automatic twin, so write it generically in the first place or the leak scan will stop the render.
- Relation cardinality: `||--o{` one-to-many, `||--||` one-to-one, `}o--o{` many-to-many.
