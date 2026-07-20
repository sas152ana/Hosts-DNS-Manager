# -*- coding: utf-8 -*-
"""Каталог сервисов/доменов/IP для редактора hosts.

Воспроизводит логику zapret/src/hosts/proxy_domains.py:
- есть несколько DNS-профилей ("вариантов"), у каждого свои IP по доменам;
- сервис = набор доменов; пользователь выбирает профиль на сервис (либо откл.);
- поддерживается как однофайловый catalog.json, так и раздельный каталог
  оригинала (dns_sources.json + dns/*.json + hosts/*.json).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

HOSTS_PROFILE_ID = "hosts"
HOSTS_PROFILE_NAME = "Вкл. (ручной hosts)"
MODE_DNS = "dns"
MODE_HOSTS = "hosts"


def _clean(value: object) -> str:
    return str(value or "").strip()


def _as_ip_list(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [_clean(x) for x in raw if _clean(x)]
    v = _clean(raw)
    return [v] if v else []


@dataclass
class Service:
    name: str
    icon: str = ""
    color: str = "#6c757d"
    category: str = ""
    mode: str = MODE_DNS
    # domain (lower) -> {profile_id: [ip, ...]}
    domains: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)  # порядок доменов

    def add_domain_ip(self, host: str, profile_id: str, ip: str) -> None:
        host = _clean(host).casefold()
        ip = _clean(ip)
        if not host or not ip or not profile_id:
            return
        bucket = self.domains.setdefault(host, {})
        if host not in self.order:
            self.order.append(host)
        ips = bucket.setdefault(profile_id, [])
        if ip not in ips:
            ips.append(ip)

    def available_profiles(self, all_profiles: list[str]) -> list[str]:
        """Профили, у которых есть хотя бы один IP в этом сервисе."""
        out: list[str] = []
        for pid in all_profiles:
            if any(pid in bucket and bucket[pid] for bucket in self.domains.values()):
                out.append(pid)
        return out

    def rows_for_profile(self, profile_id: str) -> list[tuple[str, str]]:
        """[(domain, ip), ...] для выбранного профиля."""
        rows: list[tuple[str, str]] = []
        for host in self.order:
            for ip in self.domains.get(host, {}).get(profile_id, []):
                rows.append((host, ip))
        return rows


class Catalog:
    def __init__(self) -> None:
        self.profiles: list[str] = []
        self.profile_names: dict[str, str] = {}
        self.services: list[Service] = []

    # ---------------------------------------------------------------- helpers
    def service_names(self) -> list[str]:
        return [s.name for s in self.services]

    def get_service(self, name: str) -> Service | None:
        key = _clean(name).casefold()
        for s in self.services:
            if s.name.casefold() == key:
                return s
        return None

    def profile_display(self, profile_id: str) -> str:
        return self.profile_names.get(profile_id, profile_id)

    def detect_selection(self, active_map: dict[str, str]) -> dict[str, str]:
        """По карте {домен: IP} из hosts определить активный вариант каждого сервиса.

        Работает по содержанию, а не по позиции строк: для каждого сервиса берём его
        домены, смотрим их IP в hosts и выбираем вариант с наибольшим числом
        совпадений с известными адресами.
        Возвращает {имя_сервиса: profile_id}.
        """
        detected: dict[str, str] = {}
        if not active_map:
            return detected
        norm = {str(k).casefold(): str(v).strip() for k, v in active_map.items()}
        for svc in self.services:
            best_pid = ""
            best_score = 0
            for pid in svc.available_profiles(self.profiles):
                score = 0
                for host in svc.order:
                    actual = norm.get(host.casefold())
                    if not actual:
                        continue
                    expected = [str(x).strip() for x in svc.domains.get(host, {}).get(pid, [])]
                    if actual in expected:
                        score += 1
                if score > best_score:
                    best_score = score
                    best_pid = pid
            if best_pid and best_score > 0:
                detected[svc.name] = best_pid
        return detected

    def ensure_profile(self, profile_id: str, name: str) -> None:
        if profile_id not in self.profile_names:
            self.profiles.append(profile_id)
        self.profile_names[profile_id] = name

    # ------------------------------------------------------------ single json
    def load_single(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace") or "{}")
        self._load_dict(data)

    def _load_dict(self, data: dict) -> None:
        self.profiles = []
        self.profile_names = {}
        self.services = []

        for raw in data.get("profiles") or []:
            pid = _clean(raw.get("id"))
            name = _clean(raw.get("name"))
            if pid and name:
                self.ensure_profile(pid, name)

        for raw in data.get("services") or []:
            if not isinstance(raw, dict):
                continue
            name = _clean(raw.get("name"))
            if not name:
                continue
            mode = MODE_HOSTS if _clean(raw.get("mode")).lower() in (MODE_HOSTS, "direct") else MODE_DNS
            svc = Service(
                name=name,
                icon=_clean(raw.get("icon")),
                color=_clean(raw.get("color")) or "#6c757d",
                category=_clean(raw.get("category")),
                mode=mode,
            )
            if mode == MODE_HOSTS:
                self.ensure_profile(HOSTS_PROFILE_ID, HOSTS_PROFILE_NAME)
                for row in raw.get("hosts") or []:
                    if isinstance(row, dict):
                        svc.add_domain_ip(row.get("host"), HOSTS_PROFILE_ID, row.get("ip"))
            for dom in raw.get("domains") or []:
                if not isinstance(dom, dict):
                    continue
                host = _clean(dom.get("host") or dom.get("domain"))
                ips = dom.get("ips")
                if not host or not isinstance(ips, dict):
                    continue
                for pid, value in ips.items():
                    for ip in _as_ip_list(value):
                        svc.add_domain_ip(host, pid, ip)
            self.services.append(svc)

    # ------------------------------------------------------------- split dirs
    def load_split(self, directory: str | Path) -> None:
        """Поддержка формата оригинала: dns_sources.json + dns/*.json + hosts/*.json."""
        directory = Path(directory)
        profiles_raw: object = []
        src = directory / "dns_sources.json"
        if src.exists():
            profiles_raw = json.loads(src.read_text(encoding="utf-8", errors="replace") or "[]")
        if isinstance(profiles_raw, dict):
            profiles_raw = profiles_raw.get("dns_sources") or profiles_raw.get("profiles") or []
        profiles = [
            {"id": _clean(p.get("id")), "name": _clean(p.get("name"))}
            for p in profiles_raw
            if isinstance(p, dict) and _clean(p.get("id")) and _clean(p.get("name"))
        ]

        services: list[dict] = []
        for mode, sub in ((MODE_DNS, "dns"), (MODE_HOSTS, "hosts")):
            folder = directory / sub
            if not folder.is_dir():
                continue
            for child in sorted(folder.glob("*.json")):
                try:
                    raw = json.loads(child.read_text(encoding="utf-8", errors="replace") or "{}")
                except Exception:
                    continue
                items = raw.get("services") if isinstance(raw, dict) and isinstance(raw.get("services"), list) else (
                    raw if isinstance(raw, list) else [raw]
                )
                for item in items:
                    if isinstance(item, dict):
                        d = dict(item)
                        d["mode"] = mode
                        services.append(d)

        self._load_dict({"profiles": profiles, "services": services})

    def load_any(self, path: str | Path) -> None:
        path = Path(path)
        if path.is_dir():
            self.load_split(path)
        else:
            self.load_single(path)

    # ------------------------------------------------------------ export dict
    def to_dict(self) -> dict:
        services_out = []
        for svc in self.services:
            domains_out = []
            for host in svc.order:
                domains_out.append({"host": host, "ips": svc.domains.get(host, {})})
            services_out.append({
                "name": svc.name,
                "icon": svc.icon,
                "color": svc.color,
                "category": svc.category,
                "mode": svc.mode,
                "domains": domains_out,
            })
        return {
            "version": 1,
            "profiles": [{"id": pid, "name": self.profile_names[pid]} for pid in self.profiles],
            "services": services_out,
        }

    def save_single(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "catalog.json"


def settings_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "settings.json"


def load_selection() -> dict[str, str]:
    """{service_name: profile_id} — выбор пользователя."""
    p = settings_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace") or "{}")
        return dict(data.get("hosts_selection") or {})
    except Exception:
        return {}


def save_selection(selection: dict[str, str]) -> bool:
    p = settings_path()
    try:
        data = {}
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8", errors="replace") or "{}")
        data["hosts_selection"] = dict(selection or {})
        os.makedirs(p.parent, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def load_default_catalog() -> Catalog:
    cat = Catalog()
    path = default_catalog_path()
    if path.exists():
        cat.load_single(path)
    return cat
