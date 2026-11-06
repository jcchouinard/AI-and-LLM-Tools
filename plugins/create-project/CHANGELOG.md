# Changelog

## 1.0.0 naming
- Plugin renamed from lean-start to create-project: `/create-project:new` (plugin) or `/create-project` (install.sh).

## 1.0.0 (2026-11-06)
- Four modes: low token, low token with git and pr-gate, balanced with picks, locked down.
- First-run identity detection (git and gh accounts, noreply addresses), configurable projects root.
- token-gate ported to Python (no jq). pr-gate bundled as a project skill and hook.
- Mode 4: path guard, command allowlist, OS sandbox without network, audit log of calls and blocks.
- Merge-only writes with .bak backups, manifest, doctor, uninstall, dry run.
