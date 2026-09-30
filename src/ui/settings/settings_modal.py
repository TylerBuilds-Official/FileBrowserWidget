import os
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, QPoint, QPropertyAnimation, QSize, pyqtSignal
from PyQt6.QtWidgets import (QLabel, QHBoxLayout, QCheckBox, QComboBox, QFileDialog, QVBoxLayout, QWidget,
                             QScrollArea, QKeySequenceEdit, QPushButton, QSizePolicy)
from PyQt6.QtGui import QFontMetrics, QIcon, QKeySequence


from src.ui import motion
from src.ui.custom_widgets.fluent_icon_button import FluentIconButton
from src.ui.smooth_scroll import SmoothScroll, SmoothComboBox
from src.utils import locations
from src.utils.assets import asset
from src.utils.desktop_paths import DesktopPaths
from src.utils.file_listing import SORT_ORDERS
from src.version import VERSION


class SettingsModal(QWidget):
    refresh_files = pyqtSignal()
    docking_position_changed = pyqtSignal()
    theme_mode_changed = pyqtSignal(str)
    startup_changed = pyqtSignal(bool)
    hotkey_changed = pyqtSignal(str)
    hover_behavior_changed = pyqtSignal(str)
    default_sort_changed = pyqtSignal(str)
    favorites_on_top_changed = pyqtSignal(bool)
    opened = pyqtSignal()
    closed = pyqtSignal()

    ABOUT_ICON = 32

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("settingsModal")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Settings")
        self._closing = False
        self._animation = QPropertyAnimation(self, b"pos", self)
        self._animation.finished.connect(self._finish_animation)
        if parent is not None:
            parent.installEventFilter(self)
        self.hide()

        self.layout = QVBoxLayout(self)
        # The list's rail sits 12px in from the panel edge; this one lines up with it.
        self.layout.setContentsMargins(20, 20, 12, 16)
        self.layout.setSpacing(16)
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)
        title_layout.setContentsMargins(0, 0, 8, 0)
        self.close_button = FluentIconButton("back", "Back to files")
        self.close_button.setToolTip("Back to files (Esc)")
        self.close_button.setAccessibleName("Back to files")
        self.close_button.clicked.connect(lambda: self.hide_settings())
        title_layout.addWidget(self.close_button)
        label = QLabel("Settings")
        label.setObjectName("settingsModalTitle")
        title_layout.addWidget(label, 1)
        self.layout.addLayout(title_layout)

        scroll = QScrollArea()
        self.smooth_scroll = SmoothScroll(scroll)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("settingsContent")
        settings_layout = QVBoxLayout(self.content)
        settings_layout.setContentsMargins(0, 0, 4, 0)
        settings_layout.setSpacing(10)
        scroll.setWidget(self.content)
        self.layout.addWidget(scroll, 1)

        self._section(settings_layout, "Appearance")
        self.theme_combo = SmoothComboBox()
        self.theme_combo.setAccessibleName("App theme")
        for label, value in (("Use system setting", "system"), ("Light", "light"), ("Dark", "dark")):
            self.theme_combo.addItem(label, value)
        self._restore_combo(self.theme_combo, "appearance/theme", "system")
        self._card(settings_layout, "App theme", "How File Browser looks.", self.theme_combo)

        self._section(settings_layout, "Window")
        self.docking_combo = SmoothComboBox()
        self.docking_combo.setObjectName("settingsDockingCombo")
        self.docking_combo.setAccessibleName("Docking position")
        for label, position in (
            ("Top left", "top_left"), ("Top center", "top_center"),
            ("Top right", "top_right"), ("Bottom left", "bottom_left"),
            ("Bottom center", "bottom_center"), ("Bottom right", "bottom_right"),
        ):
            self.docking_combo.addItem(label, position)
        self._restore_combo(self.docking_combo, "window/docking", "bottom_right")
        self._card(settings_layout, "Docking position", "Where the panel opens.", self.docking_combo)

        self._section(settings_layout, "Files")
        self.extensions_check = QCheckBox()
        self.extensions_check.setObjectName("settingsExtensionsCheck")
        self.extensions_check.setAccessibleName("Show file extensions")
        if settings is not None:
            self.extensions_check.setChecked(settings.value("files/show_extensions", False, type=bool))
        self._card(settings_layout, "Show file extensions", "Include endings such as .txt and .pdf.",
                   self.extensions_check)
        self.favorites_check = QCheckBox()
        self.favorites_check.setObjectName("settingsFavoritesCheck")
        self.favorites_check.setAccessibleName("Show favorites at the top")
        self.favorites_check.setChecked(settings.value("files/favorites_on_top", True, type=bool)
                                        if settings is not None else True)
        self._card(settings_layout, "Show favorites at the top",
                   "Your favorites lead the list in the folder the panel opens on.", self.favorites_check)
        self.sort_combo = SmoothComboBox()
        self.sort_combo.setObjectName("settingsSortCombo")
        self.sort_combo.setAccessibleName("Default sort")
        for label, value in SORT_ORDERS:
            self.sort_combo.addItem(label, value)
        # The same key the Filter flyout once remembered its choice under, so that choice carries over.
        self._restore_combo(self.sort_combo, "files/sort", "name")
        self.sort_combo.setToolTip("Filter can change the order for now; the panel reopens in this one.")
        self._card(settings_layout, "Default sort", "The order a folder opens in.", self.sort_combo)
        self.hover_combo = SmoothComboBox()
        self.hover_combo.setObjectName("settingsHoverCombo")
        self.hover_combo.setAccessibleName("Folder hover")
        for label, value in (("Nothing", "none"), ("Cascade contents", "cascade")):
            self.hover_combo.addItem(label, value)
        self._restore_combo(self.hover_combo, "files/hover_behavior", "none")
        self._card(settings_layout, "Folder hover", "What resting on a folder does.", self.hover_combo)
        self.start_combo = SmoothComboBox()
        self.start_combo.setObjectName("settingsStartCombo")
        self.start_combo.setAccessibleName("Start in")
        for label, value in (("Desktop", "desktop"), ("Downloads", "downloads"), ("Documents", "documents")):
            self.start_combo.addItem(label, value)
        # Drives that stay put; a USB stick chosen here would usually not be there to open on.
        for drive in locations.list_drives():
            if drive.kind in ("fixed", "network"):
                self.start_combo.addItem(f"{drive.letter} drive", str(drive.root))
        self.start_combo.addItem("Where I left off", "last")
        self._restore_start()
        self.start_combo.setSizePolicy(QSizePolicy.Policy.Fixed, self.start_combo.sizePolicy().verticalPolicy())
        start_controls = QWidget()
        start_layout = QHBoxLayout(start_controls)
        start_layout.setContentsMargins(0, 0, 0, 0)
        start_layout.setSpacing(8)
        start_layout.addWidget(self.start_combo)
        # An icon beside the box, as a Browse button: a worded one left the card's wording no room.
        self.start_browse = FluentIconButton("folder-open", "Choose a folder to start in")
        self.start_browse.setToolTip("Choose a folder of your own to start in")
        start_layout.addWidget(self.start_browse)
        self._card(settings_layout, "Start in", "The folder the panel opens on.", start_controls)
        self._section(settings_layout, "Startup and shortcuts")
        self.startup_check = QCheckBox()
        self.startup_check.setAccessibleName("Start with Windows")
        self._card(settings_layout, "Start with Windows", "Runs quietly in the tray when you sign in.",
                   self.startup_check)
        hotkey_controls = QWidget()
        hotkey_layout = QHBoxLayout(hotkey_controls)
        hotkey_layout.setContentsMargins(0, 0, 0, 0)
        saved_hotkey = settings.value("shortcuts/open", "Alt+B") if settings is not None else "Alt+B"
        self.hotkey_edit = QKeySequenceEdit(QKeySequence(saved_hotkey))
        self.hotkey_edit.setMaximumSequenceLength(1)
        self.hotkey_edit.setAccessibleName("Open browser shortcut")
        self.hotkey_edit.setFixedWidth(104)
        self.hotkey_reset = QPushButton("Reset")
        self.hotkey_reset.setToolTip("Reset shortcut to Alt+B")
        hotkey_controls.setToolTip("Ctrl or Alt with a letter, number, or function key other than F12. "
                                   "Shift is optional. Combinations Windows and other apps rely on are refused.")
        hotkey_layout.setSpacing(8)
        hotkey_layout.addWidget(self.hotkey_edit)
        hotkey_layout.addWidget(self.hotkey_reset)
        self._card(settings_layout, "Open browser shortcut", "Ctrl or Alt plus a letter, number, or F-key.",
                   hotkey_controls)
        self.integration_status = QLabel("")
        self.integration_status.setWordWrap(True)
        self.integration_status.setProperty("role", "secondary")
        settings_layout.addWidget(self.integration_status)
        # Windows utilities keep their mark for an About card at the end, not the chrome.
        self._section(settings_layout, "About")
        about = QWidget()
        about.setProperty("role", "settingCard")
        about.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        about_layout = QHBoxLayout(about)
        about_layout.setContentsMargins(14, 10, 14, 10)
        about_layout.setSpacing(14)
        self.about_icon = QLabel()
        self.about_icon.setObjectName("settingsAboutIcon")
        self.about_icon.setAccessibleName("File Browser logo")
        self._render_about_icon()
        about_layout.addWidget(self.about_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        about_wording = QVBoxLayout()
        about_wording.setSpacing(2)
        about_name = QLabel("File Browser")
        about_name.setProperty("role", "settingTitle")
        self.about_version = QLabel(f"Version {VERSION}")
        self.about_version.setProperty("role", "secondary")
        about_wording.addWidget(about_name)
        about_wording.addWidget(self.about_version)
        about_layout.addLayout(about_wording, 1)
        settings_layout.addWidget(about)
        settings_layout.addStretch()
        footer = QLabel("Changes apply automatically")
        footer.setProperty("role", "secondary")
        self.layout.addWidget(footer)

        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        self.docking_combo.currentIndexChanged.connect(self.emit_docking_position_changed)
        self.extensions_check.stateChanged.connect(self.emit_refresh)
        self.favorites_check.toggled.connect(self._favorites_changed)
        self.sort_combo.currentIndexChanged.connect(self._sort_changed)
        self.hover_combo.currentIndexChanged.connect(self._hover_changed)
        self.start_combo.currentIndexChanged.connect(lambda: self._save("files/start_in", self.start_in))
        self.start_browse.clicked.connect(self.choose_start)
        self.startup_check.toggled.connect(self.startup_changed.emit)
        self.hotkey_edit.editingFinished.connect(self._hotkey_edited)
        self.hotkey_reset.clicked.connect(lambda: self.hotkey_changed.emit("Alt+B"))

    def _hotkey_edited(self):
        self.hotkey_changed.emit(self.hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText))

    def set_startup_enabled(self, enabled):
        self.startup_check.blockSignals(True)
        self.startup_check.setChecked(enabled)
        self.startup_check.blockSignals(False)

    def set_hotkey(self, sequence):
        self.hotkey_edit.setKeySequence(QKeySequence(sequence))

    @staticmethod
    def _section(layout, text):
        label = QLabel(text)
        label.setProperty("role", "section")
        layout.addWidget(label)

    @staticmethod
    def _card(layout, title, description, control):
        """One Windows 11 settings row: wording on the left, the control on the right."""
        card = QWidget()
        card.setProperty("role", "settingCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setMinimumHeight(54)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 8, 14, 8)
        card_layout.setSpacing(16)
        wording = QVBoxLayout()
        wording.setSpacing(2)
        label = QLabel(title)
        label.setProperty("role", "settingTitle")
        label.setBuddy(control)
        detail = QLabel(description)
        detail.setProperty("role", "secondary")
        detail.setWordWrap(True)
        wording.addWidget(label)
        wording.addWidget(detail)
        card_layout.addLayout(wording, 1)
        if not control.accessibleName():
            control.setAccessibleName(title)
        if isinstance(control, QComboBox):
            # Never squeezed below its longest choice: the wording wraps instead.
            control.setSizePolicy(QSizePolicy.Policy.Fixed, control.sizePolicy().verticalPolicy())
        card_layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(card)

    def _restore_combo(self, combo, key, default):
        value = self.settings.value(key, default) if self.settings is not None else default
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else combo.findData(default))

    def _restore_start(self):
        """The saved start, where "Reopen where I left off" was once a checkbox of its own."""

        if self.settings is None:
            return
        reopened = self.settings.value("files/reopen_last", False, type=bool)
        saved = self.settings.value("files/start_in", "last" if reopened else "desktop")
        if self.start_combo.findData(saved) < 0 and Path(saved).is_absolute():
            # A folder of the user's own, or a drive that is not here today, a share away or a disk
            # unplugged: still the choice.
            self.add_start_folder(Path(saved))
        self._restore_combo(self.start_combo, "files/start_in", saved)

    def choose_start(self):
        """Pick a folder of your own to open on.

        The panel steps aside for the dialog: it is a popup, and a dialog over a popup closes it,
        and goes with it. It comes back with Settings open once the dialog is done.
        """

        panel = self.parentWidget()
        if panel is not None:
            panel.hide()
        start = self.start_in if Path(self.start_in).is_absolute() else str(Path.home())
        chosen = QFileDialog.getExistingDirectory(None, "Start in", start)
        if panel is not None:
            panel.show()
            panel.raise_()
            panel.activateWindow()
            self.show_settings()
        if chosen:
            self.set_start(Path(chosen))

    def set_start(self, folder: Path):
        """Open on a folder: a named one or a drive by its own entry, any other by an entry of its own."""

        folder = Path(os.path.normpath(folder))
        index = self.start_combo.findData(self.start_value(folder))
        if index < 0:
            index = self.add_start_folder(folder)
        self.start_combo.setCurrentIndex(index)

    @staticmethod
    def start_value(folder: Path) -> str:
        """What Settings keep for a folder: 'desktop', 'downloads', or 'documents' for those, else its path."""

        if folder == DesktopPaths().primary:
            return "desktop"
        for name, path in locations.user_folders():
            if folder == path and name.casefold() in ("downloads", "documents"):
                return name.casefold()

        return str(folder)

    def add_start_folder(self, folder: Path) -> int:
        """An entry for a folder of the user's own, in place of the last such, above "Where I left off"."""

        combo = self.start_combo
        for index in range(combo.count()):
            if combo.itemData(index, Qt.ItemDataRole.UserRole + 1):
                combo.removeItem(index)
                break
        index = max(0, combo.findData("last"))
        label = QFontMetrics(combo.font()).elidedText(self.folder_label(folder), Qt.TextElideMode.ElideMiddle, 150)
        combo.insertItem(index, label, str(folder))
        combo.setItemData(index, str(folder), Qt.ItemDataRole.ToolTipRole)
        combo.setItemData(index, True, Qt.ItemDataRole.UserRole + 1)

        return index

    @staticmethod
    def folder_label(folder: Path) -> str:
        """A folder by its name; a drive by its letter, a share by its own name."""

        if folder.name:
            return folder.name
        drive = folder.drive.rstrip("\\")
        if drive.startswith("\\\\"):
            return drive.rpartition("\\")[2]

        return f"{drive} drive"

    def _save(self, key, value):
        if self.settings is not None:
            self.settings.setValue(key, value)

    def _render_about_icon(self):
        """The mark at card height, drawn for the screen the panel is on."""

        icon = QIcon(asset("logo/fb_icon_header.png"))
        self.about_icon.setPixmap(icon.pixmap(QSize(self.ABOUT_ICON * 2, self.ABOUT_ICON), self.devicePixelRatioF()))

    def show_settings(self):
        """Slide in over the files from the right, decelerating, as a Settings page drills in."""

        parent = self.parentWidget()
        self._animation.stop()
        self._render_about_icon()
        self._closing = False
        if parent is not None:
            self.setGeometry(parent.rect())
            self.move(parent.width(), 0)
        self.show()
        self.raise_()
        self.opened.emit()
        self.close_button.setFocus()
        length = motion.duration(motion.SLOW)
        if length == 0:
            self.move(0, 0)
            return
        self._animation.setDuration(length)
        self._animation.setEasingCurve(motion.DECELERATE)
        self._animation.setStartValue(self.pos())
        self._animation.setEndValue(QPoint(0, 0))
        self._animation.start()

    def hide_settings(self, animated=True):
        """Leave the way it came, accelerating, and only then give the files back."""

        self._animation.stop()
        length = motion.duration(motion.NORMAL)
        if not animated or length == 0 or self.isHidden() or self.parentWidget() is None:
            self._close()
            return
        self._closing = True
        self._animation.setDuration(length)
        self._animation.setEasingCurve(motion.ACCELERATE)
        self._animation.setStartValue(self.pos())
        self._animation.setEndValue(QPoint(self.parentWidget().width(), 0))
        self._animation.start()

    def _finish_animation(self):
        if self._closing:
            self._close()

    def _close(self):
        self._closing = False
        self.hide()
        self.closed.emit()

    def eventFilter(self, watched, event):
        if watched == self.parentWidget():
            if event.type() == QEvent.Type.Resize:
                self._animation.stop()
                if self._closing:
                    self._close()
                self.setGeometry(watched.rect())
            elif event.type() == QEvent.Type.Hide:
                self.hide_settings(animated=False)
        return super().eventFilter(watched, event)

    def emit_refresh(self):
        self._save("files/show_extensions", self.show_extensions)
        self.refresh_files.emit()

    def emit_docking_position_changed(self):
        self._save("window/docking", self.docking_position)
        self.docking_position_changed.emit()

    def _favorites_changed(self, on):
        self._save("files/favorites_on_top", on)
        self.favorites_on_top_changed.emit(on)

    def _sort_changed(self):
        self._save("files/sort", self.default_sort)
        self.default_sort_changed.emit(self.default_sort)

    def _hover_changed(self):
        self._save("files/hover_behavior", self.hover_behavior)
        self.hover_behavior_changed.emit(self.hover_behavior)

    def _theme_changed(self):
        self._save("appearance/theme", self.theme_mode)
        self.theme_mode_changed.emit(self.theme_mode)

    @property
    def theme_mode(self):
        return self.theme_combo.currentData()

    @property
    def docking_position(self) -> str:
        return self.docking_combo.currentData()

    @property
    def show_extensions(self):
        return self.extensions_check.isChecked()

    @property
    def favorites_on_top(self) -> bool:
        """Whether favorites lead the list in the folder the panel opens on."""
        return self.favorites_check.isChecked()

    @property
    def default_sort(self) -> str:
        """The order a folder opens in: a value of SORT_ORDERS."""
        return self.sort_combo.currentData()

    @property
    def hover_behavior(self) -> str:
        return self.hover_combo.currentData()

    @property
    def start_in(self) -> str:
        """"desktop", "downloads", "documents", "last", or a drive's root."""
        return self.start_combo.currentData()

    @property
    def reopen_last(self) -> bool:
        return self.start_in == "last"
