from pathlib import Path

from src.ui.file_browser import FileBrowser
from src.ui.ui_functions import UIFunctions
from src.utils.system_theme import SystemTheme

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (QMenu,
                             QApplication, QSystemTrayIcon)



class WinTrayApp(QApplication):
    def __init__(self):
        super().__init__([])

        self.ui_functions = UIFunctions(self)

        # App Configs
        self.setQuitOnLastWindowClosed(False)

        self.setApplicationName("File Browser")
        self.preferences = QSettings("FileBrowserWidget", "FileBrowserWidget")
        self.theme_helper = SystemTheme(self, self.preferences)

        # Assets are resolved independently of the working directory.
        assets_dir = Path(__file__).resolve().parents[1] / "assets"

        # Imported Widgets
        self.file_browser = FileBrowser(settings=self.preferences)
        self.file_browser.setMinWidth(400)
        self.file_browser.setMinHeight(640)
        self.file_browser.program_clicked.connect(self.open_file)
        self.file_browser.file_location_clicked.connect(self.ui_functions.open_file_location)
        self.file_browser.settings_modal.docking_position_changed.connect(self.reposition_popup)

        self.file_browser.settings_modal.theme_mode_changed.connect(self.theme_helper.set_mode)

        icon_path = assets_dir / "filter.ico"

        # Tray Icon
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(QIcon(str(icon_path)))
        self.tray_icon.show()
        self.tray_icon.setToolTip("File Browser")

        self.tray_icon.activated.connect(self.tray_click_router)

        # Menu and actions
        self.menu = QMenu()

        self.quit_action = QAction(text="Quit")
        self.quit_action.triggered.connect(self.kill_app)
        self.menu.addAction(self.quit_action)

        self.test_action = QAction(text="Test")
        self.test_action.triggered.connect(self.test_func_connection)
        self.menu.addAction(self.test_action)

        # add menu to tray
        self.tray_icon.setContextMenu(self.menu)


    def kill_app(self):
        self.quit()

    def tray_click_router(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            print("Left Click")
            self.file_browser.show()
            self.file_browser.raise_()
            self.file_browser.activateWindow()
            self.file_browser.settings_modal.hide_settings(animated=False)


            self.file_browser.create_list_items()
            self.reposition_popup()

        if reason == QSystemTrayIcon.ActivationReason.Context:
            print("Right Click")

        if reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            print("Middle Click")

        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            print("Double Click")

    def reposition_popup(self):
        self.file_browser.move(self.ui_functions.get_popup_pos())

    def open_file(self, signal):
        print("Opening file: ", signal)
        self.ui_functions.open_file(Path(signal))

    def test_func_connection(self):
        print("Test func called")
        print(self.ui_functions.get_popup_pos())
