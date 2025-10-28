# OpenSource LangGraph Platform 문서 가이드 (Documentation Guide)

이 문서는 OpenSource LangGraph Platform 프로젝트의 `docs/` 디렉토리에 있는 모든 문서의 역할과 사용 방법을 안내합니다.

---

## 📚 문서 개요

`docs/` 폴더는 OpenSource LangGraph Platform 프로젝트의 **모든 기술 문서와 가이드**를 포함합니다. 개발자, 기여자, 사용자가 프로젝트를 이해하고 효과적으로 작업할 수 있도록 체계적으로 구성되어 있습니다.

### 문서 디렉토리의 역할

- **학습 자료**: 신규 개발자를 위한 온보딩 가이드
- **참조 문서**: 일상적인 개발 작업을 위한 빠른 참조
- **아키텍처 가이드**: 시스템 설계 및 구조 이해
- **문제 해결**: 일반적인 문제와 해결 방법
- **실전 예제**: 구체적인 사용 사례와 코드 예제

---

## 📖 문서 목록

### 핵심 문서 (Core Documents)

| 문서 | 목적 | 대상 독자 |
|------|------|----------|
| [README.md](README.md) | 문서 허브 및 시작점 | 모든 사용자 |
| [developer-guide.md](developer-guide.md) | 개발 환경 설정 및 워크플로우 (영문) | 개발자 |
| [developer-guide-ko.md](developer-guide-ko.md) | 개발 환경 설정 및 워크플로우 (한글) | 개발자 |

### 아키텍처 & 설계 (Architecture & Design)

| 문서 | 목적 | 대상 독자 |
|------|------|----------|
| [architecture-ko.md](architecture-ko.md) | 시스템 아키텍처 상세 설명 | 개발자, 아키텍트 |

### 개발 도구 & 품질 (Development Tools & Quality)

| 문서 | 목적 | 대상 독자 |
|------|------|----------|
| [code-quality.md](code-quality.md) | 코드 품질 기준 및 도구 (영문) | 기여자, 개발자 |
| [code-quality-ko.md](code-quality-ko.md) | 코드 품질 기준 및 도구 (한글) | 기여자, 개발자 |
| [migration-cheatsheet.md](migration-cheatsheet.md) | 데이터베이스 마이그레이션 빠른 참조 (영문) | 개발자 |
| [migration-cheatsheet-ko.md](migration-cheatsheet-ko.md) | 데이터베이스 마이그레이션 빠른 참조 (한글) | 개발자 |

### 관찰성 & 모니터링 (Observability & Monitoring)

| 문서 | 목적 | 대상 독자 |
|------|------|----------|
| [langfuse-usage.md](langfuse-usage.md) | Langfuse 추적 및 관찰성 설정 (영문) | 개발자, DevOps |
| [langfuse-usage-ko.md](langfuse-usage-ko.md) | Langfuse 추적 및 관찰성 설정 (한글) | 개발자, DevOps |

### 문제 해결 & 예제 (Troubleshooting & Examples)

| 문서 | 목적 | 대상 독자 |
|------|------|----------|
| [troubleshooting-ko.md](troubleshooting-ko.md) | 일반적인 문제 및 해결 방법 | 모든 개발자 |
| [examples-ko.md](examples-ko.md) | 실전 코드 예제 및 시나리오 | 개발자, 사용자 |

---

## 🗺️ 문서 읽기 순서 (Recommended Learning Path)

### 1️⃣ 신규 개발자 (New Developers)

처음 시작하는 경우 다음 순서로 읽는 것을 추천합니다:

```
1. README.md (문서 허브 이해)
   ↓
2. developer-guide-ko.md (개발 환경 설정)
   ↓
3. code-quality-ko.md (코드 표준 이해)
   ↓
4. migration-cheatsheet-ko.md (마이그레이션 명령어 참조)
   ↓
5. examples-ko.md (실전 예제 학습)
```

**목표**: 5분 안에 개발 환경을 구축하고, 첫 API 호출을 성공시키기

### 2️⃣ 아키텍처 이해 (Architecture Understanding)

시스템 설계와 구조를 깊이 이해하고 싶은 경우:

```
1. architecture-ko.md (시스템 아키텍처)
   ↓
2. developer-guide-ko.md (개발 워크플로우)
   ↓
3. examples-ko.md (아키텍처 실전 적용)
```

