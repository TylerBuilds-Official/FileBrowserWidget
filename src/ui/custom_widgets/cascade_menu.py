from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu


class CascadeMenu(QMenu):
    """One level of a folder cascade: subfolders fan out on hover, a click drills in,
    and a right-click asks for the item's own menu, the way a shell toolbar menu does."""

    def __init__(self, cascade, parent=None):
        super().__init__(parent)
        self.cascade = cascade
        self.filled = False
        self.items = {}
        self.setStyle(cascade.menu_style)
        self.hovered.connect(cascade.prefetch)

    def item_at(self, position):
        """The file or folder action under a point, ignoring separators and notices."""

        action = self.actionAt(position)

        return action if action is not None and action.data() else None

    def mousePressEvent(self, event):
        position = event.position().toPoint()
        global_position = event.globalPosition().toPoint()
        if event.button() == Qt.MouseButton.RightButton and self.rect().contains(position):
            action = self.item_at(position)
            if action is not None:
                self.cascade.show_context_menu(action.data(), global_position)
            event.accept()
            return
        super().mousePressEvent(event)
        if not self.cascade.contains(global_position):
            # Qt has closed every level; the press itself still belongs to what is under it.
            self.cascade.pressed_outside(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return
        action = self.item_at(event.position().toPoint())
        if (event.button() == Qt.MouseButton.LeftButton and action is not None
                and action.menu() is not None and action.isEnabled()):
            self.cascade.drill(action.data())
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.cascade.pointer_moved(event.globalPosition().toPoint())

    def wheelEvent(self, event):
        if self.cascade.contains(event.globalPosition().toPoint()):
            super().wheelEvent(event)
            return
        self.cascade.wheeled_outside(event)

    def keyPressEvent(self, event):
        # Left at the top level hands the keyboard back to the row that opened it.
        if event.key() == Qt.Key.Key_Left and not isinstance(self.parentWidget(), CascadeMenu):
            self.cascade.close()
            return
        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # Qt has picked a side by now but has not mapped the window yet, so a move here is silent.
        self.cascade.place_submenu(self)
