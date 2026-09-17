from pathlib import Path

from PyQt6.QtWidgets import QWidget, QScrollArea, QFileIconProvider, QHBoxLayout
from PyQt6.QtCore import Qt, QFileInfo
from PyQt6.QtWidgets import QVBoxLayout, QLabel

from src.ui.file_name_label import FileNameLabel

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

        self.icon_provider = QFileIconProvider()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("fileBrowserScrollArea")
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.title_label = QLabel("Desktop")
        self.title_label.setObjectName("fileBrowserTitle")

        layout.addWidget(self.title_label)
        layout.addWidget(self.scroll_area)


        self.file_list_layout = QVBoxLayout()
        self.file_list_layout.setContentsMargins(0, 0, 6, 0)
        self.file_list_layout.setSpacing(4)
        self.file_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)


        self.file_list_widget = QWidget()
        self.file_list_widget.setObjectName("fileList")
        self.file_list_widget.setLayout(self.file_list_layout)

        self.scroll_area.setWidget(self.file_list_widget)


    @staticmethod
    def traverse_level(folder) -> list[Path]:
        print("Traversing folder:", folder)
        folder = Path(folder)
        return list(folder.iterdir())

    def create_list_items(self):
        files = self.traverse_level(Path.home() / "Desktop")
        print("Files found:", files)

        while self.file_list_layout.count():
            item = self.file_list_layout.takeAt(0)
            item.widget().hide()
            item.widget().deleteLater()

        if not files:
            empty_label = QLabel("No files in this folder.")
            empty_label.setObjectName("fileBrowserEmpty")
            self.file_list_layout.addWidget(empty_label)

            return

        for file in files:
            file_row = QWidget()
            file_row.setObjectName("fileEntry")
            file_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            file_row.setFixedHeight(36)
            file_row.setToolTip(str(file))

            file_layout = QHBoxLayout(file_row)
            file_layout.setContentsMargins(10, 0, 10, 0)
            file_layout.setSpacing(10)

            file_icon  = self.icon_provider.icon(QFileInfo(str(file)))
            icon_label = QLabel()
            file_label = FileNameLabel(file.name)

            icon_label.setObjectName("fileEntryIcon")
            icon_label.setFixedSize(20, 20)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setPixmap(file_icon.pixmap(16, 16))

            file_layout.addWidget(icon_label)
            file_layout.addWidget(file_label, 1)
            self.file_list_layout.addWidget(file_row)


    def setMaxWidth(self, width: int):
        self.setMaximumWidth(width)

    def setMaxHeight(self, height: int):
        self.setMaximumHeight(height)

    def setMinWidth(self, width: int):
        self.setMinimumWidth(width)

    def setMinHeight(self, height: int):
        self.setMinimumHeight(height)
