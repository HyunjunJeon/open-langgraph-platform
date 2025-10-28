"""SSE 재생 기능을 위한 PostgreSQL 기반 영속적 이벤트 저장소

이 모듈은 Server-Sent Events(SSE) 스트리밍 중 발생한 모든 이벤트를
PostgreSQL 데이터베이스에 저장하여 재생 기능을 제공합니다.
클라이언트가 연결이 끊겼다가 재연결하면 저장된 이벤트를 순차적으로 다시 받을 수 있습니다.

주요 구성 요소:
• EventStore - PostgreSQL 백엔드 이벤트 저장소 (싱글톤)
• store_sse_event() - SSE 이벤트 저장 헬퍼 함수
• event_store - 전역 EventStore 인스턴스

사용 예:
    from ...services.event_store import event_store, store_sse_event

    # 이벤트 저장
    await store_sse_event(run_id, event_id, "values", {"key": "value"})

    # 특정 시점 이후 이벤트 조회 (재연결 시)
    events = await event_store.get_events_since(run_id, last_event_id)

    # 정리 작업 시작/중지
    await event_store.start_cleanup_task()
    await event_store.stop_cleanup_task()
"""

import asyncio
import contextlib
import json
from datetime import UTC, datetime

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from ..core.database import db_manager
from ..core.serializers import GeneralSerializer
from ..core.sse import SSEEvent


