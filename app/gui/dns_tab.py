# -*- coding: utf-8 -*-
"""Вкладка «DNS-серверы»: выбор варианта DNS и применение на адаптер."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QMessageBox, QPlainTextEdit,
)

from app import dns_manager
from app.providers import get_all_providers_dict, save_custom_server
from app.gui.dns_test_dialog import DnsTestDialog
from app.gui.add_dns_dialog import AddDnsDialog


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
        self.tree.setColumnWidth(0, 230)
        self.tree.setColumnWidth(1, 170)
        self.tree.setColumnWidth(2, 160)
        self._fill_providers()
        root.addWidget(self.tree, 1)

        # Текущий DNS
        self.current = QPlainTextEdit()
        self.current.setReadOnly(True)
        self.current.setFixedHeight(70)
        self.current.setPlaceholderText("Текущие DNS адаптера…")
        root.addWidget(self.current)

        # Первичная загрузка сетевых адаптеров
        self.reload_adapters()

        # Кнопки
        bottom = QHBoxLayout()
        add_custom_btn = QPushButton("+ Свой DNS")
        add_custom_btn.clicked.connect(self._add_custom_dns)
        bottom.addWidget(add_custom_btn)

        test_ai_btn = QPushButton("⚡ Проверить работу с ИИ")
        test_ai_btn.setToolTip("Тестирование ChatGPT, Claude и Google AI через каждый DoH-сервер")
        test_ai_btn.clicked.connect(self._open_dns_test)
        bottom.addWidget(test_ai_btn)

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

    # ------------------------------------------------------------------ build
    def _fill_providers(self) -> None:
        self.tree.clear()
        providers = get_all_providers_dict()
        for category, group in providers.items():
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
                parent.addChild(child)
            parent.setExpanded(True)

    def _open_dns_test(self) -> None:
        dlg = DnsTestDialog(self)
        dlg.exec_()

    def _add_custom_dns(self) -> None:
        dlg = AddDnsDialog(self)
        if dlg.exec_() == AddDnsDialog.Accepted:
            save_custom_server(dlg.get_data())
            self._fill_providers()
            QMessageBox.information(self, "Готово", "Пользовательский DNS добавлен.")

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
        ipv4 = info.get("ipv4", [])
        ipv6 = info.get("ipv6", []) if self.ipv6_check.isChecked() else []
        if not ipv4 and not ipv6:
            QMessageBox.information(
                self, "Только DoH-сервер",
                "У этого провайдера не указаны статические IP-адреса для сетевого адаптера.\n\n"
                "Он предназначен для использования через DoH в браузере (Firefox) "
                "или для автозаполнения каталога hosts во вкладке «Каталог»."
            )
            return
        result = dns_manager.apply_dns(adapter, ipv4, ipv6)
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
