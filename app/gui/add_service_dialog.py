# -*- coding: utf-8 -*-
"""Диалог добавления нового сервиса с набором доменов и категорией."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QPlainTextEdit, QDialogButtonBox, QMessageBox, QLabel,
)


class AddServiceDialog(QDialog):
    def __init__(self, existing_categories: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить сайт / сервис в hosts")
        self.resize(520, 420)

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Укажите название сервиса, категорию и список доменов. "
            "Категорию можно выбрать из существующих или вписать новую."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#aaa; font-size:12px; margin-bottom:8px;")
        layout.addWidget(hint)

        form = QFormLayout()

        # 1. Название
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Мой сервис / Spotify Web")
        form.addRow("Название сервиса:", self.name_edit)

        # 2. Категория (можно выбрать или ввести свою!)
        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        cats = sorted(set(filter(None, existing_categories)))
        if not cats:
            cats = ["Напрямую из hosts", "ИИ", "Остальные"]
        self.cat_combo.addItems(cats)
        self.cat_combo.setEditText(cats[0])
        form.addRow("Категория (группа):", self.cat_combo)

        # 3. Режим работы
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("SmartDNS (подбор IP по вариантам DNS)", "dns")
        self.mode_combo.addItem("Прямой IP / hosts (один IP на сервис)", "hosts")
        form.addRow("Режим работы:", self.mode_combo)

        # 4. Список доменов
        self.domains_edit = QPlainTextEdit()
        self.domains_edit.setPlaceholderText(
            "По одному домену на строку, например:\n"
            "example.com\n"
            "api.example.com\n"
            "cdn.example.com"
        )
        form.addRow("Список доменов:", self.domains_edit)

        # 5. Стартовые IP (необязательно)
        self.ips_edit = QLineEdit()
        self.ips_edit.setPlaceholderText("1.2.3.4 (необязательно, можно заполнить позже)")
        form.addRow("IP-адрес(а):", self.ips_edit)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self):
        name = self.name_edit.text().strip()
        domains = self.get_domains()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Укажите название сервиса.")
            return
        if not domains:
            QMessageBox.warning(self, "Ошибка", "Введите хотя бы один домен.")
            return
        self.accept()

    def get_domains(self) -> list[str]:
        raw = self.domains_edit.toPlainText().splitlines()
        res = []
        for line in raw:
            dom = line.strip().lower().strip(".")
            if dom and not dom.startswith("#") and dom not in res:
                res.append(dom)
        return res

    def get_data(self) -> dict:
        raw_ips = self.ips_edit.text().replace(";", ",").split(",")
        ips = [x.strip() for x in raw_ips if x.strip()]
        return {
            "name": self.name_edit.text().strip(),
            "category": self.cat_combo.currentText().strip() or "Остальные",
            "mode": self.mode_combo.currentData(),
            "domains": self.get_domains(),
            "ips": ips,
        }