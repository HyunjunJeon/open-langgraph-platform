# AGENTS Hierarchy Design

This repository uses `AGENTS.md` files as scoped, hierarchical instructions for coding agents.

## Goals
- Keep always-on guidance small and stable.
- Put implementation details close to the code they describe.
- Avoid duplicated docs by routing to the correct layer/module first.

## Scope Rules
- An `AGENTS.md` applies to the entire directory tree rooted at the folder that contains it.
- A deeper (more specific) `AGENTS.md` takes precedence over a higher-level one if they conflict.
- When editing a file, you must follow every `AGENTS.md` that scopes that file (from repo root down to the nearest one).

## Resolution Algorithm (Practical)
For a target file path:
1. Start at the file’s directory and walk upward to the repo root.
2. Collect every `AGENTS.md` encountered.
3. Apply them from root → leaf; if guidance conflicts, the leaf-most instruction wins.

## Authoring Guidelines
- Prefer MUST/SHOULD language for rules that matter.
- Keep “routers” short: point to code and downstream docs instead of duplicating them.
- Treat code as the source of truth; update docs when they drift.
- Be explicit about security boundaries (multi-tenancy, auth, SSRF/XSS, secret handling).

## Example
Editing `src/agent_server/core/database.py` is governed by:
- `AGENTS.md`
- `src/agent_server/AGENTS.md`
- `src/agent_server/core/AGENTS.md`

