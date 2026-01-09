"""FederationService 유닛 테스트.

이 테스트 모듈은 Federation 서비스의 핵심 기능을 테스트합니다:
- 원격 에이전트 검색 (discover_agents)
- 스킬 기반 필터링
- 서킷 브레이커 동작

테스트 환경에서는 SSRF 검증을 mock하여 테스트 URL이 차단되지 않도록 합니다.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_server.core.resilience import CircuitBreaker, CircuitState, RetryPolicy
from agent_server.services.agent_registry_service import AgentSearchFilters
from agent_server.services.federation.federation_service import FederationService


# ──────────────────────────────────────────────────────────────────────────────
# 테스트 픽스처
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_ssrf_validation():
    """테스트 URL을 허용하기 위해 SSRF 검증을 mock합니다.

    Federation 서비스는 외부 URL에 대해 SSRF 검증을 수행합니다.
    테스트 환경에서는 가짜 URL(https://peer-one 등)을 사용하므로,
    SSRF 검증을 우회하여 테스트가 정상적으로 실행되도록 합니다.

    Yields:
        None: 컨텍스트 매니저로 사용됩니다.
    """
    with patch(
        "agent_server.services.federation.federation_service.validate_url_for_ssrf",
        side_effect=lambda url, **kwargs: url,  # URL을 그대로 반환하여 검증 통과
    ):
        yield


def _make_card(name: str, url: str, skill_id: str) -> AgentCard:
    return AgentCard(
        name=name,
        description=f"{name} description",
        url=url,
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id=skill_id,
                name=skill_id.replace("-", " ").title(),
                description=f"{skill_id} skill",
                tags=[skill_id],
            )
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )


@pytest.mark.asyncio
async def test_discover_agents_returns_remote_results(mock_ssrf_validation):
    """원격 피어에서 에이전트를 검색하여 결과를 반환하는지 테스트합니다."""
    config = {
        "federation": {
            "peers": [
                {
                    "id": "peer-1",
                    "base_url": "https://peer-one",
                    "auth_type": "bearer",
                    "auth_token": "token",
                    "timeout_ms": 5000,
                }
            ]
        }
    }
    card = _make_card("Remote Agent", "https://peer-one/a2a/remote_agent", "remote-skill")
    card_resolver = AsyncMock()
    card_resolver.get_agent_card = AsyncMock(return_value=card)

    service = FederationService(
        config_getter=lambda: config,
        card_resolver=card_resolver,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    service._fetch_peer_list = AsyncMock(
        return_value=[
            {
                "graph_id": "remote_agent",
                "endpoint_url": "https://peer-one/a2a/remote_agent",
                "agent_card_url": "https://peer-one/a2a/remote_agent/.well-known/agent-card.json",
            }
        ]
    )

    results = await service.discover_agents(AgentSearchFilters())

    assert len(results) == 1
    agent = results[0]
    assert agent.graph_id == "remote_agent"
    assert agent.name == "Remote Agent"
    assert agent.source == {"type": "remote", "peer_id": "peer-1"}


@pytest.mark.asyncio
async def test_discover_agents_filters_by_skill(mock_ssrf_validation):
    """스킬 필터를 적용하여 에이전트를 검색하는지 테스트합니다."""
    config = {
        "federation": {
            "peers": [
                {
                    "id": "peer-1",
                    "base_url": "https://peer-one",
                }
            ]
        }
    }

    async def resolve_card(base_url, **_kwargs):
        if base_url.endswith("agent_one"):
            return _make_card("Agent One", "https://peer-one/a2a/agent_one", "alpha-skill")
        return _make_card("Agent Two", "https://peer-one/a2a/agent_two", "beta-skill")

    card_resolver = AsyncMock()
    card_resolver.get_agent_card = AsyncMock(side_effect=resolve_card)

    service = FederationService(
        config_getter=lambda: config,
        card_resolver=card_resolver,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    service._fetch_peer_list = AsyncMock(
        return_value=[
            {
                "graph_id": "agent_one",
                "endpoint_url": "https://peer-one/a2a/agent_one",
            },
            {
                "graph_id": "agent_two",
                "endpoint_url": "https://peer-one/a2a/agent_two",
            },
        ]
    )

    results = await service.discover_agents(AgentSearchFilters(skills=["alpha-skill"]))

    assert len(results) == 1
    assert results[0].graph_id == "agent_one"


@pytest.mark.asyncio
async def test_discover_agents_circuit_breaker_opens():
    config = {
        "federation": {
            "peers": [
                {
                    "id": "peer-1",
                    "base_url": "http://peer-one",
                }
            ]
        }
    }

    service = FederationService(
        config_getter=lambda: config,
        card_resolver=AsyncMock(),
        retry_policy=RetryPolicy(max_attempts=1),
        breaker_factory=lambda: CircuitBreaker(failure_threshold=1, reset_timeout=60),
    )

    fetch_mock = AsyncMock(side_effect=httpx.HTTPError("boom"))
    service._fetch_peer_list = fetch_mock

    results = await service.discover_agents(AgentSearchFilters())
    assert results == []
    assert service._breakers["peer-1"].state == CircuitState.OPEN

    await service.discover_agents(AgentSearchFilters())
    assert fetch_mock.await_count == 1
