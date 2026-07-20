# -*- coding: utf-8 -*-
"""Проверка и получение прав администратора (Windows)."""

from __future__ import annotations

import os
import sys


def is_admin() -> bool:
    """True, если процесс имеет права админа (на не-Windows считаем True)."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_admin() -> bool:
    """На Windows перезапускает процесс с запросом UAC.

    Возвращает True, если был запущен новый (привилегированный) процесс
    и текущий нужно завершить; False, если права уже есть.
    """
    if os.name != "nt" or is_admin():
        return False
    try:
        import ctypes

        params = " ".join(f'"{arg}"' for arg in sys.argv)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        return True
    except Exception:
        # Не смогли повысить права — продолжаем без них (часть функций будет недоступна).
        return False