**목표**: LangGraph와 FastAPI의 통합 패턴 이해하기

### 3️⃣ 기여자 (Contributors)

프로젝트에 기여하고자 하는 경우:

```
1. code-quality-ko.md (코드 품질 기준)
   ↓
2. developer-guide-ko.md (개발 워크플로우)
   ↓
3. migration-cheatsheet-ko.md (마이그레이션 작업)
   ↓
4. ../CONTRIBUTING.md (기여 가이드)
```

**목표**: PR 제출 전 모든 품질 기준 충족하기

### 4️⃣ 프로덕션 배포 (Production Deployment)

프로덕션 환경에 배포하는 경우:

```
1. developer-guide-ko.md (배포 섹션)
   ↓
2. langfuse-usage-ko.md (관찰성 설정)
   ↓
3. troubleshooting-ko.md (문제 해결)
   ↓
4. migration-cheatsheet-ko.md (마이그레이션 전략)
```

**목표**: 안전하고 모니터링 가능한 프로덕션 배포

### 5️⃣ 일상적인 개발 작업 (Daily Development)

자주 참조하게 될 문서:

- **빠른 명령어 참조**: migration-cheatsheet-ko.md
- **문제 발생 시**: troubleshooting-ko.md
- **코드 리뷰 전**: code-quality-ko.md
- **새로운 기능 구현**: examples-ko.md

---

## 🌐 한글/영어 버전 매핑 (Korean/English Version Mapping)

주요 문서에 대해 **한글과 영어 버전을 모두 제공**합니다.

### 문서 버전 대조표

| 한글 문서 | 영어 문서 | 내용 |
|-----------|-----------|------|
| [developer-guide-ko.md](developer-guide-ko.md) | [developer-guide.md](developer-guide.md) | 개발자 가이드 |
| [code-quality-ko.md](code-quality-ko.md) | [code-quality.md](code-quality.md) | 코드 품질 가이드 |
| [migration-cheatsheet-ko.md](migration-cheatsheet-ko.md) | [migration-cheatsheet.md](migration-cheatsheet.md) | 마이그레이션 치트시트 |
| [langfuse-usage-ko.md](langfuse-usage-ko.md) | [langfuse-usage.md](langfuse-usage.md) | Langfuse 사용법 |

### 한글 전용 문서 (Korean Only)

다음 문서는 현재 **한글 버전만 제공**됩니다:

- [architecture-ko.md](architecture-ko.md) - 아키텍처 가이드
- [troubleshooting-ko.md](troubleshooting-ko.md) - 문제 해결 가이드
- [examples-ko.md](examples-ko.md) - 실전 예제 가이드

### 언어 선택 가이드

- **한글이 편한 경우**: `-ko.md` 파일 사용
- **영어가 편한 경우**: 파일명에 `-ko`가 없는 영문 버전 사용

---

## 문서 템플릿 (Document Templates)

### 새 가이드 문서 템플릿

```markdown
# [문서 제목]

[간단한 소개 - 이 문서가 다루는 내용]

## 목차

- [섹션 1](#섹션-1)
- [섹션 2](#섹션-2)

---

## 섹션 1

[내용]

### 하위 섹션

[상세 내용]

```bash
# 코드 예제
```

## 섹션 2

[내용]

---

## 참고 자료

- [관련 문서 링크]
- [외부 리소스 링크]

```

### 문제 해결 문서 템플릿

```markdown
# [문제 제목]

**증상:**
```

[에러 메시지 또는 증상 설명]

```

**원인:**
- 원인 1
- 원인 2

**해결 방법:**

1. 첫 번째 해결 방법
   ```bash
   # 명령어 예제
   ```

2. 두 번째 해결 방법
   ```bash
   # 명령어 예제
   ```

**확인:**
   ```bash
   # 해결 확인 명령어
   ```

```

---

## 추가 리소스 (Additional Resources)

### 프로젝트 문서

- [메인 README](../README.md) - 프로젝트 개요
- [CLAUDE.md](../AGENTS.md) - AGENTS를 위한 프로젝트 컨텍스트

### 외부 문서

- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Alembic 마이그레이션 가이드](https://alembic.sqlalchemy.org/)
- [Agent Protocol 스펙](https://github.com/AI-Engineer-Foundation/agent-protocol)
