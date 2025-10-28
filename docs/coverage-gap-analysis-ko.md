# Coverage Gap Analysis

> 생성일: 2025-10-27
> 기준 커버리지: 70.0%
> 목표 커버리지: 85%+

## 전체 요약

- **전체 커버리지**: 70.0%
- **커버된 라인**: 1,697 / 2,424
- **누락된 라인**: 727
- **목표까지 필요한 커버리지**: 15.0%p

## 우선순위별 개선 대상

### 🔴 우선순위 1: Critical (커버리지 50% 미만)

**즉시 개선 필요** - 핵심 기능이지만 테스트 커버리지가 매우 낮음

| 파일 | 커버리지 | 누락 라인 | 카테고리 | 비고 |
|------|----------|-----------|----------|------|
| `health.py` | 0.0% | 74 | Core | 헬스체크 엔드포인트, 간단하게 테스트 가능 |
| `main.py` | 0.0% | 60 | Other | 앱 시작 코드, 통합 테스트로 커버 |
| `streaming_service.py` | 24.4% | 121 | Service | SSE 스트리밍 핵심, 즉시 개선 필요 |
| `runs.py` | 32.2% | 246 | API | 최대 API 파일 (1425 lines), 핵심 기능 |
| `database.py` | 35.8% | 34 | Core | 인프라 레이어, 안정성 중요 |
| `double_encoded_json.py` | 45.2% | 23 | Other | - |

### 🟡 우선순위 2: High (커버리지 50-70%)

**개선 권장** - 주요 기능이지만 커버리지 개선 필요

| 파일 | 커버리지 | 누락 라인 | 카테고리 |
|------|----------|-----------|----------|
| `auth_deps.py` | 52.6% | 9 | Core |

### 🟢 우선순위 3: Medium (커버리지 70-80%)

**선택적 개선** - 기본적인 커버리지는 확보, 엣지 케이스 테스트 추가

| 파일 | 커버리지 | 누락 라인 | 카테고리 |
|------|----------|-----------|----------|
| `threads.py` | 70.5% | 67 | API |
| `thread_state_service.py` | 76.3% | 14 | Service |
| `broker.py` | 76.5% | 20 | Service |
| `errors.py` | 77.8% | 2 | Model |

## 상세 분석: Critical 파일 미커버 라인

### `health.py` (0.0%)

**파일 경로**: `src/agent_server/core/health.py`

**통계**:
- 전체 라인: 74
- 커버된 라인: 0
- 누락된 라인: 74

**미커버 라인 범위** (30개 블록):
- Line 3
- Lines 5-7 (3 lines)
- Line 9
- Line 12
- Lines 15-18 (4 lines)
- Line 21
- Lines 24-27 (4 lines)
- Lines 30-31 (2 lines)
- Line 33
- Lines 41-42 (2 lines)
- ... 외 20개 블록

### `main.py` (0.0%)

**파일 경로**: `src/agent_server/main.py`

**통계**:
- 전체 라인: 60
- 커버된 라인: 0
- 누락된 라인: 60

**미커버 라인 범위** (34개 블록):
- Lines 42-47 (6 lines)
- Line 49
- Line 53
- Lines 58-61 (4 lines)
- Line 64
- Lines 66-69 (4 lines)
- Lines 71-79 (9 lines)
- Line 87
- Line 89
- Lines 92-93 (2 lines)
- ... 외 24개 블록

### `streaming_service.py` (24.4%)

**파일 경로**: `src/agent_server/services/streaming_service.py`

**통계**:
- 전체 라인: 160
- 커버된 라인: 39
- 누락된 라인: 121

**미커버 라인 범위** (52개 블록):
- Lines 135-143 (9 lines)
- Lines 173-174 (2 lines)
- Line 177
- Lines 180-181 (2 lines)
- Line 183
- Line 220
- Lines 223-224 (2 lines)
- Lines 227-229 (3 lines)
- Lines 231-232 (2 lines)
- Lines 234-235 (2 lines)
- ... 외 42개 블록

### `runs.py` (32.2%)

**파일 경로**: `src/agent_server/api/runs.py`

**통계**:
- 전체 라인: 363
- 커버된 라인: 117
- 누락된 라인: 246

**미커버 라인 범위** (124개 블록):
- Lines 95-97 (3 lines)
- Lines 99-100 (2 lines)
- Line 104
- Line 106
- Line 134
- Line 139
- Line 169
- Lines 172-175 (4 lines)
- Line 181
- Line 186
- ... 외 114개 블록

### `database.py` (35.8%)

**파일 경로**: `src/agent_server/core/database.py`

**통계**:
- 전체 라인: 53
- 커버된 라인: 19
- 누락된 라인: 34

**미커버 라인 범위** (14개 블록):
- Line 53
- Line 61
- Lines 64-66 (3 lines)
- Line 72
- Lines 80-81 (2 lines)
- Lines 84-87 (4 lines)
- Lines 89-92 (4 lines)
- Line 94
- Lines 116-119 (4 lines)
- Line 122
- ... 외 4개 블록

## 테스트 작성 가이드

### Critical 파일 우선순위

1. **runs.py** (32.2%)
   - [ ] 에러 핸들링 경로 테스트
   - [ ] 스트리밍 재연결 시나리오
   - [ ] Run 취소 및 삭제 플로우
   - [ ] Human-in-the-Loop 전체 플로우

2. **streaming_service.py** (24.4%)
   - [ ] SSE 연결 끊김 처리
   - [ ] 이벤트 재생 로직
   - [ ] 동시 스트리밍 클라이언트
   - [ ] 브로커 실패 시나리오

3. **database.py** (35.8%)
   - [ ] 초기화 실패 처리
   - [ ] 연결 풀 소진 시나리오
   - [ ] LangGraph 컴포넌트 setup 실패

## 85% 커버리지 달성 전략

**현재**: 70.0%
**목표**: 85.0%
**갭**: 15.0%p (364 lines)

### 단계별 실행 계획

1. **Phase 1** (70% → 75%): Critical 파일 집중 개선
   - runs.py 50% → 70% (+20%p)
   - streaming_service.py 24% → 60% (+36%p)
   - 예상 기간: 1주

2. **Phase 2** (75% → 80%): High 파일 개선
   - database.py 36% → 60% (+24%p)
   - threads.py 70% → 80% (+10%p)
   - 예상 기간: 1주

3. **Phase 3** (80% → 85%): Medium 파일 + 엣지 케이스
   - 모든 70-80% 파일을 85%+ 로 개선
   - 엣지 케이스 및 에러 핸들링 강화
   - 예상 기간: 1주

