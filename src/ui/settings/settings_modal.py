from PyQt6.QtCore import Qt, QEvent, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtWidgets import (QLabel, QHBoxLayout, QCheckBox,
                             QComboBox, QVBoxLayout, QWidget, QScrollArea, QKeySequenceEdit, QPushButton)
from PyQt6.QtGui import QKeySequence


from src.ui.custom_widgets.fluent_icon_button import FluentIconButton
from src.ui.smooth_scroll import SmoothScroll, SmoothComboBox


class SettingsModal(QWidget):
    refresh_files = pyqtSignal()
    docking_position_changed = pyqtSignal()
    theme_mode_changed = pyqtSignal(str)
    startup_changed = pyqtSignal(bool)
    hotkey_changed = pyqtSignal(str)
    opened = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("settingsModal")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Settings")
        self._closing = False
        self._animation = QPropertyAnimation(self, b"pos", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._finish_animation)
        if parent is not None:
            parent.installEventFilter(self)
        self.hide()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 16)
        self.layout.setSpacing(16)
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)
        self.close_button = FluentIconButton("arrow-left", "Back to files")
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
        self._card(settings_layout, "App theme", "Choose how File Browser looks.", self.theme_combo)

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
        self._card(settings_layout, "Docking position", "Place the panel on the screen with your tray.", self.docking_combo)

        self._section(settings_layout, "Files")
        self.extensions_check = QCheckBox("Show file extensions")
        self.extensions_check.setObjectName("settingsExtensionsCheck")
        if settings is not None:
            self.extensions_check.setChecked(settings.value("files/show_extensions", False, type=bool))
        self._card(settings_layout, "File names", "Include endings such as .txt and .pdf.", self.extensions_check)
        self._section(settings_layout, "Startup and shortcuts")
        self.startup_check = QCheckBox("Start with Windows")
        self._card(settings_layout, "Startup", "Start quietly in the tray when you sign in.", self.startup_check)
        hotkey_controls = QWidget()
        hotkey_layout = QHBoxLayout(hotkey_controls)
        hotkey_layout.setContentsMargins(0, 0, 0, 0)
        saved_hotkey = settings.value("shortcuts/open", "Alt+B") if settings is not None else "Alt+B"
        self.hotkey_edit = QKeySequenceEdit(QKeySequence(saved_hotkey))
        self.hotkey_edit.setMaximumSequenceLength(1)
        self.hotkey_edit.setAccessibleName("Open browser shortcut")
        self.hotkey_reset = QPushButton("Reset")
        self.hotkey_reset.setToolTip("Reset shortcut to Alt+B")
        hotkey_layout.addWidget(self.hotkey_edit, 1)
        hotkey_layout.addWidget(self.hotkey_reset)
        self._card(settings_layout, "Open browser shortcut",
                   "Press Ctrl or Alt with a letter, number, or function key (except F12). Shift is optional.",
                   hotkey_controls)
        self.integration_status = QLabel("")
        self.integration_status.setWordWrap(True)
        self.integration_status.setProperty("role", "secondary")
        settings_layout.addWidget(self.integration_status)
        settings_layout.addStretch()
        footer = QLabel("Changes apply automatically")
        footer.setProperty("role", "secondary")
        self.layout.addWidget(footer)

        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        self.docking_combo.currentIndexChanged.connect(self.emit_docking_position_changed)
        self.extensions_check.stateChanged.connect(self.emit_refresh)
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
        card = QWidget()
        card.setProperty("role", "settingCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)
        label = QLabel(title)
        label.setProperty("role", "settingTitle")
        label.setBuddy(control)
        detail = QLabel(description)
        detail.setProperty("role", "secondary")
        detail.setWordWrap(True)
        card_layout.addWidget(label)
        card_layout.addWidget(detail)
        card_layout.addWidget(control)
        layout.addWidget(card)

    def _restore_combo(self, combo, key, default):
        value = self.settings.value(key, default) if self.settings is not None else default
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else combo.findData(default))

    def _save(self, key, value):
        if self.settings is not None:
            self.settings.setValue(key, value)

    def show_settings(self):
        parent = self.parentWidget()
        self._animation.stop()
        self._closing = False
        if parent is not None:
            self.setGeometry(parent.rect())
            self.move(parent.width(), 0)
        self.show()
        self.raise_()
        self.opened.emit()
        self.close_button.setFocus()
        self._animation.setStartValue(self.pos())
        self._animation.setEndValue(QPoint(0, 0))
        self._animation.start()

    def hide_settings(self, animated=True):
        self._animation.stop()
        if not animated or self.isHidden() or self.parentWidget() is None:
            self._close()
            return
        self._closing = True
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
