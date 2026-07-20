# -*- coding: utf-8 -*-
"""Тёмная/светлая тема оформления.

Используется стиль Fusion + палитра — так все штатные виджеты
корректно выглядят в обеих темах. Выбор темы хранится в settings.json.
"""
from __future__ import annotations

import json
import os

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QStyleFactory

from app.catalog import settings_path

DARK = "dark"
LIGHT = "light"


def _dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(45, 45, 45))
    p.setColor(QPalette.WindowText, QColor(220, 220, 220))
    p.setColor(QPalette.Base, QColor(30, 30, 30))
    p.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    p.setColor(QPalette.ToolTipBase, QColor(45, 45, 45))
    p.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    p.setColor(QPalette.Text, QColor(220, 220, 220))
    p.setColor(QPalette.Button, QColor(55, 55, 55))
    p.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    p.setColor(QPalette.BrightText, QColor(255, 80, 80))
    p.setColor(QPalette.Link, QColor(80, 160, 240))
    p.setColor(QPalette.Highlight, QColor(38, 110, 183))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 120, 120))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 120, 120))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor(120, 120, 120))
    return p


def _light_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(245, 245, 245))
    p.setColor(QPalette.WindowText, QColor(30, 30, 30))
    p.setColor(QPalette.Base, QColor(255, 255, 255))
    p.setColor(QPalette.AlternateBase, QColor(235, 235, 235))
    p.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    p.setColor(QPalette.ToolTipText, QColor(30, 30, 30))
    p.setColor(QPalette.Text, QColor(30, 30, 30))
    p.setColor(QPalette.Button, QColor(240, 240, 240))
    p.setColor(QPalette.ButtonText, QColor(30, 30, 30))
    p.setColor(QPalette.BrightText, QColor(200, 0, 0))
    p.setColor(QPalette.Link, QColor(20, 100, 200))
    p.setColor(QPalette.Highlight, QColor(38, 110, 183))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(160, 160, 160))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(160, 160, 160))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor(160, 160, 160))
    return p


def apply_theme(app: QApplication, name: str) -> None:
    name = LIGHT if str(name).lower() == LIGHT else DARK
    try:
        app.setStyle(QStyleFactory.create("Fusion"))
    except Exception:
        pass
    if name == LIGHT:
        app.setPalette(_light_palette())
        hb, hf, st = "#e2e2e2", "#222222", "#666666"
    else:
        app.setPalette(_dark_palette())
        hb, hf, st = "#333333", "#dddddd", "#999999"
    app.setStyleSheet(
        f"#catHeader{{background:{hb};border-radius:4px;margin-top:6px;}}"
        f"#catTitle{{font-weight:bold;color:{hf};background:transparent;}}"
        f"#statusLabel{{color:{st};}}"
    )


def load_theme() -> str:
    p = settings_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace") or "{}")
            v = str(data.get("theme") or "").lower()
            if v in (DARK, LIGHT):
                return v
        except Exception:
            pass
    return DARK


def save_theme(name: str) -> bool:
    p = settings_path()
    try:
        data = {}
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8", errors="replace") or "{}")
        data["theme"] = LIGHT if str(name).lower() == LIGHT else DARK
        os.makedirs(p.parent, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def toggle_theme(app: QApplication) -> str:
    new = LIGHT if load_theme() == DARK else DARK
    apply_theme(app, new)
    save_theme(new)
    return new
