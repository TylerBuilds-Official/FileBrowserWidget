from PyQt6.QtCore import Qt, QEvent, QPoint, QPropertyAnimation, QSize, pyqtSignal
from PyQt6.QtWidgets import (QLabel, QHBoxLayout, QCheckBox,
                             QComboBox, QVBoxLayout, QWidget, QScrollArea, QKeySequenceEdit, QPushButton)
from PyQt6.QtGui import QIcon, QKeySequence


from src.ui import motion
from src.ui.custom_widgets.fluent_icon_button import FluentIconButton
from src.ui.smooth_scroll import SmoothScroll, SmoothComboBox
from src.utils.assets import asset
from src.version import VERSION


class SettingsModal(QWidget):
    refresh_files = pyqtSignal()
    docking_position_changed = pyqtSignal()
    theme_mode_changed = pyqtSignal(str)
    startup_changed = pyqtSignal(bool)
    hotkey_changed = pyqtSignal(str)
    hover_behavior_changed = pyqtSignal(str)
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
        self.hover_combo = SmoothComboBox()
        self.hover_combo.setObjectName("settingsHoverCombo")
        self.hover_combo.setAccessibleName("Folder hover")
        for label, value in (("Nothing", "none"), ("Cascade contents", "cascade")):
            self.hover_combo.addItem(label, value)
        self._restore_combo(self.hover_combo, "files/hover_behavior", "none")
        self._card(settings_layout, "Folder hover", "What resting on a folder does.", self.hover_combo)
        self.reopen_check = QCheckBox()
        self.reopen_check.setObjectName("settingsReopenCheck")
        self.reopen_check.setAccessibleName("Reopen where I left off")
        if settings is not None:
            self.reopen_check.setChecked(settings.value("files/reopen_last", False, type=bool))
        self._card(settings_layout, "Reopen where I left off", "Come back to the last folder instead of the Desktop.",
                   self.reopen_check)
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
        self.hover_combo.currentIndexChanged.connect(self._hover_changed)
        self.reopen_check.toggled.connect(lambda checked: self._save("files/reopen_last", checked))
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
        card_layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(card)

    def _restore_combo(self, combo, key, default):
        value = self.settings.value(key, default) if self.settings is not None else default
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else combo.findData(default))

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
    def hover_behavior(self) -> str:
        return self.hover_combo.currentData()

    @property
    def reopen_last(self) -> bool:
        return self.reopen_check.isChecked()
