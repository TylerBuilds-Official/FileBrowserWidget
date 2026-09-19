from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QApplication

class SystemInfo:
    def __init__(self, app: QApplication):
        self.app = app

    def _get_tray_screen_area_pos(self) -> tuple[QPoint, QScreen, QRect]:
        tray_pos = self.app.tray_icon.geometry().center()
        screen   = self.app.screenAt(tray_pos) or self.app.primaryScreen()
        area     = screen.availableGeometry()
        return tray_pos, screen, area

    def get_primary_monitor(self):
        screen = self.app.primaryScreen()
        return screen.size()

    def get_popup_position(self, position: str = "bottom_right") -> QPoint:
        tray_pos, screen, area = self._get_tray_screen_area_pos()
        width = self.app.file_browser.width()
        height = self.app.file_browser.height()
        # Keep the existing edge spacing, reducing it when space is tight.
        free_x = max(0, area.width() - width)
        free_y = max(0, area.height() - height)
        margin_x = min(10, free_x // 2)
        margin_y = min(5, free_y // 2)
        positions = {
            "top_left": (margin_x, margin_y),
            "top_center": (free_x // 2, margin_y),
            "top_right": (free_x - margin_x, margin_y),
            "bottom_left": (margin_x, free_y - margin_y),
            "bottom_center": (free_x // 2, free_y - margin_y),
            "bottom_right": (free_x - margin_x, free_y - margin_y),
        }
        offset_x, offset_y = positions.get(position, positions["bottom_right"])
        pop_x = area.x() + offset_x
        pop_y = area.y() + offset_y
        return QPoint(pop_x, pop_y)

    def get_bottom_left_popup_pos(self) -> QPoint:
        return self.get_popup_position("bottom_left")
