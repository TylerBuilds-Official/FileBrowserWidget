from pathlib import Path

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QLabel

class FileBrowser(QWidget):

    def __init__(self):
        super().__init__(parent=None)

        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint
        )

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Custom Tray Panel"))
        self.setLayout(layout)

        self.file_list_layout = QVBoxLayout()
        self.file_list_widget = QWidget()
        self.file_list_widget.setLayout(self.file_list_layout)

        layout.addLayout(self.file_list_layout)


    @staticmethod
    def traverse_level(folder) -> list[Path]:
        folder = Path(folder)
        return list(folder.iterdir())

    def create_list_items(self):
        files = self.traverse_level(Path.home() / "Desktop")

        for file in files:
            self.file_list_layout.addWidget(QLabel(str(file)))

