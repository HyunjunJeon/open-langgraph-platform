# AGENTS.md - `graphs/subgraph_agent/` (Subgraph Composition Example)

This document keeps only MUST-KNOW guidance for the subgraph composition example.
Long-form details are delegated to: `docs/agents_reference/graphs-subgraph_agent.md`.

## Purpose
- Provide a reference composition pattern: reusing a graph as a node (subgraph).

## Non-Goals
- Do not provide long-form guidance on subgraph event UX/tracing here (delegate to streaming layer/tests).

---

## MUST-KNOW (Invariants)
- [MUST] Graph registration single source of truth: `open_langgraph.json`
  - graph_id: `"subgraph_agent": "./graphs/subgraph_agent/graph.py:graph"`
- [MUST] This graph delegates to the `react_agent` graph as a subgraph node.
  - Subgraph: `react_agent.graph` (import name: `react_graph`)
  - Files: `graphs/subgraph_agent/graph.py`, `graphs/react_agent/graph.py`
- [MUST] `State`/`InputState`/`Context` share the exact same schema as `react_agent`.
  - Files: `graphs/react_agent/state.py`, `graphs/react_agent/context.py`
  - If you attach a different subgraph, design state compatibility (or a conversion node) first.
- [MUST] Execution path is linear: `__start__ → no_stream → subgraph_agent → __end__`
  - `no_stream` tags the LLM call with `langsmith:nostream`.
  - The server may filter events with this tag (see References).
- [SHOULD] If you need subgraph-internal events, use `stream_subgraphs=True`.
  - Without it, subgraph node events may be omitted.

---

## Common Tasks

### Replace the subgraph
- In `graphs/subgraph_agent/graph.py`, change the `react_graph` import to the desired graph.
- [MUST] If state/context is not compatible, add a conversion node.

### Debug `langsmith:nostream` filtering/streaming
- If events are missing, check:
  - 1) the tag is applied in `no_stream` (`graphs/subgraph_agent/graph.py`)
  - 2) server filtering logic (`src/agent_server/api/runs.py`)
  - 3) whether `stream_subgraphs` is enabled

---

## References
- Graph domain rules: `graphs/AGENTS.md`
- ReAct subgraph: `graphs/react_agent/AGENTS.md`
- `langsmith:nostream` event filtering: `src/agent_server/api/runs.py`
- E2E: `tests/e2e/test_streaming/test_event_filtering_and_subgraphs.py`
- (Reference) Legacy long-form doc: `docs/agents_reference/graphs-subgraph_agent.md`

## Keywords Router
- `subgraph`, `stream_subgraphs` → `src/agent_server/api/runs.py`, `tests/e2e/test_streaming/test_event_filtering_and_subgraphs.py`
- `langsmith:nostream`, `no_stream` → `graphs/subgraph_agent/graph.py`
