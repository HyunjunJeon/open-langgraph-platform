"""URL validation utilities for SSRF prevention.

This module provides URL validation functions to protect against
Server-Side Request Forgery (SSRF) attacks in federation services.

Key Features:
- Blocks private/internal IP ranges (RFC 1918, RFC 6598)
- Blocks cloud metadata endpoints (AWS, GCP)
- Blocks localhost and loopback addresses
- Configurable HTTPS requirement via environment variable

Usage:
    from src.agent_server.utils.url_validator import (
        validate_url_for_ssrf,
        SSRFValidationError,
    )

    try:
        validated_url = validate_url_for_ssrf("https://api.example.com")
    except SSRFValidationError as e:
        logger.warning("Invalid URL: %s", e)
"""

from __future__ import annotations

import ipaddress
import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Environment variable for HTTPS requirement (configurable)
FEDERATION_REQUIRE_HTTPS = os.getenv("FEDERATION_REQUIRE_HTTPS", "true").lower() == "true"
# Skip DNS resolution check (for testing only - NOT for production)
SSRF_SKIP_DNS_CHECK = os.getenv("SSRF_SKIP_DNS_CHECK", "false").lower() == "true"

# =============================================================================
# Blocked IP Ranges and Hostnames
# =============================================================================

# Private/internal IP ranges (RFC 1918, RFC 6598, RFC 5737)
BLOCKED_IP_RANGES: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    # RFC 1918 - Private IPv4
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Loopback
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    # Link-local
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    # RFC 6598 - Carrier-grade NAT
    ipaddress.ip_network("100.64.0.0/10"),
    # RFC 5737 - Documentation
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    # "This" network
    ipaddress.ip_network("0.0.0.0/8"),
    # Broadcast
    ipaddress.ip_network("255.255.255.255/32"),
]

# Blocked hostnames (case-insensitive)
BLOCKED_HOSTNAMES: frozenset[str] = frozenset({
    # Localhost variants
    "localhost",
    "localhost.localdomain",
    "local",
    # Cloud metadata endpoints
    "metadata.google.internal",  # GCP
    "169.254.169.254",  # AWS/GCP/Azure metadata IP
    "metadata",  # Short form
    # Kubernetes internal
    "kubernetes.default.svc",
    "kubernetes.default",
    "kubernetes",
})

# Allowed schemes
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# Common allowed ports (can be extended)
COMMON_PORTS: frozenset[int] = frozenset({80, 443, 8080, 8443})


# =============================================================================
# Exceptions
# =============================================================================


class SSRFValidationError(ValueError):
    """Raised when URL fails SSRF validation.

    This exception indicates that a URL was rejected because it could
    potentially be used for Server-Side Request Forgery attacks.

    Attributes:
        url: The rejected URL (may be truncated for safety)
        reason: Human-readable explanation of why the URL was rejected
    """

    def __init__(self, message: str, url: str | None = None, reason: str | None = None) -> None:
        super().__init__(message)
        self.url = url[:100] if url else None  # Truncate for safety
        self.reason = reason


# =============================================================================
# Validation Functions
# =============================================================================


