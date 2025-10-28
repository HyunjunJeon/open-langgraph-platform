"""SSE 스트리밍 오케스트레이션 서비스

이 모듈은 LangGraph 실행 이벤트를 SSE(Server-Sent Events) 프로토콜로
클라이언트에게 실시간 스트리밍하고, PostgreSQL에 영속화하여 재생을 지원합니다.

주요 구성 요소:
• StreamingService - SSE 스트리밍 및 이벤트 관리 총괄
• streaming_service - 전역 서비스 인스턴스

주요 기능:
• 실시간 이벤트 스트리밍: LangGraph 실행 이벤트를 SSE로 전달
• 이벤트 영속화: PostgreSQL에 저장하여 재연결 시 재생 가능
• 브로커 기반 분배: 프로듀서-컨슈머 패턴으로 다중 클라이언트 지원
• 이벤트 변환: LangGraph 형식 → Agent Protocol SSE 형식

사용 예:
    from services.streaming_service import streaming_service

    # 실행 스트리밍 (재연결 지원)
    async for sse_event in streaming_service.stream_run_execution(run, last_event_id="run_123_event_42"):
        yield sse_event

    # 실행 취소 시그널
    await streaming_service.signal_run_cancelled(run_id)
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from ..core.sse import create_error_event, create_metadata_event
from ..models import Run
from ..utils import extract_event_sequence, generate_event_id
from .broker import broker_manager
from .event_converter import EventConverter
from .event_store import event_store, store_sse_event

logger = logging.getLogger(__name__)


class StreamingService:
    """SSE 스트리밍 오케스트레이션 서비스 (LangGraph 호환)

    이 클래스는 LangGraph 실행 이벤트를 SSE(Server-Sent Events)로 스트리밍하고,
    PostgreSQL에 영속화하여 재연결 시 재생을 지원합니다.

    주요 기능:
    - 실시간 이벤트 스트리밍: 브로커를 통한 프로듀서-컨슈머 패턴
    - 이벤트 영속화: PostgreSQL 기반 이벤트 저장소 활용
    - 재연결 지원: last_event_id 기반 이벤트 재생
    - 이벤트 변환: LangGraph 형식 → Agent Protocol SSE 형식
    - 실행 제어: 취소, 인터럽트, 에러 시그널링

    아키텍처:
    - Producer: execute_run_async()가 LangGraph 이벤트를 broker + DB에 전달
    - Consumer: stream_run_execution()이 broker에서 이벤트를 읽어 SSE로 전송
    - Storage: event_store가 이벤트를 PostgreSQL에 저장하여 재생 가능

    사용 패턴:
    - 싱글톤 인스턴스: streaming_service (모듈 하단)
    - 비동기 스트리밍: stream_run_execution()으로 AsyncIterator 반환
    """

    def __init__(self) -> None:
        # 실행별 이벤트 시퀀스 카운터 (이벤트 ID 생성 및 중복 방지용)
        self.event_counters: dict[str, int] = {}
        # LangGraph 이벤트 → Agent Protocol SSE 변환기
        self.event_converter = EventConverter()

    def _process_interrupt_updates(self, raw_event: Any, only_interrupt_updates: bool) -> tuple[Any, bool]:
        """인터럽트 업데이트 처리 로직 (필터링 및 변환)

        사용자가 'updates' stream_mode를 요청하지 않았을 때, 인터럽트 업데이트만 선택적으로 처리합니다.
        LangGraph는 인터럽트 발생 시 __interrupt__ 키를 포함한 updates 이벤트를 발행하는데,
        이를 values 이벤트로 변환하여 클라이언트에게 전달합니다.

        동작 흐름:
        1. only_interrupt_updates=True인 경우에만 필터링 적용
        2. updates 이벤트 중 __interrupt__ 키가 있고 값이 있는 경우만 통과
        3. 통과한 인터럽트 업데이트는 values 이벤트로 변환
        4. 나머지 updates 이벤트는 스킵

        Args:
            raw_event (Any): LangGraph에서 받은 원시 이벤트 (tuple 또는 dict)
            only_interrupt_updates (bool): True이면 인터럽트 업데이트만 처리

        Returns:
            tuple[Any, bool]: (처리된 이벤트, 스킵 여부)
                - 처리된 이벤트: 변환된 이벤트 또는 원본 이벤트
                - 스킵 여부: True이면 이 이벤트를 브로커/저장소에 전달하지 않음
        """
        if (
            isinstance(raw_event, tuple)
            and len(raw_event) >= 2
            and raw_event[0] == "updates"
            and only_interrupt_updates
        ):
            # 사용자가 updates를 요청하지 않았으므로 인터럽트 업데이트만 처리
            if (
                isinstance(raw_event[1], dict)
                and "__interrupt__" in raw_event[1]
                and len(raw_event[1].get("__interrupt__", [])) > 0
            ):
                # 인터럽트 업데이트를 values 이벤트로 변환하여 클라이언트에게 전달
                return ("values", raw_event[1]), False
            else:
                # 인터럽트가 아닌 일반 업데이트는 스킵 (요청하지 않았으므로)
                return raw_event, True
        else:
            # 필터링이 필요없거나 인터럽트 모드가 아닌 경우 원본 이벤트 그대로 반환
            return raw_event, False

    def _next_event_counter(self, run_id: str, event_id: str) -> int:
        """실행별 이벤트 카운터를 업데이트하고 다음 시퀀스 번호 반환

        이 메서드는 event_id에서 시퀀스 번호를 추출하여 실행별 카운터를 업데이트합니다.
        카운터는 이벤트 ID 생성 및 중복 방지에 사용됩니다.

        동작 방식:
        1. event_id에서 시퀀스 번호 추출 (예: "run_123_event_42" → 42)
        2. 현재 저장된 카운터와 비교
        3. 추출된 번호가 더 크면 카운터 업데이트
        4. 최신 카운터 값 반환

        Args:
            run_id (str): 실행 고유 식별자
            event_id (str): 이벤트 ID (형식: {run_id}_event_{sequence})

        Returns:
            int: 업데이트된 이벤트 카운터 값
        """
        try:
            idx = self._extract_event_sequence(event_id)
            current = self.event_counters.get(run_id, 0)
            if idx > current:
                self.event_counters[run_id] = idx
                return idx
        except Exception:
            pass  # 형식 오류 무시 (비정상 event_id 포맷)
        return self.event_counters.get(run_id, 0)

    async def put_to_broker(
        self,
        run_id: str,
        event_id: str,
        raw_event: Any,
        only_interrupt_updates: bool = False,
    ) -> None:
        """이벤트를 브로커 큐에 추가하여 라이브 컨슈머(클라이언트)에게 전달

        이 메서드는 LangGraph 실행 중 발생한 이벤트를 브로커를 통해 실시간으로 전달합니다.
        프로듀서-컨슈머 패턴에서 프로듀서 역할을 수행합니다.

        동작 흐름:
        1. 실행에 해당하는 브로커 획득 또는 생성
        2. 이벤트 카운터 업데이트 (시퀀스 추적)
        3. 인터럽트 업데이트 필터링 및 변환
        4. 브로커 큐에 이벤트 추가

        Args:
            run_id (str): 실행 고유 식별자
            event_id (str): 이벤트 고유 식별자 (형식: {run_id}_event_{sequence})
            raw_event (Any): LangGraph에서 받은 원시 이벤트
            only_interrupt_updates (bool): True이면 인터럽트 업데이트만 처리 (기본값: False)

        참고:
            - 브로커는 메모리 기반 큐로 다중 클라이언트에게 이벤트 분배
            - 이벤트는 별도로 store_event_from_raw()를 통해 DB에도 저장됨
        """
        broker = broker_manager.get_or_create_broker(run_id)
        self._next_event_counter(run_id, event_id)

        # 인터럽트 업데이트 필터링 및 변환
        processed_event, should_skip = self._process_interrupt_updates(raw_event, only_interrupt_updates)
        if should_skip:
            return

        await broker.put(event_id, processed_event)

    async def store_event_from_raw(
        self,
        run_id: str,
        event_id: str,
        raw_event: Any,
        only_interrupt_updates: bool = False,
    ) -> None:
        """원시 이벤트를 저장소 형식으로 변환하여 PostgreSQL에 영속화

        이 메서드는 LangGraph 이벤트를 파싱하여 PostgreSQL 이벤트 저장소에 저장합니다.
        재연결 시 이벤트 재생을 위해 필수적입니다.

        동작 흐름:
        1. 인터럽트 업데이트 필터링 및 변환
        2. 이벤트 구조 파싱 (node_path, stream_mode, payload 추출)
        3. stream_mode에 따라 저장 형식 결정
        4. event_store를 통해 PostgreSQL에 저장

        지원하는 stream_mode:
        - messages: 메시지 청크 스트리밍 (LLM 응답 등)
        - values: 그래프 상태 값 (일반 실행 데이터)
        - updates: 상태 업데이트 (인터럽트 포함)
        - end: 실행 완료 시그널

        Args:
            run_id (str): 실행 고유 식별자
            event_id (str): 이벤트 고유 식별자
            raw_event (Any): LangGraph에서 받은 원시 이벤트
            only_interrupt_updates (bool): True이면 인터럽트 업데이트만 저장

        참고:
            - 저장된 이벤트는 stream_run_execution()의 재생 로직에서 사용됨
            - event_store.cleanup_old_events()가 주기적으로 오래된 이벤트 삭제
        """
        # 인터럽트 업데이트 필터링 및 변환
        processed_event, should_skip = self._process_interrupt_updates(raw_event, only_interrupt_updates)
        if should_skip:
            return

        # 처리된 이벤트 구조 파싱
        node_path = None
        stream_mode_label = None
        event_payload = None

        if isinstance(processed_event, tuple):
            if len(processed_event) == 2:
                # (stream_mode, payload) 형식
                stream_mode_label, event_payload = processed_event
            elif len(processed_event) == 3:
                # (node_path, stream_mode, payload) 형식
                node_path, stream_mode_label, event_payload = processed_event
        else:
            # 단일 값인 경우 values로 처리
            stream_mode_label = "values"
            event_payload = processed_event

        # stream_mode에 따라 저장 형식 결정 및 저장
        if stream_mode_label == "messages":
            # 메시지 청크 스트리밍 (LLM 응답 등)
            await store_sse_event(
                run_id,
                event_id,
                "messages",
                {
                    "type": "messages_stream",
                    "message_chunk": event_payload[0]
                    if isinstance(event_payload, tuple) and len(event_payload) >= 1
                    else event_payload,
                    "metadata": event_payload[1]
                    if isinstance(event_payload, tuple) and len(event_payload) >= 2
                    else None,
                    "node_path": node_path,
                },
            )
        elif stream_mode_label == "values" or stream_mode_label == "updates":
            # 그래프 상태 값 또는 업데이트
            await store_sse_event(
                run_id,
                event_id,
                "values",
                {"type": "execution_values", "chunk": event_payload},
            )
        elif stream_mode_label == "end":
            # 실행 완료 시그널
            payload_dict = event_payload if isinstance(event_payload, dict) else {}
            await store_sse_event(
                run_id,
                event_id,
                "end",
                {
                    "type": "run_complete",
                    "status": payload_dict.get("status", "completed"),
                    "final_output": payload_dict.get("final_output"),
                },
            )
        # 필요 시 다른 stream_mode 추가 가능

    async def signal_run_cancelled(self, run_id: str) -> None:
        """실행 취소 시그널을 브로커에 전달하여 클라이언트에게 알림

        실행이 취소되었을 때 호출되어 모든 연결된 클라이언트에게 취소 이벤트를 전송하고
        브로커를 정리합니다.

        동작 흐름:
        1. 이벤트 카운터 증가 (새로운 시퀀스 번호 생성)
        2. 취소 이벤트 ID 생성
        3. 브로커에 "end" 이벤트 전달 (status: cancelled)
        4. 브로커 정리 (더 이상 이벤트 없음)

        Args:
            run_id (str): 실행 고유 식별자

        참고:
            - 이 메서드는 cancel_run()에서 호출됨
            - 브로커 정리 후 클라이언트는 재연결 불가
        """
        counter = self.event_counters.get(run_id, 0) + 1
        self.event_counters[run_id] = counter
        event_id = generate_event_id(run_id, counter)

        broker = broker_manager.get_or_create_broker(run_id)
        if broker:
            await broker.put(event_id, ("end", {"status": "cancelled"}))

        broker_manager.cleanup_broker(run_id)

    async def signal_run_error(self, run_id: str, error_message: str) -> None:
        """실행 에러 시그널을 브로커에 전달하여 클라이언트에게 알림

        실행 중 오류가 발생했을 때 호출되어 모든 연결된 클라이언트에게 에러 이벤트를 전송하고
        브로커를 정리합니다.

        동작 흐름:
        1. 이벤트 카운터 증가 (새로운 시퀀스 번호 생성)
        2. 에러 이벤트 ID 생성
        3. 브로커에 "end" 이벤트 전달 (status: failed, error 메시지 포함)
        4. 브로커 정리

        Args:
            run_id (str): 실행 고유 식별자
            error_message (str): 에러 메시지 (클라이언트에게 전달됨)

        참고:
            - 이 메서드는 execute_run_async()의 예외 처리에서 호출됨
            - interrupt_run()에서도 호출됨 (인터럽트를 에러로 처리)
        """
        counter = self.event_counters.get(run_id, 0) + 1
        self.event_counters[run_id] = counter
        event_id = generate_event_id(run_id, counter)

        broker = broker_manager.get_or_create_broker(run_id)
        if broker:
            await broker.put(event_id, ("end", {"status": "failed", "error": error_message}))

        broker_manager.cleanup_broker(run_id)

    def _extract_event_sequence(self, event_id: str) -> int:
        """event_id에서 시퀀스 번호 추출

        이벤트 ID 형식: {run_id}_event_{sequence}
        예: "run_abc123_event_42" → 42

        Args:
            event_id (str): 이벤트 고유 식별자

        Returns:
            int: 추출된 시퀀스 번호
        """
        return extract_event_sequence(event_id)

    async def stream_run_execution(
        self,
        run: Run,
        last_event_id: str | None = None,
        cancel_on_disconnect: bool = False,
    ) -> AsyncIterator[str]:
        """실행 이벤트를 SSE로 스트리밍 (재연결 지원 포함)

        이 메서드는 LangGraph 실행의 모든 이벤트를 SSE(Server-Sent Events)로 스트리밍합니다.
        프로듀서-컨슈머 패턴의 컨슈머 역할을 수행하며, 재연결 시 이벤트 재생을 지원합니다.

        동작 흐름:
        1. 메타데이터 이벤트 전송 (시퀀스 0, 첫 연결 시에만)
        2. 저장된 이벤트 재생 (last_event_id 이후 이벤트)
        3. 라이브 이벤트 스트리밍 (브로커에서 실시간 수신)

        재연결 지원:
        - 클라이언트가 last_event_id를 제공하면 해당 이벤트 이후부터 재생
        - PostgreSQL에서 저장된 이벤트를 먼저 재생한 후 라이브 스트리밍
        - 중복 방지: 시퀀스 번호로 이미 전송된 이벤트 스킵

        Args:
            run (Run): 실행 객체 (run_id, status 등 포함)
            last_event_id (str | None): 마지막으로 수신한 이벤트 ID (재연결 시 제공)
            cancel_on_disconnect (bool): True이면 연결 끊김 시 실행 취소 (기본값: False)

        Yields:
            str: SSE 형식의 이벤트 문자열 (event: type\ndata: json\nid: id\n\n)

        Raises:
            asyncio.CancelledError: 스트리밍이 취소된 경우 (클라이언트 연결 끊김 등)

        참고:
            - FastAPI StreamingResponse와 함께 사용
            - 실행이 완료되어도 브로커가 finish될 때까지 대기
            - 에러 발생 시 에러 이벤트를 전송하고 스트리밍 종료
        """
        run_id = run.run_id
        try:
            # 메타데이터 이벤트 먼저 전송 (시퀀스 0, 저장소에 저장되지 않음)
            if not last_event_id:
                event_id = generate_event_id(run_id, 0)
                metadata_event = create_metadata_event(run_id, event_id)
                yield metadata_event

            # 저장된 이벤트 재생 (재연결 시 또는 첫 연결)
            last_sent_sequence = 0
            if last_event_id:
                last_sent_sequence = self._extract_event_sequence(last_event_id)

            async for sse_event in self._replay_stored_events(run_id, last_event_id):
                yield sse_event

            # 실행이 아직 활성 상태면 라이브 이벤트 스트리밍
            async for sse_event in self._stream_live_events(run, last_sent_sequence):
                yield sse_event

        except asyncio.CancelledError:
            logger.debug(f"Stream cancelled for run {run_id}")
            if cancel_on_disconnect:
                # 연결 끊김 시 백그라운드 실행 태스크도 취소
                self._cancel_background_task(run_id)
            raise
        except Exception as e:
            logger.error(f"Error in stream_run_execution for run {run_id}: {e}")
            yield create_error_event(str(e))

    async def _replay_stored_events(self, run_id: str, last_event_id: str | None) -> AsyncIterator[str]:
        """PostgreSQL에 저장된 이벤트를 재생 (재연결 지원)

        이 메서드는 PostgreSQL 이벤트 저장소에서 이벤트를 조회하여 클라이언트에게 재전송합니다.
        재연결 시 누락된 이벤트를 복구하는 핵심 기능입니다.

        동작 방식:
        1. last_event_id 제공 시: 해당 이벤트 이후 이벤트만 조회
        2. last_event_id 없으면: 모든 저장된 이벤트 조회 (첫 연결)
        3. 각 이벤트를 SSE 형식으로 변환하여 yield

        Args:
            run_id (str): 실행 고유 식별자
            last_event_id (str | None): 마지막으로 수신한 이벤트 ID (없으면 처음부터)

        Yields:
            str: SSE 형식의 이벤트 문자열

        참고:
            - event_store.get_events_since()는 시퀀스 번호 기반 범위 쿼리 수행
            - 저장된 이벤트는 시퀀스 순서대로 정렬되어 반환됨
        """
        if last_event_id:
            stored_events = await event_store.get_events_since(run_id, last_event_id)
        else:
            stored_events = await event_store.get_all_events(run_id)

        for ev in stored_events:
            sse_event = self._stored_event_to_sse(run_id, ev)
            if sse_event:
                yield sse_event

    async def _stream_live_events(self, run: Run, last_sent_sequence: int) -> AsyncIterator[str]:
        """브로커에서 라이브 이벤트를 스트리밍 (실시간 전송)

        이 메서드는 브로커 큐에서 실시간으로 이벤트를 수신하여 클라이언트에게 전송합니다.
        프로듀서-컨슈머 패턴의 컨슈머 역할을 수행합니다.

        동작 방식:
        1. 실행의 브로커 획득 (없으면 생성)
        2. 실행 완료 및 브로커 종료 여부 확인 (둘 다 true면 스트리밍 없음)
        3. 브로커에서 비동기 이터레이터로 이벤트 수신
        4. 중복 이벤트 스킵 (재생된 이벤트와 시퀀스 비교)
        5. 이벤트를 SSE 형식으로 변환하여 yield

        중복 방지:
        - last_sent_sequence와 비교하여 이미 전송된 이벤트 스킵
        - 재생 단계에서 전송된 이벤트를 다시 전송하지 않음

        Args:
            run (Run): 실행 객체 (상태 확인용)
            last_sent_sequence (int): 이미 전송된 마지막 시퀀스 번호

        Yields:
            str: SSE 형식의 이벤트 문자열

        참고:
            - broker.aiter()는 새 이벤트가 도착할 때까지 대기 (블로킹)
            - 브로커가 finish 시그널을 받으면 이터레이션 종료
        """
        run_id = run.run_id
        broker = broker_manager.get_or_create_broker(run_id)

        # 실행이 완료되고 브로커도 종료되었으면 스트리밍할 이벤트 없음
        if run.status in ["completed", "failed", "cancelled", "interrupted"] and broker.is_finished():
            return

        # 라이브 이벤트 스트리밍
        if broker:
            async for event_id, raw_event in broker.aiter():
                # 재생 단계에서 이미 전송된 이벤트는 스킵 (중복 방지)
                current_sequence = self._extract_event_sequence(event_id)
                if current_sequence <= last_sent_sequence:
                    continue

                sse_event = await self._convert_raw_to_sse(event_id, raw_event)
                if sse_event:
                    yield sse_event
                    last_sent_sequence = current_sequence

    def _cancel_background_task(self, run_id: str) -> None:
        """클라이언트 연결 끊김 시 백그라운드 실행 태스크 취소

        이 메서드는 cancel_on_disconnect=True일 때 클라이언트가 연결을 끊으면
        해당 실행의 백그라운드 태스크를 취소합니다.

        동작 흐름:
        1. active_runs 딕셔너리에서 실행 태스크 조회
        2. 태스크가 존재하고 아직 완료되지 않았으면 취소
        3. 실패 시 경고 로그 출력 (치명적 오류 아님)

        Args:
            run_id (str): 실행 고유 식별자

        참고:
            - active_runs는 api.runs 모듈에서 관리하는 전역 딕셔너리
            - task.cancel()은 asyncio.CancelledError를 발생시킴
            - execute_run_async()가 CancelledError를 처리하여 정리 작업 수행
        """
        try:
            from ..api.runs import active_runs

            task = active_runs.get(run_id)
            if task and not task.done():
                task.cancel()
        except Exception as e:
            logger.warning(f"Failed to cancel background task for run {run_id} on disconnect: {e}")

    async def _convert_raw_to_sse(self, event_id: str, raw_event: Any) -> str | None:
        """브로커에서 받은 원시 이벤트를 SSE 형식으로 변환

        이 메서드는 EventConverter를 사용하여 LangGraph 이벤트를 Agent Protocol SSE 형식으로 변환합니다.

        Args:
            event_id (str): 이벤트 고유 식별자
            raw_event (Any): 브로커에서 받은 원시 이벤트 (tuple 또는 dict)

        Returns:
            str | None: SSE 형식 문자열 또는 None (변환 실패 시)
        """
        return self.event_converter.convert_raw_to_sse(event_id, raw_event)

    async def interrupt_run(self, run_id: str) -> bool:
        """실행 인터럽트 (강제 중단)

        실행 중인 그래프를 인터럽트하여 중단시킵니다.
        주로 관리자 또는 긴급 중단이 필요한 경우 사용됩니다.

        동작 흐름:
        1. 에러 시그널 전송 ("Run was interrupted")
        2. 실행 상태를 "interrupted"로 업데이트
        3. 성공 여부 반환

        Args:
            run_id (str): 실행 고유 식별자

        Returns:
            bool: 인터럽트 성공 시 True, 실패 시 False

        참고:
            - signal_run_error()를 사용하여 에러 이벤트로 처리
            - LangGraph의 interrupt()와는 다른 개념 (이건 강제 중단)
        """
        try:
            await self.signal_run_error(run_id, "Run was interrupted")
            await self._update_run_status(run_id, "interrupted")
            return True
        except Exception as e:
            logger.error(f"Error interrupting run {run_id}: {e}")
            return False

    async def cancel_run(self, run_id: str) -> bool:
        """실행 취소 (대기 중이거나 실행 중인 작업)

        대기 중이거나 실행 중인 그래프 작업을 취소합니다.
        클라이언트가 명시적으로 취소를 요청한 경우 호출됩니다.

        동작 흐름:
        1. 취소 시그널 전송 (브로커에 "end" 이벤트)
        2. 실행 상태를 "cancelled"로 업데이트
        3. 성공 여부 반환

        Args:
            run_id (str): 실행 고유 식별자

        Returns:
            bool: 취소 성공 시 True, 실패 시 False

        참고:
            - signal_run_cancelled()가 브로커 정리 수행
            - 이미 완료된 실행도 취소 가능 (상태만 업데이트)
        """
        try:
            await self.signal_run_cancelled(run_id)
            await self._update_run_status(run_id, "cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling run {run_id}: {e}")
            return False

    async def _update_run_status(
        self,
        run_id: str,
        status: str,
        output: Any | None = None,
        error: str | None = None,
    ) -> None:
        """데이터베이스의 실행 상태 업데이트 (공유 업데이터 사용)

        이 메서드는 Run ORM 모델의 상태를 업데이트합니다.
        순환 import를 방지하기 위해 lazy import를 사용합니다.

        Args:
            run_id (str): 실행 고유 식별자
            status (str): 새 실행 상태 ("running", "completed", "failed", "cancelled", "interrupted")
            output (Any | None): 실행 출력 (완료 시 제공)
            error (str | None): 에러 메시지 (실패 시 제공)

        참고:
            - api.runs.update_run_status()를 사용하여 데이터베이스 업데이트
            - 이 메서드는 내부용으로 interrupt_run, cancel_run에서 호출됨
        """
        try:
            # 순환 import 방지를 위한 lazy import
            from ..api.runs import update_run_status

            await update_run_status(run_id, status, output, error)
        except Exception as e:
            logger.error(f"Error updating run status for {run_id}: {e}")

    def is_run_streaming(self, run_id: str) -> bool:
        """실행이 현재 스트리밍 중인지 확인 (브로커 활성 상태)

        이 메서드는 실행에 활성 브로커가 있고 아직 종료되지 않았는지 확인합니다.
        클라이언트가 스트리밍을 받을 수 있는 상태인지 판단하는데 사용됩니다.

        Args:
            run_id (str): 실행 고유 식별자

        Returns:
            bool: 스트리밍 중이면 True, 아니면 False

        참고:
            - 브로커가 없거나 finish() 호출된 경우 False 반환
            - 실행 완료 후에도 브로커가 finish되지 않았으면 True (마지막 이벤트 전송 중)
        """
        broker = broker_manager.get_broker(run_id)
        return broker is not None and not broker.is_finished()

    async def cleanup_run(self, run_id: str) -> None:
        """실행의 스트리밍 리소스 정리

        실행이 완료되거나 취소된 후 브로커 등 스트리밍 관련 리소스를 정리합니다.
        메모리 누수 방지를 위해 필요합니다.

        Args:
            run_id (str): 실행 고유 식별자

        참고:
            - broker_manager.cleanup_broker()가 브로커 인스턴스 제거
            - 이벤트 카운터는 메모리에 유지 (작은 용량)
            - PostgreSQL 저장된 이벤트는 cleanup_old_events()가 주기적으로 정리
        """
        broker_manager.cleanup_broker(run_id)

    def _stored_event_to_sse(self, run_id: str, ev: Any) -> str | None:
        """PostgreSQL에 저장된 이벤트 객체를 SSE 문자열로 변환

        이 메서드는 event_store에서 조회한 이벤트 객체를 SSE 형식으로 변환합니다.
        재생 로직에서 사용됩니다.

        Args:
            run_id (str): 실행 고유 식별자
            ev: 저장된 이벤트 객체 (event_store에서 반환)

        Returns:
            str | None: SSE 형식 문자열 또는 None (변환 실패 시)

        참고:
            - EventConverter.convert_stored_to_sse()를 사용하여 변환
            - 원시 이벤트 변환과는 다른 메서드 사용 (저장 형식이 다름)
        """
        return self.event_converter.convert_stored_to_sse(ev, run_id)


# ---------------------------------------------------------------------------
# 전역 스트리밍 서비스 인스턴스 (싱글톤 패턴)
# ---------------------------------------------------------------------------
# 애플리케이션 전체에서 이 인스턴스를 사용하여 SSE 스트리밍을 관리합니다
streaming_service = StreamingService()
