from PyQt6.QtWidgets import QDialog, QLabel
from PyQt6.QtWidgets import QVBoxLayout

class SettingsModal(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Settings")

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        label = QLabel("SETTINGS")

        self.layout.addWidget(label)

# TODO -- STUBBED