from pathlib import Path

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QLabel

class FileBrowser(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("fileBrowser")
        # Allow the stylesheet to paint this custom QWidget's background/border.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.title_label = QLabel("Custom Tray Panel")
        self.title_label.setObjectName("fileBrowserTitle")
        layout.addWidget(self.title_label)
        self.setLayout(layout)

        self.file_list_layout = QVBoxLayout()
        self.file_list_layout.setContentsMargins(0, 0, 0, 0)
        self.file_list_layout.setSpacing(4)
        self.file_list_widget = QWidget()
        self.file_list_widget.setObjectName("fileList")
        self.file_list_widget.setLayout(self.file_list_layout)

        layout.addWidget(self.file_list_widget)


    @staticmethod
    def traverse_level(folder) -> list[Path]:
        print("Traversing folder:", folder)
        folder = Path(folder)
        return list(folder.iterdir())

    def create_list_items(self):
        files = self.traverse_level(Path.home() / "Desktop")
        print("Files found:", files)
        if not files:
            return

        for file in files:
            file_label = QLabel(str(file))
            file_label.setProperty("role", "fileEntry")
            self.file_list_layout.addWidget(file_label)

