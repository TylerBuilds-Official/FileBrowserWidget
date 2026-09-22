from collections import deque
from pathlib import Path
from time import monotonic

from PyQt6 import sip
from PyQt6.QtWidgets import QWidget, QScrollArea, QHBoxLayout, QMenu, QPushButton, QApplication
from PyQt6.QtCore import Qt, QEvent, QMimeData, QPoint, QRect, QSize, QUrl, pyqtSignal, QFileSystemWatcher, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QVBoxLayout, QLabel


from src.ui import motion
from src.ui.custom_widgets.fluent_icon_button import FluentIconButton
from src.ui.custom_widgets.ghost import Ghost
from src.ui.custom_widgets.page_transition import PageTransition
from src.ui.file_name_label import FileNameLabel
from src.ui.breadcrumbs import Breadcrumbs
from src.ui.filter_menu import FilterMenu
from src.ui.folder_cascade import FolderCascade
from src.ui.smooth_scroll import SmoothScroll
from src.utils.favorites import Favorites
from src.utils.desktop_paths import DesktopPaths
from src.ui.custom_widgets.file_row_widget import FileRowWidget
from src.ui.settings.settings_modal import SettingsModal
from src.ui.keyboard_handler import KeyboardHandler
from src.utils.file_icons import FileIcons
from src.utils.icon_reader import IconReader
from src.utils.file_listing import (FileEntry, describe_file, extension_kinds, file_stamp,
                                    filter_options, visible_entries)
from src.utils import shell_actions, window_effects


