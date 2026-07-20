# -*- coding: utf-8 -*-
"""Вкладка «DNS-серверы»: выбор варианта DNS и применение на адаптер."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QMessageBox, QPlainTextEdit,
)

from app import dns_manager
from app.providers import DNS_PROVIDERS


class DnsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)

        # Адаптер
        top = QHBoxLayout()
        top.addWidget(QLabel("Сетевой адаптер:"))
        self.adapter_combo = QComboBox()
        top.addWidget(self.adapter_combo, 1)
        refresh = QPushButton("Обновить")
        refresh.clicked.connect(self.reload_adapters)
        top.addWidget(refresh)
        self.ipv6_check = QCheckBox("Также IPv6")
        self.ipv6_check.setChecked(True)
        top.addWidget(self.ipv6_check)
        root.addLayout(top)

        self.adapter_combo.currentIndexChanged.connect(self._show_current_dns)

        # Список провайдеров по категориям
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Провайдер / категория", "IPv4", "IPv6", "Описание"])
        self.tree.setColumnWidth(0, 220)
        self.tree.setColumnWidth(1, 180)
        self.tree.setColumnWidth(2, 180)
        self._fill_providers()
        root.addWidget(self.tree, 1)

        # Текущий DNS
        self.current = QPlainTextEdit()
        self.current.setReadOnly(True)
        self.current.setFixedHeight(70)
        self.current.setPlaceholderText("Текущие DNS адаптера…")
        root.addWidget(self.current)

        # Кнопки
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        for text, slot in (
            ("Очистить кэш", self._flush),
            ("Сбросить на авто", self._reset),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bottom.addWidget(b)
        self.apply_btn = QPushButton("Применить DNS")
        self.apply_btn.setStyleSheet("font-weight:bold;")
        self.apply_btn.clicked.connect(self._apply)
        bottom.addWidget(self.apply_btn)
        root.addLayout(bottom)

        self.reload_adapters()

    # ------------------------------------------------------------------ build
    def _fill_providers(self) -> None:
        self.tree.clear()
        for category, group in DNS_PROVIDERS.items():
            parent = QTreeWidgetItem([category])
            parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)
            f = parent.font(0)
            f.setBold(True)
            parent.setFont(0, f)
            self.tree.addTopLevelItem(parent)
            for name, info in group.items():
                child = QTreeWidgetItem([
                    name,
                    ", ".join(info.get("ipv4", [])),
                    ", ".join(info.get("ipv6", [])),
                    info.get("desc", ""),
                ])
                child.setData(0, Qt.UserRole, info)
                self.tree.addTopLevelItem(parent)  # ensure parent added
                parent.addChild(child)
            parent.setExpanded(True)

    def reload_adapters(self) -> None:
        self.adapter_combo.clear()
        adapters = dns_manager.list_adapters()
        if not adapters:
            self.adapter_combo.addItem("(адаптеры не найдены)")
        else:
            self.adapter_combo.addItems(adapters)
        self._show_current_dns()

    # ---------------------------------------------------------------- actions
    def _selected_provider(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        info = item.data(0, Qt.UserRole)
        return info

    def _current_adapter(self) -> str:
        text = self.adapter_combo.currentText()
        if text.startswith("("):
            return ""
        return text

    def _show_current_dns(self) -> None:
        adapter = self._current_adapter()
        if not adapter:
            self.current.setPlainText("")
            return
        dns = dns_manager.get_current_dns(adapter)
        self.current.setPlainText(
            f"Адаптер: {adapter}\nТекущие DNS: " + (", ".join(dns) if dns else "(не определены)")
        )

    def _apply(self) -> None:
        adapter = self._current_adapter()
        if not adapter:
            QMessageBox.warning(self, "Ошибка", "Выберите сетевой адаптер.")
            return
        info = self._selected_provider()
        if not info:
            QMessageBox.warning(self, "Ошибка", "Выберите DNS-провайдера в списке.")
            return
        ipv6 = info.get("ipv6", []) if self.ipv6_check.isChecked() else []
        result = dns_manager.apply_dns(adapter, info.get("ipv4", []), ipv6)
        self._toast(result.success, result.message)
        self._show_current_dns()

    def _reset(self) -> None:
        adapter = self._current_adapter()
        if not adapter:
            QMessageBox.warning(self, "Ошибка", "Выберите сетевой адаптер.")
            return
        result = dns_manager.reset_dns_auto(adapter)
        self._toast(result.success, result.message)
        self._show_current_dns()

    def _flush(self) -> None:
        result = dns_manager.flush_dns_cache()
        self._toast(result.success, result.message)

    def _toast(self, ok: bool, message: str) -> None:
        if ok:
            QMessageBox.information(self, "Готово", message)
        else:
            QMessageBox.warning(self, "Ошибка", message)
