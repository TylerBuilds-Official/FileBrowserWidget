from src.ui import motion
from src.ui.custom_widgets.ghost import Ghost
from src.ui.smooth_scroll import SmoothComboBox
from src.utils import window_effects

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                            QLineEdit, QComboBox, QLabel, QPushButton)


class FilterMenu(QWidget):
    """Search and view options in a popup, without taking space from the list."""

    closed = pyqtSignal()

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setObjectName("filterMenu")
        # A popup window rather than a QMenu: QMenu turns Tab into menu navigation,
        # which leaves the dropdowns below unreachable from the keyboard.
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.ghost = Ghost(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search this folder")
        self.search_edit.setAccessibleName("Search this folder")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)
        self.filter_combo = SmoothComboBox()
        self.filter_combo.setAccessibleName("Filter file types")
        self.filter_combo.addItem("All types", "all")
        self.sort_combo = SmoothComboBox()
        self.sort_combo.setAccessibleName("Sort files")
        for label, value in (("Name: A to Z", "name"), ("Name: Z to A", "name_desc"),
                             ("Newest first", "modified"), ("Largest first", "size"),
                             ("File type", "type")):
            self.sort_combo.addItem(label, value)
        saved = settings.value("files/sort", "name") if settings is not None else "name"
        self.sort_combo.setCurrentIndex(max(0, self.sort_combo.findData(saved)))
        for title, combo in (("Type", self.filter_combo), ("Sort", self.sort_combo)):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(10)
            row = QHBoxLayout()
            label = QLabel(title)
            label.setFixedWidth(36)
            label.setBuddy(combo)
            row.addWidget(label)
            row.addWidget(combo, 1)
            layout.addLayout(row)
        buttons = QHBoxLayout()
        self.clear_button = QPushButton("Clear filters")
        self.done_button = QPushButton("Done")
        buttons.addWidget(self.clear_button)
        buttons.addStretch()
        buttons.addWidget(self.done_button)
        layout.addLayout(buttons)
        self.done_button.clicked.connect(self.close)
        self.search_edit.returnPressed.connect(self.close)

    def open_at(self, button):
        """Drop down from the button, fading up, as a Windows flyout opens from its control."""

        if self.isVisible():
            self.search_edit.setFocus()
            self.search_edit.selectAll()
            return
        self.setFixedWidth(min(340, button.window().width() - 24))
        self.adjustSize()
        position = button.mapToGlobal(button.rect().bottomRight())
        position.setX(position.x() - self.width())
        self.move(position)
        if motion.animations_enabled():
            self.setWindowOpacity(0.0)
        self.show()
        window_effects.style_window(self)
        self.raise_()
        motion.arrive(self, QPoint(0, -8), motion.NORMAL)
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def setVisible(self, visible):
        if visible:
            super().setVisible(True)
            self.ghost.prepare()
            return
        if self.isVisible():
            self.ghost.depart(QPoint(0, -6), motion.FAST)
        super().setVisible(False)
        self.setWindowOpacity(1.0)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        # An open popup receives the clicks meant for everything behind it.
        if not self.rect().contains(event.position().toPoint()):
            self.close()
            return
        super().mousePressEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()
