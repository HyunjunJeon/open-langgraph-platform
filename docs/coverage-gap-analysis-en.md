# Coverage Gap Analysis

> Generated on: 2025-10-27
> Baseline Coverage: 70.0%
> Target Coverage: 85%+

## Overall Summary

- **Total Coverage**: 70.0%
- **Covered Lines**: 1,697 / 2,424
- **Missed Lines**: 727
- **Coverage needed to reach target**: 15.0%p

## Improvement Targets by Priority

### 🔴 Priority 1: Critical (Coverage < 50%)

**Immediate improvement needed** - Core functionality with very low test coverage.

| File | Coverage | Missed Lines | Category | Notes |
|------|----------|-----------|----------|------|
| `health.py` | 0.0% | 74 | Core | Health check endpoint, easy to test |
| `main.py` | 0.0% | 60 | Other | App startup code, cover with integration tests |
| `streaming_service.py` | 24.4% | 121 | Service | Core of SSE streaming, needs immediate improvement |
| `runs.py` | 32.2% | 246 | API | Largest API file (1425 lines), core functionality |
| `database.py` | 35.8% | 34 | Core | Infrastructure layer, stability is crucial |
| `double_encoded_json.py` | 45.2% | 23 | Other | - |

### 🟡 Priority 2: High (Coverage 50-70%)

**Improvement recommended** - Major functionality that needs better coverage.

| File | Coverage | Missed Lines | Category |
|------|----------|-----------|----------|
| `auth_deps.py` | 52.6% | 9 | Core |

### 🟢 Priority 3: Medium (Coverage 70-80%)

**Optional improvement** - Basic coverage is secured, add edge case tests.

| File | Coverage | Missed Lines | Category |
|------|----------|-----------|----------|
| `threads.py` | 70.5% | 67 | API |
| `thread_state_service.py` | 76.3% | 14 | Service |
| `broker.py` | 76.5% | 20 | Service |
| `errors.py` | 77.8% | 2 | Model |

## Detailed Analysis: Uncovered Lines in Critical Files

### `health.py` (0.0%)

**File Path**: `src/agent_server/core/health.py`

**Stats**:
- Total Lines: 74
- Covered Lines: 0
- Missed Lines: 74

**Uncovered Line Ranges** (30 blocks):
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
- ... and 20 more blocks

### `main.py` (0.0%)

**File Path**: `src/agent_server/main.py`

**Stats**:
- Total Lines: 60
- Covered Lines: 0
- Missed Lines: 60

**Uncovered Line Ranges** (34 blocks):
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
- ... and 24 more blocks

### `streaming_service.py` (24.4%)

**File Path**: `src/agent_server/services/streaming_service.py`

**Stats**:
- Total Lines: 160
- Covered Lines: 39
- Missed Lines: 121

**Uncovered Line Ranges** (52 blocks):
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
- ... and 42 more blocks

### `runs.py` (32.2%)

**File Path**: `src/agent_server/api/runs.py`

**Stats**:
- Total Lines: 363
- Covered Lines: 117
- Missed Lines: 246

**Uncovered Line Ranges** (124 blocks):
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
- ... and 114 more blocks

### `database.py` (35.8%)

**File Path**: `src/agent_server/core/database.py`

**Stats**:
- Total Lines: 53
- Covered Lines: 19
- Missed Lines: 34

**Uncovered Line Ranges** (14 blocks):
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
- ... and 4 more blocks

## Test Writing Guide

### Priority for Critical Files

1. **runs.py** (32.2%)
   - [ ] Error handling paths
   - [ ] Streaming reconnection scenarios
   - [ ] Run cancellation and deletion flows
   - [ ] Full Human-in-the-Loop flow

2. **streaming_service.py** (24.4%)
   - [ ] SSE connection drop handling
   - [ ] Event replay logic
   - [ ] Concurrent streaming clients
   - [ ] Broker failure scenarios

3. **database.py** (35.8%)
   - [ ] Initialization failure handling
   - [ ] Connection pool exhaustion scenarios
   - [ ] LangGraph component setup failures

## Strategy to Achieve 85% Coverage

**Current**: 70.0%
**Target**: 85.0%
**Gap**: 15.0%p (364 lines)

### Phased Execution Plan

1. **Phase 1** (70% → 75%): Focus on improving Critical files
   - runs.py 50% → 70% (+20%p)
   - streaming_service.py 24% → 60% (+36%p)
   - Estimated duration: 1 week

2. **Phase 2** (75% → 80%): Improve High priority files
   - database.py 36% → 60% (+24%p)
   - threads.py 70% → 80% (+10%p)
   - Estimated duration: 1 week

3. **Phase 3** (80% → 85%): Medium files + edge cases
   - Improve all 70-80% files to 85%+
   - Strengthen edge case and error handling
   - Estimated duration: 1 week
