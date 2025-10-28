"""스레드 상태 변환 서비스

이 모듈은 LangGraph 체크포인터의 스냅샷을 Agent Protocol의 ThreadState 형식으로 변환합니다.
LangGraph의 상태 스냅샷을 클라이언트 친화적인 형식으로 제공하여 스레드 상태 조회를 지원합니다.

주요 구성 요소:
• ThreadStateService - 스냅샷 → ThreadState 변환 서비스
• LangGraphSerializer - 태스크 및 인터럽트 직렬화

사용 예:
    from services.thread_state_service import ThreadStateService

    service = ThreadStateService()
    thread_state = service.convert_snapshot_to_thread_state(snapshot, thread_id)
"""

import logging
from datetime import datetime
from typing import Any

from ..core.serializers import LangGraphSerializer
from ..models.threads import ThreadCheckpoint, ThreadState

logger = logging.getLogger(__name__)


class ThreadStateService:
    """LangGraph 스냅샷을 ThreadState 객체로 변환하는 서비스

    이 클래스는 LangGraph 체크포인터의 스냅샷을 Agent Protocol의 ThreadState로 변환합니다.
    스냅샷에는 그래프 실행 상태, 다음 실행할 노드, 태스크, 인터럽트 등이 포함됩니다.

    주요 기능:
    - 단일/다중 스냅샷을 ThreadState로 변환
    - 체크포인트 메타데이터 추출 및 변환
    - 태스크 및 인터럽트 직렬화
    - 타임스탬프 파싱 및 정규화

    사용 패턴:
    - 싱글톤 인스턴스로 사용 가능
    - LangGraphSerializer와 결합하여 상태 변환
    """

    def __init__(self) -> None:
        # LangGraph 전용 직렬화기 (태스크, 인터럽트 변환용)
        self.serializer = LangGraphSerializer()

    def convert_snapshot_to_thread_state(self, snapshot: Any, thread_id: str) -> ThreadState:
        """LangGraph 스냅샷을 ThreadState 형식으로 변환

        이 메서드는 LangGraph의 StateSnapshot을 Agent Protocol의 ThreadState로 변환합니다.
        스냅샷에서 상태 값, 다음 실행 노드, 메타데이터, 체크포인트 정보를 추출하여
        클라이언트가 이해할 수 있는 형식으로 제공합니다.

        변환 과정:
        1. 기본 값 추출: values, next, metadata, created_at
        2. 태스크/인터럽트: serializer로 직렬화
        3. 체크포인트 객체 생성: current, parent
        4. 하위 호환성: checkpoint_id 추출

        Args:
            snapshot (Any): LangGraph StateSnapshot 객체
            thread_id (str): 스레드 고유 식별자

        Returns:
            ThreadState: Agent Protocol 형식의 스레드 상태

        Raises:
            Exception: 스냅샷 변환 중 오류 발생 시

        참고:
            - 스냅샷은 LangGraph checkpointer.aget_tuple() 등에서 반환
            - ThreadState는 GET /threads/{thread_id}/state API에서 사용
        """
        try:
            # 기본 값 추출 (그래프 상태, 다음 노드, 메타데이터 등)
            values = getattr(snapshot, "values", {})
            next_nodes = getattr(snapshot, "next", []) or []
            metadata = getattr(snapshot, "metadata", {}) or {}
            created_at = self._extract_created_at(snapshot)

            # 태스크 및 인터럽트를 직렬화기로 추출 (클라이언트 친화적 형식으로 변환)
            tasks = self.serializer.extract_tasks_from_snapshot(snapshot)
            interrupts = self.serializer.extract_interrupts_from_snapshot(snapshot)

            # 체크포인트 객체 생성 (현재 상태와 부모 상태)
            current_checkpoint = self._create_checkpoint(snapshot.config, thread_id)
            parent_checkpoint = (
                self._create_checkpoint(snapshot.parent_config, thread_id) if snapshot.parent_config else None
            )

            # 하위 호환성을 위한 체크포인트 ID 추출 (문자열 형식)
            checkpoint_id = self._extract_checkpoint_id(snapshot.config)
            parent_checkpoint_id = (
                self._extract_checkpoint_id(snapshot.parent_config) if snapshot.parent_config else None
            )

            return ThreadState(
                values=values,
                next=next_nodes,
                tasks=tasks,
                interrupts=interrupts,
                metadata=metadata,
                created_at=created_at,
                checkpoint=current_checkpoint,
                parent_checkpoint=parent_checkpoint,
                checkpoint_id=checkpoint_id,
                parent_checkpoint_id=parent_checkpoint_id,
            )

        except Exception as e:
            logger.error(
                f"Failed to convert snapshot to thread state: {e} "
                f"(thread_id={thread_id}, snapshot_type={type(snapshot).__name__})"
            )
            raise

    def convert_snapshots_to_thread_states(self, snapshots: list[Any], thread_id: str) -> list[ThreadState]:
        """여러 스냅샷을 ThreadState 객체 목록으로 변환

        이 메서드는 체크포인트 히스토리(여러 시점의 스냅샷)를 ThreadState 목록으로 변환합니다.
        각 스냅샷을 개별적으로 변환하며, 일부 스냅샷 변환에 실패해도 나머지는 계속 처리합니다.

        사용 사례:
        - GET /threads/{thread_id}/history - 전체 실행 히스토리 조회
        - 시간 역순 체크포인트 목록 제공

        Args:
            snapshots (list[Any]): LangGraph 스냅샷 목록
            thread_id (str): 스레드 고유 식별자

        Returns:
            list[ThreadState]: 변환된 ThreadState 객체 목록

        참고:
            - 개별 스냅샷 변환 실패는 로그에 기록하고 스킵
            - 배치 처리 중 일부 실패가 전체를 중단하지 않음
            - 빈 리스트 반환 가능 (모든 변환 실패 시)
        """
        thread_states = []

        for i, snapshot in enumerate(snapshots):
            try:
                thread_state = self.convert_snapshot_to_thread_state(snapshot, thread_id)
                thread_states.append(thread_state)
            except Exception as e:
                logger.error(
                    f"Failed to convert snapshot in batch: {e} (thread_id={thread_id}, snapshot_index={i})"
                )
                # 개별 스냅샷 실패 시 전체 배치를 중단하지 않고 계속 진행
                continue

        return thread_states

    def _extract_created_at(self, snapshot: Any) -> datetime | None:
        """스냅샷에서 생성 타임스탬프 추출 및 파싱

        이 메서드는 스냅샷의 created_at 필드를 datetime 객체로 변환합니다.
        문자열(ISO 8601) 또는 datetime 객체 형식을 모두 처리합니다.

        Args:
            snapshot (Any): LangGraph StateSnapshot 객체

        Returns:
            datetime | None: 파싱된 datetime 객체 또는 None

        참고:
            - ISO 8601 형식 지원: "2025-10-27T12:00:00Z"
            - Z 접미사는 +00:00으로 변환 (UTC)
            - 파싱 실패 시 경고 로그 출력 후 None 반환
        """
        created_at = getattr(snapshot, "created_at", None)
        if isinstance(created_at, str):
            try:
                # ISO 8601 형식 파싱 (Z → +00:00 변환)
                return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Invalid created_at format: {created_at}")
                return None
        elif isinstance(created_at, datetime):
            # 이미 datetime 객체인 경우 그대로 반환
            return created_at
        return None

    def _create_checkpoint(self, config: Any, thread_id: str) -> ThreadCheckpoint:
        """LangGraph 설정에서 ThreadCheckpoint 객체 생성

        이 메서드는 LangGraph의 RunnableConfig에서 체크포인트 메타데이터를 추출하여
        Agent Protocol의 ThreadCheckpoint 객체를 생성합니다.

        Args:
            config (Any): LangGraph RunnableConfig 딕셔너리
            thread_id (str): 스레드 고유 식별자

        Returns:
            ThreadCheckpoint: 체크포인트 메타데이터 객체

        참고:
            - config.configurable.checkpoint_id: 체크포인트 고유 ID
            - config.configurable.checkpoint_ns: 체크포인트 네임스페이스 (subgraph용)
            - config가 없으면 빈 체크포인트 반환
        """
        if not config or not isinstance(config, dict):
            # 설정이 없으면 빈 체크포인트 반환
            return ThreadCheckpoint(checkpoint_id=None, thread_id=thread_id, checkpoint_ns="")

        # configurable 섹션에서 체크포인트 정보 추출
        configurable = config.get("configurable", {})
        checkpoint_id = configurable.get("checkpoint_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")

        return ThreadCheckpoint(
            checkpoint_id=checkpoint_id,
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
        )

    def _extract_checkpoint_id(self, config: Any) -> str | None:
        """설정에서 체크포인트 ID를 문자열로 추출 (하위 호환성)

        이 메서드는 이전 API 버전과의 호환성을 위해 체크포인트 ID를 문자열로 반환합니다.
        ThreadCheckpoint 객체 대신 단순 문자열 ID를 사용하는 레거시 클라이언트를 지원합니다.

        Args:
            config (Any): LangGraph RunnableConfig 딕셔너리

        Returns:
            str | None: 체크포인트 ID 문자열 또는 None

        참고:
            - 신규 코드는 _create_checkpoint()로 ThreadCheckpoint 객체 사용 권장
            - 이 메서드는 하위 호환성 유지 목적
        """
        if not config or not isinstance(config, dict):
            return None

        configurable = config.get("configurable", {})
        checkpoint_id = configurable.get("checkpoint_id")
        # 체크포인트 ID를 문자열로 변환 (있는 경우)
        return str(checkpoint_id) if checkpoint_id is not None else None
