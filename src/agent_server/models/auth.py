"""인증 및 사용자 컨텍스트 모델 정의

이 모듈은 Open LangGraph의 인증(Authentication) 및 권한 부여(Authorization) 시스템에서
사용되는 Pydantic 모델을 정의합니다.

주요 모델:
• User - 인증된 사용자 정보 (identity, permissions, org_id)
• AuthContext - 요청 처리 시 사용되는 인증 컨텍스트
• TokenPayload - JWT 토큰 페이로드 구조

LangGraph 통합:
- LangGraph SDK Auth 패턴과 호환되는 사용자 모델
- Runtime[Context]를 통해 그래프 노드에서 접근 가능
- 멀티테넌트 격리를 위한 org_id 지원

사용 예:
    from models.auth import User

    user = User(
        identity="user123",
        display_name="홍길동",
        permissions=["assistants:read", "threads:write"],
        org_id="org_abc"
    )
"""

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    """인증된 사용자 정보를 담는 모델

    이 모델은 인증 미들웨어가 생성하며, FastAPI 라우터와 LangGraph 그래프 노드에서
    현재 사용자의 정보에 접근할 수 있도록 합니다.

    멀티테넌트 격리:
    - org_id를 통해 조직별 데이터 격리
    - permissions를 통해 세밀한 권한 제어
    - LangGraph 체크포인트 및 저장소 접근 시 자동으로 필터링

    LangGraph Auth 연동:
    - LangGraph SDK의 Auth.types.MinimalUserDict와 호환
    - Runtime[Context]를 통해 그래프 노드에서 user.identity, user.org_id 접근 가능
    """

    identity: str  # 사용자 고유 식별자 (예: user_id, email, sub)
    display_name: str | None = None  # 사용자 표시 이름 (UI에서 사용)
    permissions: list[str] = []  # 권한 목록 (예: ["assistants:read", "threads:write"])
    org_id: str | None = None  # 조직 ID (멀티테넌트 격리용)
    is_authenticated: bool = True  # 인증 여부 (기본값 True)


class AuthContext(BaseModel):
    """요청 처리를 위한 인증 컨텍스트

    이 모델은 HTTP 요청 처리 과정에서 사용자 정보와 요청 메타데이터를
    함께 전달하기 위한 컨테이너입니다.

    사용 위치:
    - 인증 미들웨어: request.state.auth_context에 저장
    - FastAPI 의존성: get_current_user()에서 추출
    - LangGraph 설정: inject_user_context()로 config에 주입
    """

    user: User  # 인증된 사용자 정보
    request_id: str | None = None  # 요청 추적용 고유 ID (옵저빌리티)

    model_config = ConfigDict(arbitrary_types_allowed=True)  # User 객체 등 복합 타입 허용


class TokenPayload(BaseModel):
    """JWT 토큰 페이로드 구조

    이 모델은 JWT 토큰 디코딩 시 페이로드의 표준 클레임(claim)을
    검증하고 파싱하기 위해 사용됩니다.

    표준 JWT 클레임:
    - sub (subject): 사용자 식별자
    - name: 사용자 이름
    - exp (expiration): 토큰 만료 시간 (Unix timestamp)
    - iat (issued at): 토큰 발급 시간 (Unix timestamp)

    커스텀 클레임:
    - scopes: 권한 범위 목록 (예: ["read", "write"])
    - org: 조직 식별자 (멀티테넌트)

    사용 예:
        import jwt

        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        payload = TokenPayload(**decoded)
        user = User(
            identity=payload.sub,
            display_name=payload.name,
            permissions=payload.scopes,
            org_id=payload.org
        )
    """

    sub: str  # 주체 (subject) - 사용자 고유 식별자
    name: str | None = None  # 사용자 이름 (옵션)
    scopes: list[str] = []  # 권한 범위 목록 (예: ["assistants:read"])
    org: str | None = None  # 조직 ID (멀티테넌트 격리용)
    exp: int | None = None  # 만료 시간 (Unix timestamp)
    iat: int | None = None  # 발급 시간 (Unix timestamp)
