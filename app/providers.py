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
    "Для ИИ": {
        "Xbox DNS": {
            "ipv4": ["111.88.96.50", "111.88.96.51"],
            "ipv6": [],
            "desc": "ChatGPT и др. ИИ",
            "color": "#9c27b0",
            "doh": "https://xbox-dns.ru/dns-query",
        },
        "Xbox DNS v2": {
            "ipv4": ["87.228.47.200", "87.228.47.201"],
            "ipv6": [],
            "desc": "ChatGPT и др. ИИ",
            "color": "#7b1fa2",
            "doh": "https://xbox-dns.ru/dns-query",
        },
        "Xbox DNS (old)": {
            "ipv4": ["176.99.11.77", "80.78.247.254"],
            "ipv6": [],
            "desc": "ChatGPT и др. ИИ",
            "color": "#6d6d6d",
            "doh": "https://xbox-dns.ru/dns-query",
        },
        "Comss DNS": {
            "ipv4": ["83.220.169.155", "212.109.195.93"],
            "ipv6": [],
            "desc": "ChatGPT и др. ИИ",
            "color": "#673ab7",
            "doh": "https://dns.comss.one/dns-query",
        },
        "dns.malw.link": {
            "ipv4": ["84.21.189.133", "64.188.98.242"],
            "ipv6": ["2a12:bec4:1460:d5::2", "2a01:ecc0:2c1:2::2"],
            "desc": "ChatGPT и др. ИИ",
            "color": "#2196f3",
            "doh": "https://dns.malw.link/dns-query",
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
        if not name or (not ipv4 and not ipv6):
            continue
        group[name] = {
            "ipv4": ipv4,
            "ipv6": ipv6,
            "desc": "Пользовательский",
            "color": "#22c55e",
            "doh": str(server.get("doh") or ""),
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
