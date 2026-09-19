import os
import subprocess
import sys
from pathlib import Path


class Startup:
    """Manage only this app's current-user Windows startup entry."""

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    VALUE_NAME = "FileBrowserWidget"

    def __init__(self):
        self.registry = None
        if os.name == "nt":
            import winreg
            self.registry = winreg

    @staticmethod
    def command():
        if getattr(sys, "frozen", False):
            arguments = [sys.executable, "--background"]
        else:
            python = Path(sys.executable).with_name("pythonw.exe")
            launcher = Path(__file__).resolve().parents[2] / "launch.pyw"
            if not python.is_file() or not launcher.is_file():
                raise OSError("The Python launcher could not be found. Check the app's installation.")
            arguments = [str(python), str(launcher), "--background"]
        command = subprocess.list2cmdline(arguments)
        if len(command) > 260:
            raise OSError("The installation path is too long for Windows startup. Move the app to a shorter path.")
        return command

    def is_enabled(self):
        if self.registry is None:
            return False
        reg = self.registry
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, self.RUN_KEY) as key:
                command, _ = reg.QueryValueEx(key, self.VALUE_NAME)
                return bool(command)
        except FileNotFoundError:
            return False

    def set_enabled(self, enabled):
        if self.registry is None:
            raise OSError("Start with Windows is only available on Windows.")
        reg = self.registry
        if enabled:
            command = self.command()
            with reg.CreateKeyEx(reg.HKEY_CURRENT_USER, self.RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
                reg.SetValueEx(key, self.VALUE_NAME, 0, reg.REG_SZ, command)
        else:
            try:
                with reg.OpenKey(reg.HKEY_CURRENT_USER, self.RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
                    reg.DeleteValue(key, self.VALUE_NAME)
            except FileNotFoundError:
                pass