class EventStore:
    """PostgreSQL 기반 SSE 이벤트 저장소

    이 클래스는 실행(run) 중 발생한 모든 SSE 이벤트를 PostgreSQL에 저장하고,
    재연결 시 특정 시점 이후의 이벤트를 재생할 수 있는 기능을 제공합니다.
    또한 오래된 이벤트를 주기적으로 정리하는 백그라운드 작업을 관리합니다.

    주요 기능:
    - 이벤트 저장: store_event()로 SSE 이벤트를 시퀀스 번호와 함께 저장
    - 이벤트 재생: get_events_since()로 특정 시점 이후 이벤트 조회
    - 자동 정리: 1시간 이상 된 이벤트를 300초마다 자동 삭제
    - 실행 정보: get_run_info()로 이벤트 카운트, 마지막 이벤트 조회

    데이터베이스 스키마:
    - 테이블: run_events
    - 주요 컬럼: id, run_id, seq, event, data (JSONB), created_at
    - 인덱스: run_id, (run_id, seq) 복합 인덱스

    정리 정책:
    - 정리 주기: 300초 (5분)
    - 보존 기간: 1시간
    - 백그라운드 작업: asyncio.Task로 실행

    사용 패턴:
    - 싱글톤 인스턴스: event_store
    - lifespan에서 start_cleanup_task() 호출하여 정리 작업 시작
    """

    CLEANUP_INTERVAL = 300  # 초 단위 (5분)

    def __init__(self) -> None:
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_task(self) -> None:
        """백그라운드 정리 작업 시작

        이 메서드는 오래된 이벤트를 주기적으로 삭제하는 백그라운드 작업을 시작합니다.
        작업이 이미 실행 중이면 새로운 작업을 생성하지 않습니다.

        동작:
        - 정리 작업이 없거나 완료된 경우에만 새 작업 생성
        - asyncio.create_task()로 백그라운드에서 _cleanup_loop() 실행
        - FastAPI lifespan 시작 시 호출됨

        참고:
            이 메서드는 FastAPI의 lifespan 이벤트에서 자동으로 호출됩니다.
        """
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """백그라운드 정리 작업 중지

        이 메서드는 실행 중인 정리 작업을 안전하게 취소하고 종료를 기다립니다.
        CancelledError는 자동으로 무시됩니다.

        동작:
        1. 작업이 실행 중인지 확인
        2. 작업 취소 요청 (task.cancel())
        3. 취소 완료까지 대기 (CancelledError 무시)

        참고:
            이 메서드는 FastAPI의 lifespan 종료 시 자동으로 호출됩니다.
        """
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

    async def store_event(self, run_id: str, event: SSEEvent) -> None:
        """SSE 이벤트를 시퀀스 번호와 함께 PostgreSQL에 저장

        이 메서드는 SSE 이벤트를 run_events 테이블에 저장합니다.
        이벤트 ID에서 시퀀스 번호를 추출하여 정렬 가능하도록 합니다.

        이벤트 ID 형식:
        - 예상 형식: "{run_id}_event_{seq}"
        - 예시: "abc123_event_0", "abc123_event_1"
        - seq 추출 실패 시 기본값 0 사용

        동작:
        1. event.id에서 시퀀스 번호 추출
        2. PostgreSQL 연결 획득
        3. INSERT 쿼리 실행 (충돌 시 무시)
        4. data는 JSONB 타입으로 저장

        Args:
            run_id (str): 실행 고유 식별자
            event (SSEEvent): 저장할 SSE 이벤트 (id, event, data, timestamp)

        참고:
            - ON CONFLICT DO NOTHING으로 중복 삽입 방지
            - created_at은 DB에서 NOW()로 자동 설정
        """
        # 이벤트 ID에서 시퀀스 번호 추출 (형식: {run_id}_event_{seq})
        try:
            seq = int(str(event.id).split("_event_")[-1])
        except Exception:
            seq = 0

        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            stmt = text(
                """
                INSERT INTO run_events (id, run_id, seq, event, data, created_at)
                VALUES (:id, :run_id, :seq, :event, :data, NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ).bindparams(bindparam("data", type_=JSONB))
            await conn.execute(
                stmt,
                {
                    "id": event.id,
                    "run_id": run_id,
                    "seq": seq,
                    "event": event.event,
                    "data": event.data,
                },
            )

    async def get_events_since(self, run_id: str, last_event_id: str) -> list[SSEEvent]:
        """특정 이벤트 이후의 모든 이벤트 조회 (재연결 시 재생용)

        이 메서드는 클라이언트가 재연결할 때 마지막으로 받은 이벤트 이후의
        모든 이벤트를 시퀀스 순서대로 반환합니다.

        동작:
        1. last_event_id에서 시퀀스 번호 추출
        2. 해당 시퀀스보다 큰 모든 이벤트 조회
        3. seq ASC로 정렬하여 순차 재생 보장

        Args:
            run_id (str): 실행 고유 식별자
            last_event_id (str): 마지막으로 받은 이벤트 ID (형식: "{run_id}_event_{seq}")

        Returns:
            list[SSEEvent]: 시퀀스 순으로 정렬된 이벤트 목록

        참고:
            - last_event_id 파싱 실패 시 last_seq = -1 (모든 이벤트 반환)
            - SSE Last-Event-ID 헤더와 함께 사용됨
        """
        # 마지막 이벤트 ID에서 시퀀스 번호 추출
        try:
            last_seq = int(str(last_event_id).split("_event_")[-1])
        except Exception:
            last_seq = -1  # 파싱 실패 시 모든 이벤트 반환

        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            rs = await conn.execute(
                text(
                    """
                    SELECT id, event, data, created_at
                    FROM run_events
                    WHERE run_id = :run_id AND seq > :last_seq
                    ORDER BY seq ASC
                    """
                ),
                {"run_id": run_id, "last_seq": last_seq},
            )
            rows = rs.fetchall()
        return [SSEEvent(id=r.id, event=r.event, data=r.data, timestamp=r.created_at) for r in rows]

    async def get_all_events(self, run_id: str) -> list[SSEEvent]:
        """특정 실행의 모든 이벤트 조회 (전체 재생용)

        이 메서드는 특정 실행에 대한 모든 이벤트를 시퀀스 순서대로 반환합니다.
        처음부터 전체 이벤트 스트림을 재생하거나 디버깅 시 사용됩니다.

        Args:
            run_id (str): 실행 고유 식별자

        Returns:
            list[SSEEvent]: 시퀀스 순으로 정렬된 모든 이벤트

        참고:
            - seq ASC 정렬로 발생 순서대로 반환
            - 클라이언트가 Last-Event-ID 없이 연결할 때 사용됨
        """
        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            rs = await conn.execute(
                text(
                    """
                    SELECT id, event, data, created_at
                    FROM run_events
                    WHERE run_id = :run_id
                    ORDER BY seq ASC
                    """
                ),
                {"run_id": run_id},
            )
            rows = rs.fetchall()
        return [SSEEvent(id=r.id, event=r.event, data=r.data, timestamp=r.created_at) for r in rows]

    async def cleanup_events(self, run_id: str) -> None:
        """특정 실행의 모든 이벤트 삭제

        이 메서드는 특정 실행에 대한 모든 저장된 이벤트를 데이터베이스에서 삭제합니다.
        실행이 완료되거나 더 이상 재생이 필요 없을 때 수동으로 정리할 수 있습니다.

        Args:
            run_id (str): 삭제할 실행 고유 식별자

        참고:
            - 자동 정리는 _cleanup_old_runs()에서 시간 기반으로 처리됨
            - 이 메서드는 수동 정리용 (실행 종료 후 즉시 삭제 등)
        """
        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM run_events WHERE run_id = :run_id"),
                {"run_id": run_id},
            )

    async def get_run_info(self, run_id: str) -> dict | None:
        """특정 실행의 이벤트 통계 정보 조회

        이 메서드는 실행에 대한 이벤트 메타데이터를 반환합니다.
        이벤트 카운트, 마지막 이벤트 ID 및 타임스탬프 등을 제공합니다.

        동작:
        1. MIN(seq), MAX(seq)로 첫/마지막 시퀀스 조회
        2. 마지막 이벤트의 ID와 created_at 조회
        3. 이벤트 개수 계산 (last_seq - first_seq + 1)

        Args:
            run_id (str): 실행 고유 식별자

        Returns:
            dict | None: 이벤트 통계 정보 딕셔너리 또는 None (이벤트 없을 시)
                - run_id: 실행 ID
                - event_count: 총 이벤트 개수
                - first_event_time: 첫 이벤트 시간 (현재는 None)
                - last_event_time: 마지막 이벤트 생성 시간
                - last_event_id: 마지막 이벤트 ID

        참고:
            - 이벤트가 없으면 None 반환
            - 클라이언트 상태 동기화 및 디버깅에 유용
        """
        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            # 첫 번째/마지막 시퀀스 번호 조회
            rs = await conn.execute(
                text(
                    """
                    SELECT MIN(seq) AS first_seq, MAX(seq) AS last_seq
                    FROM run_events
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id},
            )
            row = rs.fetchone()
            if not row or row.last_seq is None:
                return None

            # 마지막 이벤트의 ID와 생성 시간 조회
            rs2 = await conn.execute(
                text(
                    """
                    SELECT id, created_at
                    FROM run_events
                    WHERE run_id = :run_id AND seq = :last_seq
                    LIMIT 1
                    """
                ),
                {"run_id": run_id, "last_seq": row.last_seq},
            )
            last = rs2.fetchone()
        return {
            "run_id": run_id,
            "event_count": int(row.last_seq) - int(row.first_seq) + 1 if row.first_seq is not None else 0,
            "first_event_time": None,
            "last_event_time": last.created_at if last else None,
            "last_event_id": last.id if last else None,
        }

    async def _cleanup_loop(self) -> None:
        """정리 작업 백그라운드 루프 (내부 메서드)

        이 메서드는 무한 루프를 실행하며 CLEANUP_INTERVAL(300초)마다
        오래된 이벤트를 삭제하는 _cleanup_old_runs()를 호출합니다.

        동작:
        1. CLEANUP_INTERVAL(300초) 대기
        2. _cleanup_old_runs() 호출 (1시간 이상 된 이벤트 삭제)
        3. 1번으로 돌아가서 반복

        예외 처리:
        - CancelledError: 정상 종료 (stop_cleanup_task() 호출 시)
        - Exception: 오류 로그 출력 후 계속 실행

        참고:
            - 이 메서드는 start_cleanup_task()에서 asyncio.Task로 실행됨
            - 정리 실패 시에도 루프는 계속 실행 (서비스 안정성)
        """
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL)  # 300초 대기
                await self._cleanup_old_runs()
            except asyncio.CancelledError:
                break  # 정상 종료
            except Exception as e:
                print(f"Error in event store cleanup: {e}")

    async def _cleanup_old_runs(self) -> None:
        """1시간 이상 된 오래된 이벤트 삭제 (내부 메서드)

        이 메서드는 생성된 지 1시간 이상 경과한 모든 이벤트를 삭제합니다.
        디스크 공간 절약 및 데이터베이스 성능 유지를 위해 주기적으로 호출됩니다.

        삭제 조건:
        - created_at < NOW() - INTERVAL '1 hour'
        - 즉, 현재 시간 기준 1시간 이전에 생성된 모든 이벤트

        참고:
            - _cleanup_loop()에서 300초(5분)마다 호출됨
            - 기본 보존 기간: 1시간
            - PostgreSQL INTERVAL 문법 사용
        """
        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM run_events WHERE created_at < NOW() - INTERVAL '1 hour'"))


