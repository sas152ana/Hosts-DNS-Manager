# -*- coding: utf-8 -*-
"""Главное окно с вкладками."""

from __future__ import annotations

import os

from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QLabel, QWidget, QVBoxLayout, QPushButton,
    QApplication,
)

from app.admin import is_admin
from app.catalog import load_default_catalog
from app.gui import theme
from app.gui.hosts_tab import HostsTab
from app.gui.dns_tab import DnsTab
from app.gui.catalog_tab import CatalogTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hosts & DNS Manager")
        self.resize(940, 640)

        self.catalog = load_default_catalog()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        if os.name == "nt" and not is_admin():
            warn = QLabel(
                "  ⚠ Запущено без прав администратора — запись hosts и смена DNS могут не работать.  "
            )
            warn.setStyleSheet("background:#7a2e00;color:#fff;padding:6px;")
            layout.addWidget(warn)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Переключатель темы в углу вкладок
        self.theme_btn = QPushButton()
        self.theme_btn.setToolTip("Переключить тёмную/светлую тему")
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.tabs.setCornerWidget(self.theme_btn)
        self._sync_theme_btn()

        self.hosts_tab = HostsTab(self.catalog)
        self.dns_tab = DnsTab()
        self.catalog_tab = CatalogTab(self.catalog, on_changed=self._on_catalog_changed)

        self.tabs.addTab(self.hosts_tab, "Сайты (hosts)")
        self.tabs.addTab(self.dns_tab, "DNS-серверы")
        self.tabs.addTab(self.catalog_tab, "Каталог")

        self.statusBar().showMessage("Готово")

    def _on_catalog_changed(self) -> None:
        """После импорта/редактирования каталога обновляем вкладку сайтов."""
        self.hosts_tab.rebuild()
        self.statusBar().showMessage("Каталог обновлён")

    def _sync_theme_btn(self) -> None:
        cur = theme.load_theme()
        self.theme_btn.setText("Светлая тема" if cur == theme.DARK else "Тёмная тема")

    def _toggle_theme(self) -> None:
        theme.toggle_theme(QApplication.instance())
        self._sync_theme_btn()
