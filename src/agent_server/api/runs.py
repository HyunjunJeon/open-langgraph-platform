"""Agent Protocol 실행(Run) 엔드포인트

이 모듈은 LangGraph 그래프 실행을 관리하는 Agent Protocol API 엔드포인트를 제공합니다.
실행 생성, 스트리밍, 상태 조회, 취소/중단 등의 기능을 포함하며,
SSE(Server-Sent Events)를 통한 실시간 이벤트 스트리밍과 PostgreSQL 기반 이벤트 영속화를 지원합니다.

주요 기능:
• 실행 생성 및 비동기 백그라운드 처리
• SSE 스트리밍을 통한 실시간 이벤트 전달
• Human-in-the-Loop (HITL) 중단점 지원
• 이벤트 저장 및 재연결 시 재생
• 멀티 스트림 모드 조정
• 실행 취소/중단 및 상태 관리

엔드포인트 목록:
• POST /threads/{thread_id}/runs - 실행 생성 (백그라운드)
• POST /threads/{thread_id}/runs/stream - 실행 생성 및 스트리밍
• GET /threads/{thread_id}/runs/{run_id} - 실행 조회
• GET /threads/{thread_id}/runs - 실행 목록 조회
• PATCH /threads/{thread_id}/runs/{run_id} - 실행 상태 업데이트
• GET /threads/{thread_id}/runs/{run_id}/join - 실행 완료 대기
• GET /threads/{thread_id}/runs/{run_id}/stream - 실행 스트리밍
• POST /threads/{thread_id}/runs/{run_id}/cancel - 실행 취소/중단
• DELETE /threads/{thread_id}/runs/{run_id} - 실행 삭제

참고:
- 모든 실행은 PostgreSQL에 영속화됩니다 (ORM을 통한 Run 테이블)
- 백그라운드 작업은 asyncio.Task로 관리되며 active_runs 딕셔너리에 추적됩니다
- 이벤트 스트리밍은 streaming_service와 broker를 통해 조정됩니다
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Send, StreamMode
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth_ctx import with_auth_ctx
from ..core.auth_deps import get_current_user
from ..core.orm import Assistant as AssistantORM
from ..core.orm import Run as RunORM
from ..core.orm import Thread as ThreadORM
from ..core.orm import _get_session_maker, get_session
from ..core.serializers import GeneralSerializer
from ..core.sse import create_end_event, get_sse_headers
from ..models import Run, RunCreate, RunStatus, User
from ..services.langgraph_service import create_run_config, get_langgraph_service
from ..services.streaming_service import streaming_service
from ..utils.assistants import resolve_assistant_id

router = APIRouter()

logger = logging.getLogger(__name__)
serializer = GeneralSerializer()
# TODO: 코드베이스 전체에서 print 문과 bare exception을 구조화된 로깅으로 교체


# NOTE: asyncio.Task 핸들은 인메모리 레지스트리에만 보관합니다.
# 모든 실행 메타데이터/상태는 ORM을 통해 영속화됩니다.
active_runs: dict[str, asyncio.Task] = {}

# 백그라운드 실행에 사용되는 기본 스트림 모드
DEFAULT_STREAM_MODES: list[StreamMode] = ["values"]


def map_command_to_langgraph(cmd: dict[str, Any]) -> Command:
    """API 명령을 LangGraph Command 객체로 변환

    Agent Protocol API에서 받은 명령 딕셔너리를 LangGraph가 인식하는
    Command 객체로 변환합니다. Human-in-the-Loop 재개 시 사용됩니다.

    동작:
    1. goto 필드를 리스트로 정규화
    2. update 필드를 튜플 리스트로 변환
    3. Send 객체로 서브그래프 노드 전환 처리
    4. resume 값을 그대로 전달

    Args:
        cmd (dict[str, Any]): API 명령 딕셔너리
            - goto: 전환할 노드 이름 또는 Send 객체
            - update: 상태 업데이트 튜플 리스트
            - resume: 재개 값

    Returns:
        Command: LangGraph Command 객체
    """
    goto = cmd.get("goto")
    if goto is not None and not isinstance(goto, list):
        goto = [goto]

    update = cmd.get("update")
    if isinstance(update, (tuple, list)) and all(
        isinstance(t, (tuple, list)) and len(t) == 2 and isinstance(t[0], str) for t in update
    ):
        update = [tuple(t) for t in update]

    return Command(
        update=update,
        goto=([it if isinstance(it, str) else Send(it["node"], it["input"]) for it in goto] if goto else None),
        resume=cmd.get("resume"),
    )


def _normalize_stream_modes(
    stream_mode: str | list[str] | None,
) -> list[StreamMode] | None:
    if stream_mode is None:
        return None

    modes = [stream_mode] if isinstance(stream_mode, str) else list(stream_mode)
    normalized: list[StreamMode] = []
    for mode in modes:
        if mode == "messages-tuple":
            normalized.append("messages")
        else:
            normalized.append(cast("StreamMode", mode))
    return normalized


async def set_thread_status(session: AsyncSession, thread_id: str, status: str) -> None:
    """스레드의 상태 컬럼 업데이트

    지정된 스레드의 상태를 데이터베이스에 업데이트합니다.
    실행 시작/완료/중단 시 스레드 상태를 동기화하는 데 사용됩니다.

    Args:
        session (AsyncSession): 데이터베이스 세션
        thread_id (str): 스레드 고유 식별자
        status (str): 새 상태 ("idle", "busy", "interrupted" 등)

    Returns:
        None
    """
    await session.execute(
        update(ThreadORM).where(ThreadORM.thread_id == thread_id).values(status=status, updated_at=datetime.now(UTC))
    )
    await session.commit()


async def update_thread_metadata(session: AsyncSession, thread_id: str, assistant_id: str, graph_id: str) -> None:
    """스레드 메타데이터에 어시스턴트 및 그래프 정보 업데이트 (DB 방언 독립적)

    스레드 메타데이터에 어시스턴트 ID와 그래프 ID를 추가합니다.
    DB별 JSON concat 연산자를 피하기 위해 read-modify-write 패턴을 사용합니다.

    동작 흐름:
    1. 스레드 레코드를 데이터베이스에서 조회
    2. 기존 메타데이터를 딕셔너리로 변환
    3. assistant_id와 graph_id 추가
    4. 업데이트된 메타데이터를 데이터베이스에 저장

    Args:
        session (AsyncSession): 데이터베이스 세션
        thread_id (str): 스레드 고유 식별자
        assistant_id (str): 어시스턴트 고유 식별자
        graph_id (str): 그래프 고유 식별자

    Returns:
        None

    Raises:
        HTTPException: 스레드를 찾을 수 없는 경우 (404)
    """
    # DB별 JSON concat 연산자를 피하기 위해 read-modify-write 사용
    thread = await session.scalar(select(ThreadORM).where(ThreadORM.thread_id == thread_id))
    if not thread:
        raise HTTPException(404, f"Thread '{thread_id}' not found for metadata update")
    md = dict(getattr(thread, "metadata_json", {}) or {})
    md.update({
        "assistant_id": str(assistant_id),
        "graph_id": graph_id,
    })
    await session.execute(
        update(ThreadORM).where(ThreadORM.thread_id == thread_id).values(metadata_json=md, updated_at=datetime.now(UTC))
    )
    await session.commit()


@router.post("/threads/{thread_id}/runs", response_model=Run)
async def create_run(
    thread_id: str,
    request: RunCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Run:
    """실행을 생성하고 백그라운드에서 비동기로 처리 (영속화)

    새로운 실행을 생성하고 백그라운드 asyncio.Task로 실행을 시작합니다.
    실행 메타데이터는 즉시 PostgreSQL에 저장되며, 실행 결과는 나중에 업데이트됩니다.

    동작 흐름:
    1. resume 명령 검증 (중단된 스레드에서만 재개 가능)
    2. 어시스턴트 존재 및 그래프 유효성 검증
    3. 스레드 상태를 "busy"로 변경
    4. 스레드 메타데이터에 어시스턴트/그래프 정보 추가
    5. Run 레코드를 "pending" 상태로 데이터베이스에 저장
    6. 백그라운드 작업(execute_run_async) 시작
    7. active_runs 딕셔너리에 Task 등록
    8. Run 객체를 즉시 반환 (실행은 백그라운드에서 계속)

    Args:
        thread_id (str): 실행을 수행할 스레드 ID
        request (RunCreate): 실행 생성 요청 (입력, 설정, 명령 등)
        user (User): 인증된 사용자 (의존성 주입)
        session (AsyncSession): 데이터베이스 세션 (의존성 주입)

    Returns:
        Run: 생성된 실행 객체 ("pending" 상태)

    Raises:
        HTTPException: 스레드/어시스턴트/그래프를 찾을 수 없거나 잘못된 재개 요청인 경우

    참고:
        - 실행은 즉시 반환되지만 백그라운드에서 계속 처리됩니다
        - 실행 상태는 get_run 엔드포인트로 확인할 수 있습니다
        - 스트리밍이 필요한 경우 create_and_stream_run을 사용하세요
    """

    # resume 명령 요구사항을 조기에 검증
    if request.command and request.command.get("resume") is not None:
        # 스레드가 존재하고 중단된 상태인지 확인
        thread_stmt = select(ThreadORM).where(ThreadORM.thread_id == thread_id)
        thread = await session.scalar(thread_stmt)
        if not thread:
            raise HTTPException(404, f"Thread '{thread_id}' not found")
        if thread.status != "interrupted":
            raise HTTPException(400, "Cannot resume: thread is not in interrupted state")

    run_id = str(uuid4())

    # LangGraph 서비스 가져오기
    langgraph_service = get_langgraph_service()
    print(f"create_run: scheduling background task run_id={run_id} thread_id={thread_id} user={user.identity}")
    print(f"[create_run] scheduling background task run_id={run_id} thread_id={thread_id} user={user.identity}")

    # 어시스턴트 존재 여부를 검증하고 graph_id를 가져옵니다.
    # assistant UUID 대신 graph_id가 제공된 경우, 결정론적으로 매핑하고
    # 시작 시 생성된 기본 어시스턴트로 폴백합니다.
    requested_id = str(request.assistant_id)
    available_graphs = langgraph_service.list_graphs()
    resolved_assistant_id = resolve_assistant_id(requested_id, available_graphs)

    config = request.config
    context = request.context

    assistant_stmt = select(AssistantORM).where(
        AssistantORM.assistant_id == resolved_assistant_id,
    )
    assistant = await session.scalar(assistant_stmt)
    if not assistant:
        raise HTTPException(404, f"Assistant '{request.assistant_id}' not found")

    # 어시스턴트의 그래프가 존재하는지 검증
    available_graphs = langgraph_service.list_graphs()
    if assistant.graph_id not in available_graphs:
        raise HTTPException(404, f"Graph '{assistant.graph_id}' not found for assistant")

    # 스레드를 busy로 표시하고 어시스턴트/그래프 정보로 메타데이터 업데이트
    await set_thread_status(session, thread_id, "busy")
    await update_thread_metadata(session, thread_id, assistant.assistant_id, assistant.graph_id)

    # core.orm의 ORM 모델을 통해 Run 레코드 영속화 (Run 테이블)
    now = datetime.now(UTC)
    run_orm = RunORM(
        run_id=run_id,  # 명시적으로 설정 (생략 시 DB가 기본값 생성)
        thread_id=thread_id,
        assistant_id=resolved_assistant_id,
        status="pending",
        input=request.input or {},
        config=config,
        context=context,
        user_id=user.identity,
        created_at=now,
        updated_at=now,
        output=None,
        error_message=None,
    )
    session.add(run_orm)
    await session.commit()

    # ORM -> Pydantic 응답 객체 구성
    run = Run(
        run_id=run_id,
        thread_id=thread_id,
        assistant_id=resolved_assistant_id,
        status="pending",
        input=request.input or {},
        config=config,
        context=context,
        user_id=user.identity,
        created_at=now,
        updated_at=now,
        output=None,
        error_message=None,
    )

    # 비동기로 실행 시작
    # 트랜잭션 충돌을 피하기 위해 session을 전달하지 않음
    stream_modes = _normalize_stream_modes(request.stream_mode)

    subgraphs_flag = bool(request.stream_subgraphs)

    task = asyncio.create_task(
        execute_run_async(
            run_id,
            thread_id,
            assistant.graph_id,
            request.input or {},
            user,
            config,
            context,
            stream_modes,
            None,  # 충돌 방지를 위해 session 전달 안 함
            request.checkpoint,
            request.command,
            request.interrupt_before,
            request.interrupt_after,
            request.multitask_strategy,
            subgraphs_flag,
        )
    )
    print(f"[create_run] background task created task_id={id(task)} for run_id={run_id}")
    active_runs[run_id] = task

    return run


@router.post("/threads/{thread_id}/runs/stream")
async def create_and_stream_run(
    thread_id: str,
    request: RunCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """실행을 생성하고 SSE로 실시간 스트리밍 (영속화 + SSE)

    새로운 실행을 생성하고 즉시 SSE(Server-Sent Events)로 실시간 이벤트를 스트리밍합니다.
    백그라운드에서 실행이 진행되며, 발생하는 모든 이벤트가 클라이언트에게 전달됩니다.

    동작 흐름:
    1. resume 명령 검증 (중단된 스레드에서만 재개 가능)
    2. 어시스턴트 존재 및 그래프 유효성 검증
    3. 스레드 상태를 "busy"로 변경
    4. 스레드 메타데이터에 어시스턴트/그래프 정보 추가
    5. Run 레코드를 "streaming" 상태로 데이터베이스에 저장
    6. 백그라운드 작업(execute_run_async) 시작
    7. active_runs 딕셔너리에 Task 등록
    8. SSE StreamingResponse 반환 (브로커를 통한 실시간 이벤트 스트리밍)

    Args:
        thread_id (str): 실행을 수행할 스레드 ID
        request (RunCreate): 실행 생성 요청 (입력, 설정, 명령 등)
        user (User): 인증된 사용자 (의존성 주입)
        session (AsyncSession): 데이터베이스 세션 (의존성 주입)

    Returns:
        StreamingResponse: SSE 응답 (text/event-stream)

    Raises:
        HTTPException: 스레드/어시스턴트/그래프를 찾을 수 없거나 잘못된 재개 요청인 경우

    참고:
        - 클라이언트는 SSE 스트림을 통해 실행 이벤트를 실시간으로 수신합니다
        - 이벤트는 PostgreSQL에도 저장되어 재연결 시 재생 가능합니다
        - on_disconnect=cancel 옵션으로 클라이언트 연결 해제 시 실행 취소 가능
    """

    # resume 명령 요구사항을 조기에 검증
    if request.command and request.command.get("resume") is not None:
        # 스레드가 존재하고 중단된 상태인지 확인
        thread_stmt = select(ThreadORM).where(ThreadORM.thread_id == thread_id)
        thread = await session.scalar(thread_stmt)
        if not thread:
            raise HTTPException(404, f"Thread '{thread_id}' not found")
        if thread.status != "interrupted":
            raise HTTPException(400, "Cannot resume: thread is not in interrupted state")

    run_id = str(uuid4())

    # LangGraph 서비스 가져오기
    langgraph_service = get_langgraph_service()
    print(
        f"[create_and_stream_run] scheduling background task run_id={run_id} thread_id={thread_id} user={user.identity}"
    )

    # 어시스턴트 존재 여부를 검증하고 graph_id를 가져옵니다.
    # graph_id를 전달하면 결정론적 어시스턴트 ID로 매핑합니다.
    requested_id = str(request.assistant_id)
    available_graphs = langgraph_service.list_graphs()

    resolved_assistant_id = resolve_assistant_id(requested_id, available_graphs)

    config = request.config
    context = request.context

    assistant_stmt = select(AssistantORM).where(
        AssistantORM.assistant_id == resolved_assistant_id,
    )
    assistant = await session.scalar(assistant_stmt)
    if not assistant:
        raise HTTPException(404, f"Assistant '{request.assistant_id}' not found")

    # 어시스턴트의 그래프가 존재하는지 검증
    available_graphs = langgraph_service.list_graphs()
    if assistant.graph_id not in available_graphs:
        raise HTTPException(404, f"Graph '{assistant.graph_id}' not found for assistant")

    # 스레드를 busy로 표시하고 어시스턴트/그래프 정보로 메타데이터 업데이트
    await set_thread_status(session, thread_id, "busy")
    await update_thread_metadata(session, thread_id, assistant.assistant_id, assistant.graph_id)

    # Run 레코드 영속화
    now = datetime.now(UTC)
    run_orm = RunORM(
        run_id=run_id,
        thread_id=thread_id,
        assistant_id=resolved_assistant_id,
        status="streaming",
        input=request.input or {},
        config=config,
        context=context,
        user_id=user.identity,
        created_at=now,
        updated_at=now,
        output=None,
        error_message=None,
    )
    session.add(run_orm)
    await session.commit()

    # 스트림 컨텍스트용 응답 모델 구성
    run = Run(
        run_id=run_id,
        thread_id=thread_id,
        assistant_id=resolved_assistant_id,
        status="streaming",
        input=request.input or {},
        config=config,
        context=context,
        user_id=user.identity,
        created_at=now,
        updated_at=now,
        output=None,
        error_message=None,
    )

    # 브로커를 채울 백그라운드 실행 시작
    # 트랜잭션 충돌을 피하기 위해 session을 전달하지 않음
    stream_modes = _normalize_stream_modes(request.stream_mode)
    subgraphs_flag = bool(request.stream_subgraphs)

    task = asyncio.create_task(
        execute_run_async(
            run_id,
            thread_id,
            assistant.graph_id,
            request.input or {},
            user,
            config,
            context,
            stream_modes,
            None,  # 충돌 방지를 위해 session 전달 안 함
            request.checkpoint,
            request.command,
            request.interrupt_before,
            request.interrupt_after,
            request.multitask_strategy,
            subgraphs_flag,
        )
    )
    print(f"[create_and_stream_run] background task created task_id={id(task)} for run_id={run_id}")
    active_runs[run_id] = task

    # 요청된 스트림 모드 추출
    stream_mode = request.stream_mode
    if not stream_mode and config and "stream_mode" in config:
        stream_mode = config["stream_mode"]

    # 브로커에서 즉시 스트리밍 (초기 이벤트 재생 포함)
    cancel_on_disconnect = (request.on_disconnect or "continue").lower() == "cancel"

    return StreamingResponse(
        streaming_service.stream_run_execution(
            run,
            None,
            cancel_on_disconnect=cancel_on_disconnect,
        ),
        media_type="text/event-stream",
        headers={
            **get_sse_headers(),
            "Location": f"/threads/{thread_id}/runs/{run_id}/stream",
            "Content-Location": f"/threads/{thread_id}/runs/{run_id}",
        },
    )


@router.get("/threads/{thread_id}/runs/{run_id}", response_model=Run)
async def get_run(
    thread_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Run:
    """실행 ID로 실행 조회 (영속화)

    지정된 실행의 현재 상태를 데이터베이스에서 조회합니다.
    백그라운드 작업이 업데이트한 최신 데이터를 반환하기 위해 refresh를 수행합니다.

    Args:
        thread_id (str): 스레드 고유 식별자
        run_id (str): 실행 고유 식별자
        user (User): 인증된 사용자 (의존성 주입)
        session (AsyncSession): 데이터베이스 세션 (의존성 주입)

    Returns:
        Run: 실행 객체 (현재 상태, 출력, 에러 등 포함)

    Raises:
        HTTPException: 실행을 찾을 수 없는 경우 (404)
    """
    stmt = select(RunORM).where(
        RunORM.run_id == str(run_id),
        RunORM.thread_id == thread_id,
        RunORM.user_id == user.identity,
    )
    print(f"[get_run] querying DB run_id={run_id} thread_id={thread_id} user={user.identity}")
    run_orm = await session.scalar(stmt)
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found")

    # 백그라운드 작업이 업데이트한 최신 데이터를 가져오기 위해 refresh
    await session.refresh(run_orm)

    print(f"[get_run] found run status={run_orm.status} user={user.identity} thread_id={thread_id} run_id={run_id}")
    # Pydantic으로 변환
    return Run.model_validate({c.name: getattr(run_orm, c.name) for c in run_orm.__table__.columns})


@router.get("/threads/{thread_id}/runs", response_model=list[Run])
async def list_runs(
    thread_id: str,
    limit: int = Query(10, ge=1, description="Maximum number of runs to return"),
    offset: int = Query(0, ge=0, description="Number of runs to skip for pagination"),
    status: str | None = Query(None, description="Filter by run status"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Run]:
    """특정 스레드의 실행 목록 조회 (영속화)

    지정된 스레드에 속한 실행들을 데이터베이스에서 조회합니다.
    페이지네이션과 상태 필터링을 지원하며, 최신 순으로 정렬됩니다.

    Args:
        thread_id (str): 스레드 고유 식별자
        limit (int): 반환할 최대 실행 개수 (기본값: 10)
        offset (int): 페이지네이션을 위해 건너뛸 실행 개수 (기본값: 0)
        status (str | None): 상태로 필터링 (예: "completed", "running")
        user (User): 인증된 사용자 (의존성 주입)
        session (AsyncSession): 데이터베이스 세션 (의존성 주입)

    Returns:
        list[Run]: 실행 객체 리스트 (최신 순)

    참고:
        - 사용자는 자신의 실행만 조회할 수 있습니다
        - created_at 기준으로 내림차순 정렬됩니다
    """
    stmt = (
        select(RunORM)
        .where(
            RunORM.thread_id == thread_id,
            RunORM.user_id == user.identity,
            *([RunORM.status == status] if status else []),
        )
        .limit(limit)
        .offset(offset)
        .order_by(RunORM.created_at.desc())
    )
    print(f"[list_runs] querying DB thread_id={thread_id} user={user.identity}")
    result = await session.scalars(stmt)
    rows = result.all()
    runs = [Run.model_validate({c.name: getattr(r, c.name) for c in r.__table__.columns}) for r in rows]
    print(f"[list_runs] total={len(runs)} user={user.identity} thread_id={thread_id}")
    return runs


@router.patch("/threads/{thread_id}/runs/{run_id}")
async def update_run(
    thread_id: str,
    run_id: str,
    request: RunStatus,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Run:
    """실행 상태 업데이트 (취소/중단용, 영속화)

    실행의 상태를 업데이트합니다. 주로 실행 취소 또는 중단에 사용됩니다.
    streaming_service를 통해 백그라운드 작업에 신호를 보내고 데이터베이스를 업데이트합니다.

    동작 흐름:
    1. 실행을 데이터베이스에서 조회
    2. 요청된 상태에 따라 처리:
       - cancelled: streaming_service.cancel_run() 호출 후 DB 업데이트
       - interrupted: streaming_service.interrupt_run() 호출 후 DB 업데이트
    3. 최신 상태를 반환

    Args:
        thread_id (str): 스레드 고유 식별자
        run_id (str): 실행 고유 식별자
        request (RunStatus): 새로운 상태 ("cancelled", "interrupted")
        user (User): 인증된 사용자 (의존성 주입)
        session (AsyncSession): 데이터베이스 세션 (의존성 주입)

    Returns:
        Run: 업데이트된 실행 객체

    Raises:
        HTTPException: 실행을 찾을 수 없는 경우 (404)
    """
    print(f"[update_run] fetch for update run_id={run_id} thread_id={thread_id} user={user.identity}")
    run_orm = await session.scalar(
        select(RunORM).where(
            RunORM.run_id == str(run_id),
            RunORM.thread_id == thread_id,
            RunORM.user_id == user.identity,
        )
    )
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found")

    # 중단/취소 처리

    if request.status == "cancelled":
        print(f"[update_run] cancelling run_id={run_id} user={user.identity} thread_id={thread_id}")
        await streaming_service.cancel_run(run_id)
        print(f"[update_run] set DB status=cancelled run_id={run_id}")
        await session.execute(
            update(RunORM).where(RunORM.run_id == str(run_id)).values(status="cancelled", updated_at=datetime.now(UTC))
        )
        await session.commit()
        print(f"[update_run] commit done (cancelled) run_id={run_id}")
    elif request.status == "interrupted":
        print(f"[update_run] interrupt run_id={run_id} user={user.identity} thread_id={thread_id}")
        await streaming_service.interrupt_run(run_id)
        print(f"[update_run] set DB status=interrupted run_id={run_id}")
        await session.execute(
            update(RunORM)
            .where(RunORM.run_id == str(run_id))
            .values(status="interrupted", updated_at=datetime.now(UTC))
        )
        await session.commit()
        print(f"[update_run] commit done (interrupted) run_id={run_id}")

    # 최종 실행 상태 반환
    run_orm = await session.scalar(select(RunORM).where(RunORM.run_id == run_id))
    if run_orm:
        # 우리가 방금 업데이트한 최신 데이터를 가져오기 위해 refresh
        await session.refresh(run_orm)
    return Run.model_validate({c.name: getattr(run_orm, c.name) for c in run_orm.__table__.columns})  # type: ignore


@router.get("/threads/{thread_id}/runs/{run_id}/join")
async def join_run(
    thread_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """실행 완료 대기 및 최종 출력 반환 (영속화)

    실행이 완료될 때까지 대기한 후 최종 출력을 반환합니다.
    이미 완료된 경우 즉시 출력을 반환합니다.

    동작 흐름:
    1. 실행을 데이터베이스에서 조회
    2. 이미 완료된 경우 (completed/failed/cancelled) 즉시 출력 반환
    3. 진행 중인 경우 백그라운드 작업이 완료될 때까지 대기 (최대 30초)
    4. 데이터베이스에서 최종 출력 조회 및 반환

    Args:
        thread_id (str): 스레드 고유 식별자
        run_id (str): 실행 고유 식별자
        user (User): 인증된 사용자 (의존성 주입)
        session (AsyncSession): 데이터베이스 세션 (의존성 주입)

    Returns:
        dict[str, Any]: 실행의 최종 출력

    Raises:
        HTTPException: 실행을 찾을 수 없는 경우 (404)

    참고:
        - 타임아웃(30초)이 발생해도 에러가 아닙니다. DB에서 현재 상태를 반환합니다
        - 작업이 취소되어도 DB에서 출력을 조회합니다
    """
    # 실행을 가져와서 존재 여부 확인
    run_orm = await session.scalar(
        select(RunORM).where(
            RunORM.run_id == str(run_id),
            RunORM.thread_id == thread_id,
            RunORM.user_id == user.identity,
        )
    )
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found")

    # 이미 완료된 경우 즉시 출력 반환
    if run_orm.status in ["completed", "failed", "cancelled"]:
        # 최신 데이터를 가져오기 위해 refresh
        await session.refresh(run_orm)
        output = getattr(run_orm, "output", None) or {}
        return output

    # 백그라운드 작업이 완료될 때까지 대기
    task = active_runs.get(run_id)
    if task:
        try:
            await asyncio.wait_for(task, timeout=30.0)
        except TimeoutError:
            # 작업이 너무 오래 걸리지만 괜찮습니다 - DB 상태를 확인할 것입니다
            pass
        except asyncio.CancelledError:
            # 작업이 취소되었지만 이것도 괜찮습니다
            pass

    # 데이터베이스에서 최종 출력 반환
    run_orm = await session.scalar(select(RunORM).where(RunORM.run_id == run_id))
    if run_orm:
        await session.refresh(run_orm)  # DB에서 최신 데이터를 가져오기 위해 refresh
    output = getattr(run_orm, "output", None) or {}
    return output


# TODO: 구현이 올바르지 않아 보이므로 이 메서드가 실제로 필요한지 확인 필요
@router.get("/threads/{thread_id}/runs/{run_id}/stream")
async def stream_run(
    thread_id: str,
    run_id: str,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    _stream_mode: str | None = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """SSE 및 재연결 지원으로 실행 스트리밍 (영속화된 메타데이터)

    기존 실행의 이벤트를 SSE로 스트리밍합니다. 재연결을 지원하며
    Last-Event-ID 헤더를 사용하여 중단된 지점부터 이벤트를 재생합니다.

    동작 흐름:
    1. 실행을 데이터베이스에서 조회
    2. 완료된 실행(completed/failed/cancelled)인 경우 종료 이벤트만 전송
    3. 활성/대기 중인 실행인 경우 브로커를 통해 스트리밍
    4. last_event_id가 있으면 해당 지점부터 재생

    Args:
        thread_id (str): 스레드 고유 식별자
        run_id (str): 실행 고유 식별자
        last_event_id (str | None): 재연결 시 마지막으로 받은 이벤트 ID
        _stream_mode (str | None): 스트림 모드 (현재 사용 안 함)
        user (User): 인증된 사용자 (의존성 주입)
        session (AsyncSession): 데이터베이스 세션 (의존성 주입)

    Returns:
        StreamingResponse: SSE 응답 (text/event-stream)

    Raises:
        HTTPException: 실행을 찾을 수 없는 경우 (404)

    참고:
        - 재연결 시 저장된 이벤트를 재생하여 일관성을 보장합니다
        - 연결 해제 시 실행은 계속 진행됩니다 (cancel_on_disconnect=False)
    """
    print(f"[stream_run] fetch for stream run_id={run_id} thread_id={thread_id} user={user.identity}")
    run_orm = await session.scalar(
        select(RunORM).where(
            RunORM.run_id == str(run_id),
            RunORM.thread_id == thread_id,
            RunORM.user_id == user.identity,
        )
    )
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found")

    print(f"[stream_run] status={run_orm.status} user={user.identity} thread_id={thread_id} run_id={run_id}")
    # 이미 종료된 경우 최종 종료 이벤트 전송
    if run_orm.status in ["completed", "failed", "cancelled"]:

        async def generate_final() -> AsyncIterator[str]:
            yield create_end_event()

        print(f"[stream_run] starting terminal stream run_id={run_id} status={run_orm.status}")
        return StreamingResponse(
            generate_final(),
            media_type="text/event-stream",
            headers={
                **get_sse_headers(),
                "Location": f"/threads/{thread_id}/runs/{run_id}/stream",
                "Content-Location": f"/threads/{thread_id}/runs/{run_id}",
            },
        )

    # 활성 또는 대기 중인 실행을 브로커를 통해 스트리밍

    # 스트리밍 컨텍스트용 경량 Pydantic Run 객체 구성 (ID는 이미 문자열)
    run_model = Run.model_validate({c.name: getattr(run_orm, c.name) for c in run_orm.__table__.columns})

    return StreamingResponse(
        streaming_service.stream_run_execution(run_model, last_event_id, cancel_on_disconnect=False),
        media_type="text/event-stream",
        headers={
            **get_sse_headers(),
            "Location": f"/threads/{thread_id}/runs/{run_id}/stream",
            "Content-Location": f"/threads/{thread_id}/runs/{run_id}",
        },
    )


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_run_endpoint(
    thread_id: str,
    run_id: str,
    wait: int = Query(0, ge=0, le=1, description="Whether to wait for the run task to settle"),
    action: str = Query("cancel", pattern="^(cancel|interrupt)$", description="Cancellation action"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Run:
    """실행 취소 또는 중단 (클라이언트 호환 엔드포인트)

    실행을 취소하거나 중단합니다. 클라이언트 사용 예시와 호환됩니다:
      POST /v1/threads/{thread_id}/runs/{run_id}/cancel?wait=0&action=interrupt

    동작:
    - action=cancel: 강제 취소 (hard cancel)
    - action=interrupt: 협력적 중단 (cooperative interrupt, 지원되는 경우)
    - wait=1: 백그라운드 작업이 정리될 때까지 대기

    동작 흐름:
    1. 실행을 데이터베이스에서 조회
    2. action에 따라 처리:
       - interrupt: streaming_service.interrupt_run() 호출 후 "interrupted" 상태로 저장
       - cancel: streaming_service.cancel_run() 호출 후 "cancelled" 상태로 저장
    3. wait=1인 경우 백그라운드 작업 완료 대기
    4. 업데이트된 실행 반환

    Args:
        thread_id (str): 스레드 고유 식별자
        run_id (str): 실행 고유 식별자
        wait (int): 작업 정리 대기 여부 (0 또는 1)
        action (str): 취소 동작 ("cancel" 또는 "interrupt")
        user (User): 인증된 사용자 (의존성 주입)
        session (AsyncSession): 데이터베이스 세션 (의존성 주입)

    Returns:
        Run: 업데이트된 실행 객체

    Raises:
        HTTPException: 실행을 찾을 수 없는 경우 (404)

    참고:
        - 삭제는 별도의 엔드포인트에서 처리합니다 (여기서는 삭제하지 않음)
        - interrupt는 그래프가 지원하는 경우 깔끔하게 중단합니다
    """
    print(f"[cancel_run] fetch run run_id={run_id} thread_id={thread_id} user={user.identity}")
    run_orm = await session.scalar(
        select(RunORM).where(
            RunORM.run_id == run_id,
            RunORM.thread_id == thread_id,
            RunORM.user_id == user.identity,
        )
    )
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found")

    if action == "interrupt":
        print(f"[cancel_run] interrupt run_id={run_id} user={user.identity} thread_id={thread_id}")
        await streaming_service.interrupt_run(run_id)
        # 상태를 interrupted로 영속화
        await session.execute(
            update(RunORM)
            .where(RunORM.run_id == str(run_id))
            .values(status="interrupted", updated_at=datetime.now(UTC))
        )
        await session.commit()
    else:
        print(f"[cancel_run] cancel run_id={run_id} user={user.identity} thread_id={thread_id}")
        await streaming_service.cancel_run(run_id)
        # 상태를 cancelled로 영속화
        await session.execute(
            update(RunORM).where(RunORM.run_id == str(run_id)).values(status="cancelled", updated_at=datetime.now(UTC))
        )
        await session.commit()

    # 선택적으로 백그라운드 작업 대기
    if wait:
        task = active_runs.get(run_id)
        if task:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    # 업데이트된 Run을 다시 로드하여 반환 (여기서 삭제하지 않음; 삭제는 별도 엔드포인트)
    run_orm = await session.scalar(
        select(RunORM).where(
            RunORM.run_id == run_id,
            RunORM.thread_id == thread_id,
            RunORM.user_id == user.identity,
        )
    )
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found after cancellation")
    return Run.model_validate({c.name: getattr(run_orm, c.name) for c in run_orm.__table__.columns})


def _should_skip_event(raw_event: Any) -> bool:
    """langsmith:nostream 태그를 기반으로 이벤트를 건너뛸지 확인

    LangGraph 이벤트에 'langsmith:nostream' 태그가 있는지 확인하여
    스트리밍에서 제외해야 할 내부 이벤트를 필터링합니다.

    동작:
    1. 이벤트가 튜플 형식인지 확인
    2. 메타데이터 튜플에서 tags 배열 추출
    3. 'langsmith:nostream' 태그가 있으면 True 반환

    Args:
        raw_event (Any): LangGraph 원시 이벤트 (튜플 또는 딕셔너리)

    Returns:
        bool: 이벤트를 건너뛰어야 하면 True, 그렇지 않으면 False

    참고:
        - 파싱 실패 시 안전하게 False 반환 (이벤트를 건너뛰지 않음)
        - Langsmith 내부 추적용 이벤트를 클라이언트에게 전송하지 않기 위함
    """
    try:
        # 이벤트가 'langsmith:nostream' 태그를 포함한 메타데이터를 가지고 있는지 확인
        if isinstance(raw_event, tuple) and len(raw_event) >= 2:
            # 튜플 이벤트의 경우 세 번째 요소(메타데이터 튜플) 확인
            metadata_tuple = raw_event[len(raw_event) - 1]
            if isinstance(metadata_tuple, tuple) and len(metadata_tuple) >= 2:
                # 메타데이터 튜플의 두 번째 항목 가져오기
                metadata = metadata_tuple[1]
                if isinstance(metadata, dict) and "tags" in metadata:
                    tags = metadata["tags"]
                    if isinstance(tags, list) and "langsmith:nostream" in tags:
                        return True
        return False
    except Exception:
        # 이벤트 구조를 파싱할 수 없으면 건너뛰지 않음
        return False


async def execute_run_async(
    run_id: str,
    thread_id: str,
    graph_id: str,
    input_data: dict[str, Any],
    user: User,
    config: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    stream_mode: list[StreamMode] | None = None,
    session: AsyncSession | None = None,
    checkpoint: dict[str, Any] | None = None,
    command: dict[str, Any] | None = None,
    interrupt_before: str | list[str] | None = None,
    interrupt_after: str | list[str] | None = None,
    _multitask_strategy: str | None = None,
    subgraphs: bool = False,
) -> None:
    """백그라운드에서 실행을 비동기로 처리하며 스트리밍으로 모든 이벤트 캡처

    이 함수는 LangGraph 그래프를 실행하고 실행 중 발생하는 모든 이벤트를
    SSE(Server-Sent Events)를 통해 스트리밍하면서 동시에 PostgreSQL에 저장합니다.
    asyncio.create_task()로 백그라운드에서 실행되며, 실행 상태는 Run ORM 모델에
    지속적으로 업데이트됩니다.

    동작 흐름:
    1. 데이터베이스 세션 확보 (제공되지 않은 경우 새로 생성)
    2. 스트림 모드 정규화 ("messages-tuple" → "messages")
    3. 실행 상태를 "running"으로 업데이트
    4. LangGraph 그래프 로드 및 실행 설정 생성
    5. interrupt_before/after 설정 적용
    6. 명령(command) 또는 입력 데이터 결정
    7. graph.astream()으로 스트리밍 실행
    8. 각 이벤트를:
       - langsmith:nostream 태그 필터링
       - 브로커에 전달 (라이브 스트리밍용)
       - PostgreSQL에 저장 (재생용)
       - interrupt 체크
    9. 완료/중단 상태 업데이트 및 스레드 상태 변경
    10. 에러 발생 시 failed 상태로 업데이트

    Args:
        run_id (str): 실행 고유 식별자
        thread_id (str): 스레드 고유 식별자
        graph_id (str): 실행할 그래프 ID
        input_data (dict): 그래프 입력 데이터
        user (User): 인증된 사용자 정보
        config (dict | None): LangGraph 실행 설정
        context (dict | None): 실행 컨텍스트 (그래프에 전달)
        stream_mode (list[str] | None): 스트림 모드 리스트
        session (AsyncSession | None): 데이터베이스 세션 (None이면 새로 생성)
        checkpoint (dict | None): 체크포인트 (특정 상태에서 재개)
        command (dict[str, Any] | None): Human-in-the-Loop 명령 (재개 시)
        interrupt_before (str | list[str] | None): 중단점 전 노드 이름
        interrupt_after (str | list[str] | None): 중단점 후 노드 이름
        _multitask_strategy (str | None): 멀티태스크 전략 (현재 미사용)
        subgraphs (bool | None): 서브그래프 포함 여부

    Returns:
        None: 백그라운드 작업으로 반환값 없음

    Raises:
        asyncio.CancelledError: 실행이 취소된 경우 (cancelled 상태로 업데이트 후 재발생)
        Exception: 실행 중 오류 발생 시 (failed 상태로 업데이트 후 재발생)

    참고:
        - 이 함수는 절대 직접 호출하지 않고 asyncio.create_task()로 실행합니다
        - 모든 예외는 캡처되어 데이터베이스 상태에 반영됩니다
        - finally 블록에서 브로커 정리 및 active_runs에서 제거를 보장합니다
    """
    # 제공된 세션을 사용하거나 새로 생성
    if session is None:
        maker = _get_session_maker()
        session = maker()

    normalized_stream_mode = stream_mode

    try:
        # 상태 업데이트
        await update_run_status(run_id, "running", session=session)

        # 그래프를 가져와서 실행
        langgraph_service = get_langgraph_service()
        graph = await langgraph_service.get_graph(graph_id)

        run_config = create_run_config(run_id, thread_id, user, config or {}, checkpoint)

        # Human-in-the-Loop 필드 처리
        if interrupt_before is not None:
            run_config["interrupt_before"] = (
                interrupt_before if isinstance(interrupt_before, list) else [interrupt_before]
            )
        if interrupt_after is not None:
            run_config["interrupt_after"] = interrupt_after if isinstance(interrupt_after, list) else [interrupt_after]

        # 참고: multitask_strategy는 실행 생성 레벨에서 처리되며, 실행 레벨이 아닙니다
        # 동시 실행 동작을 제어하며, 그래프 실행 동작을 제어하지 않습니다

        # 실행할 입력 결정 (input_data 또는 command)
        execution_input: Command | dict[str, Any]
        if command is not None:
            # command가 제공되면 입력을 완전히 대체합니다 (LangGraph API 동작)
            if isinstance(command, dict):
                execution_input = map_command_to_langgraph(command)
            else:
                # 직접 resume 값 (하위 호환성)
                execution_input = Command(resume=command)
        else:
            # 명령이 없으면 일반 입력 사용
            execution_input = input_data

        # 나중에 재생할 이벤트를 캡처하기 위해 스트리밍으로 실행
        event_counter = 0
        final_output = None
        has_interrupt = False

        # 실행을 위한 스트림 모드 준비
        if normalized_stream_mode is None:
            final_stream_modes = DEFAULT_STREAM_MODES.copy()
        else:
            final_stream_modes = list(normalized_stream_mode)

        # updates 모드를 포함하여 interrupt 이벤트가 캡처되도록 보장
        # 사용자가 updates를 명시적으로 요청했는지 추적
        user_requested_updates = "updates" in final_stream_modes
        if not user_requested_updates:
            final_stream_modes.append("updates")

        only_interrupt_updates = not user_requested_updates

        async with with_auth_ctx(user.model_dump(), []):
            async for raw_event in graph.astream(
                execution_input,
                config=cast("RunnableConfig", run_config),
                context=context,
                subgraphs=subgraphs,
                stream_mode=final_stream_modes,
            ):
                # langsmith:nostream 태그를 포함한 이벤트 건너뛰기
                if _should_skip_event(raw_event):
                    continue

                event_counter += 1
                event_id = f"{run_id}_event_{event_counter}"

                # 라이브 소비자를 위해 브로커로 전달
                await streaming_service.put_to_broker(
                    run_id,
                    event_id,
                    raw_event,
                    only_interrupt_updates=only_interrupt_updates,
                )
                # 재생을 위해 저장
                await streaming_service.store_event_from_raw(
                    run_id,
                    event_id,
                    raw_event,
                    only_interrupt_updates=only_interrupt_updates,
                )

                # 이 이벤트에서 interrupt 확인
                event_data = None
                if isinstance(raw_event, tuple) and len(raw_event) >= 2:
                    event_data = raw_event[1]
                elif not isinstance(raw_event, tuple):
                    event_data = raw_event

                if isinstance(event_data, dict) and "__interrupt__" in event_data:
                    has_interrupt = True

                # 최종 출력 추적
                if isinstance(raw_event, tuple):
                    if len(raw_event) >= 2 and raw_event[0] == "values":
                        final_output = raw_event[1]
                elif not isinstance(raw_event, tuple):
                    # 튜플이 아닌 이벤트는 values 모드
                    final_output = raw_event

        if has_interrupt:
            await update_run_status(run_id, "interrupted", output=final_output or {}, session=session)
            if not session:
                raise RuntimeError(f"No database session available to update thread {thread_id} status")
            await set_thread_status(session, thread_id, "interrupted")

        else:
            # 결과로 업데이트
            await update_run_status(run_id, "completed", output=final_output or {}, session=session)
            # 스레드를 idle로 되돌리기
            if not session:
                raise RuntimeError(f"No database session available to update thread {thread_id} status")
            await set_thread_status(session, thread_id, "idle")

    except asyncio.CancelledError:
        # JSON 직렬화 문제를 피하기 위해 빈 출력 저장
        await update_run_status(run_id, "cancelled", output={}, session=session)
        if not session:
            raise RuntimeError(f"No database session available to update thread {thread_id} status") from None
        await set_thread_status(session, thread_id, "idle")
        # 브로커에 취소 신호
        await streaming_service.signal_run_cancelled(run_id)
        raise
    except Exception as e:
        # JSON 직렬화 문제를 피하기 위해 빈 출력 저장
        await update_run_status(run_id, "failed", output={}, error=str(e), session=session)
        if not session:
            raise RuntimeError(f"No database session available to update thread {thread_id} status") from None
        await set_thread_status(session, thread_id, "idle")
        # 브로커에 에러 신호
        await streaming_service.signal_run_error(run_id, str(e))
        raise
    finally:
        # 브로커 정리
        await streaming_service.cleanup_run(run_id)
        active_runs.pop(run_id, None)


async def update_run_status(
    run_id: str,
    status: str,
    output: Any = None,
    error: str | None = None,
    session: AsyncSession | None = None,
) -> None:
    """데이터베이스에서 실행 상태 업데이트 (영속화)

    실행의 상태를 데이터베이스에 업데이트합니다. 세션이 제공되지 않으면
    단기 세션을 생성하여 사용하고 종료 시 자동으로 닫습니다.

    동작 흐름:
    1. 세션 확보 (제공되지 않으면 새로 생성)
    2. 상태 및 updated_at 설정
    3. 출력이 있으면 JSON 직렬화 후 저장
    4. 에러가 있으면 error_message 설정
    5. 데이터베이스에 업데이트 및 커밋
    6. 자체 생성한 세션인 경우 종료

    Args:
        run_id (str): 실행 고유 식별자
        status (str): 새로운 상태 ("running", "completed", "failed", "cancelled", "interrupted")
        output (Any | None): 실행 출력 (JSON 직렬화 가능해야 함)
        error (str | None): 에러 메시지
        session (AsyncSession | None): 데이터베이스 세션 (None이면 새로 생성)

    Returns:
        None

    참고:
        - 출력 직렬화 실패 시 에러 정보를 대신 저장합니다
        - 세션 소유권을 추적하여 자동으로 정리합니다
    """
    owns_session = False
    if session is None:
        maker = _get_session_maker()
        session = maker()  # type: ignore[assignment]
        owns_session = True
    try:
        values = {"status": status, "updated_at": datetime.now(UTC)}
        if output is not None:
            # JSON 호환성을 보장하기 위해 출력 직렬화
            try:
                serialized_output = serializer.serialize(output)
                values["output"] = serialized_output
            except Exception as e:
                logger.warning(f"Failed to serialize output for run {run_id}: {e}")
                values["output"] = {
                    "error": "Output serialization failed",
                    "original_type": str(type(output)),
                }
        if error is not None:
            values["error_message"] = error
        print(f"[update_run_status] updating DB run_id={run_id} status={status}")
        await session.execute(update(RunORM).where(RunORM.run_id == str(run_id)).values(**values))  # type: ignore[arg-type]
        await session.commit()
        print(f"[update_run_status] commit done run_id={run_id}")
    finally:
        # 여기서 생성한 경우에만 종료
        if owns_session:
            await session.close()  # type: ignore[func-returns-value]


@router.delete("/threads/{thread_id}/runs/{run_id}", status_code=204)
async def delete_run(
    thread_id: str,
    run_id: str,
    force: int = Query(0, ge=0, le=1, description="Force cancel active run before delete (1=yes)"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """실행 레코드 삭제

    데이터베이스에서 실행 레코드를 삭제합니다. 활성 실행에 대한 안전 장치를 제공합니다.

    동작:
    - 실행이 활성(pending/running/streaming)이고 force=0이면 409 Conflict 반환
    - force=1이고 실행이 활성이면 먼저 취소한 후 삭제 (최선 노력)
    - 성공적으로 삭제되면 항상 204 No Content 반환

    동작 흐름:
    1. 실행을 데이터베이스에서 조회
    2. 활성 실행이고 force=0이면 409 에러
    3. force=1이고 활성이면:
       - streaming_service.cancel_run() 호출
       - 백그라운드 작업 완료 대기 (최선 노력)
    4. 데이터베이스에서 레코드 삭제
    5. active_runs에서 작업 정리 및 취소

    Args:
        thread_id (str): 스레드 고유 식별자
        run_id (str): 실행 고유 식별자
        force (int): 삭제 전 활성 실행 강제 취소 (1=예, 0=아니오)
        user (User): 인증된 사용자 (의존성 주입)
        session (AsyncSession): 데이터베이스 세션 (의존성 주입)

    Returns:
        None: 204 No Content

    Raises:
        HTTPException: 실행을 찾을 수 없는 경우 (404)
        HTTPException: 활성 실행이고 force=0인 경우 (409)

    참고:
        - force=1 사용 시 주의하세요. 진행 중인 작업이 중단됩니다
        - 삭제 후 복구할 수 없습니다
    """
    print(f"[delete_run] fetch run run_id={run_id} thread_id={thread_id} user={user.identity}")
    run_orm = await session.scalar(
        select(RunORM).where(
            RunORM.run_id == str(run_id),
            RunORM.thread_id == thread_id,
            RunORM.user_id == user.identity,
        )
    )
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found")

    # 활성이고 강제가 아니면 삭제 거부
    if run_orm.status in ["pending", "running", "streaming"] and not force:
        raise HTTPException(
            status_code=409,
            detail="Run is active. Retry with force=1 to cancel and delete.",
        )

    # 강제이고 활성이면 먼저 취소
    if force and run_orm.status in ["pending", "running", "streaming"]:
        print(f"[delete_run] force-cancelling active run run_id={run_id}")
        await streaming_service.cancel_run(run_id)
        # 최선 노력: 백그라운드 작업이 정리될 때까지 대기
        task = active_runs.get(run_id)
        if task:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    # 레코드 삭제
    await session.execute(
        delete(RunORM).where(
            RunORM.run_id == str(run_id),
            RunORM.thread_id == thread_id,
            RunORM.user_id == user.identity,
        )
    )
    await session.commit()

    # 활성 작업이 있으면 정리
    task = active_runs.pop(run_id, None)
    if task and not task.done():
        task.cancel()

    # 204 No Content
    return
