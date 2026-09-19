import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication

from src.utils.global_hotkey import GlobalHotkey
from src.utils.startup import Startup
from src.ui.settings.settings_modal import SettingsModal
from src.ui.win_tray_app import WinTrayApp


class StartupAndHotkeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def hotkey(self):
        hotkey = GlobalHotkey(Mock(), Mock())
        hotkey.user32 = Mock()
        hotkey.user32.RegisterHotKey.return_value = True
        self.addCleanup(hotkey.unregister)
        return hotkey

    def test_changing_hotkey_registers_new_before_releasing_old(self):
        hotkey = self.hotkey()
        hotkey.register()
        hotkey.user32.reset_mock()
        self.assertTrue(hotkey.register("Ctrl+Shift+G"))
        calls = hotkey.user32.mock_calls
        self.assertEqual(calls[0].args, (None, hotkey.HOTKEY_ID + 1, 0x4006, ord("G")))
        self.assertEqual(calls[1].args, (None, hotkey.HOTKEY_ID))
        self.assertEqual(hotkey.sequence, "Ctrl+Shift+G")
        self.assertTrue(hotkey.register("Alt+B"))
        self.assertEqual(hotkey._hotkey_id, hotkey.HOTKEY_ID)

    def test_conflicting_change_keeps_original_hotkey(self):
        hotkey = self.hotkey()
        hotkey.register()
        hotkey.user32.RegisterHotKey.return_value = False
        self.assertFalse(hotkey.register("Ctrl+Alt+Q"))
        self.assertTrue(hotkey.registered)
        self.assertEqual(hotkey.sequence, "Alt+B")
        hotkey.user32.UnregisterHotKey.assert_not_called()
        self.assertIn("Ctrl+Alt+Q", hotkey.error)

    def test_invalid_keys_do_not_change_registration(self):
        hotkey = self.hotkey()
        hotkey.register()
        hotkey.user32.reset_mock()
        for sequence in ("", "B", "Shift+B", "Ctrl+F12", "Ctrl+B, Ctrl+C", "Meta+B", "Alt+Space"):
            with self.subTest(sequence=sequence):
                self.assertFalse(hotkey.register(sequence))
                self.assertTrue(hotkey.registered)
        hotkey.user32.RegisterHotKey.assert_not_called()
        hotkey.user32.UnregisterHotKey.assert_not_called()

    def test_function_key_conversion(self):
        self.assertEqual(GlobalHotkey.key_codes("Ctrl+Alt+F24"), ("Ctrl+Alt+F24", 0x4003, 0x87))

    def test_settings_emit_edits_and_reset_without_saving_unverified_shortcut(self):
        settings = Mock()
        settings.value.side_effect = lambda key, default, **kwargs: default
        modal = SettingsModal(settings=settings)
        self.addCleanup(modal.deleteLater)
        sequences = []
        modal.hotkey_changed.connect(sequences.append)
        modal.hotkey_edit.setKeySequence(QKeySequence("Ctrl+Alt+G"))
        modal.hotkey_edit.editingFinished.emit()
        modal.hotkey_reset.click()
        self.assertEqual(sequences, ["Ctrl+Alt+G", "Alt+B"])
        settings.setValue.assert_not_called()
        toggles = []
        modal.startup_changed.connect(toggles.append)
        modal.set_startup_enabled(True)
        self.assertEqual(toggles, [])
        modal.startup_check.click()
        self.assertEqual(toggles, [False])

    def test_app_saves_success_but_keeps_previous_setting_on_conflict(self):
        hotkey = self.hotkey()
        modal = SettingsModal()
        self.addCleanup(modal.deleteLater)
        app = SimpleNamespace(global_hotkey=hotkey, file_browser=SimpleNamespace(settings_modal=modal),
                              preferences=Mock(), open_action=Mock(), tray_icon=Mock())
        self.assertTrue(WinTrayApp.set_hotkey(app, "Ctrl+Alt+G"))
        app.preferences.setValue.assert_called_once_with("shortcuts/open", "Ctrl+Alt+G")
        app.preferences.reset_mock()
        hotkey.user32.RegisterHotKey.return_value = False
        self.assertFalse(WinTrayApp.set_hotkey(app, "Alt+B"))
        app.preferences.setValue.assert_not_called()
        self.assertEqual(modal.hotkey_edit.keySequence().toString(), "Ctrl+Alt+G")
        self.assertIn("could not be registered", modal.integration_status.text())
        app.open_action.setText.assert_called_with("Open File Browser (Ctrl+Alt+G)")

    def startup(self):
        startup = Startup()
        startup.registry = MagicMock()
        return startup

    def test_startup_sets_only_current_user_app_entry(self):
        startup = self.startup()
        reg = startup.registry
        with patch.object(startup, "command", return_value='"C:/App/pythonw.exe" "C:/App/launch.pyw" --background'):
            startup.set_enabled(True)
        reg.CreateKeyEx.assert_called_once_with(reg.HKEY_CURRENT_USER, startup.RUN_KEY, 0, reg.KEY_SET_VALUE)
        self.assertEqual(reg.SetValueEx.call_args.args[1], "FileBrowserWidget")
        self.assertTrue(reg.SetValueEx.call_args.args[-1].endswith("--background"))
        startup.set_enabled(False)
        self.assertEqual(reg.DeleteValue.call_args.args[1], "FileBrowserWidget")
        reg.DeleteKey.assert_not_called()

    def test_startup_read_missing_and_permission_error(self):
        startup = self.startup()
        startup.registry.OpenKey.side_effect = FileNotFoundError
        self.assertFalse(startup.is_enabled())
        startup.set_enabled(False)
        startup.registry.OpenKey.side_effect = PermissionError("No access")
        with self.assertRaises(PermissionError):
            startup.is_enabled()

    def test_startup_command_quotes_paths_and_runs_in_background(self):
        with patch("src.utils.startup.sys.executable", "C:/App With Spaces/python.exe"), \
                patch.object(Path, "is_file", return_value=True):
            command = Startup.command()
        self.assertTrue(command.startswith('"C:\\App With Spaces\\pythonw.exe"'))
        self.assertIn("launch.pyw", command)
        self.assertTrue(command.endswith(" --background"))

    def test_failed_startup_change_restores_checkbox(self):
        modal = SettingsModal()
        self.addCleanup(modal.deleteLater)
        startup = Mock()
        startup.set_enabled.side_effect = PermissionError("No access")
        startup.is_enabled.return_value = False
        app = SimpleNamespace(startup=startup, file_browser=SimpleNamespace(settings_modal=modal))
        app.refresh_startup_state = lambda: WinTrayApp.refresh_startup_state(app)
        modal.set_startup_enabled(True)
        WinTrayApp.set_startup(app, True)
        self.assertFalse(modal.startup_check.isChecked())
        self.assertEqual(modal.integration_status.text(), "No access")


if __name__ == "__main__":
    unittest.main()
