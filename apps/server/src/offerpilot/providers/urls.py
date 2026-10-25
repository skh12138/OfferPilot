import asyncio
import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from offerpilot.api.errors import DomainError

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "spm", "from"}
SENSITIVE = {"token", "access_token", "password", "session", "ticket", "auth", "code"}


def canonical_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise DomainError("invalid_url", "链接不合法", 422) from exc
    host = parts.hostname
    if (
        parts.scheme not in {"http", "https"}
        or not host
        or parts.username
        or parts.password
        or port not in {None, 80, 443}
    ):
        raise DomainError("invalid_url", "仅支持无凭据的标准 HTTP/HTTPS 链接", 422)
    if host.lower() == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise DomainError("private_url", "不能使用私有地址", 422)
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None
    if addr and not addr.is_global:
        raise DomainError("private_url", "不能使用私有地址", 422)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if any(k.lower() in SENSITIVE for k, _ in query):
        raise DomainError("sensitive_url", "请使用不包含登录令牌的通用入口", 422)
    return urlunsplit(
        (
            parts.scheme.lower(),
            host.lower() + (f":{port}" if port else ""),
            parts.path or "/",
            urlencode([(k, v) for k, v in query if k.lower() not in TRACKING]),
            "",
        )
    )


async def validate_public_dns(url: str) -> str:
    clean = canonical_url(url)
    host = urlsplit(clean).hostname
    if not host:
        raise DomainError("invalid_url", "缺少域名", 422)
    try:
        records = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise DomainError("dns_unavailable", "来源 DNS 不可用", 422) from exc
    if not records or any(not ipaddress.ip_address(r[4][0]).is_global for r in records):
        raise DomainError("private_url", "来源解析到非公网地址", 422)
    return clean
