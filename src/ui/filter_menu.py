from PyQt6.QtWidgets import (QMenu, QWidget, QWidgetAction, QVBoxLayout, QHBoxLayout,
                            QLineEdit, QComboBox, QLabel, QPushButton)


class FilterMenu(QMenu):
    """Search and view options in a popup, without taking space from the list."""

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setObjectName("filterMenu")
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search this folder")
        self.search_edit.setAccessibleName("Search this folder")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)
        self.filter_combo = QComboBox()
        self.filter_combo.setAccessibleName("Filter file types")
        self.filter_combo.addItem("All types", "all")
        self.sort_combo = QComboBox()
        self.sort_combo.setAccessibleName("Sort files")
        for label, value in (("Name: A to Z", "name"), ("Name: Z to A", "name_desc"),
                             ("Newest first", "modified"), ("Largest first", "size"),
                             ("File type", "type")):
            self.sort_combo.addItem(label, value)
        saved = settings.value("files/sort", "name") if settings is not None else "name"
        self.sort_combo.setCurrentIndex(max(0, self.sort_combo.findData(saved)))
        for title, combo in (("Type", self.filter_combo), ("Sort", self.sort_combo)):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(10)
            row = QHBoxLayout()
            label = QLabel(title)
            label.setFixedWidth(36)
            label.setBuddy(combo)
            row.addWidget(label)
            row.addWidget(combo, 1)
            layout.addLayout(row)
        buttons = QHBoxLayout()
        self.clear_button = QPushButton("Clear filters")
        self.done_button = QPushButton("Done")
        buttons.addWidget(self.clear_button)
        buttons.addStretch()
        buttons.addWidget(self.done_button)
        layout.addLayout(buttons)
        action = QWidgetAction(self)
        action.setDefaultWidget(panel)
        self.addAction(action)
        self.done_button.clicked.connect(self.close)
        self.search_edit.returnPressed.connect(self.close)

    def open_at(self, button):
        self.setFixedWidth(min(340, button.window().width() - 24))
        position = button.mapToGlobal(button.rect().bottomRight())
        position.setX(position.x() - self.width())
        self.popup(position)
        self.search_edit.setFocus()
        self.search_edit.selectAll()
