from html import escape
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QCursor, QPalette
from PyQt6.QtWidgets import QLabel, QMenu, QSizePolicy


class Breadcrumbs(QLabel):
    folder_clicked = pyqtSignal(object)

    def __init__(self, path):
        super().__init__()
        self.paths = []
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse |
                                     Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(26)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.linkActivated.connect(self.open_link)
        self.set_name(str(path))

    def set_name(self, name):
        path = Path(name)
        self.paths = list(reversed(path.parents)) + [path]
        self.setToolTip(name)
        self.setAccessibleName("Folder path: " + name)
        self.update_links()

    def update_links(self):
        if not self.paths:
            return
        labels = [path.name or str(path) for path in self.paths]
        metrics = self.fontMetrics()
        start = 0
        while start < len(labels) - 1:
            text = ("… › " if start else "") + " › ".join(labels[start:])
            if metrics.horizontalAdvance(text) <= self.width():
                break
            start += 1
        self.hidden_paths = self.paths[:start]
        color = self.palette().color(QPalette.ColorRole.Link).name()

        def link(label, target):
            return f'<a href="{target}" style="color:{color}; text-decoration:none">{escape(label)}</a>'

        links = [link("…", "more")] if start else []
        available = max(30, self.width() - metrics.horizontalAdvance("… › " if start else ""))
        for index in range(start, len(labels)):
            label = labels[index]
            if index == start == len(labels) - 1:
                label = metrics.elidedText(label, Qt.TextElideMode.ElideMiddle, available)
            links.append(link(label, index))
        self.setText(" › ".join(links))

    def open_link(self, target):
        if target == "more":
            menu = QMenu(self)
            for path in self.hidden_paths:
                action = menu.addAction(path.name or str(path))
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked=False, path=path: self.folder_clicked.emit(path))
            menu.exec(QCursor.pos())
            menu.deleteLater()
        else:
            self.folder_clicked.emit(self.paths[int(target)])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_links()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.FontChange):
            self.update_links()
