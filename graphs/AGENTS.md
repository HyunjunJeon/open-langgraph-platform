# AGENTS.md - `graphs/` (Graph Domain Router)

This document is upstream guidance for the entire `graphs/` tree.
Graph-specific flow/state/tools live in each graph folder’s downstream `AGENTS.md`.

## Purpose
- Fix the rules that connect `open_langgraph.json` ↔ graph code.
- Standardize common graph patterns (State/Context/Tools/interrupt).
- Make the boundary between the server layer and the graph layer explicit (dependency direction).

## Non-Goals
- Do not restate full implementations/examples for all graphs here.
- Do not embed variable information like prompts/tool params here; keep those downstream.

---

## MUST-KNOW (Invariants)
- [MUST] The single source of truth for graph registration is `open_langgraph.json`.
  - Format: `"graph_id": "./graphs/<path>.py:<export_name>"`
- [MUST] The server adds `graphs/` to `sys.path` at startup (`src/agent_server/main.py`).
  - If graph import fails, first check `sys.path`/paths/`export_name`.
- [MUST] Graph code must not depend directly on FastAPI or the DB.
  - Do not pass HTTP Request/Response, SQLAlchemy sessions, or FastAPI Depends into graph nodes.
  - Pass required values via `Runtime[Context]` or (when needed) auth context (`src/agent_server/core/auth_ctx.py`).
- [MUST] State persistence is owned by LangGraph checkpointers.
  - For long-term memory, intentionally use the Store API (`/store`) or a LangGraph store.
- [SHOULD] Prefer splitting a graph package into:
  - `context.py`: `Context` (runtime config)
  - `state.py`: `State` / `InputState`
  - `tools.py`: tool functions + `TOOLS` list
  - `prompts.py`: system prompt templates
  - `graph.py`: `StateGraph` builder + compile
  - `__init__.py`: export `graph`
- [MUST] If you use HITL (interrupts), keep the `interrupt()` input/output contract stable.
  - The streaming layer can convert `__interrupt__` updates into events (see `src/agent_server/services/streaming_service.py`).

---

## Common Tasks

### 1) Add a new graph
1. Create `graphs/<new_graph>/`
2. Build `graph = builder.compile(...)` in `graph.py`
3. Export `graph` from `__init__.py`
4. Register `graph_id` in `open_langgraph.json`
5. (Recommended) Document graph-specific rules/differences in `graphs/<new_graph>/AGENTS.md`
6. (Recommended) Add at least one scenario in `tests/e2e/`

### 2) Add/modify a tool
- Add an async tool function to `tools.py` and register it in `TOOLS`.
- Tool docstrings are the LLM-facing contract; specify inputs/outputs/constraints.
- For external I/O (network/files/DB), confirm safety/security/latency policy first.

### 3) Introduce HITL (approval gates)
- Reference: `graphs/react_agent_hitl/AGENTS.md`
- Keep interrupt payloads stable so clients/servers/tests can interpret them consistently.

---

## References (Downstream)
- ReAct example: `graphs/react_agent/AGENTS.md`
- HITL example: `graphs/react_agent_hitl/AGENTS.md`
- Subgraph example: `graphs/subgraph_agent/AGENTS.md`
- Graph loading/caching: `src/agent_server/services/langgraph_service.py`
- Server domain rules: `src/agent_server/AGENTS.md`

## Keywords Router
- `open_langgraph.json`, `graph_id`, `export_name` → `open_langgraph.json`, `src/agent_server/services/langgraph_service.py`
- `StateGraph`, `Runtime[Context]`, `add_messages` → each graph’s `state.py`/`context.py`
- `interrupt`, `HITL` → `graphs/react_agent_hitl/AGENTS.md`
