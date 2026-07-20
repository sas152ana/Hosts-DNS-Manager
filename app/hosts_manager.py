# -*- coding: utf-8 -*-
"""Работа с системным файлом hosts.

Воспроизводит логику zapret/src/hosts/hosts.py:
- все записи живут в одном управляемом блоке между маркерами;
- остальной файл hosts не трогается;
- перед записью делается резервная копия, после — сброс DNS-кэша.
"""

from __future__ import annotations

import datetime
import os
import shutil
import subprocess
from pathlib import Path

MANAGED_BEGIN = "# >>> hosts-manager managed begin >>>"
MANAGED_END = "# <<< hosts-manager managed end <<<"
MANAGED_NOTICE = "# Записи ниже управляются Hosts & DNS Manager. Ручные правки внутри блока будут перезаписаны."


class HostsResult:
    def __init__(self, success: bool, message: str = "") -> None:
        self.success = success
        self.message = message

    def __bool__(self) -> bool:
        return self.success


def hosts_path() -> str:
    if os.name == "nt":
        root = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\\Windows"
        return os.path.join(root, "System32", "drivers", "etc", "hosts")
    return "/etc/hosts"


def _parse_mapping_line(line: str) -> tuple[str, list[str]] | None:
    """'1.2.3.4 a.com b.com # comment' -> (ip, [domains])."""
    body = line.split("#", 1)[0].strip()
    if not body:
        return None
    parts = body.split()
    if len(parts) < 2:
        return None
    return parts[0], parts[1:]


