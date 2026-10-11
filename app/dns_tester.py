# -*- coding: utf-8 -*-
"""Модуль тестирования DoH-серверов и разрешения доменов через DoH/UDP."""

from __future__ import annotations

import socket
import struct
import subprocess
import urllib.request
from typing import List

AI_TARGETS = [
    {"name": "ChatGPT", "url": "https://chatgpt.com"},
    {"name": "Claude", "url": "https://claude.ai"},
    {"name": "Google AI", "url": "https://aistudio.google.com"},
]


def test_doh_target(doh_url: str, target_url: str, timeout: int = 6) -> dict:
    """Проверяет доступность сайта через конкретный DoH-сервер с помощью системного curl."""
    cmd = [
        "curl", "-s", "-L",
        "-o", "NUL" if subprocess.os.name == "nt" else "/dev/null",
        "-w", "%{http_code}|%{url_effective}|%{time_total}",
        "--connect-timeout", str(min(timeout, 4)),
        "--max-time", str(timeout),
        "--doh-url", doh_url,
        "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        target_url,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = proc.stdout.strip()
        if not out or "|" not in out:
            return {"ok": False, "msg": "Нет ответа", "latency": None}

        code_str, eff_url, time_str = out.split("|", 2)
        code = int(code_str) if code_str.isdigit() else 0
        lat = round(float(time_str) * 1000)

        # 1. ChatGPT
        if "chatgpt.com" in target_url:
            if code in (200, 301, 302, 307, 308):
                return {"ok": True, "msg": f"Доступен ({code})", "latency": lat}
            if code == 403:
                return {"ok": False, "msg": "Геоблок (403)", "latency": lat}
            return {"ok": False, "msg": f"Код {code}", "latency": lat}

        # 2. Claude AI
        if "claude.ai" in target_url:
            if "unavailable" in eff_url.lower():
                return {"ok": False, "msg": "Геоблок региона", "latency": lat}
            if code in (200, 301, 302, 307, 308):
                return {"ok": True, "msg": f"Доступен ({code})", "latency": lat}
            if code == 403:
                return {"ok": False, "msg": "Геоблок (403)", "latency": lat}
            return {"ok": False, "msg": f"Код {code}", "latency": lat}

        # 3. Google AI Studio
        if "aistudio.google.com" in target_url:
            if "available_regions" in eff_url.lower() or "region" in eff_url.lower():
                return {"ok": False, "msg": "Геоблок региона", "latency": lat}
            if code in (200, 301, 302, 307, 308):
                return {"ok": True, "msg": f"Доступен ({code})", "latency": lat}
            if code == 403:
                return {"ok": False, "msg": "Геоблок (403)", "latency": lat}
            return {"ok": False, "msg": f"Код {code}", "latency": lat}

        return {"ok": code == 200, "msg": str(code), "latency": lat}

    except subprocess.TimeoutExpired:
        return {"ok": False, "msg": "Таймаут", "latency": None}
    except Exception as exc:
        return {"ok": False, "msg": f"Ошибка: {exc}", "latency": None}


def test_doh_full(doh_url: str) -> dict:
    """Комплексная проверка: ChatGPT + Claude + Google AI.
    Считается рабочим, если открывается хотя бы один сервис.
    """
    results = {}
    latencies = []
    for tgt in AI_TARGETS:
        res = test_doh_target(doh_url, tgt["url"])
        results[tgt["name"]] = res
        if res.get("latency"):
            latencies.append(res["latency"])

    working = any(r.get("ok") for r in results.values())
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else None

    return {
        "doh_url": doh_url,
        "working": working,
        "results": results,
        "latency": avg_latency,
    }


def query_doh_ips(doh_url: str, domain: str, timeout: int = 5) -> List[str]:
    """Разрешает домен в IPv4 через DoH (RFC 8484 wireformat) без сторонних библиотек."""
    domain = domain.strip().strip(".")
    if not domain or not doh_url:
        return []

    header = struct.pack(">HHHHHH", 0x1A2B, 0x0100, 1, 0, 0, 0)
    qname = b"".join(bytes([len(p)]) + p.encode("ascii") for p in domain.split(".")) + b"\x00"
    question = qname + struct.pack(">HH", 1, 1)
    body = header + question

    req = urllib.request.Request(
        doh_url,
        data=body,
        headers={
            "Content-Type": "application/dns-message",
            "Accept": "application/dns-message",
            "User-Agent": "HostsDnsManager/2.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except Exception:
        return []

    if len(data) < 12:
        return []

    ancount = struct.unpack(">H", data[6:8])[0]
    if ancount == 0:
        return []

    offset = 12
    while offset < len(data) and data[offset] != 0:
        offset += data[offset] + 1
    offset += 5

    ips = []
    for _ in range(ancount):
        if offset >= len(data):
            break
        if data[offset] & 0xC0 == 0xC0:
            offset += 2
        else:
            while offset < len(data) and data[offset] != 0:
                offset += data[offset] + 1
            offset += 1

        if offset + 10 > len(data):
            break

        rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", data[offset:offset + 10])
        offset += 10

        if rtype == 1 and rdlen == 4 and offset + 4 <= len(data):
            ip = socket.inet_ntoa(data[offset:offset + 4])
            if ip not in ips:
                ips.append(ip)
        offset += rdlen

    return ips