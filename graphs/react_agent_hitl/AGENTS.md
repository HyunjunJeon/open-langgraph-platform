# AGENTS.md - `graphs/react_agent_hitl/` (HITL ReAct Example)

This document keeps only MUST-KNOW guidance for the HITL (ReAct + interrupt) example graph.
Long-form details are delegated to: `docs/agents_reference/graphs-react_agent_hitl.md`.

## Purpose
- Provide a Human-in-the-Loop (HITL) pattern where tool execution requires human approval.

## Non-Goals
- Client UI and approval UX are out of scope; implement them in a separate UI if needed.

---

## MUST-KNOW (Invariants)
- [MUST] Graph registration single source of truth: `open_langgraph.json`
  - Default graph_id: `"agent_hitl": "./graphs/react_agent_hitl/graph.py:graph"`
- [MUST] Key difference: when `tool_calls` occur, the graph interrupts instead of immediately executing tools.
  - Approval node: `human_approval`
  - File: `graphs/react_agent_hitl/graph.py`
- [MUST] The interrupt payload is the contract for approval UI and resume logic:
  - `action_request.action == "tool_execution"`
  - `action_request.args` maps tool name → args
  - `config.allow_*` controls allowed actions (accept/edit/respond/ignore)
- [MUST] Resume is mapped in the API layer to a LangGraph `Command`.
  - Mapping: `src/agent_server/api/runs.py#map_command_to_langgraph`
- [SHOULD] The base Context/Tools structure mirrors `react_agent` (extend with the same patterns).

---

## Common Tasks

### Change the approval policy (allowed actions)
- Adjust the interrupt config `allow_*` flags in the `human_approval` node.

### Add a tool
- Add the tool to `graphs/react_agent_hitl/tools.py` and register it in `TOOLS`.

---

## References
- Graph domain rules: `graphs/AGENTS.md`
- Run/resume API contract: `src/agent_server/api/runs.py`, `src/agent_server/models/runs.py`
- (Reference) Legacy long-form doc: `docs/agents_reference/graphs-react_agent_hitl.md`

## Keywords Router
- `interrupt`, `human_approval` → `graphs/react_agent_hitl/graph.py`
- `Command`, `resume` → `src/agent_server/api/runs.py`, `src/agent_server/models/runs.py`
