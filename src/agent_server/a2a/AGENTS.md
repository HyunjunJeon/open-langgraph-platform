# AGENTS.md - `src/agent_server/a2a/` (A2A Integration)

This directory integrates LangGraph graphs with the A2A (Agent-to-Agent) protocol.

## Purpose
- Provide A2A JSON-RPC + streaming (SSE) endpoints under `/a2a/*`.
- Generate and expose Agent Cards (`.well-known`) for automatic discovery.

## Non-Goals
- Graph loading/caching/default assistant creation is owned by `src/agent_server/services/langgraph_service.py`.
- Remote federation discovery/call policy is owned by `src/agent_server/services/federation/AGENTS.md`.

---

## MUST-KNOW (Invariants)
- [MUST] The A2A routing entrypoint is `router.py`; the default base path is `/a2a/`.
- [MUST] Agent Cards are typically exposed at `{base}/.well-known/agent-card.json`.
- [MUST] A2A compatibility may be detected by rules (commonly the presence of a `messages` field).
  - A2A-compatible graphs may be auto-registered at service startup (see `src/agent_server/services/langgraph_service.py`).
- [SHOULD] Message conversion is owned by the converter (A2A Message/Part ↔ LangChain `BaseMessage`).

---

## What’s Here (Map)
- `router.py`: A2A routing (`/a2a/{graph_id}` + agent card + listing)
- `executor.py`: run LangGraph (`astream`) and convert/stream as A2A events
- `converter.py`: message format conversion
- `card_generator.py`: build Agent Cards from graph metadata/tools/docstrings
- `detector.py`: A2A compatibility detection
- `decorators.py`: metadata helpers such as `@a2a_metadata`
- `types.py`: internal types

---

## Common Tasks

### Add A2A metadata to a graph
- In graph code, use `@a2a_metadata(...)` to declare name/description/skills.

### Test A2A endpoints
- Listing: `curl http://localhost:8000/a2a/`
- Card: `curl http://localhost:8000/a2a/<graph_id>/.well-known/agent-card.json`

---

## References
- Federation (remote peers): `src/agent_server/services/federation/AGENTS.md`
- Graph registry: `open_langgraph.json`
- LangGraphService: `src/agent_server/services/langgraph_service.py`

## Keywords Router
- `agent-card`, `.well-known` → `src/agent_server/a2a/card_generator.py`, `src/agent_server/a2a/router.py`
- `message` conversion → `src/agent_server/a2a/converter.py`
- `astream`, `streaming` → `src/agent_server/a2a/executor.py`
