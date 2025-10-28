"""SSE 스트리밍용 이벤트 변환기

이 모듈은 LangGraph 실행 이벤트를 SSE(Server-Sent Events) 형식으로 변환합니다.
원본(raw) 이벤트와 저장된(stored) 이벤트 모두를 처리할 수 있습니다.

주요 구성 요소:
• EventConverter - 이벤트 변환 로직을 담당하는 클래스
• convert_raw_to_sse() - 실시간 이벤트를 SSE로 변환
• convert_stored_to_sse() - 저장된 이벤트를 SSE로 변환 (재생용)

지원하는 이벤트 타입:
- messages: 메시지 청크 (스트리밍 응답)
- values: 상태 값
- updates: 상태 업데이트
- state: 전체 상태
- logs: 로그 메시지
- tasks: 실행 작업
- subgraphs: 서브그래프 정보
- debug: 디버그 정보
- events: 커스텀 이벤트
- checkpoints: 체크포인트
- custom: 사용자 정의 이벤트
- end: 스트림 종료
- error: 오류 정보

사용 예:
    converter = EventConverter()

    # 실시간 이벤트 변환
    sse_event = converter.convert_raw_to_sse(event_id, raw_event)

    # 저장된 이벤트 변환 (재생)
    sse_event = converter.convert_stored_to_sse(stored_event, run_id)
"""

from collections.abc import Mapping
from typing import Any, Protocol

from ..core.sse import (
    create_checkpoints_event,
    create_custom_event,
    create_debug_event,
    create_end_event,
    create_error_event,
    create_events_event,
    create_logs_event,
    create_messages_event,
    create_metadata_event,
    create_state_event,
    create_subgraphs_event,
    create_tasks_event,
    create_updates_event,
    create_values_event,
)


class StoredEventLike(Protocol):
    """Protocol describing stored events replayed from the database."""

    id: str
    event: str
    data: Mapping[str, Any] | None


