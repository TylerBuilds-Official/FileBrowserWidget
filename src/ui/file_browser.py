from pathlib import Path

from PyQt6.QtWidgets import QWidget, QScrollArea, QHBoxLayout, QMenu, QLineEdit, QComboBox, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QStandardPaths
from PyQt6.QtWidgets import QVBoxLayout, QLabel


from src.ui.custom_widgets.fluent_icon_button import FluentIconButton
from src.ui.file_name_label import FileNameLabel
from src.ui.breadcrumbs import Breadcrumbs
from src.utils.favorites import Favorites
from src.ui.custom_widgets.file_row_widget import FileRowWidget
from src.ui.settings.settings_modal import SettingsModal
from src.ui.keyboard_handler import KeyboardHandler
from src.utils.file_icons import FileIcons
from src.utils.file_listing import describe_file, filter_options, visible_entries


class FileBrowser(QWidget):
    program_clicked = pyqtSignal(str)
    file_location_clicked = pyqtSignal(str)

    def __init__(self, parent=None, settings=None):
        super().__init__(parent=parent)
        self.desktop_folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
                                   or Path.home() / "Desktop")
        self.current_folder = self.desktop_folder
        self.favorites = Favorites(settings)
        self.preferences = settings
        self.entries = []
        self._icons = {}
        self.folder_history = []
        self.forward_history = []
        self.setObjectName("fileBrowser")
        # Allow the stylesheet to paint this custom QWidget's background/border.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint
        )

        self.icon_provider = FileIcons()
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
        self.back_button.setToolTip("Back (Alt+Left)")
        self.forward_button = FluentIconButton("arrow-right", "Forward")
        self.forward_button.setEnabled(False)
        self.forward_button.setToolTip("Forward (Alt+Right)")
        self.forward_button.clicked.connect(self.go_forward)

        self.title_label = FileNameLabel("Desktop")
        self.title_label.setObjectName("fileBrowserTitle")

        self.settings_button = FluentIconButton("settings", "Settings")
        self.settings_button.setObjectName("fileBrowserSettingsButton")
        self.settings_button.setToolTip("Settings")
        self.settings_button.setAccessibleName("Settings")
        self.settings_button.clicked.connect(self.show_settings_modal)

        self.header_layout.addWidget(self.back_button)
        self.header_layout.addWidget(self.forward_button)
        self.header_layout.addWidget(self.title_label, 1)
        self.header_layout.addWidget(self.settings_button)
        layout.addLayout(self.header_layout)

        places = QHBoxLayout()
        self.home_button = QPushButton("Desktop")
        self.home_button.setToolTip("Return to Desktop (Alt+Home)")
        self.home_button.clicked.connect(self.go_home)
        places.addWidget(self.home_button)
        self.favorites_button = QPushButton("Favorites")
        self.favorites_button.setAccessibleName("Open favorites")
        self.favorites_button.clicked.connect(self.show_favorites_menu)
        places.addWidget(self.favorites_button)
        places.addStretch()
        layout.addLayout(places)
        self.path_label = Breadcrumbs(self.current_folder)
        self.path_label.folder_clicked.connect(self.navigate_to)
        self.path_label.setObjectName("browserPath")
        self.path_label.setProperty("role", "secondary")
        self.path_label.setToolTip(str(self.current_folder))
        layout.addWidget(self.path_label)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search this folder (Ctrl+F)")
        self.search_edit.setAccessibleName("Search this folder")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)
        controls = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.setAccessibleName("Filter file types")
        self.filter_combo.addItem("All types", "all")
        self.sort_combo = QComboBox()
        self.sort_combo.setAccessibleName("Sort files")
        for label, value in (("Name: A to Z", "name"), ("Name: Z to A", "name_desc"),
                             ("Newest first", "modified"), ("Largest first", "size"),
                             ("File type", "type")):
            self.sort_combo.addItem(label, value)
        saved_sort = settings.value("files/sort", "name") if settings is not None else "name"
        self.sort_combo.setCurrentIndex(max(0, self.sort_combo.findData(saved_sort)))
        controls.addWidget(self.filter_combo, 1)
        controls.addWidget(self.sort_combo, 1)
        layout.addLayout(controls)
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
        self.keyboard_handler = KeyboardHandler(self)
        self.search_edit.textChanged.connect(self.apply_filters)
        self.filter_combo.currentIndexChanged.connect(self.apply_filters)
        self.sort_combo.currentIndexChanged.connect(self.sort_changed)




    @staticmethod
    def traverse_level(folder) -> list[Path]:
        folder = Path(folder)
        return list(folder.iterdir())

    def create_list_items(self, folder=None, scroll_position=None):
        folder = Path(folder) if folder is not None else self.current_folder
        if scroll_position is None:
            scroll_position = self.scroll_area.verticalScrollBar().value() if folder == self.current_folder else 0
        try:
            files = self.traverse_level(folder)
        except OSError as error:
            self.status_label.setText("Could not open this folder.")
            self.status_label.setToolTip(str(error))
            return False

        if folder != self.current_folder:
            self.search_edit.blockSignals(True)
            self.search_edit.clear()
            self.search_edit.blockSignals(False)
        self.entries = [describe_file(file) for file in files]
        self._icons.clear()
        previous_filter = self.filter_combo.currentData()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        for label, value in filter_options(self.entries):
            self.filter_combo.addItem(label, value)
        self.filter_combo.setCurrentIndex(max(0, self.filter_combo.findData(previous_filter)))
        self.filter_combo.blockSignals(False)
        self.current_folder = folder
        self.title_label.set_name(folder.name or str(folder))
        self.title_label.setToolTip(str(folder))
        self.path_label.set_name(str(folder))
        self.path_label.setToolTip(str(folder))
        self.render_entries(scroll_position)
        return True

    def apply_filters(self):
        self.render_entries(0)

    def sort_changed(self):
        if self.preferences is not None:
            self.preferences.setValue("files/sort", self.sort_combo.currentData())
        self.render_entries(0)

    def focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def render_entries(self, scroll_position=0):
        entries = visible_entries(self.entries, self.search_edit.text(),
                                  self.filter_combo.currentData(), self.sort_combo.currentData())
        entries.sort(key=lambda entry: not self.favorites.contains(entry.path))
        files = [entry.path for entry in entries]
        count = len(files)
        text = f"{count} item" + ("" if count == 1 else "s")
        if count != len(self.entries):
            text = f"{count} of {len(self.entries)} items"
        self.status_label.setText(text)
        self.status_label.setToolTip("")

        while self.file_list_layout.count():
            item = self.file_list_layout.takeAt(0)
            item.widget().hide()
            item.widget().deleteLater()

        if not files:
            empty_label = QLabel("No matching files." if self.entries else "No files in this folder.")
            empty_label.setObjectName("fileBrowserEmpty")
            self.file_list_layout.addWidget(empty_label)
            empty_label.show()
            self.restore_scroll_position(scroll_position)

            return True

        for file in files:
            file_row = FileRowWidget()
            self.keyboard_handler.register_row(file_row)
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

            if file not in self._icons:
                self._icons[file] = self.icon_provider.icon(file)
            file_icon = self._icons[file]
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
            star = QPushButton("★" if self.favorites.contains(file) else "☆")
            star.setProperty("role", "iconButton")
            star.setFixedSize(28, 28)
            star.setCheckable(True)
            star.setChecked(self.favorites.contains(file))
            label = "Remove from favorites" if star.isChecked() else "Add to favorites"
            star.setToolTip(label)
            star.setAccessibleName(f"{label}: {file.name}")
            star.clicked.connect(lambda checked=False, file=file: self.toggle_favorite(file))
            file_layout.addWidget(star)
            self.file_list_layout.addWidget(file_row)
            file_row.show()

        self.restore_scroll_position(scroll_position)
        return True

    def restore_scroll_position(self, position):
        # Update the scrollbar range before restoring a longer folder's offset.
        self.file_list_layout.activate()
        self.file_list_widget.adjustSize()
        self.scroll_area.verticalScrollBar().setValue(position)

    def current_location(self):
        return self.current_folder, self.scroll_area.verticalScrollBar().value()

    def open_item(self, file):
        file = Path(file)
        if file.is_dir():
            self.navigate_to(file)
        else:
            self.emit_file(str(file))

    def navigate_to(self, folder):
        folder = Path(folder)
        if folder == self.current_folder:
            return
        previous_location = self.current_location()
        if self.create_list_items(folder):
            self.folder_history.append(previous_location)
            self.forward_history.clear()
            self.update_navigation_buttons()

    def go_back(self):
        if not self.folder_history:
            return
        previous_location = self.current_location()
        folder, scroll_position = self.folder_history[-1]
        if self.create_list_items(folder, scroll_position):
            self.folder_history.pop()
            self.forward_history.append(previous_location)
            self.update_navigation_buttons()

    def go_forward(self):
        if not self.forward_history:
            return
        previous_location = self.current_location()
        folder, scroll_position = self.forward_history[-1]
        if self.create_list_items(folder, scroll_position):
            self.forward_history.pop()
            self.folder_history.append(previous_location)
            self.update_navigation_buttons()

    def go_home(self):
        self.navigate_to(self.desktop_folder)

    def toggle_favorite(self, file):
        self.favorites.toggle(file)
        self.render_entries(self.scroll_area.verticalScrollBar().value())

    def show_favorites_menu(self):
        menu = QMenu(self)
        paths = self.favorites.files()
        if not paths:
            menu.addAction("Star a file or folder to pin it here").setEnabled(False)
        for path in paths:
            action = menu.addAction(path.name or str(path))
            action.setToolTip(str(path))
            action.triggered.connect(lambda checked=False, path=path: self.open_favorite(path))
        if paths:
            menu.addSeparator()
            remove = menu.addMenu("Remove favorite")
            for path in paths:
                action = remove.addAction(path.name or str(path))
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked=False, path=path: self.toggle_favorite(path))
        menu.exec(self.favorites_button.mapToGlobal(self.favorites_button.rect().bottomLeft()))
        menu.deleteLater()

    def open_favorite(self, path):
        if not path.exists():
            self.status_label.setText("Favorite no longer exists.")
            self.status_label.setToolTip(str(path))
            return
        self.open_item(path)

    def go_up(self):
        self.navigate_to(self.current_folder.parent)

    def update_navigation_buttons(self):
        self.back_button.setEnabled(bool(self.folder_history))
        self.forward_button.setEnabled(bool(self.forward_history))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.BackButton:
            if self.settings_modal.isVisible():
                self.settings_modal.hide_settings()
            else:
                self.go_back()
            event.accept()
        elif event.button() == Qt.MouseButton.ForwardButton:
            if not self.settings_modal.isVisible():
                self.go_forward()
            event.accept()
        else:
            super().mousePressEvent(event)

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
        menu.addSeparator()
        favorite_action = menu.addAction("Remove from favorites" if self.favorites.contains(file)
                                         else "Add to favorites")
        favorite_action.triggered.connect(lambda: self.toggle_favorite(file))
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
