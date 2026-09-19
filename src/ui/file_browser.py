from pathlib import Path

from PyQt6.QtWidgets import QWidget, QScrollArea, QFileIconProvider, QHBoxLayout, QMenu
from PyQt6.QtCore import Qt, QFileInfo, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QLabel


from src.ui.custom_widgets.fluent_icon_button import FluentIconButton
from src.ui.file_name_label import FileNameLabel
from src.ui.custom_widgets.file_row_widget import FileRowWidget
from src.ui.settings.settings_modal import SettingsModal


class FileBrowser(QWidget):
    program_clicked = pyqtSignal(str)
    file_location_clicked = pyqtSignal(str)

    def __init__(self, parent=None, settings=None):
        super().__init__(parent=parent)
        self.current_folder = Path.home() / "Desktop"
        self.folder_history = []
        self.setObjectName("fileBrowser")
        # Allow the stylesheet to paint this custom QWidget's background/border.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint
        )

        self.icon_provider = QFileIconProvider()
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.content = QWidget()
        self.content.setObjectName("browserContent")
        outer_layout.addWidget(self.content)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("fileBrowserScrollArea")
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.header_layout = QHBoxLayout()

        self.back_button = FluentIconButton("arrow-left", "Back")
        self.back_button.setEnabled(False)
        self.back_button.clicked.connect(self.go_back)

        self.title_label = FileNameLabel("Desktop")
        self.title_label.setObjectName("fileBrowserTitle")

        self.settings_button = FluentIconButton("settings", "Settings")
        self.settings_button.setObjectName("fileBrowserSettingsButton")
        self.settings_button.setToolTip("Settings")
        self.settings_button.setAccessibleName("Settings")
        self.settings_button.clicked.connect(self.show_settings_modal)

        self.header_layout.addWidget(self.back_button)
        self.header_layout.addWidget(self.title_label, 1)
        self.header_layout.addWidget(self.settings_button)
        layout.addLayout(self.header_layout)

        self.path_label = FileNameLabel(str(self.current_folder))
        self.path_label.setObjectName("browserPath")
        self.path_label.setProperty("role", "secondary")
        self.path_label.setToolTip(str(self.current_folder))
        layout.addWidget(self.path_label)
        layout.addWidget(self.scroll_area, 1)
        self.status_label = QLabel("Desktop")
        self.status_label.setProperty("role", "secondary")
        layout.addWidget(self.status_label)

        self.file_list_layout = QVBoxLayout()
        self.file_list_layout.setContentsMargins(0, 0, 4, 0)
        self.file_list_layout.setSpacing(2)
        self.file_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)


        self.file_list_widget = QWidget()
        self.file_list_widget.setObjectName("fileList")
        self.file_list_widget.setLayout(self.file_list_layout)

        self.scroll_area.setWidget(self.file_list_widget)

        self.settings_modal = SettingsModal(self, settings=settings)
        self.settings_modal.refresh_files.connect(self.refresh_files)
        self.settings_modal.opened.connect(lambda: self.content.setEnabled(False))
        self.settings_modal.closed.connect(self._settings_closed)




    @staticmethod
    def traverse_level(folder) -> list[Path]:
        folder = Path(folder)
        return list(folder.iterdir())

    def create_list_items(self, folder=None):
        folder = Path(folder) if folder is not None else self.current_folder
        try:
            files = self.traverse_level(folder)
        except OSError as error:
            self.status_label.setText("Could not open this folder.")
            self.status_label.setToolTip(str(error))
            return False

        self.current_folder = folder
        self.title_label.set_name(folder.name or str(folder))
        self.title_label.setToolTip(str(folder))
        self.path_label.set_name(str(folder))
        self.path_label.setToolTip(str(folder))
        self.status_label.setText(f"{len(files)} item" + ("" if len(files) == 1 else "s"))
        self.status_label.setToolTip("")
        self.scroll_area.verticalScrollBar().setValue(0)

        while self.file_list_layout.count():
            item = self.file_list_layout.takeAt(0)
            item.widget().hide()
            item.widget().deleteLater()

        if not files:
            empty_label = QLabel("No files in this folder.")
            empty_label.setObjectName("fileBrowserEmpty")
            self.file_list_layout.addWidget(empty_label)

            return True

        for file in files:
            file_row = FileRowWidget()
            file_row.setObjectName("fileEntry")
            file_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            file_row.setFixedHeight(40)
            file_row.setToolTip(str(file))
            file_row.clicked.connect(lambda file=file: self.open_item(file))
            file_row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            file_row.customContextMenuRequested.connect(
                lambda pos, file=file, row=file_row: self.show_file_menu(file, row.mapToGlobal(pos))
            )

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

        return True

    def open_item(self, file):
        file = Path(file)
        if file.is_dir():
            previous_folder = self.current_folder
            if self.create_list_items(file):
                self.folder_history.append(previous_folder)
                self.back_button.setEnabled(True)
        else:
            self.emit_file(str(file))

    def go_back(self):
        if self.folder_history and self.create_list_items(self.folder_history[-1]):
            self.folder_history.pop()
            self.back_button.setEnabled(bool(self.folder_history))

    def show_file_menu(self, file, position):
        file = Path(file)
        menu = QMenu(self)
        open_action = menu.addAction("Open")
        menu.setDefaultAction(open_action)
        open_action.triggered.connect(lambda: self.open_item(file))
        if file.is_dir():
            explorer_action = menu.addAction("Open in File Explorer")
            explorer_action.triggered.connect(lambda: self.emit_file(str(file)))
        location_action = menu.addAction("Open file location")
        location_action.triggered.connect(lambda: self.file_location_clicked.emit(str(file)))
        menu.exec(position)
        menu.deleteLater()


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

    def _settings_closed(self):
        self.content.setEnabled(True)
        if self.isVisible():
            self.settings_button.setFocus()

    def show_settings_modal(self):
        self.settings_modal.show_settings()

    def hide_settings_modal(self):
        self.settings_modal.hide_settings()

    def refresh_files(self):
        self.create_list_items()
