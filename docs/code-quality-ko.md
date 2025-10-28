# 🚀 빠른 참조: 코드 품질 관리

## 신규 기여자를 위한 가이드

### 일회성 설정 (2분)

```bash
# 1. 저장소 클론
git clone https://github.com/YOUR_USERNAME/opensource-langgraph-platform.git
cd opensource-langgraph-platform

# 2. 의존성 및 후크 설치
make dev-install

# 또는 Make를 사용하지 않는 경우:
uv sync
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

### 일일 워크플로우

```bash
# 1. 브랜치 생성
git checkout -b feat/my-feature

# 2. 변경 사항 작성
# ... 파일 편집 ...

# 3. 커밋하기 전 (선택 사항이지만 권장)
make format    # 포매팅 자동 수정
make test      # 테스트 실행

# 4. 커밋 (후크가 자동으로 실행됩니다!)
git add .
git commit -m "feat: add my feature"

# 5. 푸시 및 PR 생성
git push origin feat/my-feature
```

---

## 커밋 메시지 형식

**필수 형식:** `type(scope): description`

### 빠른 예제

```bash
✅ 좋은 예:
git commit -m "feat: add user authentication"
git commit -m "fix(api): resolve rate limiting bug"
git commit -m "docs: update installation guide"
git commit -m "test: add e2e tests for threads"
git commit -m "chore: upgrade dependencies"

❌ 나쁜 예:
git commit -m "fixed stuff"
git commit -m "WIP"
git commit -m "Update"
git commit -m "changes"
```

### 타입

| 타입 | 사용 시점 | 예제 |
|------|-------------|---------|
| `feat` | 새 기능 | `feat: add OAuth login` |
| `fix` | 버그 수정 | `fix: resolve memory leak` |
| `docs` | 문서 | `docs: update API guide` |
| `style` | 포매팅 | `style: fix indentation` |
| `refactor` | 코드 재구성 | `refactor: simplify auth logic` |
| `perf` | 성능 | `perf: optimize database queries` |
| `test` | 테스트 | `test: add unit tests for auth` |
| `chore` | 유지보수 | `chore: update dependencies` |
| `ci` | CI/CD | `ci: add coverage reporting` |

### 범위 (선택사항)

영향을 받는 부분을 지정하는 데 사용:
- `api`, `auth`, `db`, `graph`, `tests`, `docs`, `ci`

---

## 커밋 시 무슨 일이 일어나나요?

```
git commit -m "feat: add feature"
         ↓
    Git 후크가 자동으로 실행됨
         ↓
┌────────────────────────────┐
│ 1. Ruff Format             │ ← 코드 포매팅
│ 2. Ruff Lint               │ ← 품질 검사
│ 3. mypy Type Check         │ ← 타입 검증
│ 4. Bandit Security         │ ← 보안 이슈 스캔
│ 5. File Checks             │ ← 파일 검증
│ 6. Commit Message Check    │ ← 형식 검증
└────────────────────────────┘
         ↓
    모두 통과? ✅
         ↓
   커밋 성공!
```

---

## 일반적인 문제 및 빠른 해결책

### ❌ "커밋 메시지 형식이 잘못되었습니다"

**오류:**
```
❌ Commit message must follow format: type(scope): description
```

**해결책:**
```bash
# 올바른 형식 사용
git commit -m "feat: add new feature"
```

### ❌ "Ruff 포매팅 실패"

**오류:**
```
❌ Files would be reformatted
```

**해결책:**
```bash
# 포매팅 자동 수정
make format

# 변경사항 스테이징
git add .

# 다시 커밋
git commit -m "feat: add feature"
```

### ❌ "린팅 오류 발견"

**오류:**
```
❌ Found 5 linting errors
```

**해결책:**
```bash
# 무엇이 잘못되었는지 확인
make lint

# 가능한 것 자동 수정
make format

