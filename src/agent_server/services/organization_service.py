"""Organization 멀티테넌시 서비스 계층

이 모듈은 조직(Organization) 기반 멀티테넌시를 위한 비즈니스 로직을 캡슐화합니다.
RBAC(Role-Based Access Control)을 통한 멤버 관리와 API 키 관리를 제공합니다.

주요 책임:
• 조직 CRUD 및 slug 자동 생성
• 멤버 관리 (초대, 역할 변경, 제거)
• API 키 관리 (생성, 조회, 폐기)
• RBAC 기반 권한 검사

주요 구성 요소:
• OrganizationService - 조직/멤버/API 키 관리
• generate_slug() - URL 친화적 slug 생성
• generate_api_key() - 안전한 API 키 생성
• get_organization_service() - FastAPI 의존성 주입 헬퍼

사용 예:
    @router.post("/organizations")
    async def create_org(
        request: OrganizationCreate,
        service: OrganizationService = Depends(get_organization_service),
        user: User = Depends(get_current_user),
    ):
        return await service.create_organization(request, user.identity)
"""

import hashlib
import re
import secrets
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.orm import APIKey as APIKeyORM
from ..core.orm import Organization as OrganizationORM
from ..core.orm import OrganizationMember as OrganizationMemberORM
from ..core.orm import get_session
from ..models.organization import (
    APIKey,
    APIKeyCreate,
    APIKeyList,
    APIKeyWithSecret,
    Organization,
    OrganizationCreate,
    OrganizationList,
    OrganizationMember,
    OrganizationMemberCreate,
    OrganizationMemberList,
    OrganizationMemberUpdate,
    OrganizationRole,
    OrganizationUpdate,
)

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def generate_slug(name: str, max_length: int = 100) -> str:
    """이름에서 URL 친화적 slug 생성

    유니코드 문자를 ASCII로 정규화하고, 특수문자를 제거하여
    URL에서 안전하게 사용할 수 있는 slug를 생성합니다.

    변환 규칙:
    1. 유니코드 정규화 (NFKD) → ASCII 호환 문자로 변환
    2. 소문자 변환
    3. 공백/밑줄 → 하이픈
    4. 영문/숫자/하이픈 외 문자 제거
    5. 연속 하이픈 축약
    6. 앞뒤 하이픈 제거
    7. 최대 길이 제한

    Args:
        name: 원본 이름 (예: "Acme Corporation 🚀")
        max_length: 최대 slug 길이 (기본: 100)

    Returns:
        str: URL 친화적 slug (예: "acme-corporation")

    Examples:
        >>> generate_slug("Acme Corporation")
        'acme-corporation'
        >>> generate_slug("My Team 2024!")
        'my-team-2024'
        >>> generate_slug("  Multiple   Spaces  ")
        'multiple-spaces'
    """
    # 유니코드 정규화 (한글/특수문자 → ASCII 호환)
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")

    # 소문자 변환
    slug = ascii_text.lower()

    # 공백과 밑줄을 하이픈으로
    slug = re.sub(r"[\s_]+", "-", slug)

    # 영문, 숫자, 하이픈만 허용
    slug = re.sub(r"[^a-z0-9-]", "", slug)

    # 연속 하이픈 축약
    slug = re.sub(r"-+", "-", slug)

    # 앞뒤 하이픈 제거
    slug = slug.strip("-")

    # 최대 길이 제한 (하이픈에서 잘리지 않도록)
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    return slug


