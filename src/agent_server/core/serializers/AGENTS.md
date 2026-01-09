# AGENTS.md - `src/agent_server/core/serializers/` (Serialization)

This directory provides a stable, JSON-compatible serialization layer for objects returned from API/Services.

## Purpose
- Safely serialize LangGraph/LangChain/Pydantic objects to JSON.
- Standardize how runtime objects (stream events, snapshots, tasks) are emitted as API responses/events.

## Non-Goals
- API/Services own "what to serialize and what the wire shape is".
- Do not hide serialization failures; let higher layers handle them gracefully if needed.

---

## MUST-KNOW (Invariants)
- [MUST] The default serializer is `GeneralSerializer`, following the LangGraph SDK `_orjson_default` style.
  - Pydantic v2: `model_dump()`
  - Pydantic v1 / LangChain: `dict()`
  - NamedTuple: `_asdict()`
  - set/tuple/list/dict are handled recursively
  - otherwise: `str(obj)` fallback
  - File: `src/agent_server/core/serializers/general.py`
- [MUST] Use `LangGraphSerializer` for LangGraph-specific objects.
  - `json.dumps(..., default=GeneralSerializer.serialize)` → `json.loads(...)` ensures JSON-safe output
  - File: `src/agent_server/core/serializers/langgraph.py`
- [SHOULD] Wrap serialization errors with `SerializationError` so higher layers can standardize logging/response format.
  - File: `src/agent_server/core/serializers/base.py`

---

## Common Pitfalls
- LangGraph runtime objects (Interrupt, Task, Snapshot) can change shape across versions.
  - If you change serialization rules, update `tests/unit/test_core/test_serializers/` accordingly.

---

## References
- Core layer overview: `src/agent_server/core/AGENTS.md`
- Thread state/snapshot conversion: `src/agent_server/services/thread_state_service.py`
