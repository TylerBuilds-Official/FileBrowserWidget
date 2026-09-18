from pathlib import Path

from PyQt6.QtWidgets import QWidget, QScrollArea, QFileIconProvider, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QFileInfo, pyqtSignal, QEvent
from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtGui import QIcon, QPainter, QPixmap


from src.ui.file_name_label import FileNameLabel
from src.ui.custom_widgets.file_row_widget import FileRowWidget
from src.ui.settings.settings_modal import SettingsModal


class FileBrowser(QWidget):
    program_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("fileBrowser")
        # Allow the stylesheet to paint this custom QWidget's background/border.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.settings_modal = SettingsModal(self)
        self.settings_modal.refresh_files.connect(self.refresh_files)

        # --- move this whole block out --- #


        assets_dir = Path(__file__).resolve().parents[1] / "assets"
        settings_icon_path = assets_dir / "dots.png"
        pixmap = QPixmap(str(settings_icon_path))
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), Qt.GlobalColor.gray)
        painter.end()

        self.settings_icon = QIcon(pixmap)


        settings_hover_icon = assets_dir / "dots.png"
        h_pixmap = QPixmap(str(settings_hover_icon))
        painter = QPainter(h_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(h_pixmap.rect(), Qt.GlobalColor.white)
        painter.end()

        self.settings_hover_icon = QIcon(h_pixmap)


        # --- end ------------------------- #


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

        self.header_layout = QHBoxLayout()

        self.title_label = QLabel("Desktop")
        self.title_label.setObjectName("fileBrowserTitle")

        self.settings_button = QPushButton()
        self.settings_button.setObjectName("fileBrowserSettingsButton")
        self.settings_button.setIcon(self.settings_icon)
        self.settings_button.installEventFilter(self)
        self.settings_button.clicked.connect(self.show_settings_modal)

        self.header_layout.addWidget(self.title_label)
        self.header_layout.addWidget(self.settings_button)
        layout.addLayout(self.header_layout)

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
            file_row = FileRowWidget()
            file_row.setObjectName("fileEntry")
            file_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            file_row.setFixedHeight(36)
            file_row.setToolTip(str(file))
            file_row.clicked.connect(lambda file=file: self.emit_file(str(file)))

            file_layout = QHBoxLayout(file_row)
            file_layout.setContentsMargins(10, 0, 10, 0)
            file_layout.setSpacing(10)

            file_icon  = self.icon_provider.icon(QFileInfo(str(file)))
            icon_label = QLabel()

            show_extension = self.settings_modal.show_extensions or file.is_dir()
            display_name = file.name if show_extension else file.stem
            file_label = FileNameLabel(display_name)

            icon_label.setObjectName("fileEntryIcon")
            icon_label.setFixedSize(20, 20)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setPixmap(file_icon.pixmap(16, 16))

            file_layout.addWidget(icon_label)
            file_layout.addWidget(file_label, 1)
            self.file_list_layout.addWidget(file_row)


    def emit_file(self, file):
        self.program_clicked.emit(file)

    def setMaxWidth(self, width: int):
        self.setMaximumWidth(width)

    def setMaxHeight(self, height: int):
        self.setMaximumHeight(height)

    def setMinWidth(self, width: int):
        self.setMinimumWidth(width)

    def setMinHeight(self, height: int):
        self.setMinimumHeight(height)

    def eventFilter(self, watched, event):
        if watched == self.settings_button:
            if event.type() == QEvent.Type.Enter:
                self.settings_button.setIcon(self.settings_hover_icon)
            elif event.type() == QEvent.Type.Leave:
                self.settings_button.setIcon(self.settings_icon)
        return super().eventFilter(watched, event)

    def show_settings_modal(self):
        self.settings_modal.show_settings()

    def hide_settings_modal(self):
        self.settings_modal.hide_settings()

    def refresh_files(self):
        self.create_list_items()