# ---------------------------------------------------------------------------
# 전역 이벤트 저장소 인스턴스
# ---------------------------------------------------------------------------

event_store = EventStore()


async def store_sse_event(run_id: str, event_id: str, event_type: str, data: dict) -> SSEEvent:
    """SSE 이벤트를 직렬화하여 저장하는 헬퍼 함수

    이 함수는 SSE 이벤트 데이터를 JSONB 안전 형식으로 직렬화한 후
    PostgreSQL에 저장합니다. 복잡한 Python 객체를 JSON으로 변환하며,
    실패 시에도 실행을 중단하지 않도록 폴백 메커니즘을 제공합니다.

    동작 흐름:
    1. GeneralSerializer로 복잡한 객체 직렬화 (datetime, UUID 등)
    2. JSON 라운드트립으로 JSONB 호환성 보장
    3. 직렬화 실패 시 문자열로 변환하여 저장 (폴백)
    4. SSEEvent 객체 생성 (UTC 타임스탬프 포함)
    5. event_store.store_event() 호출하여 DB 저장

    Args:
        run_id (str): 실행 고유 식별자
        event_id (str): 이벤트 ID (형식: "{run_id}_event_{seq}")
        event_type (str): 이벤트 타입 ("values", "messages", "end" 등)
        data (dict): 이벤트 페이로드 (복잡한 객체 포함 가능)

    Returns:
        SSEEvent: 저장된 SSE 이벤트 객체

    참고:
        - GeneralSerializer는 datetime, UUID, Pydantic 모델 등을 처리
        - 직렬화 실패 시 {"raw": str(data)}로 저장하여 실행 중단 방지
        - streaming_service.py에서 주로 사용됨
    """
    serializer = GeneralSerializer()

    # 복잡한 객체를 JSONB 안전 형식으로 직렬화
    try:
        safe_data = json.loads(json.dumps(data, default=serializer.serialize))
    except Exception:
        # 직렬화 실패 시 문자열로 변환 (실행 중단 방지)
        safe_data = {"raw": str(data)}

    event = SSEEvent(id=event_id, event=event_type, data=safe_data, timestamp=datetime.now(UTC))
    await event_store.store_event(run_id, event)
    return event
