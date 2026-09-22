from PyQt6.QtCore import QSize

from src.utils.file_icons import FileIcons
from src.utils.thread_executor import ThreadExecutor


class IconReader:
    """Read file icons off the UI thread, a batch at a time, through the thread executor.

    Windows can hold a shell icon request for seconds on a network file, so the UI thread
    never asks for one. A worker reads a batch into images, which cross threads safely, and
    the caller turns them into pixmaps on the UI thread. Whatever a batch read before an
    error still counts.
    """

    SIZE = 20

    def __init__(self, provider: FileIcons):
        self.provider = provider

    def read(self, entries: list, ratio: float, landed) -> ThreadExecutor:
        """Read the entries' icons on a worker; `landed(images)` runs on the UI thread after."""

        provider = self.provider
        size = QSize(self.SIZE, self.SIZE)
        images = []

        def task():
            for entry in entries:
                images.append((entry, provider.icon(entry.path).pixmap(size, ratio).toImage()))

        executor = ThreadExecutor(task, retries=0)
        executor.success.connect(lambda *_: landed(images))
        executor.errors.connect(lambda *_: landed(images))
        executor.run_task()

        return executor