def generate_api_key() -> tuple[str, str, str]:
    """안전한 API 키 생성

    암호학적으로 안전한 랜덤 바이트를 사용하여 API 키를 생성합니다.
    키는 'olg_' 접두사로 시작하며, SHA-256 해시만 DB에 저장됩니다.

    Returns:
        tuple: (raw_key, key_hash, key_prefix)
            - raw_key: 전체 API 키 (사용자에게 반환)
            - key_hash: SHA-256 해시 (DB 저장용)
            - key_prefix: 표시용 접두사 (예: "olg_abc12...")

    Examples:
        >>> raw_key, key_hash, key_prefix = generate_api_key()
        >>> raw_key.startswith("olg_")
        True
        >>> len(key_prefix)
        16
    """
    # 32바이트(256비트) 랜덤 토큰 생성 (urlsafe는 base64 인코딩으로 ~43자)
    key_body = secrets.token_urlsafe(32)

    # 접두사 추가
    raw_key = f"olg_{key_body}"

    # SHA-256 해시 (저장용)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # 표시용 접두사 (처음 16자)
    key_prefix = raw_key[:16] + "..."

    return raw_key, key_hash, key_prefix


def to_organization_pydantic(row: OrganizationORM) -> Organization:
    """Organization ORM → Pydantic 변환

    Args:
        row: Organization ORM 객체

    Returns:
        Organization: Pydantic 모델
    """
    return Organization.model_validate(row, from_attributes=True)


def to_member_pydantic(row: OrganizationMemberORM) -> OrganizationMember:
    """OrganizationMember ORM → Pydantic 변환

    Args:
        row: OrganizationMember ORM 객체

    Returns:
        OrganizationMember: Pydantic 모델
    """
    return OrganizationMember(
        id=row.id,
        org_id=row.org_id,
        user_id=row.user_id,
        role=OrganizationRole(row.role),
        invited_by=row.invited_by,
        joined_at=row.joined_at,
    )


def to_api_key_pydantic(row: APIKeyORM) -> APIKey:
    """APIKey ORM → Pydantic 변환

    Args:
        row: APIKey ORM 객체

    Returns:
        APIKey: Pydantic 모델
    """
    return APIKey.model_validate(row, from_attributes=True)


