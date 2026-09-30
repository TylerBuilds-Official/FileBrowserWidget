import os
from pathlib import Path


class Favorites:
    def __init__(self, settings=None):
        self.settings = settings
        saved = settings.value("files/favorites", [], type=list) if settings is not None else []
        self.paths = list({self.key(path): os.path.abspath(path) for path in saved if path}.values())
        # contains() runs several times per row on every render; keep the keys ready, and the key
        # of each path asked about, since abspath asks Windows for the full path every time.
        self.keys = {self.key(path) for path in self.paths}
        self._asked = {}

    @staticmethod
    def key(path):
        return os.path.normcase(os.path.abspath(path))

    def contains(self, path):
        key = self._asked.get(path)
        if key is None:
            if len(self._asked) > 4096:
                self._asked.clear()
            key = self._asked[path] = self.key(path)

        return key in self.keys

    def toggle(self, path):
        key = self.key(path)
        if key in self.keys:
            self.paths = [saved for saved in self.paths if self.key(saved) != key]
        else:
            self.paths.append(os.path.abspath(path))
        self.keys = {self.key(saved) for saved in self.paths}
        if self.settings is not None:
            self.settings.setValue("files/favorites", self.paths)

    def files(self):
        return [Path(path) for path in self.paths]
