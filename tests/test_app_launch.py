import ctypes
import os
import subprocess
import sys
import time
import unittest
from ctypes import wintypes
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QByteArray
from PyQt6.QtWidgets import QApplication

from src.app import main
from src.utils.global_hotkey import GlobalHotkey
from src.utils.single_instance import SingleInstance


class AppLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def instance(self, name):
        instance = SingleInstance(name=name, lock_directory=Path(__file__).resolve().parent)
        self.addCleanup(instance.deleteLater)
        self.addCleanup(instance.close)
        return instance

    def notify_process(self, name, show=True):
        script = """
import sys
from PyQt6.QtCore import QCoreApplication
from src.utils.single_instance import SingleInstance
app = QCoreApplication([])
instance = SingleInstance(name=sys.argv[1], lock_directory=sys.argv[2])
print(instance.start_or_notify(show=sys.argv[3] == "show"))
instance.close()
"""
        process = subprocess.Popen([sys.executable, "-B", "-c", script, name,
                                    str(Path(__file__).resolve().parent),
                                    "show" if show else "background"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 10
        try:
            # The primary must process IPC while the launcher sends its request.
            while process.poll() is None and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)
            output, error = process.communicate(timeout=1)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        self.assertEqual(process.returncode, 0, error)
        self.assertEqual(output.strip(), "False")
        self.app.processEvents()

    def test_later_launch_opens_existing_instance(self):
        name = "file-browser-test-" + uuid4().hex
        first = self.instance(name)
        shown = []
        first.show_requested.connect(lambda: shown.append(True))
        self.assertTrue(first.start_or_notify())
        self.notify_process(name)
        self.assertEqual(shown, [True])

    def test_background_launch_does_not_open_existing_browser(self):
        name = "file-browser-test-" + uuid4().hex
        first = self.instance(name)
        shown = []
        first.show_requested.connect(lambda: shown.append(True))
        self.assertTrue(first.start_or_notify(show=False))
        self.notify_process(name, show=False)
        self.assertEqual(shown, [])

    def test_quit_releases_instance_lock(self):
        name = "file-browser-test-" + uuid4().hex
        first = self.instance(name)
        self.assertTrue(first.start_or_notify())
        first.close()
        second = self.instance(name)
        self.assertTrue(second.start_or_notify())

    def test_multiple_launches_reuse_one_instance(self):
        name = "file-browser-test-" + uuid4().hex
        first = self.instance(name)
        shown = []
        first.show_requested.connect(lambda: shown.append(True))
        self.assertTrue(first.start_or_notify())
        self.notify_process(name)
        self.notify_process(name)
        self.assertEqual(shown, [True, True])
        self.assertTrue(first.is_primary)

    def hotkey(self):
        app = Mock()
        callback = Mock()
        hotkey = GlobalHotkey(app, callback)
        hotkey.user32 = Mock()
        hotkey.user32.RegisterHotKey.return_value = True
        self.addCleanup(hotkey.unregister)
        return app, callback, hotkey

    def test_hotkey_registers_once_and_cleans_up(self):
        app, _, hotkey = self.hotkey()
        self.assertTrue(hotkey.register())
        self.assertTrue(hotkey.register())
        hotkey.user32.RegisterHotKey.assert_called_once_with(
            None, hotkey.HOTKEY_ID, hotkey.MOD_ALT | hotkey.MOD_NOREPEAT, ord("B"))
        app.installNativeEventFilter.assert_called_once_with(hotkey)
        hotkey.unregister()
        hotkey.user32.UnregisterHotKey.assert_called_once_with(None, hotkey.HOTKEY_ID)
        app.removeNativeEventFilter.assert_called_once_with(hotkey)

    def test_hotkey_conflict_is_reported(self):
        app, _, hotkey = self.hotkey()
        hotkey.user32.RegisterHotKey.return_value = False
        self.assertFalse(hotkey.register())
        self.assertIn("Alt+B", hotkey.error)
        app.installNativeEventFilter.assert_not_called()
        self.assertFalse(hotkey.registered)

    def test_only_our_hotkey_message_opens_browser(self):
        _, callback, hotkey = self.hotkey()
        hotkey.register()
        message = wintypes.MSG()
        message.message = hotkey.WM_HOTKEY
        message.wParam = hotkey.HOTKEY_ID + 1
        pointer = ctypes.addressof(message)
        self.assertEqual(hotkey.nativeEventFilter(b"windows_dispatcher_MSG", pointer), (False, 0))
        message.wParam = hotkey.HOTKEY_ID
        self.assertEqual(hotkey.nativeEventFilter(QByteArray(b"windows_dispatcher_MSG"), pointer), (True, 0))
        self.app.processEvents()
        callback.assert_called_once()

    def test_normal_and_background_launch_modes(self):
        for arguments, show in (([], True), (["--background"], False)):
            with self.subTest(arguments=arguments), patch("src.app.WinTrayApp") as app_class:
                app = app_class.return_value
                app.is_primary = True
                app.exec.return_value = 0
                self.assertEqual(main(arguments), 0)
                app_class.assert_called_once_with(show_on_start=show)
                app.exec.assert_called_once()
                app.global_hotkey.unregister.assert_called_once()
                app.instance.close.assert_called_once()

    def test_secondary_exits_without_starting_an_event_loop(self):
        with patch("src.app.WinTrayApp") as app_class:
            app = app_class.return_value
            app.is_primary = False
            self.assertEqual(main([]), 0)
            app.exec.assert_not_called()


if __name__ == "__main__":
    unittest.main()
