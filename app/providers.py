# -*- coding: utf-8 -*-
"""Список DNS-провайдеров (варианты DNS).

Воспроизведено из zapret/src/dns/dns_providers.py — данные реальные.
Каждый провайдер: ipv4 / ipv6 / описание / цвет / DoH-шаблон.
"""

from __future__ import annotations

import copy

DNS_PROVIDERS = {
    "Популярные": {
        "Cloudflare": {
            "ipv4": ["1.1.1.1", "1.0.0.1"],
            "ipv6": ["2606:4700:4700::1111", "2606:4700:4700::1001"],
            "desc": "Быстрый и приватный",
            "color": "#f48120",
            "doh": "https://cloudflare-dns.com/dns-query",
        },
        "Google DNS": {
            "ipv4": ["8.8.8.8", "8.8.4.4"],
            "ipv6": ["2001:4860:4860::8888", "2001:4860:4860::8844"],
            "desc": "Надёжный",
            "color": "#4285f4",
            "doh": "https://dns.google/dns-query",
        },
        "Dns.SB": {
            "ipv4": ["185.222.222.222", "45.11.45.11"],
            "ipv6": ["2a09::", "2a11::"],
            "desc": "Без цензуры",
            "color": "#00bcd4",
            "doh": "https://doh.sb/dns-query",
        },
    },
    "Безопасные": {
        "Quad9": {
            "ipv4": ["9.9.9.9", "149.112.112.112"],
            "ipv6": ["2620:fe::fe", "2620:fe::9"],
            "desc": "Антивирус",
            "color": "#e91e63",
            "doh": "https://dns.quad9.net/dns-query",
        },
        "AdGuard": {
            "ipv4": ["94.140.14.14", "94.140.15.15"],
            "ipv6": ["2a10:50c0::ad1:ff", "2a10:50c0::ad2:ff"],
            "desc": "Без рекламы",
            "color": "#68bc71",
            "doh": "https://dns.adguard.com/dns-query",
        },
        "OpenDNS": {
            "ipv4": ["208.67.222.222", "208.67.220.220"],
            "ipv6": ["2620:119:35::35", "2620:119:53::53"],
            "desc": "Фильтрация",
            "color": "#ff9800",
            "doh": "https://doh.opendns.com/dns-query",
        },
        "dnsdoh.art": {
            "ipv4": ["194.180.189.33", "194.180.189.33"],
            "ipv6": [],
            "desc": "Максимальная приватность",
            "color": "#9c27b0",
            "doh": "https://dnsdoh.art:444/dns-query",
        },
    },
    "Для ИИ (SmartDNS)": {
        "DNS-AI (Рекомендуется)": {
            "ipv4": [],
            "ipv6": [],
            "desc": "Специально под ChatGPT, Claude, Gemini",
            "color": "#10a37f",
            "doh": "https://dns.dns-ai.ru/dns-query",
        },
        "GeoHide DNS": {
            "ipv4": ["194.180.189.33"],
            "ipv6": [],
            "desc": "Обход гео-блокировок ИИ",
            "color": "#0ea5e9",
            "doh": "https://dns.geohide.ru/dns-query",
        },
        "GeoHide EU Node": {
            "ipv4": [],
            "ipv6": [],
            "desc": "Европейский сервер GeoHide",
            "color": "#0284c7",
            "doh": "https://eu.geohide.ru/dns-query",
        },
        "Mafioznik DNS": {
            "ipv4": [],
            "ipv6": [],
            "desc": "Быстрый SmartDNS для нейросетей",
            "color": "#8b5cf6",
            "doh": "https://dns.mafioznik.xyz/dns-query",
        },
        "Comss DNS": {
            "ipv4": ["83.220.169.155", "212.109.195.93"],
            "ipv6": [],
            "desc": "Популярный SmartDNS (высокая нагрузка)",
            "color": "#673ab7",
            "doh": "https://dns.comss.one/dns-query",
        },
        "Xbox DNS": {
            "ipv4": ["87.228.47.200", "87.228.47.201"],
            "ipv6": [],
            "desc": "Xbox Live, Supercell и ИИ",
            "color": "#9c27b0",
            "doh": "https://xbox-dns.ru/dns-query",
        },
        "Malw DNS": {
            "ipv4": ["84.21.189.133", "64.188.98.242"],
            "ipv6": [],
            "desc": "Открытый резолвер для ИИ",
            "color": "#2196f3",
            "doh": "https://dns.malw.link/dns-query",
        },
        "Astracat DNS": {
            "ipv4": ["85.209.2.112"],
            "ipv6": [],
            "desc": "Поддержка ODoH / DoH",
            "color": "#ec4899",
            "doh": "https://dns.astracat.network/dns-query",
        },
        "Shecan (Иран)": {
            "ipv4": ["178.22.122.100", "185.51.200.2"],
            "ipv6": [],
            "desc": "Обход санкционных гео-блокировок",
            "color": "#f97316",
            "doh": "https://free.shecan.ir/dns-query",
        },
    },
}

CUSTOM_DNS_CATEGORY = "Свои DNS"


def build_dns_providers_with_custom(custom_servers: list[dict]) -> dict:
    """Добавляет пользовательские DNS-серверы отдельной категорией."""
    providers = copy.deepcopy(DNS_PROVIDERS)
    group: dict[str, dict] = {}
    for server in custom_servers or []:
        name = str(server.get("name") or "").strip()
        ipv4 = [str(x).strip() for x in server.get("ipv4", []) if str(x).strip()]
        ipv6 = [str(x).strip() for x in server.get("ipv6", []) if str(x).strip()]
        doh = str(server.get("doh") or "").strip()

        # Разрешаем сервер, если у него есть хотя бы IP или DoH URL
        if not name or (not ipv4 and not ipv6 and not doh):
            continue

        desc = "Пользовательский"
        if doh and not ipv4:
            desc = "Пользовательский (только DoH/SmartDNS)"

        group[name] = {
            "ipv4": ipv4,
            "ipv6": ipv6,
            "desc": desc,
            "color": "#22c55e",
            "doh": doh,
        }
    if group:
        providers[CUSTOM_DNS_CATEGORY] = group
    return providers


def iter_providers(providers: dict | None = None):
    """Генератор (category, name, info) по всем провайдерам."""
    src = providers if providers is not None else DNS_PROVIDERS
    for category, group in src.items():
        for name, info in group.items():
            yield category, name, info


def load_custom_servers() -> list[dict]:
    """Загружает добавленные пользователем серверы из settings.json."""
    from app.catalog import settings_path
    import json
    p = settings_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace") or "{}")
        return list(data.get("custom_dns") or [])
    except Exception:
        return []


def save_custom_server(server: dict) -> bool:
    """Сохраняет новый пользовательский DNS в settings.json."""
    from app.catalog import settings_path
    import json, os
    p = settings_path()
    try:
        data = {}
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8", errors="replace") or "{}")
        cur = list(data.get("custom_dns") or [])
        cur.append(server)
        data["custom_dns"] = cur
        os.makedirs(p.parent, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def get_all_providers_dict() -> dict:
    """Возвращает общий словарь встроенных и пользовательских провайдеров."""
    return build_dns_providers_with_custom(load_custom_servers())
