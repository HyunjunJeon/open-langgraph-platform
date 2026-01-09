# (Reference) Tests Layer (`tests/`)

> This is a long-form reference companion to `tests/AGENTS.md`.
> Prefer the MUST-KNOW guide in `tests/AGENTS.md` for project-specific testing rules.

## Test pyramid (recommended)

- **Unit tests**: fast, isolated, no DB/network
- **Integration tests**: real DB + multiple components
- **E2E tests**: full workflows (often via HTTP/SSE), slowest but highest confidence

## Directory layout (typical)

- `tests/unit/`: unit tests (pure functions, small components)
- `tests/integration/`: API/service integration with a real database
- `tests/e2e/`: end-to-end flows (server + streaming + HITL where applicable)
- `tests/fixtures/`: reusable fixtures (clients, auth, DB helpers, LangGraph mocks)
- `tests/conftest.py`: global pytest fixtures and configuration

## Running tests

Run everything:

```bash
uv run pytest
```

Run a subset:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest -k \"stream\" -vv
```

Common local checks:

```bash
make format
make lint
make type-check
```

## Writing guidelines

- Prefer unit tests for logic-heavy code paths (conversion, validation, filtering).
- Use integration tests to lock in HTTP contract behavior and DB persistence.
- Use E2E tests for “real user flows”:
  - SSE streaming
  - reconnect/replay
  - HITL interrupt/resume/cancel

## Debugging tips

- Show print output:

```bash
uv run pytest -s
```

- Stop on first failure:

```bash
uv run pytest -x
```

- Drop into debugger on failure:

```bash
uv run pytest --pdb
```

## CI

- Keep tests deterministic (no reliance on wall-clock timing where possible).
- Avoid network calls; mock external providers.
- Prefer small, focused tests over large “do everything” tests.

## References

- `tests/AGENTS.md`
- `CONTRIBUTING.md`

