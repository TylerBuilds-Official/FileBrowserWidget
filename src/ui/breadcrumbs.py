from html import escape
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QCursor, QPalette
from PyQt6.QtWidgets import QLabel, QMenu, QSizePolicy

from src.utils import locations, window_effects


class Breadcrumbs(QLabel):
    folder_clicked = pyqtSignal(object)
    edit_requested = pyqtSignal()

    def __init__(self, path):
        super().__init__()
        self.paths = []
        self._activated = False
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
        server = locations.server_root(path)
        if server is not None:
            self.paths.insert(0, server)  # A share sits under its server, whose shares the panel lists.
        self.setToolTip(name)
        self.setAccessibleName("Folder path: " + name)
        self.update_links()

    @staticmethod
    def label(path: Path) -> str:
        """A crumb's word: the name, a drive's root as it is, a server or a share by its name alone."""

        if path.name:
            return path.name
        drive = path.drive.rstrip("\\")
        if drive.startswith("\\\\"):
            return drive.rpartition("\\")[2]  # \\server -> server, \\server\share -> share

        return str(path)

    def update_links(self):
        if not self.paths:
            return
        labels = [self.label(path) for path in self.paths]
        metrics = self.fontMetrics()
        start = 0
        while start < len(labels) - 1:
            text = ("… › " if start else "") + " › ".join(labels[start:])
            if metrics.horizontalAdvance(text) <= self.width():
                break
            start += 1
        self.hidden_paths = self.paths[:start]
        # Explorer's address bar is body text with muted separators, not blue links.
        color = self.palette().color(QPalette.ColorRole.WindowText).name()
        separator = (f'<span style="color:{self.palette().color(QPalette.ColorRole.PlaceholderText).name()}">'
                     " › </span>")

        def link(label, target):
            return f'<a href="{target}" style="color:{color}; text-decoration:none">{escape(label)}</a>'

        links = [link("…", "more")] if start else []
        available = max(30, self.width() - metrics.horizontalAdvance("… › " if start else ""))
        for index in range(start, len(labels)):
            label = labels[index]
            if index == start == len(labels) - 1:
                label = metrics.elidedText(label, Qt.TextElideMode.ElideMiddle, available)
            links.append(link(label, index))
        self.setText(separator.join(links))

    def mouseReleaseEvent(self, event):
        # A click beside the crumbs types the path instead, as in Explorer. A crumb's own click is
        # handled inside the release, so whether one was hit is known once it returns.
        self._activated = False
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and not self._activated:
            self.edit_requested.emit()

    def open_link(self, target):
        self._activated = True
        if target == "more":
            menu = QMenu(self)
            for path in self.hidden_paths:
                action = menu.addAction(self.label(path))
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked=False, path=path: self.folder_clicked.emit(path))
            window_effects.style_window(menu)
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
