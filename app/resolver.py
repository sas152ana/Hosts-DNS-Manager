# -*- coding: utf-8 -*-
"""Резолвинг доменов в IP через DNS-over-HTTPS (DoH).

Не требует сторонних библиотек — только stdlib (urllib).
Использует JSON-API провайдеров (формат Google/Cloudflare):
    {"Status":0,"Answer":[{"name":..,"type":1,"data":"1.2.3.4"}]}
Позволяет самостоятельно заполнить каталог IP без закрытого файла оригинала.
"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request

# Типы DNS-записей
RTYPE_A = 1
RTYPE_AAAA = 28
RTYPE_CNAME = 5

# Доступные DoH-резолверы с JSON-API.
# json_header=True — нужен заголовок Accept: application/dns-json (Cloudflare-style),
# иначе эндпоинт /resolve отдаёт JSON без специального Accept.
RESOLVERS: dict[str, dict] = {
    "Cloudflare": {"url": "https://cloudflare-dns.com/dns-query", "json_header": True},
    "Google": {"url": "https://dns.google/resolve", "json_header": False},
    "Quad9": {"url": "https://dns.quad9.net:5053/dns-query", "json_header": True},
    "AdGuard": {"url": "https://dns.adguard.com/resolve", "json_header": False},
}

DEFAULT_RESOLVER = "Cloudflare"

_SSL_CTX = ssl.create_default_context()


class ResolveError(Exception):
    pass


def resolver_names() -> list[str]:
    return list(RESOLVERS.keys())


def _query(resolver: str, name: str, rtype: int, timeout: float) -> list[str]:
    cfg = RESOLVERS.get(resolver) or RESOLVERS[DEFAULT_RESOLVER]
    params = urllib.parse.urlencode({"name": name, "type": rtype})
    url = f"{cfg['url']}?{params}"
    headers = {"User-Agent": "HostsDnsManager/1.0"}
    if cfg.get("json_header"):
        headers["Accept"] = "application/dns-json"
    else:
        headers["Accept"] = "application/json"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise ResolveError(str(exc)) from exc

    try:
        data = json.loads(payload)
    except Exception as exc:
        raise ResolveError(f"некорректный ответ: {exc}") from exc

    answers = data.get("Answer") or []
    ips: list[str] = []
    for ans in answers:
        if not isinstance(ans, dict):
            continue
        if int(ans.get("type", -1)) != rtype:
            continue  # пропускаем CNAME и прочее
        value = str(ans.get("data", "")).strip().strip(".")
        if value and value not in ips:
            ips.append(value)
    return ips


def resolve_domain(
    name: str,
    resolver: str = DEFAULT_RESOLVER,
    want_ipv4: bool = True,
    want_ipv6: bool = False,
    timeout: float = 6.0,
) -> tuple[list[str], list[str]]:
    """Возвращает (ipv4[], ipv6[]) для домена."""
    name = (name or "").strip().strip(".")
    if not name:
        return [], []
    ipv4: list[str] = []
    ipv6: list[str] = []
    if want_ipv4:
        ipv4 = _query(resolver, name, RTYPE_A, timeout)
    if want_ipv6:
        ipv6 = _query(resolver, name, RTYPE_AAAA, timeout)
    return ipv4, ipv6


__all__ = [
    "RESOLVERS",
    "DEFAULT_RESOLVER",
    "ResolveError",
    "resolver_names",
    "resolve_domain",
]
