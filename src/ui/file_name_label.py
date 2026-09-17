from PyQt6.QtCore import Qt
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QLabel, QSizePolicy


class FileNameLabel(QLabel):
    """Keep a filename on one line within the available row width."""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self._name = name
        self.setObjectName("fileEntryName")
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setAccessibleName(name)
        self.setText(name)


    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(
            self._name, Qt.TextElideMode.ElideRight, self.contentsRect().width()
        ))
