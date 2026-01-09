# (Reference) Graph: `react_agent_hitl` (ReAct + Human-in-the-Loop)

> This is a long-form reference companion to `graphs/react_agent_hitl/AGENTS.md`.
> Prefer the MUST-KNOW guide in `graphs/react_agent_hitl/AGENTS.md` when changing HITL semantics.

## Overview

`react_agent_hitl` is a ReAct-style graph with explicit **Human-in-the-Loop** interruption points.
It is intended to demonstrate patterns like:

- approval gates before a risky tool/action runs
- pausing a run and resuming later with human input
- surfacing interrupt metadata to the client

## Typical mechanics

- The graph uses LangGraph interrupt/resume primitives to pause execution.
- The server exposes run streaming + resume endpoints; the client reacts to interrupt events.
- A resumed run should preserve tenant scoping and state persistence guarantees.

## Registration & execution

- Register the graph in `open_langgraph.json` and create an assistant as usual.
- Start a run (streaming is recommended so you can observe the interrupt event).
- Resume/cancel using the appropriate run endpoints (see `src/agent_server/api/runs.py`).

## Extension guidelines

- Make interrupt payloads explicit and stable (treat them as part of the contract).
- Never trust “human response” inputs; validate and scope them like any other external input.
- Prefer small, auditable approval decisions (yes/no + optional structured fields).

