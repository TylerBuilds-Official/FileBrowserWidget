from pathlib import Path

from PyQt6.QtCore import QPoint

from src.utils.file_opener import FileOpener
from src.utils.system_info import SystemInfo

class UIFunctions:
    def __init__(self, ui):
        self.ui = ui

        self.file_opener = FileOpener()
        self.system_info_helper = SystemInfo(ui)

    def open_file(self, file: str | Path):
        self.file_opener.open_file(file)

    def open_file_location(self, file: str | Path):
        self.file_opener.open_file_location(file)

    def get_primary_monitor(self):
        return self.system_info_helper.get_primary_monitor()

    def get_popup_pos(self) -> QPoint:
        position = self.ui.file_browser.settings_modal.docking_position
        return self.system_info_helper.get_popup_position(position)
