# -*- coding: utf-8 -*-
"""Принудительная смена DNS на сетевых адаптерах (Windows).

Оригинал (zapret) меняет DNS через WinAPI SetInterfaceDnsSettings. Здесь для
простоты и надёжности используется штатный netsh (тот же результат).
На не-Windows методы возвращают понятные сообщения-заглушки.
"""

from __future__ import annotations

import os
import re
import subprocess

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class DnsResult:
    def __init__(self, success: bool, message: str = "") -> None:
        self.success = success
        self.message = message

    def __bool__(self) -> bool:
        return self.success


def _oem_encoding() -> str:
    """Кодовая страница, в которой консольные утилиты пишут в pipe (обычно OEM)."""
    if os.name != "nt":
        return "utf-8"
    try:
        import ctypes

        cp = int(ctypes.windll.kernel32.GetOEMCP())
        if cp:
            return f"cp{cp}"
    except Exception:
        pass
    return "cp866"


def _decode(data: bytes) -> str:
    if not data:
        return ""
    for enc in (_oem_encoding(), "cp866", "utf-8"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", "replace")


def _run(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            creationflags=_NO_WINDOW,
            capture_output=True,
        )
        return proc.returncode, _decode(proc.stdout) + _decode(proc.stderr)
    except Exception as exc:
        return 1, str(exc)


def _list_adapters_winapi() -> list[str]:
    """Имена адаптеров через WinAPI GetAdaptersAddresses (Unicode, без проблем с кодировкой)."""
    import ctypes
    from ctypes import wintypes

    ULONG = wintypes.ULONG
    DWORD = wintypes.DWORD

    class IP_ADAPTER_ADDRESSES(ctypes.Structure):
        pass

    IP_ADAPTER_ADDRESSES._fields_ = [
        ("Length", ULONG),
        ("IfIndex", DWORD),
        ("Next", ctypes.POINTER(IP_ADAPTER_ADDRESSES)),
        ("AdapterName", ctypes.c_char_p),
        ("FirstUnicastAddress", ctypes.c_void_p),
        ("FirstAnycastAddress", ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p),
        ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix", ctypes.c_wchar_p),
        ("Description", ctypes.c_wchar_p),
        ("FriendlyName", ctypes.c_wchar_p),
        ("PhysicalAddress", ctypes.c_ubyte * 8),
        ("PhysicalAddressLength", ULONG),
        ("Flags", ULONG),
        ("Mtu", ULONG),
        ("IfType", DWORD),
        ("OperStatus", ctypes.c_uint),
    ]

    iphlpapi = ctypes.WinDLL("iphlpapi")
    AF_UNSPEC = 0
    GAA_FLAG_INCLUDE_PREFIX = 0x0010
    size = ULONG(0)
    iphlpapi.GetAdaptersAddresses(AF_UNSPEC, GAA_FLAG_INCLUDE_PREFIX, None, None, ctypes.byref(size))
    if size.value == 0:
        return []
    buf = ctypes.create_string_buffer(size.value)
    ret = iphlpapi.GetAdaptersAddresses(
        AF_UNSPEC, GAA_FLAG_INCLUDE_PREFIX, None,
        ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES)), ctypes.byref(size),
    )
    if ret != 0:
        return []
    names: list[str] = []
    p = ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES))
    while p:
        a = p.contents
        # IfOperStatusUp == 1 — только подключённые; IfType 24 = loopback — пропускаем
        if a.OperStatus == 1 and a.IfType != 24 and a.FriendlyName:
            names.append(a.FriendlyName)
        p = a.Next
    return names


def list_adapters() -> list[str]:
    """Список имён подключённых сетевых адаптеров."""
    if os.name != "nt":
        return ["eth0 (демо)", "wlan0 (демо)"]
    # Основной путь — WinAPI (корректные Unicode-имена, включая кириллицу)
    try:
        names = _list_adapters_winapi()
        if names:
            return names
    except Exception:
        pass
    # Запасной путь — разбор вывода netsh
    code, out = _run(["netsh", "interface", "show", "interface"])
    adapters: list[str] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        if parts[0].lower() in ("admin", "состояние", "админ") or "---" in line:
            continue
        name = " ".join(parts[3:]).strip()
        if name:
            adapters.append(name)
    return adapters


def get_current_dns(adapter: str) -> list[str]:
    """Текущие IPv4 DNS-серверы адаптера."""
    if os.name != "nt":
        return []
    code, out = _run(["netsh", "interface", "ipv4", "show", "dnsservers", f"name={adapter}"])
    ips = re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", out)
    # Отсеиваем маски/адреса вне DNS маловероятно; возвращаем как есть.
    if "DHCP" in out or "дхцп" in out.lower():
        return ["(авто / DHCP)"] + ips
    return ips


def apply_dns(adapter: str, ipv4: list[str], ipv6: list[str] | None = None) -> DnsResult:
    """Устанавливает статические DNS на адаптер."""
    if os.name != "nt":
        return DnsResult(False, "Смена DNS доступна только на Windows")
    ipv4 = [x for x in (ipv4 or []) if x]
    if not ipv4:
        return DnsResult(False, "Не заданы IPv4 DNS-серверы")

    # IPv4: первичный + дополнительные
    code, out = _run([
        "netsh", "interface", "ipv4", "set", "dnsservers",
        f"name={adapter}", "static", ipv4[0], "primary", "validate=no",
    ])
    if code != 0:
        return DnsResult(False, f"netsh (ipv4) ошибка: {out.strip()[:200]}")
    for idx, ip in enumerate(ipv4[1:], start=2):
        _run([
            "netsh", "interface", "ipv4", "add", "dnsservers",
            f"name={adapter}", ip, f"index={idx}", "validate=no",
        ])

    # IPv6 (если есть)
    ipv6 = [x for x in (ipv6 or []) if x]
    if ipv6:
        _run([
            "netsh", "interface", "ipv6", "set", "dnsservers",
            f"name={adapter}", "static", ipv6[0], "primary", "validate=no",
        ])
        for idx, ip in enumerate(ipv6[1:], start=2):
            _run([
                "netsh", "interface", "ipv6", "add", "dnsservers",
                f"name={adapter}", ip, f"index={idx}", "validate=no",
            ])

    flush_dns_cache()
    return DnsResult(True, f"DNS применён на «{adapter}»: {', '.join(ipv4)}")


def reset_dns_auto(adapter: str) -> DnsResult:
    """Возвращает адаптер к автоматическому получению DNS (DHCP)."""
    if os.name != "nt":
        return DnsResult(False, "Сброс DNS доступен только на Windows")
    code4, out4 = _run([
        "netsh", "interface", "ipv4", "set", "dnsservers",
        f"name={adapter}", "source=dhcp",
    ])
    _run([
        "netsh", "interface", "ipv6", "set", "dnsservers",
        f"name={adapter}", "source=dhcp",
    ])
    flush_dns_cache()
    if code4 != 0:
        return DnsResult(False, f"netsh ошибка: {out4.strip()[:200]}")
    return DnsResult(True, f"DNS на «{adapter}» сброшен на авто (DHCP)")


def flush_dns_cache() -> DnsResult:
    if os.name != "nt":
        return DnsResult(False, "Только на Windows")
    code, out = _run(["ipconfig", "/flushdns"])
    return DnsResult(code == 0, "DNS-кэш очищен" if code == 0 else out.strip()[:200])
