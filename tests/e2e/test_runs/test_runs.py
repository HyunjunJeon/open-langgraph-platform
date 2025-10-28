import pytest

# Match import style used by other e2e tests when run as top-level modules
from tests.e2e._utils import elog, get_e2e_client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_runs_crud_and_join_e2e():
    """
    Mirrors existing e2e style using the typed SDK client (see test_chat_streaming, test_background_run_join).
    Validates the non-streaming "background run" flow and CRUD around it:
      1) Ensure assistant exists (graph_id=agent)
      2) Create a thread
      3) Create a background run (non-stream)
      4) Join the run for final output
      5) Get the run by id
      6) List runs for the same thread and ensure presence
      7) Stream endpoint for a terminal run should yield an end event quickly via SDK wrapper
    """
    client = get_e2e_client()

    # 1) Assistant
    assistant = await client.assistants.create(
        graph_id="agent",
        config={"tags": ["chat", "runs-crud"]},
        if_exists="do_nothing",
    )
    elog("Assistant.create", assistant)
    assert "assistant_id" in assistant
    assistant_id = assistant["assistant_id"]

    # 2) Thread
    thread = await client.threads.create()
    elog("Threads.create", thread)
    thread_id = thread["thread_id"]

    # 3) Background run (non-streaming)
    run = await client.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input={"messages": [{"role": "user", "content": "Say one short sentence."}]},
        stream_mode=[
            "messages",
            "values",
        ],  # ensure both modes are available for later stream
    )
    elog("Runs.create", run)
    assert "run_id" in run
    run_id = run["run_id"]

    # 4) Join run and assert final output (dict)
    final_state = await client.runs.join(thread_id, run_id)
    elog("Runs.join", final_state)
    assert isinstance(final_state, dict)

    # 5) Get run by id
    got = await client.runs.get(thread_id, run_id)
    elog("Runs.get", got)
    assert got["run_id"] == run_id
    assert got["thread_id"] == thread_id
    assert got["assistant_id"] == assistant_id
    assert got["status"] in (
        "completed",
        "failed",
        "cancelled",
        "running",
        "streaming",
        "pending",
    )

    # 6) List runs for the thread and ensure our run is present
    runs_list = await client.runs.list(thread_id)
    elog("Runs.list", runs_list)
    assert isinstance(runs_list, list)
    assert any(r["run_id"] == run_id for r in runs_list)

    # 7) Stream endpoint after completion: should yield an end event quickly.
    # Reuse the SDK join_stream to align with current helper patterns.
    # We accept that there may be zero deltas and just an "end".
    end_seen = False
    async for chunk in client.runs.join_stream(
        thread_id=thread_id,
        run_id=run_id,
        stream_mode=["messages", "values"],
    ):
        elog("Runs.stream(terminal) event", {"event": getattr(chunk, "event", None)})
        if getattr(chunk, "event", None) == "end":
            end_seen = True
            break
    assert end_seen, "Expected an 'end' event when streaming a terminal run"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_runs_cancel_e2e():
    """
    Cancellation flow aligned with e2e client helpers:
      1) Create assistant and thread
      2) Start a streaming run via SDK client
      3) Cancel the run via SDK
      4) Verify status is cancelled/interrupted/final afterward
    """
    client = get_e2e_client()

    # Assistant + thread
    assistant = await client.assistants.create(
        graph_id="agent",
        config={"tags": ["chat", "runs-cancel"]},
        if_exists="do_nothing",
    )
    thread = await client.threads.create()
    thread_id = thread["thread_id"]
    assistant_id = assistant["assistant_id"]

    # Start streaming run (returns an async iterator through the SDK)
    stream = client.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input={"messages": [{"role": "user", "content": "Keep talking slowly."}]},
        stream_mode=["messages"],
    )

    # Consume a couple of events then cancel
    events_seen = 0
    async for chunk in stream:
        events_seen += 1
        elog("Runs.stream (pre-cancel)", {"event": getattr(chunk, "event", None)})
        # Try to fetch a run id by listing runs; server persists runs metadata now
        if events_seen >= 2:
            break

    # Find the most recent run id
    runs_list = await client.runs.list(thread_id)
    assert len(runs_list) > 0, "Expected at least one run for cancellation test"
    run_id = runs_list[0]["run_id"]

    # Cancel the run
    patched = await client.runs.cancel(thread_id, run_id)
    elog("Runs.cancel", patched)
    assert patched["status"] in ("cancelled", "interrupted")

    # Verify final state
    got = await client.runs.get(thread_id, run_id)
    elog("Runs.get(post-cancel)", got)
    assert got["status"] in ("cancelled", "interrupted", "failed", "completed")
