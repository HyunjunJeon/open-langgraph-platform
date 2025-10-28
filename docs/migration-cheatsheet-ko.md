# 마이그레이션 명령어 빠른 참조

> **📚 전체 문서는 [개발자 가이드](developer-guide.md)를 참조하세요**

**⚠️ 중요**: 항상 먼저 가상 환경을 활성화하세요:

```bash
source .venv/bin/activate  # Mac/Linux
# 또는 .venv/Scripts/activate  # Windows
```

## 🚀 필수 명령어

```bash
# 대기 중인 모든 마이그레이션 적용
python3 scripts/migrate.py upgrade

# 새 마이그레이션 생성
python3 scripts/migrate.py revision --autogenerate -m "Description"

# 마지막 마이그레이션 롤백
python3 scripts/migrate.py downgrade

# 마이그레이션 히스토리 확인
python3 scripts/migrate.py history

# 현재 버전 확인
python3 scripts/migrate.py current

# 데이터베이스 초기화 (⚠️ 주의: 모든 데이터 삭제됨)
python3 scripts/migrate.py reset
```

## 🛠️ 일상 워크플로우

**Docker (초보자에게 권장):**

```bash
# 모든 서비스 시작
docker compose up open-langgraph
```

**로컬 개발 환경 (고급 사용자에게 권장):**

```bash
# 개발 환경 시작
docker compose up postgres -d
python3 scripts/migrate.py upgrade
python3 run_server.py

# 데이터베이스 변경 후
python3 scripts/migrate.py revision --autogenerate -m "Add new feature"
python3 scripts/migrate.py upgrade
```

## 🔍 빠른 문제 해결

| 문제                        | 해결 방법                                |
| --------------------------- | ---------------------------------------- |
| 데이터베이스 연결 실패      | `docker compose up postgres -d`          |
| 마이그레이션 실패           | `python3 scripts/migrate.py current`     |
| 권한 거부 오류              | `chmod +x scripts/migrate.py`            |
| 데이터베이스 손상           | `python3 scripts/migrate.py reset` ⚠️    |

## 📚 추가 도움이 필요하신가요?

- **📖 [전체 개발자 가이드](developer-guide.md)** - 완전한 설정, 설명 및 문제 해결
- **🔗 [Alembic 공식 문서](https://alembic.sqlalchemy.org/)** - Alembic 공식 문서
