from pathlib import Path

from src.ui.file_browser import FileBrowser
from src.ui.ui_functions import UIFunctions
from src.utils.system_theme import SystemTheme
from src.utils.global_hotkey import GlobalHotkey
from src.utils.single_instance import SingleInstance

from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (QMenu,
                             QApplication, QSystemTrayIcon)



class WinTrayApp(QApplication):
    def __init__(self, show_on_start=True):
        super().__init__([])
        self.setQuitOnLastWindowClosed(False)
        self.instance = SingleInstance(self)
        self.is_primary = self.instance.start_or_notify(show=show_on_start)
        if not self.is_primary:
            return
        self.aboutToQuit.connect(self.instance.close)
        self.instance.show_requested.connect(self.show_browser)

        self.ui_functions = UIFunctions(self)

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

        self.open_action = QAction(text="Open File Browser (Alt+B)")
        self.open_action.triggered.connect(self.show_browser)
        self.menu.addAction(self.open_action)
        self.menu.addSeparator()

        self.quit_action = QAction(text="Quit")
        self.quit_action.triggered.connect(self.kill_app)
        self.menu.addAction(self.quit_action)

        self.test_action = QAction(text="Test")
        self.test_action.triggered.connect(self.test_func_connection)
        self.menu.addAction(self.test_action)

        # add menu to tray
        self.tray_icon.setContextMenu(self.menu)

        self.global_hotkey = GlobalHotkey(self, self.show_browser)
        if not self.global_hotkey.register():
            self.open_action.setText("Open File Browser (Alt+B unavailable)")
            self.tray_icon.setToolTip("File Browser â€” Alt+B unavailable")
            QTimer.singleShot(1000, self.show_hotkey_error)
        if show_on_start:
            QTimer.singleShot(0, self.show_browser)


    def kill_app(self):
        self.quit()

    def tray_click_router(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_browser()

    def show_browser(self):
        self.file_browser.settings_modal.hide_settings(animated=False)
        self.file_browser.create_list_items()
        self.file_browser.show()
        self.reposition_popup()
        self.file_browser.raise_()
        self.file_browser.activateWindow()

    def show_hotkey_error(self):
        self.tray_icon.showMessage("File Browser", self.global_hotkey.error,
                                  QSystemTrayIcon.MessageIcon.Warning)

    def reposition_popup(self):
        self.file_browser.move(self.ui_functions.get_popup_pos())

    def open_file(self, signal):
        print("Opening file: ", signal)
        self.ui_functions.open_file(Path(signal))

    def test_func_connection(self):
        print("Test func called")
        print(self.ui_functions.get_popup_pos())
