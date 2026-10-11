# -*- coding: utf-8 -*-
"""Вкладка «Каталог»: просмотр, редактирование, импорт/экспорт и автозаполнение IP."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QFileDialog, QLabel, QDialog, QComboBox,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QHeaderView, QInputDialog, QProgressDialog, QGroupBox, QMenu,
)

from app.catalog import Catalog, Service, default_catalog_path
from app import resolver
from app.catalog_updater import update_catalog


class AutoFillWorker(QThread):
    done_signal = pyqtSignal(bool)

    def run(self):
        code = update_catalog(pre_check_ai=True)
        self.done_signal.emit(code == 0)


def _set_profile_ips(svc: Service, host: str, profile_id: str, ips: list[str]) -> None:
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
    progress = pyqtSignal(int, int, str)
    resolved = pyqtSignal(str, str, list, list)
    finished_all = pyqtSignal(int, int)

    def __init__(self, tasks, resolver_name, want_ipv6, parent=None) -> None:
        super().__init__(parent)
        self._tasks = list(tasks)
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
    def __init__(self, catalog: Catalog, service: Service, parent=None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.service = service
        self.setWindowTitle(f"Каталог: {service.name}")
        self.resize(780, 500)

        layout = QVBoxLayout(self)

        # Выбор / смена категории сервиса
        cat_box = QHBoxLayout()
        cat_box.addWidget(QLabel("Категория (группа):"))
        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        existing_cats = sorted(set(filter(None, [s.category for s in catalog.services])))
        self.cat_combo.addItems(existing_cats)
        self.cat_combo.setEditText(service.category or "Остальные")
        cat_box.addWidget(self.cat_combo, 1)
        layout.addLayout(cat_box)

        layout.addWidget(QLabel(
            "Строки — домены, колонки — варианты DNS. Несколько IP вводятся через запятую."
        ))

        self.profiles = list(catalog.profiles)
        self.table = QTableWidget(0, 1 + len(self.profiles))
        headers = ["Домен"] + [catalog.profile_display(p) for p in self.profiles]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        for host in service.order:
            self._add_row(host, service.domains.get(host, {}))

        btns = QHBoxLayout()
        add = QPushButton("+ Добавить домен")
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

    def _save(self) -> None:
        self.service.category = self.cat_combo.currentText().strip() or "Остальные"
        self.service.domains = {}
        self.service.order = []
        for r in range(self.table.rowCount()):
            host_item = self.table.item(r, 0)
            host = (host_item.text() if host_item else "").strip().casefold()
            if not host:
                continue
            # Сохраняем домен в списке порядка, даже если IP пока не заполнены
            if host not in self.service.order:
                self.service.order.append(host)
            bucket = self.service.domains.setdefault(host, {})

            for col, pid in enumerate(self.profiles, start=1):
                cell = self.table.item(r, col)
                raw = cell.text() if cell else ""
                ips = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
                if ips:
                    bucket[pid] = ips
        self.accept()


class CatalogTab(QWidget):
    def __init__(self, catalog: Catalog, on_changed=None) -> None:
        super().__init__()
        self.catalog = catalog
        self.on_changed = on_changed
        self._worker = None

        root = QVBoxLayout(self)

        # 1. Верхняя панель: управление сервисами и меню каталога
        top_bar = QHBoxLayout()
        add_btn = QPushButton("+ Сервис")
        add_btn.clicked.connect(self._add_service)
        edit_btn = QPushButton("Редактировать")
        edit_btn.clicked.connect(self._edit_service)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_service)

        top_bar.addWidget(add_btn)
        top_bar.addWidget(edit_btn)
        top_bar.addWidget(del_btn)
        top_bar.addStretch(1)

        # Выпадающее меню «Файл / Каталог»
        menu_btn = QPushButton("Каталог ▾")
        file_menu = QMenu(self)
        file_menu.addAction("Сохранить изменения (catalog.json)", self._save_default)
        file_menu.addSeparator()
        file_menu.addAction("Импорт из JSON…", self._import_json)
        file_menu.addAction("Экспорт в JSON…", self._export_json)
        file_menu.addAction("Импорт из папки (формат zapret)…", self._import_dir)
        menu_btn.setMenu(file_menu)
        top_bar.addWidget(menu_btn)

        save_quick = QPushButton("Сохранить")
        save_quick.setStyleSheet("font-weight:bold;")
        save_quick.clicked.connect(self._save_default)
        top_bar.addWidget(save_quick)

        root.addLayout(top_bar)

        # 2. Центральное дерево каталога
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Сервис / домен", "Варианты с IP-адресами"])
        self.tree.setColumnWidth(0, 380)
        self.tree.itemDoubleClicked.connect(lambda *_: self._edit_service())
        root.addWidget(self.tree, 1)

        # 3. Блок 1: Автозаполнение рабочих IP нейросетей через SmartDNS (Основное)
        smart_box = QGroupBox("Обновление обходных IP для нейросетей (SmartDNS)")
        smart_layout = QHBoxLayout(smart_box)
        smart_info = QLabel(
            "Автоматически тестирует SmartDNS (DNS-AI, Comss, GeoHide и др.), находит живые серверы "
            "и заполняет рабочие прокси-IP для ChatGPT, Claude, Gemini в каталоге."
        )
        smart_info.setWordWrap(True)
        smart_info.setStyleSheet("color:#aaa;")
        smart_layout.addWidget(smart_info, 1)

        autofill_btn = QPushButton("⚡ Обновить IP через SmartDNS")
        autofill_btn.setStyleSheet("font-weight:bold; padding:8px 14px;")
        autofill_btn.clicked.connect(self._start_autofill)
        smart_layout.addWidget(autofill_btn)
        root.addWidget(smart_box)

        # 4. Блок 2: Прямой DoH-резолвинг (Дополнительно, для незаблокированных сервисов)
        direct_box = QGroupBox("Дополнительно: прямое разрешение IP через публичный DoH")
        direct_layout = QHBoxLayout(direct_box)

        direct_layout.addWidget(QLabel("Резолвер:"))
        self.resolver_combo = QComboBox()
        self.resolver_combo.addItems(resolver.resolver_names())
        direct_layout.addWidget(self.resolver_combo)

        direct_layout.addWidget(QLabel("→ в профиль:"))
        self.target_combo = QComboBox()
        self._reload_target_combo()
        direct_layout.addWidget(self.target_combo)

        self.ipv6_check = QCheckBox("IPv6")
        direct_layout.addWidget(self.ipv6_check)

        direct_layout.addStretch(1)
        b_one = QPushButton("Заполнить для выбранного")
        b_one.clicked.connect(lambda: self._resolve(all_services=False))
        b_all = QPushButton("Заполнить для всех")
        b_all.clicked.connect(lambda: self._resolve(all_services=True))
        direct_layout.addWidget(b_one)
        direct_layout.addWidget(b_all)

        root.addWidget(direct_box)

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

    def _resolve(self, all_services: bool) -> None:
        if not self.catalog.profiles:
            QMessageBox.warning(self, "Нет вариантов", "Сначала добавьте варианты DNS в каталоге.")
            return
        target = self.target_combo.currentData()
        if not target:
            QMessageBox.warning(self, "Нет варианта", "Выберите вариант, куда записать IP.")
            return

        if all_services:
            services = list(self.catalog.services)
        else:
            svc = self._selected_service()
            if not svc:
                QMessageBox.information(self, "Сервис", "Выберите сервис в списке выше.")
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

        dlg = QProgressDialog("Разрешение доменов через DoH…", "Отмена", 0, len(tasks), self)
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
                f"IP записаны в профиль «{self.catalog.profile_display(target)}».\n"
                "Не забудьте нажать «Сохранить».",
            )

        worker.progress.connect(on_progress)
        worker.resolved.connect(on_resolved)
        worker.finished_all.connect(on_done)
        worker.start()
        dlg.exec_()
        worker.wait()

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
            QMessageBox.information(self, "Готово", "Каталог успешно сохранён в data/catalog.json.")
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))

    def _add_service(self) -> None:
        from app.gui.add_service_dialog import AddServiceDialog
        existing_cats = [s.category for s in self.catalog.services]
        dlg = AddServiceDialog(existing_cats, self)
        if dlg.exec_() != AddServiceDialog.Accepted:
            return

        data = dlg.get_data()
        name = data["name"]
        if self.catalog.get_service(name):
            QMessageBox.warning(self, "Ошибка", f"Сервис «{name}» уже существует.")
            return

        mode = data["mode"]
        svc = Service(
            name=name,
            category=data["category"],
            mode=mode,
        )

        for dom in data["domains"]:
            if data["ips"]:
                for ip in data["ips"]:
                    if mode == "hosts":
                        svc.add_domain_ip(dom, "hosts", ip)
                    else:
                        for pid in self.catalog.profiles:
                            svc.add_domain_ip(dom, pid, ip)
            else:
                svc.order.append(dom)

        self.catalog.services.append(svc)
        self.catalog.save_single(default_catalog_path())
        self._notify_changed()

    def _edit_service(self) -> None:
        svc = self._selected_service()
        if not svc:
            QMessageBox.information(self, "Сервис", "Выберите сервис для редактирования.")
            return
        if not self.catalog.profiles:
            QMessageBox.warning(self, "Нет профилей", "Сначала добавьте варианты DNS в каталоге.")
            return
        dlg = DomainEditor(self.catalog, svc, self)
        if dlg.exec_() == QDialog.Accepted:
            self._notify_changed()

    def _delete_service(self) -> None:
        svc = self._selected_service()
        if not svc:
            return
        if not getattr(svc, "custom", False):
            QMessageBox.information(
                self, "Защита данных",
                f"Сервис «{svc.name}» является встроенным. "
                "Его нельзя удалить, но вы можете отключить его галочкой на вкладке «Сайты (hosts)»."
            )
            return

        if QMessageBox.question(self, "Удалить", f"Удалить пользовательский сервис «{svc.name}»?") == QMessageBox.Yes:
            self.catalog.services = [s for s in self.catalog.services if s is not svc]
            self.catalog.save_single(default_catalog_path())
            self._notify_changed()

    def _start_autofill(self) -> None:
        msg = QMessageBox.question(
            self,
            "Автозаполнение каталога",
            "Запустить онлайн-проверку DoH SmartDNS и обновление IP-адресов в catalog.json?\n\n"
            "Скрипт протестирует доступность ChatGPT, Claude и Google AI, отберет живые шлюзы "
            "и запишет актуальные адреса для обхода геоблокировок.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if msg != QMessageBox.Yes:
            return

        prog = QProgressDialog("Опрос SmartDNS и наполнение каталога…", None, 0, 0, self)
        prog.setWindowModality(Qt.WindowModal)
        prog.show()

        self._af_worker = AutoFillWorker(self)

        def on_done(ok):
            prog.close()
            if ok:
                self.catalog.load_single(default_catalog_path())
                self._notify_changed()
                QMessageBox.information(self, "Готово", "Каталог успешно обновлен рабочими IP от SmartDNS!")
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось обновить каталог.")

        self._af_worker.done_signal.connect(on_done)
        self._af_worker.start()