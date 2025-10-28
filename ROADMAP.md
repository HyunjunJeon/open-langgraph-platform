# Open LangGraph Roadmap

이 문서는 Open LangGraph 프로젝트의 방향성과 구체적인 개발 계획을 담고 있습니다.

## Vision & Mission

**Mission**: LangGraph의 강력한 기능을 벤더 종속 없이 누구나 사용할 수 있도록 한다.

**Vision**:
- 완전한 셀프 호스팅 LangGraph Platform 대안 제공
- 프로덕션 준비된 에이전트 오케스트레이션 인프라
- 개발자 친화적이고 확장 가능한 아키텍처

## Core Principles

1. **Zero Vendor Lock-in**: 모든 컴포넌트는 교체 가능해야 함
2. **Production Ready**: 엔터프라이즈 환경에서 바로 사용 가능한 품질
3. **Developer First**: 탁월한 DX(Developer Experience) 제공
4. **Open Source**: 투명성과 커뮤니티 중심 개발

---

## ✅ Completed Milestones (2025 Q3)

### Core Infrastructure
- [x] **Agent Protocol Implementation** - 공식 Agent Protocol 사양 완전 준수
- [x] **PostgreSQL Persistence** - LangGraph 공식 체크포인터/스토어 통합
- [x] **Streaming Support** - SSE 기반 실시간 스트리밍 + 재연결 지원
- [x] **Authentication Framework** - 확장 가능한 인증 시스템 (JWT/OAuth/NoAuth)
- [x] **Database Migration System** - Alembic 기반 스키마 버전 관리

### Advanced Features
- [x] **Human-in-the-Loop** - 에이전트 워크플로우에서 사용자 개입 지점 지원
- [x] **Langfuse Integration** - 선택적 관찰성 및 추적 기능
- [x] **Event Store & Replay** - 이벤트 영속화 및 재생 메커니즘

### UI Compatibility
- [x] **Agent Chat UI Support** - LangChain 공식 UI와 완전 호환
- [x] **CopilotKit Integration** - AG-UI 프로토콜 지원

### Developer Experience
- [x] **Comprehensive Documentation** - 개발자 가이드, 마이그레이션 치트시트
- [x] **Docker Compose Setup** - 5분 만에 로컬 환경 구축
- [x] **Test Suite** - 349+ 단위/통합 테스트

---

## 🚀 Current Focus (2025 Q4)

### 1. Deployment & Operations

#### Kubernetes Ready Deployment
**목표**: 프로덕션 Kubernetes 환경에서 바로 배포 가능한 구성 제공

**작업 항목**:
- [ ] Helm Chart 작성 (ConfigMap, Secret, Service, Ingress)
- [ ] Horizontal Pod Autoscaler (HPA) 설정
- [ ] Health check / Readiness probe 최적화
- [ ] Rolling update 전략 문서화
- [ ] Multi-region deployment 가이드

**왜 중요한가**: 대부분의 엔터프라이즈는 Kubernetes를 사용하며, 프로덕션 배포의 복잡성을 줄여야 함

**기술적 고려사항**:
- PostgreSQL StatefulSet vs 외부 관리형 DB
- Redis 캐싱 레이어 추가 여부
- Service Mesh (Istio/Linkerd) 호환성

#### Monitoring & Observability
**목표**: 프로덕션 운영에 필요한 메트릭 및 로깅 개선

**작업 항목**:
- [ ] Prometheus 메트릭 엔드포인트 (`/metrics`)
- [ ] Grafana 대시보드 템플릿 제공
- [ ] 구조화된 로깅 (JSON 포맷)
- [ ] OpenTelemetry 통합 (optional)
- [ ] 에러 추적 (Sentry 통합 예제)

**메트릭 종류**:
- Request latency (p50, p95, p99)
- Active threads/runs
- Database connection pool stats
- Stream event throughput
- Error rates by endpoint

### 2. Performance Optimization

#### Redis Caching Layer
**목표**: 자주 조회되는 데이터의 캐싱으로 DB 부하 감소

**작업 항목**:
- [ ] Redis client 통합 (aioredis)
- [ ] Assistant/Thread 메타데이터 캐싱
- [ ] LRU eviction 전략
- [ ] Cache invalidation 로직
- [ ] 성능 벤치마크 (before/after)

