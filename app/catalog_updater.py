# -*- coding: utf-8 -*-
"""Автозаполнение catalog.json IP-адресами SmartDNS/DoH-сервисов."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.dns_tester import test_doh_full, query_doh_ips
from app.providers import load_custom_servers
from app.catalog import default_catalog_path

PROFILES_CONFIG = {
    "dns_ai": {
        "name": "DNS-AI",
        "doh": "https://dns.dns-ai.ru/dns-query",
    },
    "geohide": {
        "name": "GeoHide DNS",
        "doh": "https://dns.geohide.ru/dns-query",
    },
    "geohide_eu": {
        "name": "GeoHide EU",
        "doh": "https://eu.geohide.ru/dns-query",
    },
    "mafioznik": {
        "name": "Mafioznik DNS",
        "doh": "https://dns.mafioznik.xyz/dns-query",
    },
    "comss": {
        "name": "Comss DNS",
        "doh": "https://dns.comss.one/dns-query",
    },
    "xbox": {
        "name": "XBOX DNS",
        "doh": "https://xbox-dns.ru/dns-query",
    },
    "malw": {
        "name": "Malw DNS",
        "doh": "https://dns.malw.link/dns-query",
    },
    "astracat": {
        "name": "Astracat DNS",
        "doh": "https://dns.astracat.network/dns-query",
    },
    "shecan": {
        "name": "Shecan SmartDNS",
        "doh": "https://free.shecan.ir/dns-query",
    },
}

TIMEOUT = 5


def get_all_profiles() -> dict:
    """Объединяет встроенные профили и пользовательские DNS (с DoH) из settings.json."""
    profiles = dict(PROFILES_CONFIG)
    for c in load_custom_servers():
        name = c.get("name", "").strip()
        doh = c.get("doh", "").strip()
        if name and doh:
            pid = "custom_" + name.lower().replace(" ", "_")
            profiles[pid] = {"name": name, "doh": doh}
    return profiles


def update_catalog(pre_check_ai: bool = True) -> int:
    catalog_path = default_catalog_path()
    if not catalog_path.exists():
        print(f"[-] Файл не найден: {catalog_path}")
        return 1

    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_profiles = data.setdefault("profiles", [])
    existing_ids = {p.get("id") for p in catalog_profiles}

    all_profiles = get_all_profiles()

    for pid, cfg in all_profiles.items():
        if pid not in existing_ids:
            catalog_profiles.append({"id": pid, "name": cfg["name"]})

    active_profiles = {}
    print("\n--- Шаг 1: Тестирование DoH-серверов на работу с ИИ ---")
    for pid, cfg in all_profiles.items():
        doh_url = cfg.get("doh")
        if pre_check_ai and doh_url:
            print(f"Тест {cfg['name']}... ", end="", flush=True)
            res = test_doh_full(doh_url)
            if res["working"]:
                print(f"[OK] ({res['latency']} мс)")
                active_profiles[pid] = cfg
            else:
                print("[ПРОПУСК] Не отвечает или заблокирован")
        else:
            active_profiles[pid] = cfg

    if not active_profiles:
        print("[-] Ни один DNS-сервер не прошел проверку. Прерывание.")
        return 1

    print("\n--- Шаг 2: Разрешение доменов и наполнение каталога ---")
    total_domains = 0
    total_filled = 0

    for svc in data.get("services", []):
        if svc.get("mode") == "hosts":
            continue

        svc_name = svc.get("name", "?")
        for dom in svc.get("domains", []):
            host = dom.get("host")
            if not host:
                continue
            total_domains += 1
            ips_map = dom.setdefault("ips", {})

            for pid, cfg in active_profiles.items():
                if ips_map.get(pid):
                    continue

                found = query_doh_ips(cfg["doh"], host, timeout=TIMEOUT)
                if found:
                    ips_map[pid] = found
                    total_filled += 1
                    print(f"  {svc_name[:12]:>12} | {host:<35} -> {pid}: {', '.join(found)}")

    catalog_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[OK] Завершено. Обработано доменов: {total_domains}, добавлено IP: {total_filled}")
    return 0


if __name__ == "__main__":
    sys.exit(update_catalog(pre_check_ai=True))