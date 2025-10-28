"""실행별 이벤트 큐 관리를 위한 메시지 브로커

이 모듈은 LangGraph 실행 이벤트의 Producer-Consumer 패턴을 구현합니다.
각 실행(Run)마다 독립적인 이벤트 큐를 관리하여 여러 클라이언트가 동시에
실시간 스트리밍을 받을 수 있도록 합니다.

주요 구성 요소:
• RunBroker - 단일 실행의 이벤트 큐 및 분배 관리
• BrokerManager - 여러 RunBroker 인스턴스 생명주기 관리
• broker_manager - 전역 싱글톤 인스턴스

사용 예:
    from services.broker import broker_manager

    # Producer: 이벤트 전송
    broker = broker_manager.get_or_create_broker(run_id)
    await broker.put(event_id, payload)

    # Consumer: 이벤트 수신
    async for event_id, payload in broker.aiter():
        print(f"Received: {event_id}")
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any

from .base_broker import BaseBrokerManager, BaseRunBroker

logger = logging.getLogger(__name__)


class RunBroker(BaseRunBroker):
    """특정 실행의 이벤트 큐 및 분배 관리자

    단일 LangGraph 실행에 대한 이벤트 브로커입니다.
    Producer(실행 엔진)가 이벤트를 put()으로 전송하면
    여러 Consumer(SSE 스트림)가 aiter()로 동일한 이벤트를 수신합니다.

    주요 기능:
    - asyncio.Queue 기반 이벤트 큐잉
    - 여러 Consumer 간 이벤트 브로드캐스트 (현재는 단일 Consumer)
    - 실행 완료 감지 및 자동 정리
    - 브로커 생성 시간 추적 (자동 정리용)

    사용 패턴:
    - Producer: execute_run_async()에서 이벤트 전송
    - Consumer: streaming_service.stream_run_execution()에서 수신
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self.finished = asyncio.Event()  # 실행 완료 플래그
        self._created_at = asyncio.get_event_loop().time()  # 생성 시간 (초 단위)

    async def put(self, event_id: str, payload: Any) -> None:
        """이벤트를 브로커 큐에 추가 (Producer 역할)

        LangGraph 실행 엔진이 생성한 이벤트를 큐에 넣습니다.
        Consumer(SSE 스트림)는 aiter()를 통해 이 이벤트를 받게 됩니다.

        Args:
            event_id (str): 이벤트 고유 식별자 (UUID)
            payload (Any): 이벤트 페이로드 (event_type, data 등)

        참고:
            - 실행이 이미 완료된 브로커에는 이벤트를 추가할 수 없습니다
            - "end" 이벤트가 전송되면 브로커를 자동으로 완료 상태로 전환합니다
        """
        if self.finished.is_set():
            logger.warning(f"Attempted to put event {event_id} into finished broker for run {self.run_id}")
            return

        await self.queue.put((event_id, payload))

        # "end" 이벤트 감지 시 브로커 완료 처리
        # payload는 (event_type, data) 형식의 튜플
        if isinstance(payload, tuple) and len(payload) >= 1 and payload[0] == "end":
            self.mark_finished()

    async def aiter(self) -> AsyncIterator[tuple[str, Any]]:
        """이벤트를 비동기 이터레이터로 순회 (Consumer 역할)

        SSE 스트림이 이 메서드를 호출하여 큐에서 이벤트를 하나씩 받아갑니다.
        큐가 비어있으면 새 이벤트가 도착할 때까지 대기합니다.

        동작 흐름:
        1. queue.get()으로 이벤트 대기 (타임아웃 0.1초)
        2. 이벤트 수신 시 (event_id, payload) 튜플 반환
        3. "end" 이벤트 수신 시 이터레이션 종료
        4. 타임아웃 시 실행 완료 여부 확인 후 계속 대기 또는 종료

        Yields:
            tuple[str, Any]: (event_id, payload) 쌍

        참고:
            - 타임아웃을 사용하여 주기적으로 실행 완료 상태를 확인합니다
            - "end" 이벤트를 받으면 즉시 이터레이션을 종료합니다
            - 실행이 완료되고 큐가 비어있으면 이터레이션을 종료합니다
        """
        while True:
            try:
                # 타임아웃을 사용하여 주기적으로 실행 완료 여부 확인
                event_id, payload = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                yield event_id, payload

                # "end" 이벤트 감지 시 즉시 종료
                if isinstance(payload, tuple) and len(payload) >= 1 and payload[0] == "end":
                    break

            except TimeoutError:
                # 실행이 완료되고 큐가 비어있으면 이터레이션 종료
                if self.finished.is_set() and self.queue.empty():
                    break
                continue

    def mark_finished(self) -> None:
        """브로커를 완료 상태로 표시

        실행이 종료되었음을 표시합니다.
        이후 aiter()는 큐의 남은 이벤트를 모두 소비한 후 종료됩니다.

        참고:
            - "end" 이벤트 수신 시 자동으로 호출됩니다
            - 수동으로 호출하여 브로커를 강제 종료할 수도 있습니다
        """
        self.finished.set()
        logger.debug(f"Broker for run {self.run_id} marked as finished")

    def is_finished(self) -> bool:
        """브로커가 완료 상태인지 확인

        Returns:
            bool: 완료 상태이면 True, 아니면 False
        """
        return self.finished.is_set()

    def is_empty(self) -> bool:
        """큐가 비어있는지 확인

        Returns:
            bool: 큐가 비어있으면 True, 아니면 False
        """
        return self.queue.empty()

    def get_age(self) -> float:
        """브로커의 생성 후 경과 시간 반환

        자동 정리 작업에서 오래된 브로커를 식별하는 데 사용됩니다.

        Returns:
            float: 브로커 생성 후 경과 시간 (초 단위)
        """
        return asyncio.get_event_loop().time() - self._created_at