**예상 효과**:
- 메타데이터 조회 50-80% 속도 향상
- PostgreSQL 읽기 부하 30-50% 감소

#### Streaming Performance
**목표**: 대량의 동시 스트리밍 연결 처리 능력 향상

**작업 항목**:
- [ ] Connection pooling 최적화
- [ ] Backpressure 처리 개선
- [ ] Event batching 옵션
- [ ] 메모리 사용량 프로파일링
- [ ] Load testing (10k+ concurrent streams)

### 3. Developer Tooling

#### CLI Tool (`open-langgraph`)
**목표**: 개발자 생산성 향상을 위한 공식 CLI 도구

**작업 항목**:
- [ ] `olg init` - 프로젝트 스캐폴딩
- [ ] `olg graph add` - 새로운 그래프 템플릿 생성
- [ ] `olg migrate` - 마이그레이션 래퍼
- [ ] `olg deploy` - 배포 헬퍼 (Docker/K8s)
- [ ] `olg test` - 에이전트 로컬 테스팅
- [ ] `olg logs` - 실시간 로그 스트리밍

**기술 스택**: Python Click/Typer + Rich (UI)

#### VS Code Extension (Optional)
**목표**: IDE 내에서 에이전트 개발 및 디버깅

**기능**:
- Graph 시각화
- 브레이크포인트 디버깅
- 로컬 테스트 실행
- Langfuse 트레이스 연동

---

## 🎯 Near-term Goals (2026 Q1)

### 1. Advanced Agent Features

#### Custom HTTP Endpoints
**목표**: 에이전트가 임의의 HTTP 엔드포인트를 노출할 수 있도록 함

**Use Case**:
- Webhook 수신
- REST API 엔드포인트
- GraphQL 게이트웨이

**작업 항목**:
- [ ] `open_langgraph.json`에 HTTP route 정의
- [ ] FastAPI 동적 라우팅 생성
- [ ] Request validation (Pydantic)
- [ ] 에이전트로 요청 전달 메커니즘
- [ ] 문서 자동 생성 (OpenAPI)

**설정 예시**:
```json
{
  "graphs": {
    "webhook_agent": {
      "module": "./graphs/webhook.py:graph",
      "endpoints": [
        {
          "path": "/webhook/github",
          "method": "POST",
          "handler": "process_github_event"
        }
      ]
    }
  }
}
```

#### Generative UI Support
**목표**: 에이전트가 동적 UI 컴포넌트를 생성하도록 지원 (Vercel AI SDK 스타일)

**작업 항목**:
- [ ] UI 컴포넌트 메타데이터 스트리밍
- [ ] React/Vue/Svelte 렌더러 예제
- [ ] Type-safe 컴포넌트 인터페이스
- [ ] 에이전트→UI 상태 동기화

**참고**: CopilotKit의 Generative UI 패턴과 통합 가능

### 2. Multi-tenancy & Isolation

#### Organization-level Isolation
**목표**: 단일 인스턴스에서 여러 조직/팀 격리

**작업 항목**:
- [ ] Organization 모델 추가
- [ ] Row-level security (PostgreSQL)
- [ ] API Key 기반 인증
- [ ] 리소스 쿼터 (rate limiting)
- [ ] Audit logging

**데이터베이스 스키마 변경**:
```sql
ALTER TABLE assistants ADD COLUMN org_id UUID;
ALTER TABLE threads ADD COLUMN org_id UUID;
CREATE INDEX idx_org_id ON assistants(org_id);
-- RLS policies...
```

### 3. Integration Ecosystem

#### LangChain Hub Integration
**목표**: LangChain Hub에서 에이전트 템플릿 직접 가져오기

**작업 항목**:
- [ ] Hub API 클라이언트
- [ ] `olg graph import <hub-id>` 명령어
- [ ] 자동 종속성 설치
- [ ] 템플릿 버전 관리

#### Vector Database Integrations
**목표**: 주요 벡터 DB와 손쉬운 통합

**지원 예정**:
- [ ] Pinecone 설정 템플릿
- [ ] Weaviate 예제
- [ ] Qdrant 통합
- [ ] ChromaDB (로컬 개발)
- [ ] Supabase Vector

---

## 🌟 Mid-term Goals (2026 Q2-Q3)

### 1. Enterprise Features

