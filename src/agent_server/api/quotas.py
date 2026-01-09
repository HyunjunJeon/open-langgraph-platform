"""조직 쿼터 관리 API

이 모듈은 조직의 Rate Limit 및 리소스 쿼터를 관리하는 API를 제공합니다.

엔드포인트:
- GET  /organizations/{org_id}/quotas       - 조직 쿼터 조회
- GET  /organizations/{org_id}/quotas/usage - 조직 사용량 조회
- PUT  /organizations/{org_id}/quotas/limits - Rate Limit 업데이트

권한:
- 조회: MEMBER 이상
- 수정: ADMIN 이상
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import db_manager
from ..models.organization import OrganizationRole
from ..models.rate_limit import (
    OrgQuotaResponse,
    OrgRateLimits,
    OrgRateLimitsUpdate,
    OrgUsageStats,
)
from ..services.organization_service import OrganizationService
from ..services.quota_service import quota_service

if TYPE_CHECKING:
    from ..models.auth import User

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/organizations/{org_id}/quotas",
    tags=["Quotas"],
)


# =============================================================================
# 의존성
# =============================================================================


async def get_session() -> AsyncSession:
    """DB 세션 의존성"""
    async with db_manager.session() as session:
        yield session


async def get_current_user_from_request(
    request: "Request",  # noqa: F821
) -> User:
    """현재 사용자 의존성

    Note: Request 타입은 런타임에 주입됨
    """
    from ..core.auth_deps import get_current_user

    return get_current_user(request)


# =============================================================================
# API 엔드포인트
# =============================================================================


@router.get("", response_model=OrgQuotaResponse)
async def get_org_quotas(
    org_id: str,
    user: Annotated[User, Depends(get_current_user_from_request)],
    session: Annotated[AsyncSession, Depends(get_session)],
    include_usage: bool = True,
) -> OrgQuotaResponse:
    """조직 쿼터 조회

    조직의 Rate Limit 설정, 리소스 쿼터, 현재 사용량을 반환합니다.

    Args:
        org_id: 조직 ID
        user: 현재 사용자
        session: DB 세션
        include_usage: 사용량 포함 여부 (기본: True)

    Returns:
        조직 쿼터 응답

    Raises:
        HTTPException 403: 조직 멤버가 아닌 경우
        HTTPException 404: 조직을 찾을 수 없는 경우
    """
    # 조직 멤버십 확인
    await _require_org_membership(org_id, user.identity, session)

    return await quota_service.get_org_quota_response(
        org_id=org_id,
        include_usage=include_usage,
    )


@router.get("/usage", response_model=OrgUsageStats)
async def get_org_usage(
    org_id: str,
    user: Annotated[User, Depends(get_current_user_from_request)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrgUsageStats:
    """조직 사용량 조회

    조직의 현재 Rate Limit 사용량 통계를 반환합니다.

    Args:
        org_id: 조직 ID
        user: 현재 사용자
        session: DB 세션

    Returns:
        조직 사용량 통계

    Raises:
        HTTPException 403: 조직 멤버가 아닌 경우
        HTTPException 404: 조직을 찾을 수 없는 경우
    """
    # 조직 멤버십 확인
    await _require_org_membership(org_id, user.identity, session)

    return await quota_service.get_org_usage_stats(org_id)


@router.put("/limits", response_model=OrgRateLimits)
async def update_org_limits(
    org_id: str,
    limits: OrgRateLimitsUpdate,
    user: Annotated[User, Depends(get_current_user_from_request)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrgRateLimits:
    """조직 Rate Limit 업데이트

    조직의 Rate Limit 설정을 업데이트합니다.
    ADMIN 이상의 권한이 필요합니다.

    Args:
        org_id: 조직 ID
        limits: 업데이트할 Rate Limit 설정
        user: 현재 사용자
        session: DB 세션

    Returns:
        업데이트된 Rate Limit 설정

    Raises:
        HTTPException 403: ADMIN 권한이 없는 경우
        HTTPException 404: 조직을 찾을 수 없는 경우
    """
    # ADMIN 이상 권한 확인
    await _require_admin_role(org_id, user.identity, session)

    return await quota_service.update_org_limits(
        org_id=org_id,
        limits=limits,
        session=session,
    )


# =============================================================================
# 헬퍼 함수
# =============================================================================


async def _require_org_membership(
    org_id: str,
    user_id: str,
    session: AsyncSession,
) -> None:
    """조직 멤버십 확인

    Args:
        org_id: 조직 ID
        user_id: 사용자 ID
        session: DB 세션

    Raises:
        HTTPException 403: 조직 멤버가 아닌 경우
        HTTPException 404: 조직을 찾을 수 없는 경우
    """
    try:
        # OrganizationService를 사용하여 멤버십 확인
        org_service = OrganizationService(session)
        member = await org_service.get_member(
            org_id=org_id,
            user_id=user_id,
            requesting_user_id=user_id,
        )
        if member is None:
            raise HTTPException(
                status_code=403,
                detail="Organization membership required",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to check org membership: {e}")
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        ) from e


async def _require_admin_role(
    org_id: str,
    user_id: str,
    session: AsyncSession,
) -> None:
    """ADMIN 이상 권한 확인

    Args:
        org_id: 조직 ID
        user_id: 사용자 ID
        session: DB 세션

    Raises:
        HTTPException 403: ADMIN 권한이 없는 경우
        HTTPException 404: 조직을 찾을 수 없는 경우
    """
    try:
        org_service = OrganizationService(session)
        member = await org_service.get_member(
            org_id=org_id,
            user_id=user_id,
            requesting_user_id=user_id,
        )
        if member is None:
            raise HTTPException(
                status_code=403,
                detail="Organization membership required",
            )

        # ADMIN 또는 OWNER 권한 확인
        allowed_roles = {OrganizationRole.ADMIN, OrganizationRole.OWNER}
        if member.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="ADMIN role required to modify quotas",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to check admin role: {e}")
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        ) from e
