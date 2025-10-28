# Open LangGraph 개발자 가이드

Open LangGraph에 오신 것을 환영합니다! 이 가이드는 데이터베이스 마이그레이션을 처음 접하는 개발자부터 숙련된 개발자까지 모두가 개발을 시작할 수 있도록 도와드립니다.

## 📋 목차

- [🚀 신규 개발자를 위한 빠른 시작](#-신규-개발자를-위한-빠른-시작)
- [✨ 코드 품질 및 표준](#-코드-품질-및-표준)
- [📚 데이터베이스 마이그레이션 이해하기](#-데이터베이스-마이그레이션-이해하기)
- [🔧 데이터베이스 마이그레이션 명령어](#-데이터베이스-마이그레이션-명령어)
- [🛠️ 개발 워크플로우](#️-개발-워크플로우)
- [📁 프로젝트 구조](#-프로젝트-구조)
- [🔍 마이그레이션 파일 이해하기](#-마이그레이션-파일-이해하기)
- [🚨 일반적인 문제 및 해결방법](#-일반적인-문제-및-해결방법)
- [🧪 변경사항 테스트하기](#-변경사항-테스트하기)
- [🚀 프로덕션 배포](#-프로덕션-배포)
- [📖 모범 사례](#-모범-사례)
- [🔗 유용한 리소스](#-유용한-리소스)
- [🆘 도움 받기](#-도움-받기)
- [📋 빠른 참조](#-빠른-참조)

## 🚀 신규 개발자를 위한 빠른 시작

### 사전 요구사항

- Python 3.11+
- Docker
- Git
- uv (Python 패키지 매니저)

### 처음 설정하기 (5분 소요)

```bash
# 1. 클론 및 설정
git clone https://github.com/HyunjunJeon/open-langgraph-platform.git
cd open-langgraph
uv install

# 2. 가상환경 활성화 (중요!)
source .venv/bin/activate  # Mac/Linux
# 또는 .venv/Scripts/activate  # Windows

# 3. 모든 것 시작하기 (데이터베이스 + 마이그레이션 + 서버)
docker compose up open-langgraph
```

🎉 **개발 준비 완료!** http://localhost:8000/docs 에서 API를 확인하세요.

## ✨ 코드 품질 및 표준

Open LangGraph는 높은 표준과 일관성을 유지하기 위해 자동화된 코드 품질 검사를 사용합니다.

### 설정

**옵션 1: Make 사용 (권장 - 자동으로 훅 설치)**
```bash
make dev-install     # 의존성 + git 훅 설치
```

**옵션 2: uv 직접 사용**
```bash
uv sync
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

훅은 커밋 전에 자동으로 코드를 검사합니다.

### 자동으로 검사되는 항목

커밋 시 다음 검사가 자동으로 실행됩니다:
- ✅ **코드 포맷팅** (Ruff) - 코드를 자동으로 포맷팅
- ✅ **린팅** (Ruff) - 코드 품질 검사
- ✅ **타입 검사** (mypy) - 타입 힌트 검증
- ✅ **보안 검사** (Bandit) - 취약점 스캔
- ✅ **커밋 메시지** - 형식 강제

### 커밋 메시지 형식

**필수 형식:** `type(scope): description`

```bash
# 좋은 예시 ✅
git commit -m "feat: add user authentication"
git commit -m "fix(api): resolve rate limiting bug"
git commit -m "docs: update installation guide"

# 나쁜 예시 ❌
git commit -m "fixed stuff"
git commit -m "WIP"
```

**타입:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`

### 유용한 명령어

```bash
make format        # 코드 자동 포맷팅
make lint          # 코드 품질 검사
make type-check    # 타입 검사 실행
make test          # 테스트 실행
make test-cov      # 커버리지와 함께 테스트
make ci-check      # 모든 CI 검사를 로컬에서 실행
```

### 커밋 전에 확인하기

```bash
# 커밋 전 빠른 검사
make format  # 문제 자동 수정
make test    # 테스트 통과 확인

# 또는 모든 것을 한 번에 실행
make ci-check
```

📖 **자세한 정보는 다음을 참조하세요**:
- [코드 품질 빠른 참조](code-quality.md) - 명령어 및 문제 해결
- [CONTRIBUTING.md](../CONTRIBUTING.md) - 완전한 기여 가이드

## 📚 데이터베이스 마이그레이션 이해하기

### 데이터베이스 마이그레이션이란?

마이그레이션은 **데이터베이스 구조를 위한 버전 관리**라고 생각하면 됩니다. 수동으로 테이블을 생성하는 대신, 다음과 같은 작업을 수행하는 스크립트를 작성합니다:

- 테이블, 컬럼, 인덱스 생성
- 순서대로 적용 가능
- 필요시 롤백 가능
- 버전 관리에서 추적됨

### Alembic을 사용하는 이유

- **업계 표준**: 대부분의 Python 프로젝트에서 사용
- **안전성**: 변경사항을 롤백할 수 있음
- **팀 친화적**: 모든 팀원이 동일한 데이터베이스 구조를 가짐
- **프로덕션 준비**: 검증된 마이그레이션 프로세스

### 한국 개발자를 위한 추가 설명

데이터베이스 마이그레이션은 코드의 Git과 같은 역할을 합니다. 개발자가 직접 SQL을 실행하여 테이블을 만들거나 수정하는 대신, 마이그레이션 파일을 통해 변경사항을 관리합니다. 이를 통해:

1. **협업이 쉬워집니다**: 팀원 모두가 같은 데이터베이스 스키마를 사용
2. **배포가 안전해집니다**: 스테이징과 프로덕션에 동일한 스키마 적용
3. **변경 이력을 추적할 수 있습니다**: 언제, 누가, 왜 변경했는지 확인 가능
4. **롤백이 가능합니다**: 문제 발생 시 이전 상태로 쉽게 복원

## 🔧 데이터베이스 마이그레이션 명령어

### 커스텀 스크립트 사용 (권장)

**⚠️ 중요**: 마이그레이션 명령을 실행하기 전에 가상환경이 활성화되어 있는지 확인하세요:

```bash
source .venv/bin/activate  # Mac/Linux
# 또는 .venv/Scripts/activate  # Windows
```

Alembic 명령을 래핑한 편리한 스크립트를 제공합니다:

```bash
# 대기 중인 모든 마이그레이션 적용
python3 scripts/migrate.py upgrade

# 새 마이그레이션 생성
python3 scripts/migrate.py revision --autogenerate -m "Add user preferences"

# 마지막 마이그레이션 롤백
python3 scripts/migrate.py downgrade

# 마이그레이션 이력 표시
python3 scripts/migrate.py history

# 현재 버전 표시
python3 scripts/migrate.py current

# 데이터베이스 리셋 (⚠️ 파괴적 - 모든 데이터 삭제)
python3 scripts/migrate.py reset
```

### Alembic 직접 사용

Alembic을 직접 사용하고 싶다면:

```bash
# 마이그레이션 적용
alembic upgrade head

# 새 마이그레이션 생성
alembic revision --autogenerate -m "Description"

# 롤백
alembic downgrade -1

# 이력 표시
alembic history
```

## 🛠️ 개발 워크플로우

### 옵션 1: Docker 개발 (초보자 권장)

```bash
# 모든 것 시작 (데이터베이스 + 마이그레이션 + 서버)
docker compose up open-langgraph

# 또는 백그라운드에서 시작
docker compose up -d open-langgraph
```

**장점:**

- ✅ 한 명령으로 모든 것 시작
- ✅ 마이그레이션 자동 실행
- ✅ 일관된 환경
- ✅ 프로덕션과 유사한 설정

### 옵션 2: 로컬 개발 (숙련된 사용자 권장)

```bash
# 1. 데이터베이스 시작
docker compose up postgres -d

# 2. 새로운 마이그레이션 적용
python3 scripts/migrate.py upgrade

# 3. 개발 서버 시작
python3 run_server.py
```

**장점:**

- ✅ 각 구성요소에 대한 완전한 제어
- ✅ 디버깅이 쉬움
- ✅ 빠른 개발 사이클
- ✅ 로그에 직접 접근

### 데이터베이스 변경하기

데이터베이스 구조를 변경해야 할 때:

```bash
# 1. 코드/모델을 변경

# 2. 마이그레이션 생성
python3 scripts/migrate.py revision --autogenerate -m "Add new feature"

# 3. 생성된 마이그레이션 파일 검토
# 확인: alembic/versions/XXXX_add_new_feature.py

# 4. 마이그레이션 적용
python3 scripts/migrate.py upgrade

# 5. 변경사항 테스트
python3 run_server.py
```

### 마이그레이션 테스트

```bash
# 업그레이드 경로 테스트
python3 scripts/migrate.py reset  # 새로 시작
python3 scripts/migrate.py upgrade  # 모두 적용

# 다운그레이드 경로 테스트
python3 scripts/migrate.py downgrade  # 하나 롤백
python3 scripts/migrate.py upgrade    # 다시 적용
```

### 한국 개발자를 위한 워크플로우 팁

**초보자**: Docker 옵션을 사용하세요. 복잡한 설정 없이 바로 개발을 시작할 수 있습니다.

**숙련자**: 로컬 개발 옵션을 사용하면 각 서비스를 개별적으로 제어할 수 있어 디버깅과 성능 최적화가 쉽습니다.

**팀 협업 시**: 항상 마이그레이션 파일을 커밋하고, pull 받은 후에는 `python3 scripts/migrate.py upgrade`를 실행하여 최신 스키마를 적용하세요.

## 📁 프로젝트 구조

```
open-langgraph/
├── alembic/                    # 데이터베이스 마이그레이션
│   ├── versions/              # 마이그레이션 파일
│   ├── env.py                 # Alembic 설정
│   └── script.py.mako         # 마이그레이션 템플릿
├── src/agent_server/          # 메인 애플리케이션 코드
│   ├── core/database.py       # 데이터베이스 연결
│   ├── api/                   # API 엔드포인트
│   └── models/                # 데이터 모델
├── scripts/
│   └── migrate.py             # 마이그레이션 헬퍼 스크립트
├── docs/
│   ├── developer-guide.md     # 원본 가이드
│   ├── developer-guide-ko.md  # 이 파일
│   └── migrations.md          # 상세 마이그레이션 문서
├── alembic.ini                # Alembic 설정
└── docker compose.yml         # 데이터베이스 설정
```

### 주요 디렉토리 설명

- **alembic/versions/**: 모든 데이터베이스 스키마 변경사항이 저장되는 곳입니다. 각 파일은 하나의 마이그레이션을 나타냅니다.
- **src/agent_server/**: 실제 애플리케이션 로직이 있는 곳입니다. API 엔드포인트, 비즈니스 로직, 데이터 모델이 여기에 있습니다.
- **scripts/**: 개발을 도와주는 유틸리티 스크립트들이 있습니다.

## 🔍 마이그레이션 파일 이해하기

### 마이그레이션 파일 구조

`alembic/versions/`의 각 마이그레이션 파일은 다음을 포함합니다:

```python
"""Add user preferences table

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # 마이그레이션 적용 시 실행됨
    op.create_table('user_preferences',
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('theme', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('user_id')
    )

def downgrade() -> None:
    # 마이그레이션 롤백 시 실행됨
    op.drop_table('user_preferences')
```

### 핵심 개념

- **Revision ID**: 마이그레이션의 고유 식별자
- **Revises**: 이전 마이그레이션을 가리킴 (연결 리스트 구조)
- **upgrade()**: 마이그레이션을 적용할 때 수행할 작업
- **downgrade()**: 마이그레이션을 롤백할 때 수행할 작업

### 한국 개발자를 위한 심화 설명

마이그레이션 파일은 **양방향 변환**을 정의합니다:
- `upgrade()`: 데이터베이스를 새 버전으로 변경
- `downgrade()`: 데이터베이스를 이전 버전으로 복원

이는 Git의 commit과 revert와 유사한 개념입니다. 각 마이그레이션은 체인처럼 연결되어 있어, Alembic은 현재 상태에서 원하는 상태까지 필요한 모든 마이그레이션을 순서대로 실행합니다.

**중요**: `downgrade()` 함수는 `upgrade()`의 정확한 역순 작업을 수행해야 합니다. 그래야 롤백이 안전하게 작동합니다.

## 🚨 일반적인 문제 및 해결방법

### Docker의 마이그레이션 문제

**문제**: Docker 컨테이너에서 마이그레이션 실패

```bash
# 해결방법: 컨테이너 로그 확인
docker compose logs open-langgraph

# 해결방법: 디버깅을 위해 수동으로 마이그레이션 실행
docker compose up postgres -d
python3 scripts/migrate.py upgrade
python3 run_server.py
```

**문제**: Docker의 데이터베이스 연결 문제

```bash
# 해결방법: 데이터베이스 준비 상태 확인
docker compose ps postgres

# 해결방법: 데이터베이스 재시작
docker compose restart postgres
```

### 데이터베이스 연결 문제

**문제**: 데이터베이스에 연결할 수 없음

```bash
# 해결방법: 데이터베이스 시작
docker compose up postgres -d
```

**문제**: 연결 오류로 마이그레이션 실패

```bash
# 해결방법: 데이터베이스 실행 중인지 확인
docker compose ps postgres

# 실행 중이 아니면 시작
docker compose up postgres -d
```

### 마이그레이션 문제

**문제**: "No such revision" 오류

```bash
# 해결방법: 현재 상태 확인
python3 scripts/migrate.py current

# 필요시 리셋 후 재적용
python3 scripts/migrate.py reset
```

**문제**: 마이그레이션 충돌

```bash
# 해결방법: 마이그레이션 이력 확인
python3 scripts/migrate.py history

# 필요시 리셋 (⚠️ 파괴적)
python3 scripts/migrate.py reset
```

### 권한 문제

**문제**: 마이그레이션 스크립트에서 "Permission denied"

```bash
# 해결방법: 스크립트를 실행 가능하게 만들기
chmod +x scripts/migrate.py
```

### 한국 개발자를 위한 추가 문제 해결

**문제**: 가상환경이 활성화되지 않아서 모듈을 찾을 수 없음

```bash
# 해결방법: 가상환경 활성화 확인
which python  # .venv/bin/python이 표시되어야 함

# 활성화되지 않았다면
source .venv/bin/activate
```

**문제**: 이전 팀원의 마이그레이션과 충돌

```bash
# 해결방법: 최신 코드를 pull하고 마이그레이션 적용
git pull
python3 scripts/migrate.py upgrade
```

## 🧪 변경사항 테스트하기

### 테스트 실행

```bash
# 모든 테스트 실행
pytest

# 특정 테스트 파일 실행
pytest tests/test_api/test_assistants.py

# 커버리지와 함께 실행
pytest --cov=src/agent_server
```

### 데이터베이스 변경사항 테스트

```bash
# 1. 테스트 마이그레이션 생성
python3 scripts/migrate.py revision --autogenerate -m "Test feature"

# 2. 적용
python3 scripts/migrate.py upgrade

# 3. 애플리케이션 테스트
python3 run_server.py

# 4. 문제가 있으면 롤백
python3 scripts/migrate.py downgrade
```

### 테스트 시 체크리스트

1. ✅ 마이그레이션이 성공적으로 적용되는가?
2. ✅ 애플리케이션이 정상적으로 시작되는가?
3. ✅ API 엔드포인트가 예상대로 작동하는가?
4. ✅ 롤백이 제대로 작동하는가?
5. ✅ 모든 단위 테스트가 통과하는가?

## 🚀 프로덕션 배포

### 배포 전 체크리스트

1. **스테이징에서 마이그레이션 테스트**:

   ```bash
   # 스테이징 데이터베이스에 적용
   python3 scripts/migrate.py upgrade
   ```

2. **프로덕션 데이터베이스 백업**:

   ```bash
   # 마이그레이션 전 항상 백업
   pg_dump your_database > backup.sql
   ```

3. **마이그레이션과 함께 배포**:
   ```bash
   # Docker가 자동으로 마이그레이션 실행
   docker compose up open-langgraph
   ```

### 모니터링

```bash
# 마이그레이션 상태 확인
python3 scripts/migrate.py current

# 마이그레이션 이력 보기
python3 scripts/migrate.py history
```

### 한국 개발자를 위한 배포 가이드

**프로덕션 배포 시 주의사항**:

1. **항상 백업을 먼저**: 데이터 손실은 복구가 어렵습니다
2. **스테이징 환경에서 먼저 테스트**: 프로덕션과 동일한 환경에서 검증
3. **배포 시간 고려**: 트래픽이 적은 시간대에 배포
4. **롤백 계획 준비**: 문제 발생 시 빠르게 복구할 수 있도록
5. **팀원에게 공지**: 배포 시간과 예상 다운타임을 미리 알림

**배포 후 확인사항**:
- 애플리케이션 정상 작동 확인
- 로그 모니터링
- 주요 API 엔드포인트 테스트
- 데이터 무결성 확인

## 📖 모범 사례

### 마이그레이션 생성

1. **가능하면 항상 autogenerate 사용**:

   ```bash
   python3 scripts/migrate.py revision --autogenerate -m "Descriptive message"
   ```

2. **생성된 마이그레이션 검토**:

   - 실행될 SQL 확인
   - 의도와 일치하는지 확인
   - 프로덕션 데이터 복사본에서 테스트

3. **설명적인 메시지 사용**:

   ```bash
   # 좋은 예
   python3 scripts/migrate.py revision --autogenerate -m "Add user preferences table"

   # 나쁜 예
   python3 scripts/migrate.py revision --autogenerate -m "fix"
   ```

### 코드 구성

1. **마이그레이션을 작게 유지**: 마이그레이션당 하나의 논리적 변경
2. **마이그레이션 테스트**: 항상 업그레이드와 다운그레이드 경로 테스트
3. **변경사항 문서화**: 명확한 마이그레이션 메시지 사용
4. **버전 관리**: 코드 변경사항과 함께 마이그레이션 파일 커밋

### 한국 개발자를 위한 추가 모범 사례

**마이그레이션 네이밍 규칙**:
- 영어로 작성하되, 의미가 명확하게
- 동사로 시작: "add", "remove", "modify", "rename"
- 예시: "add_user_avatar_column", "remove_deprecated_status_field"

**팀 협업 시**:
- 마이그레이션을 생성하기 전에 최신 코드를 pull
- PR에 마이그레이션 파일을 반드시 포함
- 리뷰 시 마이그레이션의 upgrade/downgrade 로직 확인

**데이터 마이그레이션**:
- 스키마 변경과 데이터 변경을 분리
- 대용량 데이터 변경은 별도 스크립트로 작성
- 트랜잭션 범위를 고려하여 청크 단위로 처리

## 🔗 유용한 리소스

### 공식 문서
- [Alembic 문서](https://alembic.sqlalchemy.org/)
- [SQLAlchemy 문서](https://docs.sqlalchemy.org/)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Agent Protocol 사양](https://github.com/langchain-ai/agent-protocol)

### 한국어 리소스
- [SQLAlchemy 한국어 튜토리얼](https://wikidocs.net/book/5145)
- [FastAPI 한국어 가이드](https://fastapi.tiangolo.com/ko/)
- [Docker 한국어 문서](https://docs.docker.com/language/ko/)

### 커뮤니티
- GitHub Issues: 버그 리포트 및 기능 요청
- Discussions: 일반적인 질문 및 토론
- Discord/Slack: 실시간 도움 (설정된 경우)

## 🆘 도움 받기

### 막혔을 때

1. **로그 확인**:

   ```bash
   docker compose logs postgres
   ```

2. **데이터베이스 상태 확인**:

   ```bash
   python3 scripts/migrate.py current
   python3 scripts/migrate.py history
   ```

3. **필요시 리셋** (⚠️ 파괴적):

   ```bash
   python3 scripts/migrate.py reset
   ```

4. **도움 요청**:
   - GitHub에서 기존 이슈 확인
   - 상세 정보와 함께 새 이슈 생성
   - 커뮤니티 토론에 참여

### 자주 묻는 질문

**Q: 개발을 시작할 때마다 마이그레이션을 실행해야 하나요?**
A: 새로운 마이그레이션이 있을 때만 실행하면 됩니다. Docker 설정은 자동으로 실행합니다.

**Q: 실수로 데이터베이스를 망가뜨렸다면?**
A: `python3 scripts/migrate.py reset`을 사용하여 새로 시작하세요 (⚠️ 모든 데이터 손실).

**Q: 대기 중인 마이그레이션을 어떻게 알 수 있나요?**
A: `python3 scripts/migrate.py history`를 사용하여 모든 마이그레이션과 상태를 확인하세요.

**Q: 기존 마이그레이션을 수정할 수 있나요?**
A: 일반적으로 불가능합니다 - 대신 새 마이그레이션을 생성하세요. 기존 마이그레이션 수정은 문제를 일으킬 수 있습니다.

**Q: 여러 개발자가 동시에 마이그레이션을 만들면?**
A: Git merge conflict가 발생할 수 있습니다. 이 경우 팀원과 협의하여 마이그레이션 순서를 조정하고, 필요시 하나를 재생성하세요.

**Q: 프로덕션에서 마이그레이션이 실패하면?**
A: 즉시 롤백하고, 백업에서 복원하세요. 그런 다음 스테이징 환경에서 원인을 파악하고 수정하세요.

---

🎉 **이제 Open LangGraph에 기여할 준비가 되었습니다!**

작은 변경사항부터 시작하고, 마이그레이션을 테스트하며, 도움이 필요하면 주저하지 마세요. 즐거운 코딩 되세요!

---

## 📋 빠른 참조

### 필수 명령어

```bash
# 대기 중인 모든 마이그레이션 적용
python3 scripts/migrate.py upgrade

# 새 마이그레이션 생성
python3 scripts/migrate.py revision --autogenerate -m "Description"

# 마지막 마이그레이션 롤백
python3 scripts/migrate.py downgrade

# 마이그레이션 이력 표시
python3 scripts/migrate.py history

# 현재 버전 표시
python3 scripts/migrate.py current

# 데이터베이스 리셋 (⚠️ 파괴적 - 모든 데이터 손실)
python3 scripts/migrate.py reset
```

### 일일 개발 워크플로우

**Docker (권장):**

```bash
# 모든 것 시작
docker compose up open-langgraph
```

**로컬 개발:**

```bash
# 데이터베이스 시작
docker compose up postgres -d

# 마이그레이션 적용
python3 scripts/migrate.py upgrade

# 서버 시작
python3 run_server.py
```

### 일반적인 패턴

**새 테이블 추가:**

```bash
python3 scripts/migrate.py revision --autogenerate -m "Add users table"
python3 scripts/migrate.py upgrade
```

**컬럼 추가:**

```bash
python3 scripts/migrate.py revision --autogenerate -m "Add email to users"
python3 scripts/migrate.py upgrade
```

**마이그레이션 테스트:**

```bash
python3 scripts/migrate.py reset
python3 scripts/migrate.py upgrade
```

### 문제 해결 빠른 참조

| 문제                   | 해결방법                              |
| ---------------------- | ------------------------------------- |
| 데이터베이스 연결 불가 | `docker compose up postgres -d`       |
| 마이그레이션 실패      | `python3 scripts/migrate.py current`  |
| 권한 거부됨            | `chmod +x scripts/migrate.py`         |
| 데이터베이스 손상      | `python3 scripts/migrate.py reset` ⚠️ |
| 가상환경 미활성화      | `source .venv/bin/activate`           |
| 모듈을 찾을 수 없음    | `uv install` 후 가상환경 재활성화     |

### 환경 설정

**Docker 개발 시:**

```bash
# 가상환경 활성화 (중요!)
source .venv/bin/activate  # Mac/Linux
# 또는 .venv/Scripts/activate  # Windows

# 의존성 설치
uv install

# 모든 것 시작
docker compose up open-langgraph
```

**로컬 개발 시:**

```bash
# 가상환경 활성화 (중요!)
source .venv/bin/activate  # Mac/Linux
# 또는 .venv/Scripts/activate  # Windows

# 의존성 설치
uv install

# 데이터베이스 시작
docker compose up postgres -d

# 마이그레이션 적용
python3 scripts/migrate.py upgrade
```

### 코드 품질 명령어

```bash
# 코드 포맷팅
make format

# 린트 검사
make lint

# 타입 검사
make type-check

# 보안 검사
make security

# 모든 검사 실행
make ci-check

# 테스트 실행
make test

# 커버리지와 함께 테스트
make test-cov
```

### Git 워크플로우

```bash
# 변경사항 커밋 (자동 품질 검사)
git add .
git commit -m "feat(api): add new endpoint"

# 커밋 전 수동 검사
make ci-check

# 코드 자동 수정
make format
```

### 도커 명령어

```bash
# 모든 서비스 시작
docker compose up

# 특정 서비스만 시작
docker compose up postgres -d

# 로그 보기
docker compose logs open-langgraph
docker compose logs postgres

# 서비스 재시작
docker compose restart open-langgraph

# 모든 것 중지 및 제거
docker compose down

# 볼륨까지 제거 (데이터 삭제)
docker compose down -v
```

---

## 추가 한국어 도움말

### 개발 환경 세팅 문제

**문제**: uv를 찾을 수 없음
```bash
# 해결방법: uv 설치
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**문제**: Docker Desktop이 실행되지 않음
```bash
# 해결방법: Docker Desktop 앱을 먼저 실행
# Mac: Applications에서 Docker 실행
# Windows: 시작 메뉴에서 Docker Desktop 실행
```

### 성능 최적화 팁

1. **개발 중에는 Docker 대신 로컬 실행 권장**
   - 더 빠른 피드백 루프
   - 실시간 코드 리로드

2. **데이터베이스 연결 풀 설정**
   - 환경 변수로 연결 수 조정 가능
   - 개발 시에는 작은 값 사용

3. **마이그레이션 자주 적용**
   - 작은 변경사항을 자주 마이그레이션
   - 큰 변경사항 한 번보다 안전함

### 보안 고려사항

1. **환경 변수 관리**
   - `.env` 파일을 절대 커밋하지 마세요
   - `.env.example`은 템플릿으로 제공

2. **데이터베이스 백업**
   - 로컬 개발 환경도 주기적으로 백업
   - 중요한 테스트 데이터 손실 방지

3. **인증 정보 보호**
   - 개발 환경과 프로덕션 환경의 자격 증명 분리
   - 로컬에서는 약한 비밀번호 사용 가능

이 가이드가 도움이 되셨기를 바랍니다. 궁금한 점이 있으면 언제든지 GitHub Issues에 질문해주세요!
