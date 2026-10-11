# -*- coding: utf-8 -*-
"""Диалог тестирования DoH/DNS-серверов на доступность к ИИ."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QProgressBar,
    QCheckBox, QMessageBox,
)

from app.dns_tester import test_doh_full
from app.providers import get_all_providers_dict


class DnsTestWorker(QThread):
    progress = pyqtSignal(int, int, str)
    server_tested = pyqtSignal(str, str, dict)
    finished_all = pyqtSignal()

    def __init__(self, servers: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.servers = servers
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        total = len(self.servers)
        for idx, (name, doh_url) in enumerate(self.servers, start=1):
            if self._cancel:
                break
            self.progress.emit(idx, total, name)
            res = test_doh_full(doh_url)
            self.server_tested.emit(name, doh_url, res)
        self.finished_all.emit()


class DnsTestDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Тестирование DoH-серверов для ИИ")
        self.resize(880, 530)

        layout = QVBoxLayout(self)

        top_info = QLabel(
            "Проверка DoH-серверов на прохождение запросов к ChatGPT, Claude и Google AI Studio. "
            "Зеленым отмечаются работающие DNS-прокси."
        )
        top_info.setStyleSheet("color:#aaa;")
        layout.addWidget(top_info)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Провайдер", "ChatGPT", "Claude", "Google AI", "Пинг", "Итог"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        filter_bar = QHBoxLayout()
        self.only_working_check = QCheckBox("Показывать только работающие с ИИ")
        self.only_working_check.toggled.connect(self._apply_filter)
        filter_bar.addWidget(self.only_working_check)
        filter_bar.addStretch(1)
        layout.addLayout(filter_bar)

        bottom = QHBoxLayout()
        self.start_btn = QPushButton("Проверить все")
        self.start_btn.setStyleSheet("font-weight:bold;")
        self.start_btn.clicked.connect(self._toggle_test_all)
        bottom.addWidget(self.start_btn)

        self.test_one_btn = QPushButton("Проверить выбранный")
        self.test_one_btn.clicked.connect(self._test_selected)
        bottom.addWidget(self.test_one_btn)

        bottom.addStretch(1)
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self.worker: DnsTestWorker | None = None
        self._load_servers()

    def _load_servers(self):
        self.servers_to_test = []
        providers = get_all_providers_dict()
        for group in providers.values():
            for name, info in group.items():
                doh = info.get("doh")
                if doh:
                    self.servers_to_test.append((name, doh))

        self.table.setRowCount(len(self.servers_to_test))
        for r, (name, _) in enumerate(self.servers_to_test):
            self.table.setItem(r, 0, QTableWidgetItem(name))
            for col in range(1, 6):
                it = QTableWidgetItem("—")
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, col, it)

    def _start_test(self):
        self.start_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.servers_to_test))
        self.progress.setValue(0)

        self.worker = DnsTestWorker(self.servers_to_test, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.server_tested.connect(self._on_server_tested)
        self.worker.finished_all.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, done, total, name):
        self.progress.setValue(done)

    def _on_server_tested(self, name, doh_url, res):
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == name:
                cg = res["results"].get("ChatGPT", {})
                self._set_cell(r, 1, cg.get("msg", "—"), cg.get("ok", False))

                cl = res["results"].get("Claude", {})
                self._set_cell(r, 2, cl.get("msg", "—"), cl.get("ok", False))

                ga = res["results"].get("Google AI", {})
                self._set_cell(r, 3, ga.get("msg", "—"), ga.get("ok", False))

                lat = res.get("latency")
                it_lat = QTableWidgetItem(f"{lat} мс" if lat else "—")
                it_lat.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 4, it_lat)

                is_ok = res.get("working", False)
                verdict = "Работает" if is_ok else "Недоступен"
                self._set_cell(r, 5, verdict, is_ok)
                break

    def _set_cell(self, row, col, text, ok):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        if ok:
            item.setForeground(Qt.green)
        elif "Геоблок" in text or "недоступен" in text.lower():
            item.setForeground(Qt.red)
        self.table.setItem(row, col, item)

    def _toggle_test_all(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.start_btn.setText("Останавливаем…")
            self.start_btn.setEnabled(False)
            return

        self.start_btn.setText("Остановить")
        self.test_one_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.servers_to_test))
        self.progress.setValue(0)

        self.worker = DnsTestWorker(self.servers_to_test, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.server_tested.connect(self._on_server_tested)
        self.worker.finished_all.connect(self._on_finished)
        self.worker.start()

    def _test_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.servers_to_test):
            QMessageBox.information(self, "Выбор", "Выберите строку с DNS-сервером в таблице.")
            return
        name, doh = self.servers_to_test[row]
        self.start_btn.setEnabled(False)
        self.test_one_btn.setEnabled(False)

        worker = DnsTestWorker([(name, doh)], self)
        worker.server_tested.connect(self._on_server_tested)
        def on_done():
            self.start_btn.setEnabled(True)
            self.test_one_btn.setEnabled(True)
        worker.finished_all.connect(on_done)
        worker.start()

    def _apply_filter(self):
        only_ok = self.only_working_check.isChecked()
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 5)
            verdict = it.text() if it else ""
            if not only_ok:
                self.table.setRowHidden(r, False)
            else:
                self.table.setRowHidden(r, verdict != "Работает")

    def _on_finished(self):
        self.start_btn.setText("Проверить все")
        self.start_btn.setEnabled(True)
        self.test_one_btn.setEnabled(True)
        self.progress.setVisible(False)
        self._apply_filter()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        super().closeEvent(event)