class BrokerManager(BaseBrokerManager):
    """여러 RunBroker 인스턴스의 생명주기 관리자

    이 클래스는 애플리케이션의 모든 실행(Run)에 대한 브로커를 관리합니다.
    각 실행마다 독립적인 RunBroker를 생성하고 추적합니다.

    주요 기능:
    - 실행별 브로커 생성 및 조회
    - 완료된 브로커 자동 정리
    - 백그라운드 정리 작업 관리
    - 메모리 누수 방지 (오래된 브로커 삭제)

    사용 패턴:
    - 싱글톤 인스턴스: broker_manager
    - FastAPI lifespan에서 정리 작업 시작/중지
    - 실행 생성 시 get_or_create_broker() 호출
    """

    def __init__(self) -> None:
        self._brokers: dict[str, RunBroker] = {}  # run_id -> RunBroker 매핑
        self._cleanup_task: asyncio.Task | None = None  # 백그라운드 정리 작업

    def get_or_create_broker(self, run_id: str) -> RunBroker:
        """실행에 대한 브로커를 조회하거나 새로 생성

        지정된 run_id에 대한 브로커가 없으면 새로 생성합니다.
        이미 존재하면 기존 브로커를 반환합니다.

        Args:
            run_id (str): 실행 고유 식별자

        Returns:
            RunBroker: 해당 실행의 브로커 인스턴스
        """
        if run_id not in self._brokers:
            self._brokers[run_id] = RunBroker(run_id)
            logger.debug(f"Created new broker for run {run_id}")
        return self._brokers[run_id]

    def get_broker(self, run_id: str) -> RunBroker | None:
        """기존 브로커를 조회 (없으면 None 반환)

        Args:
            run_id (str): 실행 고유 식별자

        Returns:
            RunBroker | None: 브로커 인스턴스 또는 None
        """
        return self._brokers.get(run_id)

    def cleanup_broker(self, run_id: str) -> None:
        """브로커를 정리 대상으로 표시

        브로커를 완료 상태로 표시하지만 즉시 삭제하지는 않습니다.
        Consumer가 아직 큐에서 이벤트를 소비 중일 수 있기 때문입니다.

        Args:
            run_id (str): 실행 고유 식별자

        참고:
            - 브로커를 즉시 삭제하지 않고 mark_finished()만 호출합니다
            - 실제 삭제는 백그라운드 정리 작업에서 처리합니다
        """
        if run_id in self._brokers:
            self._brokers[run_id].mark_finished()
            # Consumer가 아직 읽고 있을 수 있으므로 즉시 삭제하지 않음
            logger.debug(f"Marked broker for run {run_id} for cleanup")

    def remove_broker(self, run_id: str) -> None:
        """브로커를 완전히 제거

        브로커를 완료 상태로 표시하고 딕셔너리에서 삭제합니다.
        메모리를 즉시 해제해야 하는 경우에 사용합니다.

        Args:
            run_id (str): 실행 고유 식별자
        """
        if run_id in self._brokers:
            self._brokers[run_id].mark_finished()
            del self._brokers[run_id]
            logger.debug(f"Removed broker for run {run_id}")

    async def start_cleanup_task(self) -> None:
        """오래된 브로커를 정리하는 백그라운드 작업 시작

        FastAPI 앱 시작 시 lifespan에서 호출됩니다.
        백그라운드 작업을 생성하여 주기적으로 완료된 브로커를 정리합니다.

        참고:
            - 작업이 이미 실행 중이거나 완료되지 않았으면 새로 생성하지 않습니다
        """
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_old_brokers())

    async def stop_cleanup_task(self) -> None:
        """백그라운드 정리 작업 중지

        FastAPI 앱 종료 시 lifespan에서 호출됩니다.
        실행 중인 정리 작업을 취소하고 완료를 대기합니다.

        참고:
            - CancelledError는 자동으로 무시됩니다 (정상적인 종료)
        """
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

    async def _cleanup_old_brokers(self) -> None:
        """오래된 완료 브로커를 정리하는 백그라운드 작업

        5분마다 실행되며 다음 조건을 만족하는 브로커를 삭제합니다:
        1. 실행이 완료됨 (finished 플래그가 설정됨)
        2. 큐가 비어있음 (모든 이벤트가 소비됨)
        3. 생성된 지 1시간 이상 경과

        동작 흐름:
        1. 5분마다 모든 브로커를 순회
        2. 정리 조건을 만족하는 브로커 식별
        3. 식별된 브로커를 메모리에서 제거
        4. 오류 발생 시 로그 기록 후 계속 실행

        참고:
            - 이 작업은 애플리케이션이 실행되는 동안 계속 실행됩니다
            - CancelledError는 정상적인 종료로 간주됩니다
        """
        while True:
            try:
                await asyncio.sleep(300)  # 5분마다 확인

                asyncio.get_event_loop().time()
                to_remove = []

                for run_id, broker in self._brokers.items():
                    # 완료되고, 비어있고, 1시간 이상 경과한 브로커 삭제
                    if (
                        broker.is_finished()
                        and broker.is_empty()
                        and broker.get_age() > 3600  # 1시간 = 3600초
                    ):
                        to_remove.append(run_id)

                for run_id in to_remove:
                    self.remove_broker(run_id)
                    logger.info(f"Cleaned up old broker for run {run_id}")

            except asyncio.CancelledError:
                # 정상적인 종료 시그널
                break
            except Exception as e:
                logger.error(f"Error in broker cleanup task: {e}")


# 전역 브로커 관리자 인스턴스 (싱글톤 패턴)
# 애플리케이션 전체에서 이 인스턴스를 사용하여 실행별 브로커에 접근합니다
broker_manager = BrokerManager()