#### RBAC (Role-Based Access Control)
**목표**: 세밀한 권한 관리

**역할 예시**:
- `admin`: 모든 작업 가능
- `developer`: 그래프 생성/수정
- `viewer`: 읽기 전용
- `api_user`: API 호출만 가능

**작업 항목**:
- [ ] 역할 및 권한 스키마
- [ ] 미들웨어 권한 체크
- [ ] UI에서 역할 관리
- [ ] 감사 로그 (누가, 언제, 무엇을)

#### SSO Integration
**목표**: 엔터프라이즈 SSO 프로바이더 지원

**지원 프로바이더**:
- [ ] Okta
- [ ] Auth0
- [ ] Azure AD
- [ ] Google Workspace
- [ ] SAML 2.0

### 2. Advanced Persistence

#### Multi-Database Support
**목표**: PostgreSQL 외 다른 DB 지원

**우선순위**:
1. [ ] MySQL/MariaDB (Alembic 마이그레이션 포팅)
2. [ ] SQLite (로컬 개발/테스트)
3. [ ] Cockroach DB (distributed SQL)

**도전 과제**: LangGraph 체크포인터는 PostgreSQL 전용 → 어댑터 레이어 필요

#### S3-Compatible Storage
**목표**: 대용량 아티팩트(파일, 이미지) 외부 저장

**작업 항목**:
- [ ] S3/MinIO 클라이언트 통합
- [ ] Presigned URL 생성
- [ ] 에이전트에서 파일 업로드/다운로드
- [ ] Lifecycle policy 관리

### 3. Developer Portal

#### Web-based Admin UI
**목표**: 코드 없이 에이전트 관리할 수 있는 웹 인터페이스

**기능**:
- [ ] 그래프 시각화 (노드/엣지)
- [ ] 실시간 실행 모니터링
- [ ] 스레드/메시지 브라우징
- [ ] 설정 변경 (JSON 에디터)
- [ ] 로그 조회 및 필터링

**기술 스택 후보**:
- Next.js + shadcn/ui
- Remix + Tailwind
- SvelteKit

---

## 🔮 Long-term Vision (2026 Q4+)

### 1. Agentic Platform

#### Agent Marketplace
**목표**: 커뮤니티가 에이전트를 공유하고 재사용할 수 있는 플랫폼

**기능**:
- 에이전트 템플릿 업로드/다운로드
- 평점 및 리뷰
- 사용량 통계
- 버전 관리

#### Federated Agents
**목표**: 에이전트가 다른 에이전트를 호출하는 분산 시스템

**Use Case**:
- 마이크로서비스 스타일의 에이전트 아키텍처
- 조직 간 에이전트 협업

### 2. AI-Powered Development

#### Auto-scaling & Cost Optimization
**목표**: ML 기반 리소스 최적화

**아이디어**:
- 사용 패턴 학습으로 자동 스케일링
- LLM 프로바이더 비용 최적화 (가장 저렴한 모델 선택)
- 캐시 hit rate 예측

#### Self-healing Infrastructure
**목표**: 장애 자동 감지 및 복구

**기능**:
- Anomaly detection (메트릭 기반)
- 자동 롤백
- Circuit breaker 패턴

### 3. Community & Ecosystem

#### Plugin System
**목표**: 타사 개발자가 기능 확장할 수 있는 플러그인 아키텍처

**예시**:
- Custom storage backends
- Alternative auth providers
- Monitoring integrations

#### Documentation Hub
**목표**: 세계적 수준의 문서 사이트

**내용**:
- 대화형 튜토리얼
- 비디오 가이드
- 커뮤니티 레시피
- API 레퍼런스 (자동 생성)

---

## 📊 Success Metrics

우리가 추적하는 지표:

### Adoption
- GitHub Stars
- Docker Hub pulls
- Weekly active deployments

### Quality
- Test coverage (목표: 90%+)
- Bug report resolution time
- Production uptime (목표: 99.9%)

### Community
- Contributors 수
- Discord/Slack 멤버
- Stack Overflow 질문/답변

### Performance
- 평균 응답 시간 (<200ms for metadata, <2s for streaming first token)
- Concurrent streams 처리량 (목표: 10k+)

---

**마지막 업데이트**: 2025년 10월
**버전**: 0.1.0
