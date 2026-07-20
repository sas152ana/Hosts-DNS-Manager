# -*- coding: utf-8 -*-
"""Hosts & DNS Manager - упрощённый аналог вкладок hosts/DNS из zapret.

Стек: Python 3 + PyQt5. ОС: Windows (часть функций работает и на Linux).

Запуск:
    python main.py
На Windows при старте запрашиваются права администратора (нужны для записи hosts и смены DNS).
"""

import os
import sys

# Гарантируем, что пакет app импортируется независимо от текущей папки.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.admin import ensure_admin  # noqa: E402


def main() -> int:
    # На Windows перезапускаемся с правами админа до импорта тяжёлых библиотек.
    if ensure_admin():
        return 0  # управление ушло в перезапущенный процесс

    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QIcon
    from app.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Hosts & DNS Manager")

    # Иконка приложения (работает и из исходников, и из собранного exe)
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    from app.gui.theme import apply_theme, load_theme
    apply_theme(app, load_theme())

    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