class HostsManager:
    def __init__(self) -> None:
        self.path = hosts_path()
        self.last_status = ""

    # ------------------------------------------------------------- read/write
    def is_readable(self) -> bool:
        try:
            return os.path.isfile(self.path) and os.access(self.path, os.R_OK)
        except Exception:
            return False

    def is_writable(self) -> bool:
        try:
            return os.access(self.path, os.W_OK)
        except Exception:
            return False

    def read(self) -> str | None:
        for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
            try:
                with open(self.path, "r", encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except FileNotFoundError:
                return ""
            except Exception:
                return None
        return None

    def backup(self) -> str | None:
        try:
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            dst = f"{self.path}.backup-{stamp}"
            shutil.copy2(self.path, dst)
            return dst
        except Exception:
            return None

    def _write(self, content: str) -> bool:
        try:
            with open(self.path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            return True
        except Exception as exc:
            self.last_status = f"Ошибка записи: {exc}"
            return False

    # --------------------------------------------------------------- managed
    @staticmethod
    def _strip_block(lines: list[str]) -> tuple[list[str], int]:
        out: list[str] = []
        inside = False
        removed = 0
        for line in lines:
            stripped = line.strip()
            if stripped == MANAGED_BEGIN:
                inside = True
                continue
            if inside:
                if stripped == MANAGED_END:
                    inside = False
                    continue
                if _parse_mapping_line(stripped):
                    removed += 1
                continue
            out.append(line)
        return out, removed

    @staticmethod
    def _strip_managed_domains(lines: list[str], domains) -> list[str]:
        """Удаляет из ВСЕГО файла записи для указанных доменов.

        Нужно, чтобы старые/чужие записи (например, от оригинального
        приложения или ручные) не перекрывали новые: при разрешении hosts
        побеждает первое вхождение домена. Строки без наших доменов не трогаем;
        если в строке несколько доменов — убираем только управляемые.
        """
        dom = {str(d).casefold() for d in (domains or [])}
        if not dom:
            return list(lines)
        out: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                out.append(line)
                continue
            parsed = _parse_mapping_line(stripped)
            if not parsed:
                out.append(line)
                continue
            ip, domains_in = parsed
            keep = [d for d in domains_in if d.casefold() not in dom]
            if len(keep) == len(domains_in):
                out.append(line)
            elif keep:
                nl = f"{ip} {' '.join(keep)}"
                out.append(nl + "\n" if line.endswith("\n") else nl)
            # иначе — строка целиком удаляется
        return out

    def get_active_domains_map(self) -> dict[str, str]:
        content = self.read()
        if not content:
            return {}
        result: dict[str, str] = {}
        inside = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == MANAGED_BEGIN:
                inside = True
                continue
            if not inside:
                continue
            if stripped == MANAGED_END:
                break
            parsed = _parse_mapping_line(stripped)
            if not parsed:
                continue
            ip, domains = parsed
            for dom in domains:
                result[dom.casefold()] = ip
        return result

    def get_all_domain_map(self) -> dict[str, str]:
        """Карта {домен: IP} по ВСЕМу файлу hosts (не только наш блок).

        Используется для умного авто-определения применённых настроек: распознаём
        записи независимо от их позиции/порядка и от того, какое приложение их добавило.
        При повторах домена побеждает первое вхождение (как при реальном разрешении).
        """
        content = self.read()
        if not content:
            return {}
        result: dict[str, str] = {}
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parsed = _parse_mapping_line(stripped)
            if not parsed:
                continue
            ip, domains = parsed
            for dom in domains:
                result.setdefault(dom.casefold(), ip)
        return result

    def apply_rows(self, rows: list[tuple[str, str]], managed_domains=None) -> HostsResult:
        """Перезаписывает управляемый блок заданными (domain, ip).

        Если передан managed_domains — сначала удаляем эти домены из ВСЕГО
        файла (чужие блоки, ручные дубли), чтобы не оставалось перекрывающих записей.
        """
        content = self.read()
        if content is None:
            return HostsResult(False, "Не удалось прочитать файл hosts")

        lines = content.splitlines(keepends=True)
        new_lines, _removed = self._strip_block(lines)
        if managed_domains:
            new_lines = self._strip_managed_domains(new_lines, managed_domains)
        while new_lines and new_lines[-1].strip() == "":
            new_lines.pop()

        # Уникальные (domain, ip)
        seen: set[tuple[str, str]] = set()
        clean_rows: list[tuple[str, str]] = []
        for domain, ip in rows or []:
            domain = str(domain).strip()
            ip = str(ip).strip()
            if not domain or not ip:
                continue
            key = (domain.casefold(), ip.casefold())
            if key in seen:
                continue
            seen.add(key)
            clean_rows.append((domain, ip))

        block: list[str] = []
        if clean_rows:
            if new_lines and new_lines[-1].strip() != "":
                block.append("\n")
            block.append(MANAGED_BEGIN + "\n")
            block.append(MANAGED_NOTICE + "\n")
            for domain, ip in clean_rows:
                block.append(f"{ip} {domain}\n")
            block.append(MANAGED_END + "\n")

        final = "".join(new_lines)
        if final and not final.endswith("\n"):
            final += "\n"
        final += "".join(block)

        if final == content:
            return HostsResult(True, "Файл hosts уже актуален")

        backup = self.backup()
        if not self._write(final):
            return HostsResult(False, self.last_status or "Ошибка записи")
        self.flush_dns()
        msg = f"Применено записей: {len(clean_rows)}"
        if backup:
            msg += f"  |  бэкап: {os.path.basename(backup)}"
        return HostsResult(True, msg)

    def clear(self, managed_domains=None) -> HostsResult:
        """Удаляет управляемый блок (и, если задано, все управляемые домены везде)."""
        content = self.read()
        if content is None:
            return HostsResult(False, "Не удалось прочитать файл hosts")
        new_lines, removed = self._strip_block(content.splitlines(keepends=True))
        if managed_domains:
            before = len(new_lines)
            new_lines = self._strip_managed_domains(new_lines, managed_domains)
            removed += max(0, before - len(new_lines))
        while new_lines and new_lines[-1].strip() == "":
            new_lines.pop()
        final = "".join(new_lines)
        if final and not final.endswith("\n"):
            final += "\n"
        if final == content:
            return HostsResult(True, "Блок уже пуст")
        backup = self.backup()
        if not self._write(final):
            return HostsResult(False, self.last_status or "Ошибка записи")
        self.flush_dns()
        msg = f"Удалено записей: {removed}"
        if backup:
            msg += f"  |  бэкап: {os.path.basename(backup)}"
        return HostsResult(True, msg)

    def restore_backup(self, backup_file: str) -> HostsResult:
        try:
            shutil.copy2(backup_file, self.path)
            self.flush_dns()
            return HostsResult(True, "Файл hosts восстановлен из бэкапа")
        except Exception as exc:
            return HostsResult(False, str(exc))

    def list_backups(self) -> list[str]:
        folder = os.path.dirname(self.path)
        base = os.path.basename(self.path)
        try:
            names = [n for n in os.listdir(folder) if n.startswith(base + ".backup-")]
            return sorted((os.path.join(folder, n) for n in names), reverse=True)
        except Exception:
            return []

    @staticmethod
    def flush_dns() -> None:
        if os.name != "nt":
            return
        try:
            subprocess.run(
                ["ipconfig", "/flushdns"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
                capture_output=True,
            )
        except Exception:
            pass

    def open_in_editor(self) -> HostsResult:
        try:
            if os.name == "nt":
                import ctypes

                ctypes.windll.shell32.ShellExecuteW(None, "runas", "notepad.exe", self.path, None, 1)
            else:
                subprocess.Popen(["xdg-open", self.path])
            return HostsResult(True, self.path)
        except Exception as exc:
            return HostsResult(False, str(exc))
