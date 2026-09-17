from pathlib import Path

from src.ui.file_browser import FileBrowser

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (QMainWindow, QMenu,
                             QApplication, QSystemTrayIcon)



class ScratchApp(QApplication):
    def __init__(self):
        super().__init__([])
        # App Configs
        self.setQuitOnLastWindowClosed(False)

        # Shared stylesheet, resolved independently of the working directory.
        assets_dir = Path(__file__).resolve().parents[1] / "assets"
        self.setStyleSheet((assets_dir / "styles.qss").read_text(encoding="utf-8"))

        # Imported Widgets
        self.file_browser = FileBrowser()

        icon_path = assets_dir / "filter.ico"

        # Tray Icon
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(QIcon(str(icon_path)))
        self.tray_icon.show()
        self.tray_icon.setToolTip("Scratch App")

        self.tray_icon.activated.connect(self.action_router)

        # Menu and actions
        self.menu = QMenu()

        self.quit_action = QAction(text="Quit")
        self.quit_action.triggered.connect(self.kill_app)
        self.menu.addAction(self.quit_action)

        # add menu to tray
        self.tray_icon.setContextMenu(self.menu)


    def kill_app(self):
        self.quit()

    def action_router(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            print("Left Click")
            self.file_browser.show()
            self.file_browser.raise_()
            self.file_browser.activateWindow()
            self.file_browser.move(self.tray_icon.geometry().topLeft())
            self.file_browser.create_list_items()

        if reason == QSystemTrayIcon.ActivationReason.Context:
            print("Right Click")

        if reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            print("Middle Click")

        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            print("Double Click")
