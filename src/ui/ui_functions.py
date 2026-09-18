from src.utils.file_opener import FileOpener

class UIFunctions:
    def __init__(self, ui):
        self.ui = ui

    def open_file(self, file: str | Path):
        FileOpener.open_file(file)