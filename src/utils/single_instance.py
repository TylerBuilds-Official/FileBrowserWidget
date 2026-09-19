import ctypes
import hashlib
import os
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QLockFile, QStandardPaths, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    """Keep one background app per user; later launches can ask it to open."""

    show_requested = pyqtSignal()

    def __init__(self, parent=None, name=None, lock_directory=None):
        super().__init__(parent)
        user = hashlib.sha256(str(Path.home()).encode()).hexdigest()[:16]
        self.name = name or f"FileBrowserWidget-{user}"
        directory = Path(lock_directory or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))
        self.lock = QLockFile(str(directory / f"{self.name}.lock"))
        self.lock.setStaleLockTime(0)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept_connections)
        self.is_primary = False

    def start_or_notify(self, show=True):
        if self.lock.tryLock(0):
            # The lock also protects against two simultaneous launches on Windows.
            QLocalServer.removeServer(self.name)
            if not self.server.listen(self.name):
                self.lock.unlock()
                raise RuntimeError(self.server.errorString())
            self.is_primary = True
            return True

        # Allow the first process a moment to create its local server.
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            socket = QLocalSocket()
            socket.connectToServer(self.name)
            if socket.waitForConnected(200):
                if show:
                    self._allow_foreground()
                socket.write(b"show\n" if show else b"background\n")
                if socket.bytesToWrite() and not socket.waitForBytesWritten(1000):
                    raise RuntimeError("Could not contact the running File Browser.")
                socket.disconnectFromServer()
                return False
            socket.abort()
            time.sleep(0.05)
        raise RuntimeError("File Browser is already running, but its launcher did not respond.")

    def _allow_foreground(self):
        # A user-launched second process can grant the running app focus rights.
        if os.name == "nt":
            valid, pid, _, _ = self.lock.getLockInfo()
            if valid:
                ctypes.windll.user32.AllowSetForegroundWindow(ctypes.c_uint(pid))

    def _accept_connections(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.readyRead.connect(lambda socket=socket: self._read_request(socket))
            socket.disconnected.connect(socket.deleteLater)
            self._read_request(socket)

    def _read_request(self, socket):
        while socket.canReadLine():
            if bytes(socket.readLine()).strip() == b"show":
                self.show_requested.emit()

    def close(self):
        if self.is_primary:
            self.server.close()
            self.lock.unlock()
            self.is_primary = False