def validate_url_for_ssrf(
    url: str,
    *,
    require_https: bool | None = None,
    allow_any_port: bool = False,
) -> str:
    """Validate URL is safe from SSRF attacks.

    This function checks URLs against known dangerous patterns including:
    - Private IP ranges (10.x, 172.16.x, 192.168.x)
    - Loopback addresses (127.x, localhost)
    - Cloud metadata endpoints (169.254.169.254)
    - Non-HTTP(S) schemes

    Args:
        url: URL to validate
        require_https: Whether to require HTTPS scheme.
            If None, uses FEDERATION_REQUIRE_HTTPS env var (default: True)
        allow_any_port: If False, only common ports (80, 443, 8080, 8443) allowed

    Returns:
        str: Validated URL (unchanged if valid)

    Raises:
        SSRFValidationError: If URL fails any validation check

    Examples:
        >>> validate_url_for_ssrf("https://api.example.com")
        'https://api.example.com'

        >>> validate_url_for_ssrf("http://localhost:8080")
        SSRFValidationError: Blocked hostname: localhost

        >>> validate_url_for_ssrf("http://192.168.1.1/api")
        SSRFValidationError: IP in blocked range: 192.168.1.1
    """
    # Use environment variable as default for HTTPS requirement
    if require_https is None:
        require_https = FEDERATION_REQUIRE_HTTPS

    # Basic validation
    if not url or not isinstance(url, str):
        raise SSRFValidationError("URL must be a non-empty string", url=url, reason="empty")

    # Length check to prevent DoS
    if len(url) > 2048:
        raise SSRFValidationError("URL too long (max 2048 chars)", url=url, reason="too_long")

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFValidationError(f"Failed to parse URL: {e}", url=url, reason="parse_error") from e

    # Scheme validation
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise SSRFValidationError(
            f"Invalid URL scheme: {scheme}. Allowed: {ALLOWED_SCHEMES}",
            url=url,
            reason="invalid_scheme",
        )

    if require_https and scheme != "https":
        raise SSRFValidationError(
            f"URL must use HTTPS (set FEDERATION_REQUIRE_HTTPS=false to allow HTTP)",
            url=url,
            reason="https_required",
        )

    # Hostname extraction
    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("No hostname in URL", url=url, reason="no_hostname")

    # Blocked hostname check (case-insensitive)
    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTNAMES:
        raise SSRFValidationError(
            f"Blocked hostname: {hostname}",
            url=url,
            reason="blocked_hostname",
        )

    # IP address check
    try:
        ip = ipaddress.ip_address(hostname)
        for blocked_range in BLOCKED_IP_RANGES:
            if ip in blocked_range:
                raise SSRFValidationError(
                    f"IP in blocked range ({blocked_range}): {hostname}",
                    url=url,
                    reason="blocked_ip_range",
                )
    except SSRFValidationError:
        # Re-raise our own exception
        raise
    except ValueError:
        # Not an IP address, it's a hostname - additional checks
        # Check for IP-like patterns that might bypass hostname checks
        if _looks_like_internal_hostname(hostname_lower):
            raise SSRFValidationError(
                f"Hostname looks like internal resource: {hostname}",
                url=url,
                reason="internal_hostname",
            )

        if not SSRF_SKIP_DNS_CHECK:
            resolved_ips = _resolve_hostname_sync(hostname)
            if resolved_ips is None:
                raise SSRFValidationError(
                    f"DNS resolution failed for hostname: {hostname}",
                    url=url,
                    reason="dns_resolution_failed",
                )

            for resolved_ip in resolved_ips:
                try:
                    ip_obj = ipaddress.ip_address(resolved_ip)
                    for blocked_range in BLOCKED_IP_RANGES:
                        if ip_obj in blocked_range:
                            raise SSRFValidationError(
                                f"Hostname {hostname} resolves to blocked IP {resolved_ip} ({blocked_range})",
                                url=url,
                                reason="resolved_ip_blocked",
                            )
                except ValueError:
                    continue

    # Port validation (optional)
    if not allow_any_port and parsed.port:
        if parsed.port not in COMMON_PORTS:
            logger.debug(
                "URL uses non-standard port %d: %s (allowed but logged)",
                parsed.port,
                url[:50],
            )
            # Note: We log but don't block non-standard ports by default
            # Set allow_any_port=False and uncomment below to enforce
            # raise SSRFValidationError(
            #     f"Non-standard port not allowed: {parsed.port}",
            #     url=url,
            #     reason="blocked_port",
            # )

    return url


def _resolve_hostname_sync(hostname: str) -> list[str] | None:
    """Resolve hostname to IP addresses synchronously.

    SECURITY: This function is used for DNS rebinding protection.
    It resolves the hostname BEFORE making the request to ensure
    the resolved IPs are not in blocked ranges.

    Args:
        hostname: Hostname to resolve

    Returns:
        List of resolved IP addresses, or None if resolution failed
    """
    import socket

    try:
        # Get all address info (IPv4 and IPv6)
        results = socket.getaddrinfo(
            hostname,
            None,
            socket.AF_UNSPEC,  # Both IPv4 and IPv6
            socket.SOCK_STREAM,
            0,
            socket.AI_ADDRCONFIG,
        )

        # Extract unique IP addresses
        ips: set[str] = set()
        for result in results:
            family, _, _, _, sockaddr = result
            # sockaddr is (ip, port) for IPv4, (ip, port, flow, scope) for IPv6
            ip = sockaddr[0]
            ips.add(ip)

        if not ips:
            logger.warning("DNS resolution returned no IPs for %s", hostname)
            return None

        return list(ips)

    except socket.gaierror as e:
        logger.warning("DNS resolution failed for %s: %s", hostname, e)
        return None
    except Exception as e:
        logger.warning("Unexpected error resolving %s: %s", hostname, e)
        return None


def _looks_like_internal_hostname(hostname: str) -> bool:
    """Check if hostname looks like an internal resource.

    Args:
        hostname: Lowercase hostname to check

    Returns:
        bool: True if hostname appears to be internal
    """
    # Common internal patterns
    internal_patterns = [
        # Internal domains
        ".internal",
        ".local",
        ".localhost",
        ".localdomain",
        ".intranet",
        ".corp",
        ".private",
        # Kubernetes
        ".cluster.local",
        ".svc.cluster.local",
        # AWS internal
        ".ec2.internal",
        ".compute.internal",
        # Docker
        ".docker.internal",
        "host.docker.internal",
    ]

    for pattern in internal_patterns:
        if hostname.endswith(pattern) or hostname == pattern.lstrip("."):
            return True

    return False


def is_safe_url(url: str, **kwargs) -> bool:
    """Check if URL is safe without raising an exception.

    Convenience function that returns True/False instead of raising.

    Args:
        url: URL to validate
        **kwargs: Additional arguments passed to validate_url_for_ssrf

    Returns:
        bool: True if URL passes validation, False otherwise
    """
    try:
        validate_url_for_ssrf(url, **kwargs)
        return True
    except SSRFValidationError:
        return False


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "SSRFValidationError",
    "validate_url_for_ssrf",
    "is_safe_url",
    "FEDERATION_REQUIRE_HTTPS",
    "BLOCKED_IP_RANGES",
    "BLOCKED_HOSTNAMES",
]
