"""URL validator 유닛 테스트 (SSRF 보호).

이 테스트 모듈은 SSRF(Server-Side Request Forgery) 공격을 방지하기 위한
URL 검증 로직을 테스트합니다.

테스트 환경에서는 실제 DNS 조회를 수행하지 않도록 skip_dns_check fixture를
사용하여 외부 호스트명에 대한 테스트가 네트워크 환경에 의존하지 않도록 합니다.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

import src.agent_server.utils.url_validator as url_validator_module
from src.agent_server.utils.url_validator import (
    BLOCKED_HOSTNAMES,
    BLOCKED_IP_RANGES,
    SSRFValidationError,
    is_safe_url,
    validate_url_for_ssrf,
)


# ──────────────────────────────────────────────────────────────────────────────
# 테스트 픽스처
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def skip_dns_check():
    """외부 호스트명을 사용하는 테스트를 위해 DNS 해결 검사를 건너뜁니다.

    테스트 환경(CI/CD, 격리된 네트워크 등)에서는 외부 도메인에 대한
    DNS 조회가 실패할 수 있습니다. 이 픽스처는 SSRF_SKIP_DNS_CHECK
    환경 변수를 True로 설정하여 DNS 해결 단계를 건너뛰도록 합니다.

    Yields:
        tuple: (validate_url_for_ssrf, is_safe_url) 함수들을 반환합니다.
    """
    with patch.object(url_validator_module, "SSRF_SKIP_DNS_CHECK", True):
        yield url_validator_module.validate_url_for_ssrf, url_validator_module.is_safe_url


class TestValidateUrlForSSRF:
    """SSRF URL 검증 테스트.

    URL 검증 함수가 다양한 유형의 URL을 올바르게 처리하는지 확인합니다.
    외부 도메인을 사용하는 테스트는 skip_dns_check fixture를 사용하여
    네트워크 환경에 의존하지 않도록 합니다.
    """

    # ==================== 유효한 URL 테스트 ====================

    def test_valid_https_url(self, skip_dns_check) -> None:
        """HTTPS URL이 검증을 통과해야 합니다."""
        validate_func, _ = skip_dns_check
        url = "https://api.example.com/v1/agents"
        result = validate_func(url)
        assert result == url

    def test_valid_https_with_port(self, skip_dns_check) -> None:
        """표준 포트를 가진 HTTPS URL이 통과해야 합니다."""
        validate_func, _ = skip_dns_check
        assert validate_func("https://api.example.com:443/path")
        assert validate_func("https://api.example.com:8443/path")

    def test_valid_http_when_allowed(self, skip_dns_check) -> None:
        """require_https=False일 때 HTTP URL이 통과해야 합니다."""
        validate_func, _ = skip_dns_check
        url = "http://api.example.com/v1/agents"
        result = validate_func(url, require_https=False)
        assert result == url

    # ==================== Blocked Hostnames ====================

    def test_blocks_localhost(self) -> None:
        """Should block localhost."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_url_for_ssrf("https://localhost:8080/api", require_https=False)
        assert "Blocked hostname" in str(exc_info.value)
        assert exc_info.value.reason == "blocked_hostname"

    def test_blocks_localhost_variants(self) -> None:
        """Should block localhost variants."""
        localhost_urls = [
            "http://localhost/api",
            "http://localhost.localdomain/api",
            "http://local/api",
        ]
        for url in localhost_urls:
            with pytest.raises(SSRFValidationError):
                validate_url_for_ssrf(url, require_https=False)

    def test_blocks_metadata_endpoint(self) -> None:
        """Should block cloud metadata endpoints."""
        metadata_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
        ]
        for url in metadata_urls:
            with pytest.raises(SSRFValidationError):
                validate_url_for_ssrf(url, require_https=False)

    # ==================== Blocked IP Ranges ====================

    def test_blocks_private_ip_10_range(self) -> None:
        """Should block 10.0.0.0/8 private IPs."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_url_for_ssrf("http://10.0.0.1/api", require_https=False)
        assert "blocked range" in str(exc_info.value).lower()

    def test_blocks_private_ip_172_range(self) -> None:
        """Should block 172.16.0.0/12 private IPs."""
        with pytest.raises(SSRFValidationError):
            validate_url_for_ssrf("http://172.16.0.1/api", require_https=False)

    def test_blocks_private_ip_192_range(self) -> None:
        """Should block 192.168.0.0/16 private IPs."""
        with pytest.raises(SSRFValidationError):
            validate_url_for_ssrf("http://192.168.1.1/api", require_https=False)

    def test_blocks_loopback(self) -> None:
        """Should block 127.0.0.0/8 loopback IPs."""
        with pytest.raises(SSRFValidationError):
            validate_url_for_ssrf("http://127.0.0.1/api", require_https=False)
        with pytest.raises(SSRFValidationError):
            validate_url_for_ssrf("http://127.0.0.2/api", require_https=False)

    def test_blocks_link_local(self) -> None:
        """Should block 169.254.0.0/16 link-local IPs."""
        with pytest.raises(SSRFValidationError):
            validate_url_for_ssrf("http://169.254.1.1/api", require_https=False)

    # ==================== Scheme Validation ====================

    def test_blocks_non_http_schemes(self) -> None:
        """Should block non-HTTP schemes."""
        invalid_urls = [
            "ftp://example.com/file",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
        ]
        for url in invalid_urls:
            with pytest.raises(SSRFValidationError) as exc_info:
                validate_url_for_ssrf(url, require_https=False)
            assert "scheme" in str(exc_info.value).lower()

    def test_requires_https_by_default(self) -> None:
        """Should require HTTPS by default."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_url_for_ssrf("http://api.example.com/v1")
        assert "HTTPS" in str(exc_info.value)
        assert exc_info.value.reason == "https_required"

    # ==================== URL Structure ====================

    def test_blocks_empty_url(self) -> None:
        """Should block empty URLs."""
        with pytest.raises(SSRFValidationError):
            validate_url_for_ssrf("")

    def test_blocks_url_without_hostname(self) -> None:
        """Should block URLs without hostname."""
        with pytest.raises(SSRFValidationError):
            validate_url_for_ssrf("https:///path")

    def test_blocks_very_long_url(self) -> None:
        """Should block excessively long URLs."""
        long_url = "https://example.com/" + "a" * 3000
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_url_for_ssrf(long_url)
        assert exc_info.value.reason == "too_long"

    # ==================== Internal Hostname Patterns ====================

    def test_blocks_internal_domain_patterns(self) -> None:
        """Should block internal domain patterns."""
        internal_urls = [
            "http://api.internal/service",
            "http://app.local/api",
            "http://host.docker.internal:8080",
            "http://service.cluster.local/api",
        ]
        for url in internal_urls:
            with pytest.raises(SSRFValidationError):
                validate_url_for_ssrf(url, require_https=False)

    # ==================== 환경 변수 테스트 ====================

    def test_respects_https_env_var_false(self) -> None:
        """FEDERATION_REQUIRE_HTTPS=false 환경 변수를 존중해야 합니다.

        이 테스트는 환경 변수 변경을 위해 모듈을 다시 로드합니다.
        DNS 검사도 건너뛰도록 SSRF_SKIP_DNS_CHECK도 함께 설정합니다.
        """
        env_vars = {
            "FEDERATION_REQUIRE_HTTPS": "false",
            "SSRF_SKIP_DNS_CHECK": "true",  # DNS 검사 건너뛰기
        }
        with patch.dict(os.environ, env_vars):
            # 환경 변수 변경을 적용하기 위해 모듈 다시 로드
            from importlib import reload

            import src.agent_server.utils.url_validator as module

            reload(module)
            try:
                # 이제 HTTP가 허용되어야 함
                result = module.validate_url_for_ssrf("http://api.example.com")
                assert result == "http://api.example.com"
            finally:
                # 기본값으로 복원
                reload(module)


class TestIsSafeUrl:
    """is_safe_url 편의 함수 테스트."""

    def test_returns_true_for_valid_url(self, skip_dns_check) -> None:
        """유효한 URL에 대해 True를 반환해야 합니다."""
        _, is_safe_func = skip_dns_check
        assert is_safe_func("https://api.example.com") is True

    def test_returns_false_for_blocked_url(self) -> None:
        """Should return False for blocked URLs."""
        assert is_safe_url("http://localhost") is False
        assert is_safe_url("http://192.168.1.1") is False
        assert is_safe_url("http://169.254.169.254") is False


class TestSSRFValidationError:
    """Test SSRFValidationError exception."""

    def test_truncates_url_in_exception(self) -> None:
        """Should truncate long URLs in exception."""
        long_url = "https://example.com/" + "a" * 200
        error = SSRFValidationError("Test error", url=long_url, reason="test")
        assert len(error.url or "") <= 100

    def test_stores_reason(self) -> None:
        """Should store reason in exception."""
        error = SSRFValidationError("Test error", reason="blocked_ip_range")
        assert error.reason == "blocked_ip_range"
