def generate_event_id(run_id: str, sequence: int) -> str:
    """Generate an SSE event ID in the format: {run_id}_event_{sequence}

    Args:
        run_id: The run identifier.
        sequence: The event sequence number.

    Returns:
        The formatted event ID string.
    """
    return f"{run_id}_event_{sequence}"


def extract_event_sequence(event_id: str) -> int:
    """Extract the numeric sequence from an event_id of the format: {run_id}_event_{sequence}

    Args:
        event_id: The event ID string.

    Returns:
        The sequence number if extraction is successful, otherwise 0.
    """
    try:
        return int(event_id.split("_event_")[-1])
    except (ValueError, IndexError):
        return 0
