# AGENTS.md - `graphs/react_agent/` (ReAct Example Graph)

This document keeps only MUST-KNOW guidance for the ReAct example graph.
Long-form details are delegated to: `docs/agents_reference/graphs-react_agent.md`.

## Purpose
- Provide a baseline example graph implementing the ReAct (Reasoning ↔ Acting) pattern in LangGraph.

## Non-Goals
- This graph is a reference/example, not a production-ready template; adjust tools/prompts/guardrails to your needs.

---

## MUST-KNOW (Invariants)
- [MUST] Graph registration single source of truth: `open_langgraph.json`
  - Default graph_id: `"agent": "./graphs/react_agent/graph.py:graph"`
- [MUST] Export rule: `graphs/react_agent/__init__.py` must export `graph`.
- [MUST] State is message-accumulation (`add_messages`), and LangGraph uses `is_last_step` to manage recursion limits.
  - File: `graphs/react_agent/state.py`
- [MUST] Node structure is a 2-node loop: model call ↔ tool execution.
  - `call_model` → (if `tool_calls`) `tools` → `call_model` … → `__end__`
  - File: `graphs/react_agent/graph.py`
- [MUST] Model loading expects a `"provider/model"` string.
  - Invalid format can cause split errors in `load_chat_model()`.
  - File: `graphs/react_agent/utils.py`
- [SHOULD] Runtime context can be overridden via env vars:
  - `MODEL`, `SYSTEM_PROMPT`, `MAX_SEARCH_RESULTS`
  - File: `graphs/react_agent/context.py`

---

## Customization Points
- Prompts: `graphs/react_agent/prompts.py`
- Model/context: `graphs/react_agent/context.py`
- Tools: `graphs/react_agent/tools.py` (add and register in `TOOLS`)

---

## Common Tasks

### Change the model
- Set env var like `MODEL=anthropic/<model>` or adjust `Context(model=...)`.

### Add a tool
1. Add an async tool function in `graphs/react_agent/tools.py`
2. Register it in `TOOLS`
3. If needed, add config fields to `Context`

---

## References
- Graph domain rules: `graphs/AGENTS.md`
- Server graph loading: `src/agent_server/services/langgraph_service.py`
- (Reference) Legacy long-form doc: `docs/agents_reference/graphs-react_agent.md`

## Keywords Router
- `ReAct`, `ToolNode`, `tool_calls` → `graphs/react_agent/graph.py`
- `Context`, `MODEL`, `SYSTEM_PROMPT` → `graphs/react_agent/context.py`
- `load_chat_model` → `graphs/react_agent/utils.py`
