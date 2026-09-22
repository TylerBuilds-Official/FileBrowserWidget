from pathlib import Path

from src.ui.file_browser import FileBrowser
from src.ui.ui_functions import UIFunctions
from src.utils.system_theme import SystemTheme
from src.utils.global_hotkey import GlobalHotkey
from src.utils.single_instance import SingleInstance
from src.utils.startup import Startup
from src.utils.assets import asset
from src.ui import motion
from src.version import VERSION

from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (QMenu,
                             QApplication, QSystemTrayIcon)



class WinTrayApp(QApplication):
    def __init__(self, user_launch=True):
        super().__init__([])
        self.setQuitOnLastWindowClosed(False)
        self.instance = SingleInstance(self)
        self.is_primary = self.instance.start_or_notify(show=user_launch)
        if not self.is_primary:
            return
        self.aboutToQuit.connect(self.instance.close)
        self.instance.show_requested.connect(self.show_browser)

        self.ui_functions = UIFunctions(self)

        self.setApplicationName("File Browser")
        self.setApplicationVersion(VERSION)
        self.preferences = QSettings("FileBrowserWidget", "FileBrowserWidget")
        self.theme_helper = SystemTheme(self, self.preferences)

        # Imported Widgets
        self.file_browser = FileBrowser(settings=self.preferences)
        self.file_browser.setMinWidth(400)
        self.file_browser.setMinHeight(640)
        self.file_browser.program_clicked.connect(self.open_file)
        self.file_browser.file_location_clicked.connect(self.ui_functions.open_file_location)
        self.file_browser.settings_modal.docking_position_changed.connect(self.reposition_popup)

        self.file_browser.settings_modal.theme_mode_changed.connect(self.theme_helper.set_mode)

        self.logo = QIcon(asset("logo/fb_icon.ico"))
        self.setWindowIcon(self.logo)

        # Tray Icon
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self.logo)
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

        # add menu to tray
        self.tray_icon.setContextMenu(self.menu)

        self.global_hotkey = GlobalHotkey(self, self.hotkey_activated)
        self.startup = Startup()
        modal = self.file_browser.settings_modal
        modal.startup_changed.connect(self.set_startup)
        modal.hotkey_changed.connect(self.set_hotkey)
        modal.opened.connect(self.refresh_startup_state)
        self.refresh_startup_state()
        saved_hotkey = self.preferences.value("shortcuts/open", "Alt+B")
        if not self.set_hotkey(saved_hotkey):
            QTimer.singleShot(1000, self.show_hotkey_error)
        if user_launch:
            QTimer.singleShot(0, self.show_intro)


    def refresh_startup_state(self):
        modal = self.file_browser.settings_modal
        try:
            modal.set_startup_enabled(self.startup.is_enabled())
        except OSError as error:
            modal.integration_status.setText(str(error))

    def set_startup(self, enabled):
        modal = self.file_browser.settings_modal
        try:
            self.startup.set_enabled(enabled)
            modal.integration_status.setText("Startup enabled." if enabled else "Startup disabled.")
        except OSError as error:
            modal.integration_status.setText(str(error))
        self.refresh_startup_state()

    def set_hotkey(self, sequence):
        modal = self.file_browser.settings_modal
        success = self.global_hotkey.register(sequence)
        if success:
            self.preferences.setValue("shortcuts/open", self.global_hotkey.sequence)
            modal.set_hotkey(self.global_hotkey.sequence)
            modal.integration_status.setText(f"{self.global_hotkey.sequence} opens File Browser.")
        else:
            modal.integration_status.setText(self.global_hotkey.error)
            modal.set_hotkey(self.global_hotkey.sequence if self.global_hotkey.registered
                             else self.preferences.value("shortcuts/open", "Alt+B"))
        label = self.global_hotkey.sequence if self.global_hotkey.registered else "shortcut unavailable"
        self.open_action.setText(f"Open File Browser ({label})")
        self.tray_icon.setToolTip(f"File Browser ({label})")
        return success

    def kill_app(self):
        self.quit()

    def hotkey_activated(self):
        """The shortcut opens the panel and, while it is open, closes it again."""

        browser = self.file_browser
        editor = browser.settings_modal.hotkey_edit
        # Windows consumes the active combination before the recorder sees it.
        if editor.isVisible() and (editor.hasFocus() or editor.isAncestorOf(self.focusWidget())):
            editor.setKeySequence(self.global_hotkey.sequence)
            return
        if browser.isVisible():
            browser.hide()
        else:
            self.show_browser()

    def tray_click_router(self, reason):
        """A tray click toggles the panel; the press that closed it is not also an open."""

        if reason != QSystemTrayIcon.ActivationReason.Trigger:
            return
        browser = self.file_browser
        if browser.isVisible():
            browser.hide()
        elif not browser.dismissed_by_press_in(self.tray_icon.geometry()):
            self.show_browser()

    def show_browser(self):
        browser = self.file_browser
        browser.settings_modal.hide_settings(animated=False)
        arriving = not browser.isVisible()
        if arriving:
            browser.reset_location()
            browser.prepare_arrival()
        scanning = browser.needs_scan()
        if scanning:
            browser.show_scanning()
        browser.show()
        self.reposition_popup()
        browser.raise_()
        browser.activateWindow()
        if arriving:
            browser.arrive()
        if scanning:
            # Put the panel on screen first; reading a cold folder takes a moment.
            QTimer.singleShot(0, browser.ensure_loaded)

    def show_intro(self):
        """Starting the app leaves the panel closed, so say once where it went."""
        if self.preferences.value("intro/shown", False, type=bool):
            return
        if self.global_hotkey.error:
            return  # The shortcut warning already says the app is running.
        self.preferences.setValue("intro/shown", True)
        self.tray_icon.showMessage("File Browser is running",
                                  f"Open it from the tray icon or with {self.global_hotkey.sequence}.",
                                  QSystemTrayIcon.MessageIcon.Information)

    def show_hotkey_error(self):
        self.tray_icon.showMessage("File Browser", self.global_hotkey.error,
                                  QSystemTrayIcon.MessageIcon.Warning)

    def reposition_popup(self):
        """A docking change glides the showing panel to its new corner; otherwise just place it."""

        browser = self.file_browser
        target = self.ui_functions.get_popup_pos()
        if browser.isVisible() and browser.windowOpacity() == 1.0:
            motion.travel(browser, target, motion.SLOW)
        else:
            browser.move(target)

    def open_file(self, signal):
        self.ui_functions.open_file(Path(signal))

    def report_file_error(self, path, error):
        self.file_browser.status_label.setText("Could not open item. See details.")
        details = f"{path}\n{error}"
        self.file_browser.status_label.setToolTip(details)
        self.tray_icon.showMessage("Could not open item", details,
                                  QSystemTrayIcon.MessageIcon.Warning)
