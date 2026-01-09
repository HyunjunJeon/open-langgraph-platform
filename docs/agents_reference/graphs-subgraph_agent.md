# (Reference) Graph: `subgraph_agent` (Subgraphs / Composition)

> This is a long-form reference companion to `graphs/subgraph_agent/AGENTS.md`.
> Prefer the MUST-KNOW guide in `graphs/subgraph_agent/AGENTS.md`.

## Overview

`subgraph_agent` demonstrates composing multiple LangGraph graphs via **subgraphs**.
Use this pattern when you want:

- reusable “skills” as independent graphs
- a top-level orchestrator graph that delegates work
- namespaced state and clearer boundaries between phases

## Common patterns

- A parent graph invokes a child graph (subgraph) as a node.
- Subgraphs should have well-defined input/output shapes.
- Subgraph boundaries are a good place to enforce invariants:
  - state shape normalization
  - tool availability per phase
  - safety checks before side effects

## Registration & execution

- Register the graph in `open_langgraph.json`.
- Runs are executed the same way as any other assistant/graph.

## Extension guidelines

- Keep subgraphs focused: one responsibility, clear I/O.
- Avoid hidden coupling via globals; pass config explicitly.
- Be careful with streaming semantics: decide whether the parent should forward child events.

