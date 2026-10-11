# -*- coding: utf-8 -*-
"""Диалог добавления пользовательского DNS-сервера."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QMessageBox,
)


class AddDnsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить свой DNS")
        self.resize(420, 200)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Мой SmartDNS")
        form.addRow("Название:", self.name_edit)

        self.doh_edit = QLineEdit()
        self.doh_edit.setPlaceholderText("https://example.com/dns-query")
        form.addRow("DoH URL:", self.doh_edit)

        self.ipv4_edit = QLineEdit()
        self.ipv4_edit.setPlaceholderText("1.2.3.4, 1.2.3.5 (необязательно)")
        form.addRow("IPv4 адреса:", self.ipv4_edit)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self):
        name = self.name_edit.text().strip()
        doh = self.doh_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Укажите название DNS-сервера.")
            return
        if not doh and not self.ipv4_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Укажите DoH URL или хотя бы один IPv4-адрес.")
            return
        self.accept()

    def get_data(self) -> dict:
        raw_ips = self.ipv4_edit.text().replace(";", ",").split(",")
        ipv4 = [x.strip() for x in raw_ips if x.strip()]
        return {
            "name": self.name_edit.text().strip(),
            "doh": self.doh_edit.text().strip(),
            "ipv4": ipv4,
            "ipv6": [],
        }