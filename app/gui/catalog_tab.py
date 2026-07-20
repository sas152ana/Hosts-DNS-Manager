# -*- coding: utf-8 -*-
"""Вкладка «Каталог»: просмотр/редактирование/импорт/экспорт каталога,
а также автозаполнение IP через DoH-резолвер."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QFileDialog, QLabel, QDialog, QComboBox,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QHeaderView, QInputDialog, QProgressDialog,
)

from app.catalog import Catalog, Service, default_catalog_path
from app import resolver


def _set_profile_ips(svc: Service, host: str, profile_id: str, ips: list[str]) -> None:
    """Заменяет (не добавляет) список IP для домена в указанном профиле."""
    host = (host or "").strip().casefold()
    if not host or not profile_id:
        return
    bucket = svc.domains.setdefault(host, {})
    if host not in svc.order:
        svc.order.append(host)
    cleaned: list[str] = []
    for ip in ips:
        ip = (ip or "").strip()
        if ip and ip not in cleaned:
            cleaned.append(ip)
    if cleaned:
        bucket[profile_id] = cleaned
    else:
        bucket.pop(profile_id, None)


class ResolveWorker(QThread):
    """Фоновое разрешение доменов через DoH."""

    progress = pyqtSignal(int, int, str)          # done, total, текущий домен
    resolved = pyqtSignal(str, str, list, list)   # service_name, host, ipv4, ipv6
    finished_all = pyqtSignal(int, int)           # успешно, всего

    def __init__(self, tasks, resolver_name, want_ipv6, parent=None) -> None:
        super().__init__(parent)
        self._tasks = list(tasks)               # [(service_name, host), ...]
        self._resolver = resolver_name
        self._want_ipv6 = bool(want_ipv6)
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        total = len(self._tasks)
        ok = 0
        for i, (svc_name, host) in enumerate(self._tasks, start=1):
            if self._cancel:
                break
            self.progress.emit(i, total, host)
            try:
                ipv4, ipv6 = resolver.resolve_domain(
                    host, self._resolver, want_ipv4=True, want_ipv6=self._want_ipv6
                )
                if ipv4 or ipv6:
                    ok += 1
                self.resolved.emit(svc_name, host, ipv4, ipv6)
            except Exception:
                self.resolved.emit(svc_name, host, [], [])
        self.finished_all.emit(ok, total)


class DomainEditor(QDialog):
    """Редактор доменов/IP одного сервиса: строки = домены, колонки = профили."""

    def __init__(self, catalog: Catalog, service, parent=None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.service = service
        self.setWindowTitle(f"Каталог: {service.name}")
        self.resize(760, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Строки — домены, колонки — варианты DNS. Несколько IP — через запятую."
        ))

        self.profiles = list(catalog.profiles)
        self.table = QTableWidget(0, 1 + len(self.profiles))
        headers = ["Домен"] + [catalog.profile_display(p) for p in self.profiles]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        for host in service.order:
            self._add_row(host, service.domains.get(host, {}))

        # Панель DoH-резолвера
        doh = QHBoxLayout()
        doh.addWidget(QLabel("DoH:"))
        self.resolver_combo = QComboBox()
        self.resolver_combo.addItems(resolver.resolver_names())
        doh.addWidget(self.resolver_combo)
        doh.addWidget(QLabel("→ в вариант:"))
        self.target_combo = QComboBox()
        for pid in self.profiles:
            self.target_combo.addItem(catalog.profile_display(pid), userData=pid)
        doh.addWidget(self.target_combo)
        self.ipv6_check = QCheckBox("IPv6")
        doh.addWidget(self.ipv6_check)
        resolve_btn = QPushButton("Заполнить IP через DoH")
        resolve_btn.clicked.connect(self._resolve)
        doh.addWidget(resolve_btn)
        doh.addStretch(1)
        layout.addLayout(doh)

        btns = QHBoxLayout()
        add = QPushButton("+ Домен")
        add.clicked.connect(lambda: self._add_row("", {}))
        rm = QPushButton("− Удалить строку")
        rm.clicked.connect(self._remove_row)
        btns.addWidget(add)
        btns.addWidget(rm)
        btns.addStretch(1)
        layout.addLayout(btns)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._save)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _add_row(self, host: str, ips: dict) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(host))
        for col, pid in enumerate(self.profiles, start=1):
            value = ", ".join(ips.get(pid, []))
            self.table.setItem(r, col, QTableWidgetItem(value))

    def _remove_row(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def _hosts_in_table(self) -> list[str]:
        hosts = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            host = (item.text() if item else "").strip()
            if host:
                hosts.append(host)
        return hosts

    def _resolve(self) -> None:
        hosts = self._hosts_in_table()
        if not hosts:
            QMessageBox.information(self, "Нет доменов", "Сначала добавьте домены.")
            return
        target = self.target_combo.currentData()
        target_col = self.profiles.index(target) + 1
        want_ipv6 = self.ipv6_check.isChecked()
        resolver_name = self.resolver_combo.currentText()

        results: dict[str, list[str]] = {}
        tasks = [("_", h) for h in hosts]
        worker = ResolveWorker(tasks, resolver_name, want_ipv6, self)

        dlg = QProgressDialog("Разрешение доменов…", "Отмена", 0, len(tasks), self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.canceled.connect(worker.cancel)

        def on_progress(done, total, host):
            dlg.setValue(done)
            dlg.setLabelText(f"Разрешение: {host}  ({done}/{total})")

        def on_resolved(_svc, host, ipv4, ipv6):
            results[host.casefold()] = list(ipv4) + list(ipv6)

        def on_done(ok, total):
            dlg.setValue(total)
            # Записываем результаты в столбец целевого варианта
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                host = (item.text() if item else "").strip().casefold()
                if host in results and results[host]:
                    self.table.setItem(r, target_col, QTableWidgetItem(", ".join(results[host])))
            QMessageBox.information(
                self, "Готово",
                f"Разрешено {ok} из {total} доменов через {resolver_name}.",
            )

        worker.progress.connect(on_progress)
        worker.resolved.connect(on_resolved)
        worker.finished_all.connect(on_done)
        worker.start()
        dlg.exec_()
        worker.wait()

    def _save(self) -> None:
        self.service.domains = {}
        self.service.order = []
        for r in range(self.table.rowCount()):
            host_item = self.table.item(r, 0)
            host = (host_item.text() if host_item else "").strip()
            if not host:
                continue
            for col, pid in enumerate(self.profiles, start=1):
                cell = self.table.item(r, col)
                raw = cell.text() if cell else ""
                for ip in [x.strip() for x in raw.replace(";", ",").split(",")]:
                    if ip:
                        self.service.add_domain_ip(host, pid, ip)
        self.accept()


class CatalogTab(QWidget):
    def __init__(self, catalog: Catalog, on_changed=None) -> None:
        super().__init__()
        self.catalog = catalog
        self.on_changed = on_changed
        self._worker = None

        root = QVBoxLayout(self)

        info = QLabel(
            "Сервисы, их домены и IP по вариантам DNS. Можно импортировать готовый каталог "
            "или автоматически заполнить IP через DoH-резолвер."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#999;")
        root.addWidget(info)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Сервис / домен", "Варианты с IP"])
        self.tree.setColumnWidth(0, 360)
        self.tree.itemDoubleClicked.connect(lambda *_: self._edit_service())
        root.addWidget(self.tree, 1)

        # Панель массового DoH-резолвинга
        doh = QHBoxLayout()
        doh.addWidget(QLabel("DoH-резолвер:"))
        self.resolver_combo = QComboBox()
        self.resolver_combo.addItems(resolver.resolver_names())
        doh.addWidget(self.resolver_combo)
        doh.addWidget(QLabel("→ вариант:"))
        self.target_combo = QComboBox()
        self._reload_target_combo()
        doh.addWidget(self.target_combo)
        self.ipv6_check = QCheckBox("IPv6")
        doh.addWidget(self.ipv6_check)
        b_one = QPushButton("Заполнить IP: сервис")
        b_one.clicked.connect(lambda: self._resolve(all_services=False))
        b_all = QPushButton("Заполнить IP: все")
        b_all.clicked.connect(lambda: self._resolve(all_services=True))
        doh.addWidget(b_one)
        doh.addWidget(b_all)
        doh.addStretch(1)
        root.addLayout(doh)

        btns = QHBoxLayout()
        for text, slot in (
            ("Импорт JSON", self._import_json),
            ("Импорт папки (оригинал)", self._import_dir),
            ("Экспорт JSON", self._export_json),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            btns.addWidget(b)
        btns.addStretch(1)
        for text, slot in (
            ("+ Сервис", self._add_service),
            ("Редактировать", self._edit_service),
            ("Удалить", self._delete_service),
            ("Сохранить каталог", self._save_default),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            btns.addWidget(b)
        root.addLayout(btns)

        self.rebuild()

    def _reload_target_combo(self) -> None:
        self.target_combo.clear()
        for pid in self.catalog.profiles:
            self.target_combo.addItem(self.catalog.profile_display(pid), userData=pid)

    def rebuild(self) -> None:
        self.tree.clear()
        for svc in self.catalog.services:
            avail = svc.available_profiles(self.catalog.profiles)
            top = QTreeWidgetItem([svc.name, ", ".join(self.catalog.profile_display(p) for p in avail) or "(нет IP)"])
            for host in svc.order:
                ips = svc.domains.get(host, {})
                summary = "; ".join(f"{self.catalog.profile_display(p)}: {', '.join(v)}" for p, v in ips.items())
                top.addChild(QTreeWidgetItem([host, summary]))
            self.tree.addTopLevelItem(top)

    # ---------------------------------------------------------------- helpers
    def _selected_service(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        while item.parent() is not None:
            item = item.parent()
        return self.catalog.get_service(item.text(0))

    def _notify_changed(self) -> None:
        self._reload_target_combo()
        self.rebuild()
        if self.on_changed:
            self.on_changed()

    # ------------------------------------------------------------- doh resolve
    def _resolve(self, all_services: bool) -> None:
        if not self.catalog.profiles:
            QMessageBox.warning(self, "Нет вариантов", "Сначала добавьте варианты DNS (профили).")
            return
        target = self.target_combo.currentData()
        if not target:
            QMessageBox.warning(self, "Нет варианта", "Выберите вариант (колонку), куда записать IP.")
            return

        if all_services:
            services = list(self.catalog.services)
        else:
            svc = self._selected_service()
            if not svc:
                QMessageBox.information(self, "Сервис", "Выберите сервис в списке.")
                return
            services = [svc]

        tasks: list[tuple[str, str]] = []
        for svc in services:
            for host in svc.order:
                tasks.append((svc.name, host))
        if not tasks:
            QMessageBox.information(self, "Нет доменов", "У выбранных сервисов нет доменов.")
            return

        resolver_name = self.resolver_combo.currentText()
        want_ipv6 = self.ipv6_check.isChecked()
        worker = ResolveWorker(tasks, resolver_name, want_ipv6, self)
        self._worker = worker

        dlg = QProgressDialog("Разрешение доменов…", "Отмена", 0, len(tasks), self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.canceled.connect(worker.cancel)

        def on_progress(done, total, host):
            dlg.setValue(done)
            dlg.setLabelText(f"Разрешение: {host}  ({done}/{total})")

        def on_resolved(svc_name, host, ipv4, ipv6):
            svc = self.catalog.get_service(svc_name)
            if svc is not None and (ipv4 or ipv6):
                _set_profile_ips(svc, host, target, list(ipv4) + list(ipv6))

        def on_done(ok, total):
            dlg.setValue(total)
            self._notify_changed()
            QMessageBox.information(
                self, "Готово",
                f"Разрешено {ok} из {total} доменов через {resolver_name}.\n"
                f"IP записаны в вариант «{self.catalog.profile_display(target)}».\n"
                "Не забудьте «Сохранить каталог».",
            )

        worker.progress.connect(on_progress)
        worker.resolved.connect(on_resolved)
        worker.finished_all.connect(on_done)
        worker.start()
        dlg.exec_()
        worker.wait()

    # ---------------------------------------------------------------- actions
    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Импорт каталога (JSON)", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.catalog.load_single(path)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка импорта", str(exc))
            return
        self._notify_changed()

    def _import_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка каталога (dns_sources.json + dns/ + hosts/)")
        if not path:
            return
        try:
            self.catalog.load_split(path)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка импорта", str(exc))
            return
        self._notify_changed()

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт каталога", "catalog.json", "JSON (*.json)")
        if not path:
            return
        try:
            self.catalog.save_single(path)
            QMessageBox.information(self, "Готово", f"Сохранено: {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))

    def _save_default(self) -> None:
        try:
            self.catalog.save_single(default_catalog_path())
            QMessageBox.information(self, "Готово", "Каталог сохранён как основной (data/catalog.json).")
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))

    def _add_service(self) -> None:
        name, ok = QInputDialog.getText(self, "Новый сервис", "Название сервиса:")
        if not ok or not name.strip():
            return
        if self.catalog.get_service(name):
            QMessageBox.warning(self, "Ошибка", "Сервис с таким именем уже есть.")
            return
        self.catalog.services.append(Service(name=name.strip()))
        self._notify_changed()

    def _edit_service(self) -> None:
        svc = self._selected_service()
        if not svc:
            QMessageBox.information(self, "Сервис", "Выберите сервис.")
            return
        if not self.catalog.profiles:
            QMessageBox.warning(self, "Нет профилей", "Сначала добавьте варианты DNS (профили) в каталоге.")
            return
        dlg = DomainEditor(self.catalog, svc, self)
        if dlg.exec_() == QDialog.Accepted:
            self._notify_changed()

    def _delete_service(self) -> None:
        svc = self._selected_service()
        if not svc:
            return
        if QMessageBox.question(self, "Удалить", f"Удалить сервис «{svc.name}»?") == QMessageBox.Yes:
            self.catalog.services = [s for s in self.catalog.services if s is not svc]
            self._notify_changed()