class EventConverter:
    """LangGraph 이벤트를 SSE 형식으로 변환하는 변환기

    이 클래스는 LangGraph 그래프 실행 중 발생하는 다양한 이벤트를
    SSE(Server-Sent Events) 표준 형식으로 변환합니다.

    주요 기능:
    - 실시간 이벤트 변환: LangGraph astream()에서 나오는 이벤트 처리
    - 저장된 이벤트 변환: PostgreSQL에 저장된 이벤트 재생
    - 스트림 모드 감지: 이벤트 타입 자동 인식 및 적절한 SSE 형식 적용
    - Interrupt 처리: __interrupt__ 업데이트를 values 이벤트로 변환

    SSE 형식:
    - event: {이벤트_타입}
    - data: {JSON_페이로드}
    - id: {이벤트_ID}

    사용 패턴:
    - 싱글톤 또는 서비스 계층에서 인스턴스화
    - streaming_service에서 각 이벤트마다 convert_raw_to_sse() 호출
    - event_store에서 재생 시 convert_stored_to_sse() 호출
    """

    def convert_raw_to_sse(self, event_id: str, raw_event: Any) -> str | None:
        """실시간 원본 이벤트를 SSE 형식으로 변환

        LangGraph의 graph.astream()에서 나오는 원본 이벤트를 받아
        SSE(Server-Sent Events) 표준 형식의 문자열로 변환합니다.

        동작 흐름:
        1. 원본 이벤트를 파싱하여 스트림 모드와 페이로드 추출
        2. 스트림 모드에 따라 적절한 SSE 이벤트 생성
        3. SSE 형식 문자열 반환

        Args:
            event_id (str): 이벤트 고유 식별자 (순차 증가 ID)
            raw_event (Any): LangGraph에서 받은 원본 이벤트
                - tuple: (stream_mode, payload) 또는 (node_path, stream_mode, payload)
                - dict: 기본값 "values" 모드로 처리

        Returns:
            str | None: SSE 형식 문자열 또는 None (변환 불가 시)

        SSE 형식 예시:
            event: messages
            data: {"chunk": "Hello", "metadata": {...}}
            id: 1

        사용 예:
            converter = EventConverter()
            sse_event = converter.convert_raw_to_sse("1", ("messages", message_data))
        """
        stream_mode, payload = self._parse_raw_event(raw_event)
        return self._create_sse_event(stream_mode, payload, event_id)

    def convert_stored_to_sse(self, stored_event: StoredEventLike, run_id: str | None = None) -> str | None:
        """PostgreSQL에 저장된 이벤트를 SSE 형식으로 변환

        event_store에 저장된 이벤트를 SSE 형식으로 변환하여 재생합니다.
        클라이언트가 연결이 끊겼다가 재연결할 때 이전 이벤트를 다시 전송하는 데 사용됩니다.

        동작 흐름:
        1. 저장된 이벤트의 타입(event) 확인
        2. 저장된 데이터(data) 필드에서 페이로드 추출
        3. 이벤트 타입별로 적절한 SSE 형식 생성
        4. 원본 이벤트 ID 유지 (순서 보장)

        Args:
            stored_event: event_store에서 가져온 이벤트 ORM 객체
                - event (str): 이벤트 타입
                - data (dict): 저장된 페이로드
                - id (str): 원본 이벤트 ID
            run_id (str | None): 실행 ID (metadata 이벤트에 필요)

        Returns:
            str | None: SSE 형식 문자열 또는 None (변환 불가 시)

        지원하는 이벤트 타입:
            - messages: 메시지 청크 (message_chunk, metadata)
            - values: 상태 값 (chunk)
            - metadata: 실행 메타데이터 (run_id 필요)
            - state: 전체 상태 (state)
            - logs: 로그 (logs)
            - tasks: 작업 목록 (tasks)
            - subgraphs: 서브그래프 정보 (subgraphs)
            - debug: 디버그 정보 (debug)
            - events: 커스텀 이벤트 (event)
            - end: 스트림 종료
            - error: 오류 정보 (error)

        사용 예:
            stored_event = await event_store.get_event(event_id)
            sse_event = converter.convert_stored_to_sse(stored_event, run_id)
        """
        event_type = stored_event.event
        data: Mapping[str, Any] | None = stored_event.data
        event_id = stored_event.id

        def _coerce_dict(value: Any) -> dict[str, Any]:
            if isinstance(value, Mapping):
                return dict(value)
            return {}

        data_dict = _coerce_dict(data)

        if event_type == "messages":
            message_chunk = data_dict.get("message_chunk")
            metadata = data_dict.get("metadata")
            if message_chunk is None:
                return None
            # 메타데이터가 있으면 튜플로, 없으면 청크만 전달
            message_data = (message_chunk, metadata) if metadata is not None else message_chunk
            return create_messages_event(message_data, event_id=event_id)
        elif event_type == "values":
            return create_values_event(_coerce_dict(data_dict), event_id)
        elif event_type == "metadata":
            if run_id is None:
                return None
            return create_metadata_event(run_id, event_id)
        elif event_type == "state":
            return create_state_event(_coerce_dict(data_dict.get("state")), event_id)
        elif event_type == "logs":
            return create_logs_event(_coerce_dict(data_dict.get("logs")), event_id)
        elif event_type == "tasks":
            return create_tasks_event(_coerce_dict(data_dict.get("tasks")), event_id)
        elif event_type == "subgraphs":
            return create_subgraphs_event(_coerce_dict(data_dict.get("subgraphs")), event_id)
        elif event_type == "debug":
            return create_debug_event(_coerce_dict(data_dict.get("debug")), event_id)
        elif event_type == "events":
            return create_events_event(_coerce_dict(data_dict.get("event")), event_id)
        elif event_type == "end":
            return create_end_event(event_id)
        elif event_type == "error":
            error_payload = data_dict.get("error")
            error_message = error_payload if isinstance(error_payload, str) else str(error_payload)
            return create_error_event(error_message, event_id)
        return None

    def _parse_raw_event(self, raw_event: Any) -> tuple[str, Any]:
        """원본 이벤트를 파싱하여 (스트림_모드, 페이로드) 튜플 반환

        LangGraph의 graph.astream()은 여러 형식으로 이벤트를 반환할 수 있습니다:
        - 2-튜플: (stream_mode, payload)
        - 3-튜플: (node_path, stream_mode, payload)
        - 단일 값: 딕셔너리 또는 기타 데이터

        이 메서드는 이러한 다양한 형식을 정규화하여 일관된 처리가 가능하도록 합니다.

        Args:
            raw_event (Any): LangGraph에서 받은 원본 이벤트
                - tuple(2): (stream_mode, payload)
                - tuple(3): (node_path, stream_mode, payload)
                - 기타: 단일 값 (기본 "values" 모드로 처리)

        Returns:
            tuple[str, Any]: (stream_mode, payload) 정규화된 튜플
                - stream_mode: "messages", "values", "updates" 등
                - payload: 이벤트 데이터

        사용 예:
            # 2-튜플 이벤트
            mode, payload = self._parse_raw_event(("messages", message_data))
            # 결과: ("messages", message_data)

            # 3-튜플 이벤트 (노드 경로 포함)
            mode, payload = self._parse_raw_event(("path.to.node", "updates", data))
            # 결과: ("updates", data) - 노드 경로는 현재 무시

            # 단일 값 이벤트
            mode, payload = self._parse_raw_event({"key": "value"})
            # 결과: ("values", {"key": "value"})
        """
        if isinstance(raw_event, tuple):
            if len(raw_event) == 2:
                # (stream_mode, payload) 형식
                return raw_event[0], raw_event[1]
            elif len(raw_event) == 3:
                # (node_path, stream_mode, payload) 형식
                # 노드 경로는 현재 사용하지 않으므로 무시하고 모드와 페이로드만 반환
                return raw_event[1], raw_event[2]

        # 튜플이 아닌 경우 기본 "values" 모드로 처리
        return "values", raw_event

    def _create_sse_event(self, stream_mode: str, payload: Any, event_id: str) -> str | None:
        """스트림 모드에 따라 적절한 SSE 이벤트 생성

        파싱된 스트림 모드와 페이로드를 받아 해당하는 SSE 형식 문자열을 생성합니다.
        각 스트림 모드별로 적절한 SSE 생성 함수를 호출합니다.

        특별 처리 규칙:
        - updates 모드: __interrupt__ 키가 있으면 values 이벤트로 변환
          (Human-in-the-Loop 인터럽트는 클라이언트에게 values로 전달)

        Args:
            stream_mode (str): 이벤트 스트림 모드
                - "messages": 메시지 청크
                - "values": 상태 값
                - "updates": 상태 업데이트
                - "state": 전체 상태
                - "logs": 로그 메시지
                - "tasks": 실행 작업
                - "subgraphs": 서브그래프 정보
                - "debug": 디버그 정보
                - "events": 커스텀 이벤트
                - "checkpoints": 체크포인트
                - "custom": 사용자 정의
                - "end": 스트림 종료
            payload (Any): 이벤트 데이터 페이로드
            event_id (str): SSE 이벤트 ID

        Returns:
            str | None: SSE 형식 문자열 또는 None (알 수 없는 모드)

        SSE 형식:
            event: {stream_mode}
            data: {JSON_직렬화된_payload}
            id: {event_id}

        사용 예:
            sse = self._create_sse_event("messages", message_data, "1")
            # 결과:
            # event: messages
            # data: {"chunk": "Hello"}
            # id: 1
        """
        if stream_mode == "messages":
            return create_messages_event(payload, event_id=event_id)
        elif stream_mode == "values":
            return create_values_event(payload, event_id)
        elif stream_mode == "updates":
            # Interrupt 업데이트를 values로 변환, 그 외에는 updates 유지
            # HITL(Human-in-the-Loop) 패턴에서 __interrupt__ 키는 사용자 승인 대기 상태를 나타냄
            if isinstance(payload, dict) and "__interrupt__" in payload:
                return create_values_event(payload, event_id)
            else:
                return create_updates_event(payload, event_id)
        elif stream_mode == "state":
            return create_state_event(payload, event_id)
        elif stream_mode == "logs":
            return create_logs_event(payload, event_id)
        elif stream_mode == "tasks":
            return create_tasks_event(payload, event_id)
        elif stream_mode == "subgraphs":
            return create_subgraphs_event(payload, event_id)
        elif stream_mode == "debug":
            return create_debug_event(payload, event_id)
        elif stream_mode == "events":
            return create_events_event(payload, event_id)
        elif stream_mode == "checkpoints":
            return create_checkpoints_event(payload, event_id)
        elif stream_mode == "custom":
            return create_custom_event(payload, event_id)
        elif stream_mode == "end":
            return create_end_event(event_id)

        # 알 수 없는 스트림 모드는 None 반환 (무시됨)
        return None


class StoredEventLike(Protocol):
    """Minimal protocol describing stored events replayed from the database."""

    id: str
    event: str
    data: Mapping[str, Any] | None