# 나머지 문제 수동으로 수정
# 그런 다음 다시 커밋
```

### ❌ "타입 체크 실패"

**오류:**
```
❌ mypy found type errors
```

**해결책:**
```bash
# 구체적인 오류 확인
make type-check

# 타입 힌트 추가
def my_function(name: str) -> str:
    return f"Hello {name}"
```

---

## 긴급 상황: 후크 우회

**⚠️ 권장하지 않음** - CI에서 여전히 실패합니다!

```bash
git commit --no-verify -m "emergency fix"
```

진정한 긴급 상황에서만 사용하세요. PR은 여전히 CI를 통과해야 합니다.

---

## 푸시하기 전: 모든 검사 실행

```bash
# CI가 실행할 모든 것을 실행
make ci-check
```

다음을 실행합니다:
- ✅ 포매팅
- ✅ 린팅
- ✅ 타입 검사
- ✅ 보안 스캔
- ✅ 테스트

---

## Pull Request 체크리스트

PR 생성 전:

- [ ] Git 후크 설치됨 (`make setup-hooks`)
- [ ] 모든 커밋이 형식을 따름
- [ ] 테스트 통과 (`make test`)
- [ ] 코드 포매팅됨 (`make format`)
- [ ] 린팅 오류 없음 (`make lint`)
- [ ] PR 제목이 형식을 따름: `type: description`

---

## 사용 가능한 명령어

```bash
make help          # 모든 명령어 표시
make dev-install   # 의존성 설치
make setup-hooks   # git 후크 설치
make format        # 코드 포매팅
make lint          # 코드 품질 검사
make type-check    # 타입 검사
make security      # 보안 스캔
make test          # 테스트 실행
make test-cov      # 커버리지와 함께 테스트
make ci-check      # 모든 CI 검사 실행
make clean         # 캐시 파일 정리
```

---

## CI/CD 파이프라인

모든 푸시 및 PR은 다음을 트리거합니다:

1. **포매팅 검사** - 코드가 포매팅되어야 함
2. **린트 검사** - 품질 문제 없음
3. **타입 검사** - 타입이 유효해야 함
4. **보안 검사** - 취약점 없음
5. **테스트** - 모든 테스트가 통과해야 함
6. **커버리지** - 커버리지 보고서 생성

**매트릭스:** 테스트는 Python 3.11 및 3.12에서 실행됩니다

---

## 브랜치 보호 (관리자)

GitHub에서 `main` 브랜치에 대해 다음을 활성화하세요:

- ✅ 병합 전 상태 검사 필요
- ✅ PR 리뷰 필요 (1명 승인)
- ✅ 브랜치가 최신 상태여야 함
- ✅ 대화 해결 필요

---

## 도움 받기

1. **오류 메시지 읽기** - 무엇을 수정해야 하는지 알려줍니다
2. **ENFORCEMENT.md 확인** - 상세한 문제 해결
3. **`make ci-check` 실행** - 모든 것을 로컬에서 테스트
4. **PR 댓글에서 질문** - 관리자가 도와드립니다

---

## 왜 이것이 중요한가요

### 귀하를 위해
- ✅ 리뷰 전에 버그 포착
- ✅ 모범 사례 학습
- ✅ 더 빠른 PR 승인

### 팀을 위해
- ✅ 일관된 코드 스타일
- ✅ 더 높은 품질
- ✅ 더 적은 리뷰 시간
- ✅ 더 나은 유지보수성

---

## 빠른 시작 체크리스트

- [ ] 저장소 클론됨
- [ ] `make dev-install` 완료
- [ ] `make setup-hooks` 완료 ← **중요**
- [ ] 테스트 커밋 성공
- [ ] CONTRIBUTING.md 읽음
- [ ] 기여할 준비 완료! 🚀

---

**기억하세요:** 도구는 도와주기 위해 있습니다! 문제를 조기에 포착하여 훌륭한 코드 작성에 집중할 수 있습니다. 💪
