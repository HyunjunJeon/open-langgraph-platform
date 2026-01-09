# (Reference) Graph: `react_agent` (ReAct)

> This is a long-form reference companion to `graphs/react_agent/AGENTS.md`.
> Prefer the MUST-KNOW guide in `graphs/react_agent/AGENTS.md` when changing graph behavior.

## Overview

`react_agent` is a LangGraph example graph that implements the ReAct loop:

```
User message
  -> Model decides next step (final answer vs tool call)
  -> Tool executes (if requested)
  -> Observation is fed back to the model
  -> Repeat until final answer (bounded by recursion_limit)
```

It is intended as a baseline “tool-using chat agent” that is easy to extend.

## Key files (typical)

- `graphs/react_agent/graph.py`: builds and exports `graph`
- `graphs/react_agent/state.py`: state schema (messages, counters, etc.)
- `graphs/react_agent/tools.py`: tool functions available to the model
- `graphs/react_agent/prompts.py`: system prompt template(s)
- `graphs/react_agent/context.py`: runtime config (model name, limits, prompt vars)
- `graphs/react_agent/utils.py`: helpers (model loading, message extraction, etc.)

## Registration & execution

- Register the graph in `open_langgraph.json`, e.g.:
  - `"agent": "./graphs/react_agent/graph.py:graph"`
- Create an assistant for that graph and run it via:
  - HTTP: `/threads/{thread_id}/runs` and `/threads/{thread_id}/runs/stream`
  - SDK: LangGraph client against this server

## Extension guidelines

- Keep state minimal and serializable.
- Prefer tools for side effects (network/DB/IO) and keep nodes mostly pure.
- Always keep a recursion/step limit to prevent infinite loops.
- If you add new configuration knobs, thread them via runtime/context instead of globals.