class OrganizationService:
    """조직 관리 서비스

    조직의 생성, 조회, 수정, 삭제(CRUD)와 멤버/API 키 관리를 담당합니다.
    RBAC을 통해 권한 검사를 수행하며, 사용자 컨텍스트 기반으로 접근을 제어합니다.

    주요 기능:
    - 조직 CRUD (생성 시 slug 자동 생성)
    - 멤버 관리 (초대, 역할 변경, 제거)
    - API 키 관리 (생성, 조회, 폐기)
    - RBAC 권한 검사

    Attributes:
        session (AsyncSession): SQLAlchemy 비동기 세션
    """

    def __init__(self, session: AsyncSession) -> None:
        """OrganizationService 초기화

        Args:
            session (AsyncSession): 데이터베이스 세션
        """
        self.session: AsyncSession = session

    # ---------------------------------------------------------------------------
    # RBAC Helper Methods
    # ---------------------------------------------------------------------------

    async def _get_user_role(self, org_id: str, user_id: str) -> OrganizationRole | None:
        """사용자의 조직 내 역할 조회

        Args:
            org_id: 조직 ID
            user_id: 사용자 ID

        Returns:
            OrganizationRole | None: 역할 (멤버가 아니면 None)
        """
        stmt = select(OrganizationMemberORM.role).where(
            OrganizationMemberORM.org_id == org_id,
            OrganizationMemberORM.user_id == user_id,
        )
        role = await self.session.scalar(stmt)
        return OrganizationRole(role) if role else None

    async def _require_role(self, org_id: str, user_id: str, min_roles: list[OrganizationRole]) -> OrganizationRole:
        """최소 역할 요구 검사

        사용자가 지정된 역할 중 하나 이상을 가지고 있는지 확인합니다.

        Args:
            org_id: 조직 ID
            user_id: 사용자 ID
            min_roles: 허용되는 최소 역할 목록

        Returns:
            OrganizationRole: 사용자의 실제 역할

        Raises:
            HTTPException(403): 권한 부족
            HTTPException(404): 조직 멤버가 아님
        """
        role = await self._get_user_role(org_id, user_id)
        if role is None:
            raise HTTPException(404, f"Organization '{org_id}' not found or you are not a member")
        if role not in min_roles:
            raise HTTPException(403, f"Insufficient permissions. Required: {[r.value for r in min_roles]}")
        return role

    # ---------------------------------------------------------------------------
    # Organization CRUD
    # ---------------------------------------------------------------------------

    async def create_organization(self, request: OrganizationCreate, user_identity: str) -> Organization:
        """새로운 조직 생성

        조직을 생성하고 생성자를 OWNER로 자동 추가합니다.
        slug가 제공되지 않으면 name에서 자동 생성합니다.

        동작 흐름:
        1. slug 생성/검증
        2. slug 중복 검사
        3. 조직 레코드 생성
        4. 생성자를 OWNER로 멤버십 추가

        Args:
            request: 조직 생성 요청
            user_identity: 생성자 사용자 ID

        Returns:
            Organization: 생성된 조직

        Raises:
            HTTPException(409): slug 중복
        """
        # slug 생성 또는 사용자 제공 값 사용
        slug = request.slug or generate_slug(request.name)

        # 빈 slug 검사
        if not slug:
            raise HTTPException(400, "Could not generate a valid slug from the organization name")

        # slug 중복 검사
        existing = await self.session.scalar(select(OrganizationORM).where(OrganizationORM.slug == slug))
        if existing:
            raise HTTPException(409, f"Organization with slug '{slug}' already exists")

        # 조직 생성
        org_orm = OrganizationORM(
            name=request.name,
            slug=slug,
            description=request.description,
            settings=request.settings or {},
            metadata_dict=request.metadata or {},
        )
        self.session.add(org_orm)
        await self.session.commit()
        await self.session.refresh(org_orm)

        # 생성자를 OWNER로 추가
        member_orm = OrganizationMemberORM(
            org_id=org_orm.org_id,
            user_id=user_identity,
            role=OrganizationRole.OWNER.value,
            invited_by=None,  # 자기 자신
        )
        self.session.add(member_orm)
        await self.session.commit()

        return to_organization_pydantic(org_orm)

    async def get_organization(self, org_id: str, user_identity: str) -> Organization:
        """조직 조회

        사용자가 멤버인 조직만 조회할 수 있습니다.

        Args:
            org_id: 조직 ID
            user_identity: 요청자 사용자 ID

        Returns:
            Organization: 조직 정보

        Raises:
            HTTPException(404): 조직이 없거나 멤버가 아님
        """
        # 멤버십 확인
        await self._require_role(org_id, user_identity, list(OrganizationRole))

        org = await self.session.get(OrganizationORM, org_id)
        if not org:
            raise HTTPException(404, f"Organization '{org_id}' not found")

        return to_organization_pydantic(org)

    async def get_organization_by_slug(self, slug: str, user_identity: str) -> Organization:
        """slug로 조직 조회

        Args:
            slug: 조직 slug
            user_identity: 요청자 사용자 ID

        Returns:
            Organization: 조직 정보

        Raises:
            HTTPException(404): 조직이 없거나 멤버가 아님
        """
        org = await self.session.scalar(select(OrganizationORM).where(OrganizationORM.slug == slug))
        if not org:
            raise HTTPException(404, f"Organization with slug '{slug}' not found")

        # 멤버십 확인
        await self._require_role(org.org_id, user_identity, list(OrganizationRole))

        return to_organization_pydantic(org)

    async def list_user_organizations(self, user_identity: str) -> OrganizationList:
        """사용자가 속한 조직 목록 조회

        Args:
            user_identity: 사용자 ID

        Returns:
            OrganizationList: 조직 목록
        """
        # 사용자가 멤버인 조직 ID 조회
        member_stmt = select(OrganizationMemberORM.org_id).where(OrganizationMemberORM.user_id == user_identity)
        org_ids = list(await self.session.scalars(member_stmt))

        if not org_ids:
            return OrganizationList(organizations=[], total=0)

        # 조직 정보 조회
        stmt = select(OrganizationORM).where(OrganizationORM.org_id.in_(org_ids))
        orgs = await self.session.scalars(stmt)
        org_list = [to_organization_pydantic(o) for o in orgs.all()]

        return OrganizationList(organizations=org_list, total=len(org_list))

    async def update_organization(self, org_id: str, request: OrganizationUpdate, user_identity: str) -> Organization:
        """조직 정보 업데이트

        ADMIN 이상 역할이 필요합니다.

        Args:
            org_id: 조직 ID
            request: 업데이트 요청
            user_identity: 요청자 사용자 ID

        Returns:
            Organization: 업데이트된 조직

        Raises:
            HTTPException(403): 권한 부족
            HTTPException(404): 조직이 없거나 멤버가 아님
        """
        # ADMIN 이상 역할 필요
        await self._require_role(org_id, user_identity, [OrganizationRole.OWNER, OrganizationRole.ADMIN])

        org = await self.session.get(OrganizationORM, org_id)
        if not org:
            raise HTTPException(404, f"Organization '{org_id}' not found")

        # 업데이트할 값 준비
        update_values: dict[str, Any] = {"updated_at": datetime.now(UTC)}

        if request.name is not None:
            update_values["name"] = request.name
        if request.description is not None:
            update_values["description"] = request.description
        if request.settings is not None:
            # 얕은 병합
            merged_settings = {**org.settings, **request.settings}
            update_values["settings"] = merged_settings
        if request.metadata is not None:
            # 얕은 병합
            merged_metadata = {**org.metadata_dict, **request.metadata}
            update_values["metadata_dict"] = merged_metadata

        await self.session.execute(
            update(OrganizationORM).where(OrganizationORM.org_id == org_id).values(**update_values)
        )
        await self.session.commit()

        updated_org = await self.session.get(OrganizationORM, org_id)
        return to_organization_pydantic(updated_org)

    async def delete_organization(self, org_id: str, user_identity: str) -> dict:
        """조직 삭제

        OWNER 역할만 삭제할 수 있습니다.
        CASCADE로 멤버십, API 키도 함께 삭제됩니다.

        Args:
            org_id: 조직 ID
            user_identity: 요청자 사용자 ID

        Returns:
            dict: {"status": "deleted"}

        Raises:
            HTTPException(403): OWNER가 아님
            HTTPException(404): 조직이 없거나 멤버가 아님
        """
        # OWNER 역할만 허용
        await self._require_role(org_id, user_identity, [OrganizationRole.OWNER])

        org = await self.session.get(OrganizationORM, org_id)
        if not org:
            raise HTTPException(404, f"Organization '{org_id}' not found")

        await self.session.delete(org)
        await self.session.commit()

        return {"status": "deleted"}

    # ---------------------------------------------------------------------------
    # Member Management
    # ---------------------------------------------------------------------------

    async def list_members(self, org_id: str, user_identity: str) -> OrganizationMemberList:
        """조직 멤버 목록 조회

        모든 멤버가 목록을 조회할 수 있습니다.

        Args:
            org_id: 조직 ID
            user_identity: 요청자 사용자 ID

        Returns:
            OrganizationMemberList: 멤버 목록
        """
        # 멤버십 확인
        await self._require_role(org_id, user_identity, list(OrganizationRole))

        stmt = select(OrganizationMemberORM).where(OrganizationMemberORM.org_id == org_id)
        members = await self.session.scalars(stmt)
        member_list = [to_member_pydantic(m) for m in members.all()]

        return OrganizationMemberList(members=member_list, total=len(member_list))

    async def add_member(
        self, org_id: str, request: OrganizationMemberCreate, user_identity: str
    ) -> OrganizationMember:
        """조직에 멤버 추가

        ADMIN 이상 역할이 필요합니다.
        OWNER 역할 부여는 기존 OWNER만 가능합니다.

        Args:
            org_id: 조직 ID
            request: 멤버 추가 요청
            user_identity: 요청자 사용자 ID

        Returns:
            OrganizationMember: 추가된 멤버

        Raises:
            HTTPException(403): 권한 부족
            HTTPException(409): 이미 멤버임
        """
        # ADMIN 이상 역할 필요
        requester_role = await self._require_role(
            org_id, user_identity, [OrganizationRole.OWNER, OrganizationRole.ADMIN]
        )

        # OWNER 역할 부여는 OWNER만 가능
        if request.role == OrganizationRole.OWNER and requester_role != OrganizationRole.OWNER:
            raise HTTPException(403, "Only OWNER can add another OWNER")

        # 중복 멤버 검사
        existing = await self.session.scalar(
            select(OrganizationMemberORM).where(
                OrganizationMemberORM.org_id == org_id,
                OrganizationMemberORM.user_id == request.user_id,
            )
        )
        if existing:
            raise HTTPException(409, f"User '{request.user_id}' is already a member")

        # 멤버 추가
        member_orm = OrganizationMemberORM(
            org_id=org_id,
            user_id=request.user_id,
            role=request.role.value,
            invited_by=user_identity,
        )
        self.session.add(member_orm)
        await self.session.commit()
        await self.session.refresh(member_orm)

        return to_member_pydantic(member_orm)

    async def update_member_role(
        self, org_id: str, user_id: str, request: OrganizationMemberUpdate, user_identity: str
    ) -> OrganizationMember:
        """멤버 역할 변경

        ADMIN 이상 역할이 필요합니다.
        OWNER 역할 변경 관련 제약:
        - OWNER → 다른 역할: OWNER만 가능, 최소 1명 OWNER 유지 필요
        - 다른 역할 → OWNER: OWNER만 가능

        Args:
            org_id: 조직 ID
            user_id: 변경 대상 사용자 ID
            request: 역할 변경 요청
            user_identity: 요청자 사용자 ID

        Returns:
            OrganizationMember: 업데이트된 멤버

        Raises:
            HTTPException(403): 권한 부족
            HTTPException(404): 멤버가 아님
            HTTPException(400): 마지막 OWNER 강등 시도
        """
        # ADMIN 이상 역할 필요
        requester_role = await self._require_role(
            org_id, user_identity, [OrganizationRole.OWNER, OrganizationRole.ADMIN]
        )

        # 대상 멤버 조회
        member = await self.session.scalar(
            select(OrganizationMemberORM).where(
                OrganizationMemberORM.org_id == org_id,
                OrganizationMemberORM.user_id == user_id,
            )
        )
        if not member:
            raise HTTPException(404, f"Member '{user_id}' not found in organization")

        current_role = OrganizationRole(member.role)
        new_role = request.role

        # OWNER 역할 관련 검증: OWNER 변경은 OWNER만 가능
        involves_owner = current_role == OrganizationRole.OWNER or new_role == OrganizationRole.OWNER
        if involves_owner and requester_role != OrganizationRole.OWNER:
            raise HTTPException(403, "Only OWNER can change OWNER roles")

        # 마지막 OWNER 강등 방지
        if current_role == OrganizationRole.OWNER and new_role != OrganizationRole.OWNER:
            owner_count = await self.session.scalar(
                select(func.count()).where(
                    OrganizationMemberORM.org_id == org_id,
                    OrganizationMemberORM.role == OrganizationRole.OWNER.value,
                )
            )
            if owner_count <= 1:
                raise HTTPException(400, "Cannot demote the last OWNER")

        # 역할 업데이트
        await self.session.execute(
            update(OrganizationMemberORM)
            .where(
                OrganizationMemberORM.org_id == org_id,
                OrganizationMemberORM.user_id == user_id,
            )
            .values(role=new_role.value)
        )
        await self.session.commit()

        updated_member = await self.session.scalar(
            select(OrganizationMemberORM).where(
                OrganizationMemberORM.org_id == org_id,
                OrganizationMemberORM.user_id == user_id,
            )
        )
        return to_member_pydantic(updated_member)

    async def remove_member(self, org_id: str, user_id: str, user_identity: str) -> dict:
        """조직에서 멤버 제거

        ADMIN 이상 역할이 필요합니다.
        자기 자신을 제거하는 것은 허용됩니다 (탈퇴).
        마지막 OWNER는 제거할 수 없습니다.

        Args:
            org_id: 조직 ID
            user_id: 제거 대상 사용자 ID
            user_identity: 요청자 사용자 ID

        Returns:
            dict: {"status": "removed"}

        Raises:
            HTTPException(403): 권한 부족
            HTTPException(404): 멤버가 아님
            HTTPException(400): 마지막 OWNER 제거 시도
        """
        requester_role = await self._get_user_role(org_id, user_identity)
        if requester_role is None:
            raise HTTPException(404, f"Organization '{org_id}' not found or you are not a member")

        # 자기 자신 제거(탈퇴)는 항상 허용, 다른 사람 제거는 ADMIN 이상만 가능
        is_self_remove = user_id == user_identity
        has_remove_permission = requester_role in [OrganizationRole.OWNER, OrganizationRole.ADMIN]
        if not is_self_remove and not has_remove_permission:
            raise HTTPException(403, "Insufficient permissions to remove members")

        # 대상 멤버 조회
        member = await self.session.scalar(
            select(OrganizationMemberORM).where(
                OrganizationMemberORM.org_id == org_id,
                OrganizationMemberORM.user_id == user_id,
            )
        )
        if not member:
            raise HTTPException(404, f"Member '{user_id}' not found in organization")

        # OWNER 제거 검증
        if member.role == OrganizationRole.OWNER.value:
            # OWNER를 제거하려면 요청자도 OWNER여야 함
            if requester_role != OrganizationRole.OWNER and not is_self_remove:
                raise HTTPException(403, "Only OWNER can remove another OWNER")

            # 마지막 OWNER 제거 방지
            owner_count = await self.session.scalar(
                select(func.count()).where(
                    OrganizationMemberORM.org_id == org_id,
                    OrganizationMemberORM.role == OrganizationRole.OWNER.value,
                )
            )
            if owner_count <= 1:
                raise HTTPException(400, "Cannot remove the last OWNER")

        await self.session.delete(member)
        await self.session.commit()

        return {"status": "removed"}

    # ---------------------------------------------------------------------------
    # API Key Management
    # ---------------------------------------------------------------------------

    async def list_api_keys(self, org_id: str, user_identity: str) -> APIKeyList:
        """조직 API 키 목록 조회

        MEMBER 이상 역할이 필요합니다.

        Args:
            org_id: 조직 ID
            user_identity: 요청자 사용자 ID

        Returns:
            APIKeyList: API 키 목록 (raw_key 제외)
        """
        # MEMBER 이상 역할 필요
        await self._require_role(
            org_id,
            user_identity,
            [OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.MEMBER],
        )

        stmt = select(APIKeyORM).where(APIKeyORM.org_id == org_id)
        keys = await self.session.scalars(stmt)
        key_list = [to_api_key_pydantic(k) for k in keys.all()]

        return APIKeyList(api_keys=key_list, total=len(key_list))

    async def create_api_key(self, org_id: str, request: APIKeyCreate, user_identity: str) -> APIKeyWithSecret:
        """API 키 생성

        ADMIN 이상 역할이 필요합니다.
        생성된 raw_key는 이 응답에서만 확인 가능합니다.

        Args:
            org_id: 조직 ID
            request: API 키 생성 요청
            user_identity: 요청자 사용자 ID

        Returns:
            APIKeyWithSecret: 생성된 API 키 (raw_key 포함)
        """
        # ADMIN 이상 역할 필요
        await self._require_role(org_id, user_identity, [OrganizationRole.OWNER, OrganizationRole.ADMIN])

        # API 키 생성
        raw_key, key_hash, key_prefix = generate_api_key()

        # 만료 시간 계산
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.now(UTC) + timedelta(days=request.expires_in_days)

        # DB에 저장
        key_orm = APIKeyORM(
            org_id=org_id,
            name=request.name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=request.scopes,
            expires_at=expires_at,
            created_by=user_identity,
        )
        self.session.add(key_orm)
        await self.session.commit()
        await self.session.refresh(key_orm)

        # raw_key 포함하여 반환
        return APIKeyWithSecret(
            key_id=key_orm.key_id,
            org_id=key_orm.org_id,
            name=key_orm.name,
            key_prefix=key_orm.key_prefix,
            scopes=key_orm.scopes,
            expires_at=key_orm.expires_at,
            last_used_at=key_orm.last_used_at,
            created_by=key_orm.created_by,
            created_at=key_orm.created_at,
            revoked_at=key_orm.revoked_at,
            raw_key=raw_key,
        )

    async def revoke_api_key(self, org_id: str, key_id: str, user_identity: str) -> APIKey:
        """API 키 폐기

        ADMIN 이상 역할이 필요합니다.
        폐기된 키는 더 이상 인증에 사용할 수 없습니다.

        Args:
            org_id: 조직 ID
            key_id: API 키 ID
            user_identity: 요청자 사용자 ID

        Returns:
            APIKey: 폐기된 API 키

        Raises:
            HTTPException(404): API 키가 없음
            HTTPException(400): 이미 폐기됨
        """
        # ADMIN 이상 역할 필요
        await self._require_role(org_id, user_identity, [OrganizationRole.OWNER, OrganizationRole.ADMIN])

        key = await self.session.scalar(
            select(APIKeyORM).where(
                APIKeyORM.org_id == org_id,
                APIKeyORM.key_id == key_id,
            )
        )
        if not key:
            raise HTTPException(404, f"API key '{key_id}' not found")

        if key.revoked_at:
            raise HTTPException(400, "API key is already revoked")

        # 폐기 시간 기록
        await self.session.execute(
            update(APIKeyORM).where(APIKeyORM.key_id == key_id).values(revoked_at=datetime.now(UTC))
        )
        await self.session.commit()

        updated_key = await self.session.get(APIKeyORM, key_id)
        return to_api_key_pydantic(updated_key)

    async def verify_api_key(self, raw_key: str) -> tuple[str, list[str]] | None:
        """API 키 검증

        제공된 raw_key의 해시를 계산하여 DB에서 유효한 키를 찾습니다.
        유효한 키면 (org_id, scopes)를 반환하고, last_used_at을 업데이트합니다.

        Args:
            raw_key: 검증할 API 키

        Returns:
            tuple[str, list[str]] | None: (org_id, scopes) 또는 None (유효하지 않음)
        """
        # 해시 계산
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # DB에서 키 조회
        key = await self.session.scalar(select(APIKeyORM).where(APIKeyORM.key_hash == key_hash))

        if not key:
            return None

        # 폐기 여부 확인
        if key.revoked_at:
            return None

        # 만료 여부 확인
        if key.expires_at and key.expires_at < datetime.now(UTC):
            return None

        # last_used_at 업데이트
        await self.session.execute(
            update(APIKeyORM).where(APIKeyORM.key_id == key.key_id).values(last_used_at=datetime.now(UTC))
        )
        await self.session.commit()

        return (key.org_id, key.scopes)


def get_organization_service(
    session: AsyncSession = Depends(get_session),
) -> OrganizationService:
    """OrganizationService 의존성 주입 헬퍼

    FastAPI의 Depends()에서 사용되어 OrganizationService 인스턴스를 생성합니다.

    사용 예:
        @router.post("/organizations")
        async def create_org(
            request: OrganizationCreate,
            service: OrganizationService = Depends(get_organization_service),
        ):
            return await service.create_organization(request, user.identity)

    Args:
        session (AsyncSession): 데이터베이스 세션 (자동 주입)

    Returns:
        OrganizationService: OrganizationService 인스턴스
    """
    return OrganizationService(session)
