from pathlib import Path
from time import monotonic

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, QTimer
from PyQt6.QtGui import QCursor, QIcon, QMouseEvent, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QApplication, QStyle

from src.ui.custom_widgets.cascade_menu import CascadeMenu
from src.ui.custom_widgets.file_row_widget import FileRowWidget
from src.ui.custom_widgets.scrolling_menu_style import ScrollingMenuStyle
from src.utils import window_effects
from src.utils.file_listing import list_folder
from src.utils.thread_executor import ThreadExecutor


class FolderCascade(QObject):
    """Fan a folder's contents out beside the panel when the pointer rests on its row.

    The rows act as the top level of a shell toolbar menu: resting on a folder opens its
    menu after the system menu delay, resting on another row moves it, clicking a row still
    opens it in the panel, and a right-click on any level shows that item's own menu.

    Only pointer movement counts as resting. Qt also raises Enter events for whatever lands
    under a still pointer when the list is rebuilt, scrolled, or uncovered by a closing menu,
    and none of those should fan a folder out. Scrolling the list is the opposite of resting:
    it cancels a pending level, closes an open one, and asks for a real move before the
    pointer can rest again, and a wheel over the panel scrolls the list rather than the menu.

    Nothing here touches the disk or the shell on the UI thread. Folders are read by the
    thread executor as soon as the pointer rests on their row or item, so a level is usually
    ready before it is due; one that is not shows "Loading…" until its items arrive. Icons
    are read the same way, a few at a time, and painted in behind the open menu.
    """

    MAX_ITEMS = 250
    ICON_BATCH = 8
    HIDDEN_ATTRIBUTE = 0x2
    GRACE_MS = 150
    PREFETCH_MS = 80
    LISTING_SECONDS = 5
    LISTING_LIMIT = 200

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.enabled = False
        self.leftward = False
        self.menu_style = ScrollingMenuStyle()
        self._menu = None
        self._menus = []
        self._source_row = None
        self._hover_row = None
        self._keyboard = False
        self._pointer = None
        self._scrolled_at = None
        self._generation = 0
        self._listings = {}
        self._in_flight = set()
        self._waiting = {}

        delay = QApplication.style().styleHint(QStyle.StyleHint.SH_Menu_SubMenuPopupDelay)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(delay if delay > 0 else 400)
        self.timer.timeout.connect(self._hover_settled)

        # Sweeping down the list should not read every folder passed; a short rest earns a read.
        self.prefetch_timer = QTimer(self)
        self.prefetch_timer.setSingleShot(True)
        self.prefetch_timer.setInterval(self.PREFETCH_MS)
        self.prefetch_timer.timeout.connect(self._prefetch_hover_row)

        # Rows swallow plain moves, but Qt hands a hover move to every ancestor that asks.
        browser.file_list_widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        browser.file_list_widget.installEventFilter(self)
        browser.scroll_area.verticalScrollBar().valueChanged.connect(self._list_scrolled)

    def set_behavior(self, behavior: str):
        self.enabled = behavior == "cascade"
        if not self.enabled:
            self.close()
            self._set_hover_row(None)

    def register_row(self, row: FileRowWidget):
        row.installEventFilter(self)

    def is_open(self) -> bool:
        return self._menu is not None

    def menus(self) -> list[CascadeMenu]:
        return [menu for menu in self._menus if not sip.isdeleted(menu) and menu.isVisible()]

    def contains(self, global_position: QPoint) -> bool:
        """Whether a point lies over any open level of the cascade."""

        return any(menu.geometry().contains(global_position) for menu in self.menus())

    def eventFilter(self, watched, event):
        kind = event.type()
        if watched is self.browser.file_list_widget:
            if kind == QEvent.Type.HoverMove:
                self._pointer_over_list(event.globalPosition().toPoint())
            elif kind == QEvent.Type.HoverLeave:
                self._pointer = None  # Coming back to the same pixel later is a move.
                self._set_hover_row(None)
        elif isinstance(watched, FileRowWidget):
            if kind == QEvent.Type.ToolTip and self.enabled and watched.is_folder:
                return True  # The path tooltip and the menu would answer the same rest.
            if kind == QEvent.Type.MouseButtonPress:
                self.timer.stop()  # The click opens or drags the row; a menu would be in the way.
            elif kind == QEvent.Type.Hide:
                if watched is self._source_row:
                    # A rebuild hides every row and shows the survivors again in the same call.
                    QTimer.singleShot(0, self._source_row_settled)
                if watched is self._hover_row:
                    self._set_hover_row(None)

        return super().eventFilter(watched, event)

    def _pointer_over_list(self, position: QPoint):
        """Only a pointer that moved counts; a repeated position is Qt speaking for a still one."""

        if position == self._pointer:
            return
        self._pointer = position
        if self._scrolled_at is not None:
            if (position - self._scrolled_at).manhattanLength() < QApplication.startDragDistance():
                return
            self._scrolled_at = None
        if self.enabled and QApplication.mouseButtons() == Qt.MouseButton.NoButton:
            self._set_hover_row(self.row_at(position))

    def _list_scrolled(self, *_):
        """Wheeling past folders is not resting on them, and an open level would drift from its row."""

        self._scrolled_at = self._pointer if self._pointer is not None else QCursor.pos()
        self._set_hover_row(None)
        self.close()

    def _source_row_settled(self):
        """After a rebuild, keep the menu on a row that came back and drop it otherwise."""

        row, menu = self._source_row, self._menu
        if row is None or menu is None:
            return
        if sip.isdeleted(row) or not row.isVisible():
            self.close()
        elif not sip.isdeleted(menu) and menu.isVisible():
            menu.move(self.anchor(row, menu.width()))
            self.fit_menu_heights()

    def pointer_moved(self, global_position: QPoint):
        """The open menu owns the pointer, so the rows hear about it from here."""

        self._set_hover_row(None if self.contains(global_position) else self.row_at(global_position))

    def row_at(self, global_position: QPoint) -> FileRowWidget | None:
        browser = self.browser
        viewport = browser.scroll_area.viewport()
        if not browser.content.isEnabled() or not viewport.rect().contains(viewport.mapFromGlobal(global_position)):
            return None
        widget = browser.file_list_widget.childAt(browser.file_list_widget.mapFromGlobal(global_position))
        while widget is not None and not isinstance(widget, FileRowWidget):
            widget = widget.parentWidget()

        return widget

    def _set_hover_row(self, row: FileRowWidget | None):
        if row is self._hover_row:
            return
        self._hover_row = row
        self.timer.stop()
        self.prefetch_timer.stop()
        if row is not None and row is not self._source_row and (row.is_folder or self.is_open()):
            self.timer.start()
            if row.is_folder:
                self.prefetch_timer.start()  # Read it while the pointer settles.

    def _prefetch_hover_row(self):
        row = self._hover_row
        if row is not None and not sip.isdeleted(row) and row.is_folder:
            self.ensure_listing(row.path)

    def _hover_settled(self):
        row = self._hover_row
        if row is None:
            return
        if row.is_folder:
            self.open_for(row)
        else:
            self.close()

    def prefetch(self, action):
        """A highlighted folder item is read before its level is due to open."""

        if action is not None and action.menu() is not None and action.data():
            self.ensure_listing(Path(action.data()))

    def open_focused(self):
        """Right on a focused folder row fans it out, whatever the hover setting; arrows go on inside."""

        row = self.browser.focusWidget()
        if isinstance(row, FileRowWidget) and row.is_folder:
            self.open_for(row, keyboard=True)

    def open_for(self, row: FileRowWidget, keyboard: bool = False):
        """Fan the row's folder out beside the panel, top aligned with the row."""

        self.timer.stop()
        browser = self.browser
        if not ((self.enabled or keyboard) and browser.isVisible() and browser.content.isEnabled()
                and row.isVisible()):
            return
        self.close()
        self._generation += 1
        self._keyboard = keyboard
        # Every level fans out away from the screen edge the panel sits against.
        panel = browser.frameGeometry()
        self.leftward = panel.center().x() > browser.screen().availableGeometry().center().x()
        menu = CascadeMenu(self, browser)
        self._menu = menu
        self._menus = [menu]
        self._source_row = row
        row.set_cascaded(True)
        menu.aboutToHide.connect(self._closed)
        entries = self.cached_listing(row.path)
        if entries is not None:
            self.populate(menu, entries)
            self.show_menu(menu)
            return
        self.await_listing(menu, row.path)
        # A folder that answers within a moment appears complete, with no flash of "Loading…".
        QTimer.singleShot(self.GRACE_MS, lambda: self.show_menu(menu))

    def show_menu(self, menu: CascadeMenu):
        """Put the top level on screen, once."""

        row = self._source_row
        if menu is not self._menu or sip.isdeleted(menu) or menu.isVisible() or row is None or sip.isdeleted(row):
            return
        window_effects.style_window(menu)
        menu.popup(self.anchor(row, menu.sizeHint().width()))
        if self._keyboard:
            self.highlight_first(menu)

    @staticmethod
    def highlight_first(menu: CascadeMenu):
        """A level opened from the keyboard starts on its first item, as a menu bar's would."""

        for action in menu.actions():
            if action.isEnabled() and action.data():
                menu.setActiveAction(action)
                return

    def anchor(self, row: FileRowWidget, width: int) -> QPoint:
        """Beside the panel on the cascade's side, with the first item level with the row."""

        panel = self.browser.frameGeometry()
        x = self.fit_beside(panel.left() - width, panel.right() + 1, width)
        # The menu's own top padding sits above its first item.
        y = row.mapToGlobal(QPoint(0, 0)).y() - 4

        return QPoint(x, y)

    def fit_beside(self, left_x: int, right_x: int, width: int) -> int:
        """The x on the cascade's side; the other side only when that one leaves the screen."""

        screen = self.browser.screen().availableGeometry()
        first, second = (left_x, right_x) if self.leftward else (right_x, left_x)
        for x in (first, second):
            if screen.left() <= x and x + width - 1 <= screen.right():
                return x

        return max(screen.left(), min(first, screen.right() - width + 1))

    def place_submenu(self, menu: CascadeMenu):
        """Qt puts a submenu on whichever side has room, tucked under its parent's padding;
        keep every level on the cascade's side, edge to edge with the level before it."""

        parent = menu.parentWidget()
        if not isinstance(parent, CascadeMenu):
            return
        frame = parent.geometry()
        x = self.fit_beside(frame.left() - menu.width(), frame.right() + 1, menu.width())
        menu.move(x, menu.y())

    def relayout(self, menu: CascadeMenu):
        """Size a showing level again after its items arrived, keeping it on the cascade's side."""

        if sip.isdeleted(menu) or not menu.isVisible():
            return
        # popup() on a showing menu refits it to the screen and resets its scroll state
        # without touching its link to the level that opened it.
        menu.popup(menu.pos())
        if menu is self._menu and self._source_row is not None and not sip.isdeleted(self._source_row):
            menu.move(self.anchor(self._source_row, menu.width()))
        else:
            self.place_submenu(menu)
        self.fit_menu_heights()

    def fill_on_show(self, menu: CascadeMenu, folder: Path):
        """A level lists itself when Qt shows it, from the read made while it was highlighted."""

        if menu.filled:
            return
        entries = self.cached_listing(folder)
        if entries is not None:
            self.populate(menu, entries)
        else:
            self.await_listing(menu, folder)
        window_effects.style_window(menu)

    def cached_listing(self, folder: Path) -> list | None:
        record = self._listings.get(folder)
        if record is None or monotonic() - record[0] > self.LISTING_SECONDS:
            return None

        return record[1]

    def ensure_listing(self, folder: Path):
        if self.cached_listing(folder) is None:
            self.request_listing(folder)

    def await_listing(self, menu: CascadeMenu, folder: Path):
        """Show a level as loading until the executor delivers its folder."""

        self.show_notice(menu, "Loading…")
        self._waiting.setdefault(folder, []).append(menu)
        self.request_listing(folder)

    def request_listing(self, folder: Path):
        """Read one folder on a worker; the result lands on the UI thread through the executor."""

        if folder in self._in_flight:
            return
        self._in_flight.add(folder)
        entries = []

        def task():
            entries.extend(list_folder(folder, self.HIDDEN_ATTRIBUTE))

        executor = ThreadExecutor(task, retries=0)
        executor.success.connect(lambda ok: self._listed(folder, entries))
        executor.errors.connect(lambda errors: self._listing_failed(folder, errors[-1]))
        executor.run_task()

    def _listed(self, folder: Path, entries: list):
        if sip.isdeleted(self):
            return
        self._in_flight.discard(folder)
        self._listings[folder] = (monotonic(), entries)
        while len(self._listings) > self.LISTING_LIMIT:
            del self._listings[next(iter(self._listings))]
        for menu in self._waiting.pop(folder, []):
            if not sip.isdeleted(menu):
                self.populate(menu, entries)
                self._arrived(menu)

    def _listing_failed(self, folder: Path, error: Exception):
        if sip.isdeleted(self):
            return
        self._in_flight.discard(folder)
        for menu in self._waiting.pop(folder, []):
            if not sip.isdeleted(menu):
                menu.filled = True
                self.show_notice(menu, "Could not open this folder", str(error))
                self._arrived(menu)

    def _arrived(self, menu: CascadeMenu):
        """A level's items landed: show a waiting top level, or refit one already showing."""

        if menu is self._menu and not menu.isVisible():
            self.show_menu(menu)
        else:
            self.relayout(menu)
            if menu is self._menu and self._keyboard:
                self.highlight_first(menu)

    @staticmethod
    def show_notice(menu: CascadeMenu, text: str, detail: str = ""):
        menu.clear()
        menu.items = {}
        notice = menu.addAction(text)
        notice.setEnabled(False)
        notice.setToolTip(detail)

    def populate(self, menu: CascadeMenu, entries: list):
        """Build one level's items; subfolders get levels that list themselves when shown."""

        menu.clear()
        menu.items = {}
        menu.filled = True
        if not entries:
            menu.addAction("Empty folder").setEnabled(False)
            return
        show_extensions = self.browser.settings_modal.show_extensions
        wanted = []
        for entry in entries[:self.MAX_ITEMS]:
            is_folder = "folders" in entry.kinds
            name = entry.path.name if show_extensions or is_folder else entry.path.stem
            text = name.replace("&", "&&")  # A lone ampersand would become a mnemonic.
            if is_folder:
                submenu = CascadeMenu(self, menu)
                submenu.setTitle(text)
                submenu.aboutToShow.connect(
                    lambda submenu=submenu, path=entry.path: self.fill_on_show(submenu, path))
                self._menus.append(submenu)
                action = menu.addMenu(submenu)
            else:
                action = menu.addAction(text)
                action.triggered.connect(lambda checked=False, path=entry.path: self.activate(path))
            action.setData(str(entry.path))
            action.setIcon(self.icon_for(entry, wanted))
            menu.items[str(entry.path)] = action
        if len(entries) > self.MAX_ITEMS:
            menu.addSeparator()
            more = menu.addAction(f"Show all {len(entries)} items")
            more.triggered.connect(lambda checked=False, path=entry.path.parent: self.drill(path))
        self.load_icons(menu, wanted)

    def icon_for(self, entry, wanted: list) -> QIcon:
        """A cached icon shows now; the rest start generic and are read behind the open menu."""

        browser = self.browser
        cached = browser._icons.get(entry.path)
        if cached is not None and cached[0] == browser.icon_stamp(entry):
            return QIcon(cached[1])
        if not (entry.online_only or entry.error):
            wanted.append(entry)

        return QIcon(browser.generic_pixmap("folders" in entry.kinds))

    def load_icons(self, menu: CascadeMenu, queue: list):
        """Read a few icons on a worker, paint them in, then go again until the level is done."""

        generation = self._generation
        if not queue or sip.isdeleted(menu):
            return
        batch, rest = queue[:self.ICON_BATCH], queue[self.ICON_BATCH:]

        def landed(images):
            if sip.isdeleted(self) or generation != self._generation or sip.isdeleted(menu):
                return
            self._apply_icons(menu, images)
            self.load_icons(menu, rest)

        self.browser.icon_reader.read(batch, self.browser.devicePixelRatioF(), landed)

    def _apply_icons(self, menu: CascadeMenu, images: list):
        browser = self.browser
        for entry, image in images:
            pixmap = QPixmap.fromImage(image)
            browser._icons[entry.path] = (browser.icon_stamp(entry), pixmap)
            action = menu.items.get(str(entry.path))
            if action is not None:
                action.setIcon(QIcon(pixmap))
        self.fit_menu_heights()

    def fit_menu_heights(self):
        """A changed action makes QMenu grow back to its full height; keep each level on the screen."""

        screen = self.browser.screen().availableGeometry()
        for menu in self.menus():
            overflow = menu.geometry().bottom() - screen.bottom()
            if overflow > 0:
                menu.resize(menu.width(), max(menu.height() - overflow, 1))

    def pressed_outside(self, event: QMouseEvent):
        """Qt closed the cascade on this press; hand the press to the panel or dismiss it."""

        if event.button() != Qt.MouseButton.LeftButton:
            return
        browser = self.browser
        global_position = event.globalPosition().toPoint()
        local = browser.mapFromGlobal(global_position)
        if not browser.rect().contains(local):
            browser.record_dismissal(global_position)
            browser.hide()
            return
        target = browser.childAt(local) or browser
        position = QPointF(target.mapFromGlobal(global_position))
        press = QMouseEvent(QEvent.Type.MouseButtonPress, position, QPointF(global_position),
                            event.button(), event.buttons(), event.modifiers())
        QApplication.sendEvent(target, press)

    def wheeled_outside(self, event: QWheelEvent):
        """A wheel over the panel is meant for the list; the cascade only stands in the way."""

        global_position = event.globalPosition().toPoint()
        self.close()
        # A sent wheel reaches only its receiver, never its parents, so aim at the viewport.
        viewport = self.browser.scroll_area.viewport()
        local = viewport.mapFromGlobal(global_position)
        if not viewport.rect().contains(local):
            return
        wheel = QWheelEvent(QPointF(local), QPointF(global_position), event.pixelDelta(), event.angleDelta(),
                            event.buttons(), event.modifiers(), event.phase(), event.inverted())
        QApplication.sendEvent(viewport, wheel)

    def activate(self, path: str | Path):
        self.close()
        self.browser.open_item(Path(path))

    def drill(self, path: str | Path):
        self.close()
        self.browser.navigate_to(Path(path))

    def show_context_menu(self, path: str | Path, global_position: QPoint):
        self.browser.show_file_menu(Path(path), global_position)
        self.close()

    def close(self):
        self.timer.stop()
        menu = self._menu
        if menu is None:
            return
        if not sip.isdeleted(menu) and menu.isVisible():
            menu.hide()  # aboutToHide finishes the job.
        else:
            self._closed()

    def _closed(self):
        menu, self._menu = self._menu, None
        self._menus = []
        self._waiting = {}
        self._generation += 1  # Icon reads still on their way land nowhere.
        row, self._source_row = self._source_row, None
        if row is not None and not sip.isdeleted(row):
            row.set_cascaded(False)
        if menu is not None and not sip.isdeleted(menu):
            menu.deleteLater()
