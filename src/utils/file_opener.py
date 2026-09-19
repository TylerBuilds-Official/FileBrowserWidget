import os
from pathlib import Path

from src.utils.thread_executor import ThreadExecutor


class FileOpener:
    @staticmethod
    def open_file_location(file: str | Path):
        FileOpener.open_file(Path(file).absolute().parent)

    @staticmethod
    def open_file(file: str | Path):
        file = Path(file)
        try:
            task = ThreadExecutor(task=os.startfile, args=(file.absolute(),))
            task.run_task()
        except Exception as e:
            raise e


