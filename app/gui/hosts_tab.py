# -*- coding: utf-8 -*-
"""Вкладка «Сайты (hosts)»: выбор сервисов и варианта DNS по каждому."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QGridLayout, QLabel,
    QCheckBox, QComboBox, QPushButton, QLineEdit, QMessageBox, QFrame,
    QFileDialog, QInputDialog, QDialog,
)

from app.catalog import Catalog, load_selection, save_selection
from app.hosts_manager import HostsManager

OFF_LABEL = "— выкл —"


class ServiceRow:
    def __init__(self, service, all_profiles, profile_display):
        self.service = service
        self.check = QCheckBox()
        self.color = QLabel()
        self.color.setFixedSize(12, 12)
        self.color.setStyleSheet(f"background:{service.color};border-radius:6px;")
        self.name = QLabel(service.name)
        self.name.setWordWrap(True)
        self.combo = QComboBox()
        self.combo.addItem(OFF_LABEL, userData="")
        self.available = service.available_profiles(all_profiles)
        for pid in self.available:
            self.combo.addItem(profile_display(pid), userData=pid)

        # --- Автоматическая синхронизация чекбокса и комбобокса ---
        self.combo.activated.connect(self._on_combo_changed)
        self.check.toggled.connect(self._on_check_toggled)

        if not self.available:
            self.name.setToolTip("Нет IP-адресов ни для одного варианта. Заполните во вкладке «Каталог».")
            self.combo.setEnabled(False)
            self.check.setEnabled(False)

    def _on_combo_changed(self) -> None:
        """Если выбрали DNS — автоматически ставим галочку; если «— выкл —» — снимаем."""
        self.check.setChecked(bool(self.combo.currentData()))

    def _on_check_toggled(self, checked: bool) -> None:
        """Если поставили галочку, а профиль не выбран — выбираем первый доступный."""
        if checked and not self.combo.currentData() and self.available:
            self.combo.setCurrentIndex(1)
        elif not checked and self.combo.currentIndex() != 0:
            self.combo.setCurrentIndex(0)

    def selected_profile(self) -> str:
        if not self.check.isChecked():
            return ""
        return self.combo.currentData() or ""

    def set_selection(self, profile_id: str) -> None:
        if not profile_id:
            self.check.setChecked(False)
            return
        idx = self.combo.findData(profile_id)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
            self.check.setChecked(True)


class HostsTab(QWidget):
    def __init__(self, catalog: Catalog, on_changed=None) -> None:
        super().__init__()
        self.catalog = catalog
        self.on_changed = on_changed
        self.manager = HostsManager()
        self.rows: list[ServiceRow] = []

        root = QVBoxLayout(self)

        # Верхняя панель: поиск + массовые действия
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск сервиса…")
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search, 1)

        self.bulk_combo = QComboBox()
        self.bulk_combo.setToolTip("Массово выбрать вариант DNS для всех доступных сервисов")
        top.addWidget(QLabel("Всем:"))
        top.addWidget(self.bulk_combo)
        btn_all = QPushButton("Вкл. все")
        btn_all.clicked.connect(self._enable_all)
        btn_none = QPushButton("Выкл. все")
        btn_none.clicked.connect(self._disable_all)
        top.addWidget(btn_all)
        top.addWidget(btn_none)

        btn_add = QPushButton("+ Добавить сайт")
        btn_add.setStyleSheet("font-weight:bold;")
        btn_add.setToolTip("Добавить свой сайт/сервис с доменами и группой")
        btn_add.clicked.connect(self._add_custom_service)
        top.addWidget(btn_add)

        btn_add_cat = QPushButton("+ Категория")
        btn_add_cat.setToolTip("Создать новую категорию для группировки сайтов")
        btn_add_cat.clicked.connect(self._create_category)
        top.addWidget(btn_add_cat)

        btn_detect = QPushButton("Считать из hosts")
        btn_detect.setToolTip("Определить уже применённые настройки из текущего файла hosts")
        btn_detect.clicked.connect(self.rebuild)
        top.addWidget(btn_detect)
        root.addLayout(top)

        # Область со списком сервисов
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setColumnStretch(2, 1)
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

        # Нижняя панель
        bottom = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("statusLabel")
        bottom.addWidget(self.status, 1)

        for text, slot in (
            ("Открыть hosts", self._open_hosts),
            ("Восстановить бэкап", self._restore_backup),
            ("Очистить блок", self._clear),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bottom.addWidget(b)
        self.apply_btn = QPushButton("Применить в hosts")
        self.apply_btn.setStyleSheet("font-weight:bold;")
        self.apply_btn.clicked.connect(self._apply)
        bottom.addWidget(self.apply_btn)
        root.addLayout(bottom)

        self.rebuild()

    # ------------------------------------------------------------------ build
    def rebuild(self) -> None:
        # Очистка сетки
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.rows = []

        header = ["✓", "", "Сервис", "Вариант DNS"]
        for col, text in enumerate(header):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-weight:bold;color:#aaa;")
            self.grid.addWidget(lbl, 0, col)

        profiles = self.catalog.profiles
        # Умное авто-определение: читаем весь hosts и сопоставляем IP с известными вариантами
        try:
            detected = self.catalog.detect_selection(self.manager.get_all_domain_map())
        except Exception:
            detected = {}
        self._detected_count = len(detected)
        # Приоритет — реальное состояние hosts; если ничего не найдено — сохранённый выбор
        selection = detected if detected else load_selection()

        # Доступные варианты DNS по категориям (для группового переключения)
        cat_profiles: dict[str, list[str]] = {}
        for svc in self.catalog.services:
            cat_key = svc.category or "Прочее"
            bucket = cat_profiles.setdefault(cat_key, [])
            for pid in svc.available_profiles(profiles):
                if pid not in bucket:
                    bucket.append(pid)

        self.headers = []  # [{category, row, widget, combo}]
        r = 1
        prev_cat = None
        for svc in self.catalog.services:
            cat = svc.category or "Прочее"
            if cat != prev_cat:
                hdr = QFrame()
                hdr.setObjectName("catHeader")
                hdr.setContextMenuPolicy(Qt.CustomContextMenu)
                hdr.customContextMenuRequested.connect(
                    lambda pos, c=cat: self._show_category_context_menu(pos, c)
                )
                hl = QHBoxLayout(hdr)
                hl.setContentsMargins(8, 4, 8, 4)
                title = QLabel(cat)
                title.setObjectName("catTitle")
                title.setToolTip("Правый клик: переименовать категорию")
                hl.addWidget(title)
                hl.addStretch(1)
                gl = QLabel("Всей группе:")
                hl.addWidget(gl)
                gcombo = QComboBox()
                gcombo.setToolTip("Выбрать вариант DNS сразу для всей группы")
                gcombo.addItem(OFF_LABEL, userData="")
                for pid in cat_profiles.get(cat, []):
                    gcombo.addItem(self.catalog.profile_display(pid), userData=pid)
                gcombo.activated.connect(
                    lambda _i, c=cat, cb=gcombo: self._set_group(c, cb.currentData() or "")
                )
                hl.addWidget(gcombo)
                self.grid.addWidget(hdr, r, 0, 1, 4)
                self.headers.append({"category": cat, "row": r, "widget": hdr, "combo": gcombo})
                prev_cat = cat
                r += 1

            row = ServiceRow(svc, profiles, self.catalog.profile_display)
            row.grid_row = r
            row.category = cat

            # Контекстное меню и подсказки для сервиса
            row.name.setContextMenuPolicy(Qt.CustomContextMenu)
            row.name.customContextMenuRequested.connect(
                lambda pos, s=svc: self._show_service_context_menu(pos, s)
            )
            # Двойной клик на имени открывает редактирование
            row.name.mouseDoubleClickEvent = lambda evt, s=svc: self._edit_service_modal(s)

            if svc.custom:
                row.name.setText(f"{svc.name}  ★")
                row.name.setToolTip("Пользовательский сайт (★). Двойной клик — редактировать, правый клик — меню действий.")
            else:
                row.name.setToolTip("Встроенный сайт. Двойной клик — просмотр/редактирование, правый клик — меню.")

            self.grid.addWidget(row.check, r, 0, alignment=Qt.AlignCenter)
            self.grid.addWidget(row.color, r, 1, alignment=Qt.AlignCenter)
            self.grid.addWidget(row.name, r, 2)
            self.grid.addWidget(row.combo, r, 3)
            if svc.name in selection:
                row.set_selection(selection[svc.name])
            self.rows.append(row)
            r += 1

        # Заполняем bulk_combo всеми профилями
        self.bulk_combo.clear()
        self.bulk_combo.addItem(OFF_LABEL, userData="")
        for pid in profiles:
            self.bulk_combo.addItem(self.catalog.profile_display(pid), userData=pid)

        self._refresh_status()

    # ---------------------------------------------------------------- filters
    def _apply_filter(self, text: str) -> None:
        text = (text or "").casefold()
        visible_cats: set[str] = set()
        for row in self.rows:
            visible = text in row.service.name.casefold()
            if visible:
                visible_cats.add(getattr(row, "category", ""))
            for col in range(4):
                item = self.grid.itemAtPosition(row.grid_row, col)
                if item and item.widget():
                    item.widget().setVisible(visible)
        # Заголовок категории виден, только если виден хотя бы один её сервис
        for hdr in getattr(self, "headers", []):
            hdr["widget"].setVisible(hdr["category"] in visible_cats)

    def _enable_all(self) -> None:
        pid = self.bulk_combo.currentData() or ""
        for row in self.rows:
            if not row.available:
                continue
            if pid and row.combo.findData(pid) >= 0:
                row.set_selection(pid)
            else:
                # берём первый доступный
                if row.available:
                    row.set_selection(row.available[0])

    def _disable_all(self) -> None:
        for row in self.rows:
            row.check.setChecked(False)

    def _set_group(self, category: str, profile_id: str) -> None:
        """Установить вариант DNS сразу для всей категории."""
        for row in self.rows:
            if getattr(row, "category", "") != category:
                continue
            if not row.available:
                continue
            if not profile_id:
                row.check.setChecked(False)
            elif row.combo.findData(profile_id) >= 0:
                row.set_selection(profile_id)

    # ---------------------------------------------------------------- actions
    def _managed_domains(self) -> set[str]:
        """Все домены из каталога — ими управляет приложение."""
        doms: set[str] = set()
        for svc in self.catalog.services:
            for host in svc.order:
                doms.add(host)
        return doms

    def _current_selection(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in self.rows:
            pid = row.selected_profile()
            if pid:
                out[row.service.name] = pid
        return out

    def _apply(self) -> None:
        selection = self._current_selection()
        save_selection(selection)

        rows: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for svc_name, pid in selection.items():
            svc = self.catalog.get_service(svc_name)
            if not svc:
                continue
            for domain, ip in svc.rows_for_profile(pid):
                key = (domain.casefold(), ip.casefold())
                if key not in seen:
                    seen.add(key)
                    rows.append((domain, ip))

        if not rows:
            QMessageBox.information(
                self, "Нечего применять",
                "Не выбрано ни одного сервиса с заполненными IP.\n"
                "Блок hosts будет очищен.",
            )
        result = self.manager.apply_rows(rows, self._managed_domains())
        self._toast(result.success, result.message)
        self._refresh_status()

    def _clear(self) -> None:
        result = self.manager.clear(self._managed_domains())
        self._toast(result.success, result.message)
        self._refresh_status()

    def _open_hosts(self) -> None:
        result = self.manager.open_in_editor()
        if not result.success:
            QMessageBox.warning(self, "Ошибка", result.message)

    def _restore_backup(self) -> None:
        backups = self.manager.list_backups()
        start_dir = backups[0] if backups else self.manager.path
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл бэкапа", start_dir)
        if not path:
            return
        result = self.manager.restore_backup(path)
        self._toast(result.success, result.message)
        self._refresh_status()

    # ------------------------------------------------------------------ utils
    def _refresh_status(self) -> None:
        active = self.manager.get_active_domains_map()
        access = "доступен" if self.manager.is_writable() else "только чтение (нужны права админа)"
        detected = getattr(self, "_detected_count", 0)
        self.status.setText(
            f"Активных доменов в hosts: {len(active)}  |  распознано сервисов: {detected}  |  файл: {access}"
        )

    def _toast(self, ok: bool, message: str) -> None:
        if ok:
            QMessageBox.information(self, "Готово", message)
        else:
            QMessageBox.warning(self, "Ошибка", message)
    def _save_new_service(self, data: dict) -> None:
        """Единый метод сохранения нового сервиса в каталог."""
        from app.catalog import Service, default_catalog_path

        svc_name = data["name"]
        if self.catalog.get_service(svc_name):
            QMessageBox.warning(self, "Ошибка", f"Сервис «{svc_name}» уже существует.")
            return

        mode = data["mode"]
        svc = Service(
            name=svc_name,
            category=data["category"],
            mode=mode,
            custom=True,
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
                svc.domains.setdefault(dom, {})

        self.catalog.services.append(svc)
        self.catalog.save_single(default_catalog_path())
        self.rebuild()
        if self.on_changed:
            self.on_changed()
        QMessageBox.information(
            self, "Готово",
            f"Сервис «{svc_name}» успешно добавлен в категорию «{data['category']}»."
        )

    def _add_custom_service(self) -> None:
        from app.gui.add_service_dialog import AddServiceDialog
        existing_cats = [s.category for s in self.catalog.services]
        dlg = AddServiceDialog(existing_cats, self)
        if dlg.exec_() == QDialog.Accepted:
            self._save_new_service(dlg.get_data())
    # -------------------------------------------------- service context menu
    def _show_service_context_menu(self, pos, service) -> None:
        from PyQt5.QtWidgets import QMenu, QAction
        from app.catalog import default_catalog_path

        menu = QMenu(self)

        # 1. Редактировать
        act_edit = menu.addAction("✏️ Редактировать сервис / домены…")
        act_edit.triggered.connect(lambda: self._edit_service_modal(service))

        # 2. Переместить в категорию (подменю)
        move_menu = menu.addMenu("📁 Переместить в категорию")
        all_cats = sorted(set(filter(None, [s.category for s in self.catalog.services])))
        for cat in all_cats:
            if cat != service.category:
                act_cat = move_menu.addAction(cat)
                act_cat.triggered.connect(lambda _, c=cat, s=service: self._move_service_to_category(s, c))

        move_menu.addSeparator()
        act_new_cat = move_menu.addAction("＋ Создать новую категорию…")
        act_new_cat.triggered.connect(lambda _, s=service: self._move_service_to_new_category(s))

        menu.addSeparator()

        # 3. Удалить сервис
        act_del = menu.addAction("🗑️ Удалить сервис")
        if not service.custom:
            act_del.setEnabled(False)
            act_del.setText("🗑️ Удалить (встроенный сервис защищен)")
        else:
            act_del.triggered.connect(lambda _, s=service: self._delete_custom_service(s))

        menu.exec_(self.sender().mapToGlobal(pos))

    def _edit_service_modal(self, service) -> None:
        from app.gui.catalog_tab import DomainEditor
        from app.catalog import default_catalog_path

        dlg = DomainEditor(self.catalog, service, self)
        if dlg.exec_() == QDialog.Accepted:
            self.catalog.save_single(default_catalog_path())
            self.rebuild()
            if self.on_changed:
                self.on_changed()

    def _move_service_to_category(self, service, new_category: str) -> None:
        from app.catalog import default_catalog_path
        service.category = new_category.strip()
        self.catalog.save_single(default_catalog_path())
        self.rebuild()
        if self.on_changed:
            self.on_changed()

    def _move_service_to_new_category(self, service) -> None:
        from app.catalog import default_catalog_path
        name, ok = QInputDialog.getText(self, "Новая категория", "Введите название новой категории:")
        if ok and name.strip():
            self._move_service_to_category(service, name.strip())

    def _delete_custom_service(self, service) -> None:
        from app.catalog import default_catalog_path, load_selection, save_selection

        res = QMessageBox.question(
            self, "Удаление",
            f"Вы уверены, что хотите удалить сайт «{service.name}» из каталога?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res != QMessageBox.Yes:
            return

        # Удаляем из сохраненных выборов
        sel = load_selection()
        if service.name in sel:
            del sel[service.name]
            save_selection(sel)

        # Удаляем из каталога
        self.catalog.remove_service(service.name)
        self.catalog.save_single(default_catalog_path())
        self.rebuild()
        if self.on_changed:
            self.on_changed()
        QMessageBox.information(self, "Готово", f"Сайт «{service.name}» удалён.")

    # ------------------------------------------------- category management
    def _create_category(self) -> None:
        name, ok = QInputDialog.getText(self, "Создать категорию", "Название новой категории:")
        if not ok or not name.strip():
            return
        cat_name = name.strip()
        existing = {s.category.casefold() for s in self.catalog.services}
        if cat_name.casefold() in existing:
            QMessageBox.information(self, "Информация", "Такая категория уже существует.")
            return

        from app.gui.add_service_dialog import AddServiceDialog
        existing_cats = [s.category for s in self.catalog.services] + [cat_name]
        dlg = AddServiceDialog(existing_cats, self)
        dlg.cat_combo.setEditText(cat_name)
        if dlg.exec_() == QDialog.Accepted:
            self._save_new_service(dlg.get_data())

    def _show_category_context_menu(self, pos, category_name: str) -> None:
        from PyQt5.QtWidgets import QMenu
        from app.catalog import default_catalog_path

        menu = QMenu(self)
        act_ren = menu.addAction(f"✏️ Переименовать категорию «{category_name}»…")

        def rename():
            new_name, ok = QInputDialog.getText(
                self, "Переименование категории",
                "Новое название категории:", text=category_name
            )
            if ok and new_name.strip() and new_name.strip() != category_name:
                self.catalog.rename_category(category_name, new_name.strip())
                self.catalog.save_single(default_catalog_path())
                self.rebuild()
                if self.on_changed:
                    self.on_changed()

        act_ren.triggered.connect(rename)
        menu.exec_(self.sender().mapToGlobal(pos))