class FileBrowser(QWidget):
    program_clicked = pyqtSignal(str)
    file_location_clicked = pyqtSignal(str)

    RESCAN_SECONDS = 30
    SEARCH_DELAY = 120
    CACHE_LIMIT = 2000
    ICON_BATCH = 8
    HIDDEN_ATTRIBUTE = 0x2
    SLIDE = 24
    DISMISS_SECONDS = 0.5

    def __init__(self, parent=None, settings=None):
        super().__init__(parent=parent)

        self.desktop_paths = DesktopPaths()
        self.desktop_folder = self.desktop_paths.primary

        self._scan_errors = []

        self.current_folder = self.desktop_folder
        self.favorites = Favorites(settings)
        self.preferences = settings

        self.entries = []
        self._icons = {}
        self._rows = {}
        self._entry_cache = {}

        self._rendered_state = None
        self._loaded = False
        self._dirty = True

        self._last_scan = 0
        self.folder_stamps = {}

        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.mark_dirty)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(200)
        self.refresh_timer.timeout.connect(self.refresh_if_visible)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(self.RESCAN_SECONDS * 1000)
        self.poll_timer.timeout.connect(self.mark_dirty)
        self.poll_timer.start()

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(self.SEARCH_DELAY)
        self.search_timer.timeout.connect(self.apply_filters)

        self._generic_icons = {}
        self._icon_queue = deque()
        self._icon_reading = False

        self.folder_history = []
        self.forward_history = []
        self._arrival = None
        self._dismissed = (0.0, QPoint())

        self.setObjectName("fileBrowser")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint
        )
        self.ghost = Ghost(self)

        self.icon_provider = FileIcons()
        self.icon_reader = IconReader(self.icon_provider)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.content = QWidget()
        self.content.setObjectName("browserContent")
        outer_layout.addWidget(self.content)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(6)

        self.scroll_area = QScrollArea()
        self.smooth_scroll = SmoothScroll(self.scroll_area)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("fileBrowserScrollArea")
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.header_layout = QHBoxLayout()

        self.back_button = FluentIconButton("back", "Back")
        self.back_button.setEnabled(False)
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setToolTip("Back (Alt+Left)")
        self.forward_button = FluentIconButton("forward", "Forward")
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

        navigation = QHBoxLayout()
        navigation.setSpacing(4)
        self.home_button = FluentIconButton("home", "Desktop")
        self.home_button.setToolTip("Return to Desktop (Alt+Home)")
        self.home_button.clicked.connect(self.go_home)
        self.favorites_button = FluentIconButton("star", "Favorites")
        self.favorites_button.clicked.connect(self.show_favorites_menu)
        for button in (self.home_button, self.favorites_button):
            navigation.addWidget(button)
        self.path_label = Breadcrumbs(self.current_folder)
        self.path_label.folder_clicked.connect(self.navigate_to)
        self.path_label.setObjectName("browserPath")
        self.path_label.setProperty("role", "secondary")
        self.path_label.setToolTip(str(self.current_folder))
        navigation.addWidget(self.path_label, 1)
        self.filter_button = QPushButton("Filter")
        self.filter_button.setObjectName("filterButton")
        self.filter_button.setFixedWidth(72)
        self.filter_button.setToolTip("Search, filter, and sort (Ctrl+F)")
        self.filter_button.setAccessibleName("Search, filter, and sort")
        self.filter_button.setCheckable(True)
        self.filter_button.clicked.connect(self.focus_search)
        navigation.addWidget(self.filter_button)

        # Title and path are one block, ruled off from the list like Explorer's command bar.
        self.header = QWidget()
        self.header.setObjectName("browserHeader")
        self.header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_box = QVBoxLayout(self.header)
        header_box.setContentsMargins(0, 0, 0, 8)
        header_box.setSpacing(6)
        header_box.addLayout(self.header_layout)
        header_box.addLayout(navigation)
        layout.addWidget(self.header)

        self.filter_menu = FilterMenu(self.filter_button, settings)
        self.search_edit = self.filter_menu.search_edit
        self.filter_combo = self.filter_menu.filter_combo
        self.sort_combo = self.filter_menu.sort_combo
        self.filter_menu.clear_button.clicked.connect(self.clear_filters)
        self.filter_menu.closed.connect(self.update_filter_button)
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
        self.settings_modal.refresh_files.connect(self.update_file_labels)
        self.settings_modal.opened.connect(lambda: self.content.setEnabled(False))
        self.settings_modal.closed.connect(self._settings_closed)
        self.keyboard_handler = KeyboardHandler(self)
        self.cascade = FolderCascade(self)
        self.cascade.set_behavior(self.settings_modal.hover_behavior)
        self.settings_modal.hover_behavior_changed.connect(self.cascade.set_behavior)
        # Rebuilding the list on every keystroke is too slow in a large folder.
        self.search_edit.textChanged.connect(self.search_timer.start)
        self.filter_combo.currentIndexChanged.connect(self.apply_filters)
        self.sort_combo.currentIndexChanged.connect(self.sort_changed)
        if settings is not None and self.settings_modal.reopen_last:
            saved = settings.value("files/last_folder", "")
            if saved:
                # Not checked here: a stat on a dead share would stall the start. Opening it reports.
                self.current_folder = Path(saved)
                self.show_location(self.current_folder)




    @staticmethod
    def traverse_level(folder) -> list[Path]:
        folder = Path(folder)
        return list(folder.iterdir())

    def needs_scan(self):
        # A normal reopen does no filesystem or icon work.
        if not self._loaded or self._dirty:
            return True
        if monotonic() - self._last_scan >= self.RESCAN_SECONDS:
            return True
        # A hidden panel stops watching, so ask the folders themselves instead.
        return not self.watcher.directories() and self.sources_changed()

    def ensure_loaded(self):
        if self.needs_scan():
            self.create_list_items()

    def mark_dirty(self, *_):
        self._dirty = True
        if self.isVisible():
            self.refresh_timer.start()

    def refresh_if_visible(self):
        if self.isVisible() and self._dirty:
            self.create_list_items()

    def scan_sources(self, folder):
        return self.desktop_paths.sources() if folder == self.desktop_paths.primary else [folder]

    def sources_changed(self):
        for folder in self.scan_sources(self.current_folder):
            try:
                if self.folder_stamps.get(folder) != file_stamp(folder.stat()):
                    return True
            except OSError:
                return True
        return False

    def watch_folder(self):
        # Watching parents also catches a removed directory being recreated.
        wanted = {str(path) for source in self.scan_sources(self.current_folder)
                  for path in (source, source.parent)}
        current = set(self.watcher.directories())
        if current - wanted:
            self.watcher.removePaths(list(current - wanted))
        for path in wanted - current:
            self.watcher.addPath(path)

    def unwatch(self):
        # These handles stop Explorer renaming or moving any folder above this one.
        if self.watcher.directories():
            self.watcher.removePaths(self.watcher.directories())

    def reset_location(self):
        """Reopen on the Desktop the way the shell's own chevron menus do, unless asked to stay put."""
        if self.settings_modal.reopen_last:
            return
        # History goes even when the panel was closed on the Desktop it walked back to.
        self.folder_history.clear()
        self.forward_history.clear()
        self.update_navigation_buttons()
        if self.current_folder == self.desktop_folder:
            return
        self.current_folder = self.desktop_folder
        self.clear_search()
        self.entries = []
        self._loaded = False
        self._rendered_state = None
        self.show_location(self.desktop_folder)

    def show_location(self, folder):
        self.title_label.set_name("Desktop" if folder == self.desktop_folder else folder.name or str(folder))
        self.title_label.setToolTip(str(folder))
        self.path_label.set_name(str(folder))
        self.path_label.setToolTip(str(folder))

    def clear_search(self):
        self.search_timer.stop()
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)

    def show_scanning(self):
        """Fill the panel after it is on screen; a cold folder takes a moment to read."""
        self.status_label.setText("Loading…")
        self.status_label.setToolTip("")
        if not self.entries:
            self.show_message("Loading…")

    def show_message(self, text, detail="", retry=False):
        self.clear_list_layout()
        for message in (text, detail):
            if message:
                label = QLabel(message)
                label.setObjectName("fileBrowserEmpty")
                label.setWordWrap(True)
                self.file_list_layout.addWidget(label)
                label.show()
        if retry:
            button = QPushButton("Try again")
            button.clicked.connect(self.refresh_files)
            self.file_list_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
            button.show()
        self._rendered_state = None

    def clear_list_layout(self):
        while self.file_list_layout.count():
            widget = self.file_list_layout.takeAt(0).widget()
            widget.hide()
            if not isinstance(widget, FileRowWidget):
                widget.deleteLater()

    def update_file_labels(self):
        self.render_entries(self.scroll_area.verticalScrollBar().value())

    def create_list_items(self, folder=None, scroll_position=None, force=False):
        folder = Path(folder) if folder is not None else self.current_folder
        if scroll_position is None:
            scroll_position = self.scroll_area.verticalScrollBar().value() if folder == self.current_folder else 0
        try:
            if folder == self.desktop_folder:
                if self.desktop_folder == self.desktop_paths.primary:
                    files, scan_errors = self.desktop_paths.list_files(self.traverse_level)
                else:
                    files, scan_errors = self.traverse_level(folder), []
            else:
                files, scan_errors = self.traverse_level(folder), []
        except OSError as error:
            self.status_label.setText("Could not open this folder.")
            self.status_label.setToolTip(str(error))
            if folder == self.current_folder:
                # Keep this folder unloaded so the next open tries it again. A folder we
                # failed to navigate *to* must leave the shown folder's refresh alone.
                self._dirty = True
                self._loaded = False
                self._last_scan = monotonic()
                self.refresh_timer.stop()
                self.watch_folder()
                self.show_message("Could not open this folder.", str(error), retry=True)
            return False

        rescan = folder == self.current_folder
        if not rescan:
            self.clear_search()
        entries = []
        for file in files:
            cached = self._entry_cache.get(file)
            try:
                info = file.stat()
            except OSError as error:
                # describe_file must not make a second attempt after stat fails.
                entry = FileEntry(file, extension_kinds(file), error=str(error))
            else:
                if getattr(info, "st_file_attributes", 0) & self.HIDDEN_ATTRIBUTE:
                    continue  # Explorer keeps hidden items such as desktop.ini out of the list.
                if not force and cached is not None and cached.stamp == file_stamp(info):
                    entry = cached
                else:
                    entry = describe_file(file, info)
            if force:
                self._icons.pop(file, None)
            entries.append(entry)
        if rescan:
            for path in {entry.path for entry in self.entries} - {entry.path for entry in entries}:
                self._entry_cache.pop(path, None)
                self._icons.pop(path, None)
        self.entries = entries
        # Other folders keep their metadata and icons for back and forward, until the caches grow.
        self._entry_cache.update({entry.path: entry for entry in entries})
        if len(self._entry_cache) > self.CACHE_LIMIT:
            self._entry_cache = {entry.path: entry for entry in entries}
        if len(self._icons) > self.CACHE_LIMIT:
            self._icons = {path: icon for path, icon in self._icons.items() if path in self._entry_cache}
        self.folder_stamps = {}
        for source in self.scan_sources(folder):
            try:
                self.folder_stamps[source] = file_stamp(source.stat())
            except OSError:
                pass
        self._dirty = False
        self._loaded = True
        self._last_scan = monotonic()
        self.refresh_timer.stop()
        self._scan_errors = [f"{path}: {error}" for path, error in scan_errors]
        self._scan_errors.extend(f"{entry.path}: {entry.error}" for entry in self.entries if entry.error)
        previous_filter = self.filter_combo.currentData()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        for label, value in filter_options(self.entries):
            self.filter_combo.addItem(label, value)
        self.filter_combo.setCurrentIndex(max(0, self.filter_combo.findData(previous_filter)))
        self.filter_combo.blockSignals(False)
        self.current_folder = folder
        self.show_location(folder)
        self.watch_folder()
        if not rescan and self.preferences is not None and self.settings_modal.reopen_last:
            self.preferences.setValue("files/last_folder", str(folder))
        if force:
            self._rendered_state = None
        self.render_entries(scroll_position)
        return True

    def apply_filters(self):
        self.render_entries(0)

    def sort_changed(self):
        if self.preferences is not None:
            self.preferences.setValue("files/sort", self.sort_combo.currentData())
        self.render_entries(0)

    def focus_search(self):
        self.filter_menu.open_at(self.filter_button)

    def clear_filters(self):
        self.search_edit.blockSignals(True)
        self.filter_combo.blockSignals(True)
        self.search_edit.clear()
        self.filter_combo.setCurrentIndex(0)
        self.search_edit.blockSignals(False)
        self.filter_combo.blockSignals(False)
        self.apply_filters()

    def update_filter_button(self):
        active = bool(self.search_edit.text().strip()) or self.filter_combo.currentData() != "all"
        changed = active or self.sort_combo.currentData() != "name"
        self.filter_button.setChecked(changed)
        self.filter_button.setText("Filter \u2022" if changed else "Filter")
        details = ["Search, filter, and sort (Ctrl+F)"]
        if self.search_edit.text().strip():
            details.append("Search: " + self.search_edit.text().strip())
        if self.filter_combo.currentData() != "all":
            details.append("Type: " + self.filter_combo.currentText())
        details.append("Sort: " + self.sort_combo.currentText())
        self.filter_button.setToolTip("\n".join(details))
        self.filter_menu.clear_button.setEnabled(active)

    def render_entries(self, scroll_position=0):
        self.update_filter_button()
        entries = visible_entries(self.entries, self.search_edit.text(),
                                  self.filter_combo.currentData(), self.sort_combo.currentData())
        entries.sort(key=lambda entry: not self.favorites.contains(entry.path))
        files = [entry.path for entry in entries]
        count = len(files)
        text = f"{count} item" + ("" if count == 1 else "s")
        if count != len(self.entries):
            text = f"{count} of {len(self.entries)} items"
        if self._scan_errors:
            text += f" | {len(self._scan_errors)} unavailable (details)"
        self.status_label.setText(text)
        self.status_label.setToolTip("\n".join(self._scan_errors))

        listed = {entry.path for entry in self.entries}
        state = (self.current_folder, tuple(listed), tuple((entry.path, entry.stamp, entry.error, entry.online_only,
                        self.favorites.contains(entry.path)) for entry in entries),
                 self.settings_modal.show_extensions)
        if state == self._rendered_state:
            self.restore_scroll_position(scroll_position)
            return True
        self._rendered_state = state
        focused = self.focusWidget()
        self._icon_queue.clear()
        self.clear_list_layout()
        for path in list(self._rows):
            if path not in listed:
                self._rows.pop(path).deleteLater()

        if not files:
            empty_label = QLabel("No matching files." if self.entries else "No files in this folder.")
            empty_label.setObjectName("fileBrowserEmpty")
            self.file_list_layout.addWidget(empty_label)
            empty_label.show()
        for entry in entries:
            row = self._rows.get(entry.path)
            if row is None:
                row = self.create_file_row(entry)
                self._rows[entry.path] = row
            else:
                self.update_file_row(row, entry)
            self.file_list_layout.addWidget(row)
            row.show()
        # The star buttons take focus too, so keep whatever inside a surviving row had it.
        if focused is not None and self.isAncestorOf(focused) and focused.isVisibleTo(self):
            focused.setFocus()
        self.read_icons()  # Once per render, so the first batch is a full one.

        self.restore_scroll_position(scroll_position)
        return True

    def create_file_row(self, entry):
        file = entry.path
        file_row = FileRowWidget()
        self.keyboard_handler.register_row(file_row)
        self.cascade.register_row(file_row)
        file_row.setObjectName("fileEntry")
        file_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        file_row.setFixedHeight(40)
        file_row.setToolTip(str(file))
        file_row.clicked.connect(lambda file=file: self.open_item(file))
        file_row.middle_clicked.connect(lambda file=file: self.open_in_explorer(file))
        file_row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        file_row.customContextMenuRequested.connect(
            lambda pos, file=file, row=file_row: self.show_file_menu(file, row.mapToGlobal(pos))
        )

        file_layout = QHBoxLayout(file_row)
        file_layout.setContentsMargins(10, 0, 10, 0)
        file_layout.setSpacing(10)

        icon_label = QLabel()

        show_extension = self.settings_modal.show_extensions or "folders" in entry.kinds
        display_name = file.name if show_extension else file.stem
        file_label = FileNameLabel(display_name)

        icon_label.setObjectName("fileEntryIcon")
        icon_label.setFixedSize(20, 20)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        file_layout.addWidget(icon_label)
        file_layout.addWidget(file_label, 1)
        star = FluentIconButton("star", "Add to favorites")
        star.clicked.connect(lambda checked=False, file=file: self.toggle_favorite(file))
        file_layout.addWidget(star)
        file_row.name_label = file_label
        file_row.icon_label = icon_label
        file_row.star_button = star
        file_row.path = file
        file_row.is_folder = "folders" in entry.kinds
        self.set_row_icon(file_row, entry)
        self.update_star(file_row, entry)
        return file_row

    def icon_stamp(self, entry):
        return entry.stamp, self.devicePixelRatioF()

    def generic_pixmap(self, folder):
        """One shell call covers every row still waiting for its own icon."""
        key = (folder, self.devicePixelRatioF())
        if key not in self._generic_icons:
            icon = self.icon_provider.generic_icon(folder)
            self._generic_icons[key] = icon.pixmap(QSize(20, 20), self.devicePixelRatioF())
        return self._generic_icons[key]

    def set_row_icon(self, row, entry):
        """Cached icons paint now; the rest start generic and are read off the UI thread."""

        cached = self._icons.get(entry.path)
        if cached is not None and cached[0] == self.icon_stamp(entry):
            row.icon_label.setPixmap(cached[1])
            return
        generic = self.generic_pixmap("folders" in entry.kinds)
        row.icon_label.setPixmap(generic)
        if entry.online_only or entry.error:
            self._icons[entry.path] = (self.icon_stamp(entry), generic)  # Never ask the shell for these.
            return
        self._icon_queue.append(entry)

    def read_icons(self):
        """One batch at a time on a worker; the rows fill in as each batch lands."""

        if self._icon_reading:
            return
        batch = []
        while self._icon_queue and len(batch) < self.ICON_BATCH:
            entry = self._icon_queue.popleft()
            if entry.path in self._rows and entry not in batch:
                batch.append(entry)
        if not batch:
            return
        self._icon_reading = True
        self.icon_reader.read(batch, self.devicePixelRatioF(), self._icons_landed)

    def _icons_landed(self, images):
        if sip.isdeleted(self):
            return
        self._icon_reading = False
        for entry, image in images:
            pixmap = QPixmap.fromImage(image)
            self._icons[entry.path] = (self.icon_stamp(entry), pixmap)
            row = self._rows.get(entry.path)
            if row is not None and not sip.isdeleted(row):
                row.icon_label.setPixmap(pixmap)
        self.read_icons()

    def update_file_row(self, row, entry):
        file = entry.path
        show_extension = self.settings_modal.show_extensions or "folders" in entry.kinds
        row.name_label.set_name(file.name if show_extension else file.stem)
        row.is_folder = "folders" in entry.kinds
        self.set_row_icon(row, entry)
        self.update_star(row, entry)

    def update_star(self, row, entry):
        pinned = self.favorites.contains(entry.path)
        label = "Remove from favorites" if pinned else "Add to favorites"
        row.star_button.set_glyph("star-filled" if pinned else "star")
        row.star_button.setToolTip(label)
        row.star_button.setAccessibleName(f"{label}: {entry.path.name}")
        row.star_button.set_state(pinned=pinned)
        row.refresh_star()

    def restore_scroll_position(self, position):
        self.smooth_scroll.stop()
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

    def page_before(self):
        """A picture of the list as it is, for the drill that follows a navigation."""

        if self.isVisible() and motion.duration(motion.NORMAL) > 0:
            return self.scroll_area.viewport().grab()

        return None

    def page_after(self, before, forward: bool):
        """Drill in towards a folder below, or out towards one above or behind."""

        PageTransition.play(self.scroll_area.viewport(), before, forward)

    def navigate_to(self, folder):
        folder = Path(folder)
        if folder == self.current_folder:
            return
        previous_location = self.current_location()
        forward = not self.current_folder.is_relative_to(folder)
        before = self.page_before()
        if self.create_list_items(folder):
            self.folder_history.append(previous_location)
            self.forward_history.clear()
            self.update_navigation_buttons()
            self.page_after(before, forward)

    def go_back(self):
        if not self.folder_history:
            return
        previous_location = self.current_location()
        folder, scroll_position = self.folder_history[-1]
        before = self.page_before()
        if self.create_list_items(folder, scroll_position):
            self.folder_history.pop()
            self.forward_history.append(previous_location)
            self.update_navigation_buttons()
            self.page_after(before, forward=False)

    def go_forward(self):
        if not self.forward_history:
            return
        previous_location = self.current_location()
        folder, scroll_position = self.forward_history[-1]
        before = self.page_before()
        if self.create_list_items(folder, scroll_position):
            self.forward_history.pop()
            self.folder_history.append(previous_location)
            self.update_navigation_buttons()
            self.page_after(before, forward=True)

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
        window_effects.style_window(menu)
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
            if not self.rect().contains(event.position().toPoint()):
                self.record_dismissal(event.globalPosition().toPoint())  # Qt closes the popup on this press.
            super().mousePressEvent(event)

    def record_dismissal(self, point: QPoint):
        self._dismissed = (monotonic(), point)

    def dismissed_by_press_in(self, area: QRect) -> bool:
        """Whether a press inside the area just closed the panel; its click is still on its way."""

        stamp, point = self._dismissed

        return monotonic() - stamp < self.DISMISS_SECONDS and area.contains(point)

    def open_in_explorer(self, file):
        """A middle click shows the item in File Explorer: a folder itself, a file where it lives."""

        file = Path(file)
        if file.is_dir():
            self.emit_file(str(file))
        else:
            self.file_location_clicked.emit(str(file))

    def properties_focused(self):
        file = self.focused_file()
        if file is not None:
            self.show_file_properties(file)

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
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(lambda: self.copy_file(file))
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.delete_file(file))
        menu.addSeparator()
        favorite_action = menu.addAction("Remove from favorites" if self.favorites.contains(file)
                                         else "Add to favorites")
        favorite_action.triggered.connect(lambda: self.toggle_favorite(file))
        properties_action = menu.addAction("Properties")
        properties_action.triggered.connect(lambda: self.show_file_properties(file))
        window_effects.style_window(menu)
        menu.exec(position)
        menu.deleteLater()


    def emit_file(self, file):
        self.program_clicked.emit(file)

    def copy_file(self, file):
        """Put the file on the clipboard as a file, so Explorer and mail clients can paste it."""
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(Path(file).absolute()))])
        QApplication.clipboard().setMimeData(data)
        self.status_label.setText(f"Copied {Path(file).name}")
        self.status_label.setToolTip("")

    def delete_file(self, file):
        error = shell_actions.recycle(file)
        if error:
            self.status_label.setText(error)
            self.status_label.setToolTip(str(file))
        else:
            self.mark_dirty()

    def show_file_properties(self, file):
        error = shell_actions.show_properties(file)
        if error:
            self.status_label.setText(error)
            self.status_label.setToolTip(str(file))

    def focused_file(self):
        widget = self.focusWidget()
        return widget.path if isinstance(widget, FileRowWidget) else None

    def copy_focused(self):
        file = self.focused_file()
        if file is not None:
            self.copy_file(file)

    def delete_focused(self):
        file = self.focused_file()
        if file is not None:
            self.delete_file(file)

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

    def edge_offset(self, distance: int) -> QPoint:
        """Towards the screen edge the panel is docked against: down for the taskbar, up for the top."""

        upward = self.settings_modal.docking_position.startswith("top")

        return QPoint(0, -distance if upward else distance)

    def prepare_arrival(self):
        """Start invisible, so the first frame on screen is the entrance and not a flash."""

        if motion.animations_enabled():
            self.setWindowOpacity(0.0)

    def arrive(self):
        """Slide in from the docked edge and fade up, the way a tray flyout opens."""

        self._arrival = motion.arrive(self, self.edge_offset(self.SLIDE), motion.SLOW)

    def setVisible(self, visible):
        """Hide at once, leaving a picture of the panel to go the way it came."""

        if visible:
            super().setVisible(True)
            self.ghost.prepare()
            return
        if self.isVisible():
            # A finished entrance has deleted itself; only a running one needs stopping.
            if self._arrival is not None and not sip.isdeleted(self._arrival):
                self._arrival.stop()
            self._arrival = None
            self.ghost.depart(self.edge_offset(self.SLIDE // 2), motion.NORMAL)
        super().setVisible(False)
        self.setWindowOpacity(1.0)  # Ready for a plain show; an entrance sets its own start.

    def hideEvent(self, event):
        self.cascade.close()
        self.filter_menu.close()
        self.unwatch()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.watch_folder()
        window_effects.style_window(self)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            self._rendered_state = None
            self.render_entries(self.scroll_area.verticalScrollBar().value())

    def show_settings_modal(self):
        self.cascade.close()
        self.filter_menu.close()
        self.settings_modal.show_settings()

    def hide_settings_modal(self):
        self.settings_modal.hide_settings()

    def refresh_files(self):
        self.create_list_items(force=True)
