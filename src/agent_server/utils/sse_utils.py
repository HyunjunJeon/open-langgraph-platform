def generate_event_id(run_id: str, sequence: int) -> str:
    """SSE 이벤트 ID를 다음 형식으로 생성합니다: {run_id}_event_{sequence}

    매개변수:
        run_id: 실행 식별자
        sequence: 이벤트 순서 번호

    반환값:
        형식화된 이벤트 ID 문자열
    """
    return f"{run_id}_event_{sequence}"


def extract_event_sequence(event_id: str) -> int:
    """event_id 형식에서 숫자 시퀀스 추출: {run_id}_event_{sequence}

    매개변수:
        event_id: 이벤트 ID 문자열

    반환값:
        추출에 성공한 경우 시퀀스 번호, 실패 시 0
    """
    try:
        return int(event_id.split("_event_")[-1])
    except (ValueError, IndexError):
        return 0
