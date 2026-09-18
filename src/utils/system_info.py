from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

class SystemInfo:
    def __init__(self, app: QApplication):
        self.app = app

    def get_primary_monitor(self):
        screen = self.app.primaryScreen()
        return screen.size()

    def get_popup_position(self) -> QPoint:
        tray_pos = self.app.tray_icon.geometry().center()
        screen   = self.app.screenAt(tray_pos) or self.app.primaryScreen()
        area     = screen.availableGeometry()

        pop_x = area.x() + area.width() - self.app.file_browser.width() - 10
        pop_y = area.y() + area.height() - self.app.file_browser.height() - 5
        return QPoint(pop_x, pop_y)

