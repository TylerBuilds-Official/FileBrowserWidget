from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QLabel, QHBoxLayout, QCheckBox, QPushButton
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget


class SettingsModal(QWidget):

    refresh_files = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsModal")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(300, 200)
        self.hide_settings()

        self.setWindowTitle("Settings")

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.layout)

        title_layout = QHBoxLayout()
        label = QLabel("Settings")
        label.setObjectName("settingsModalTitle")
        title_layout.addWidget(label)
        self.layout.addLayout(title_layout)

        self.close_button = QPushButton("X")
        self.close_button.clicked.connect(self.hide_settings)
        title_layout.addWidget(self.close_button)

        settings_layout = QVBoxLayout()
        self.extensions_check = QCheckBox("Show File Extensions")
        self.extensions_check.setObjectName("settingsExtensionsCheck")
        self.extensions_check.stateChanged.connect(self.emit_refresh)
        settings_layout.addWidget(self.extensions_check)
        self.layout.addLayout(settings_layout)

        self.extensions_check.setChecked(False)

    def show_settings(self):
        print("Showing Settings Modal")
        self.show()
        self.raise_()

        # center of file browser
        self.move(self.parent().width() // 2 - self.width() // 2, self.parent().height() // 2 - self.height() // 2)

    def hide_settings(self):
        self.hide()

    def emit_refresh(self):
        self.refresh_files.emit()

    @property
    def show_extensions(self):
        return self.extensions_check.isChecked()