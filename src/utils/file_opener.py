import os
import logging
from pathlib import Path

from src.utils.thread_executor import ThreadExecutor


class FileOpener:
    @staticmethod
    def open_file_location(file: str | Path, on_error=None):
        folder = Path(file).absolute().parent
        if on_error is None:
            return FileOpener.open_file(folder)
        return FileOpener.open_file(folder, on_error=on_error)

    @staticmethod
    def open_file(file: str | Path, on_error=None):
        file = Path(file).absolute()
        # Launching twice can open duplicate windows; failures need user action.
        task = ThreadExecutor(task=os.startfile, args=(file,), retries=0)

        def report(errors):
            error = errors[-1]
            logging.getLogger(__name__).error("Could not open %s: %s", file, error)
            if on_error is not None:
                on_error(file, error)

        task.errors.connect(report)
        task.run_task()
        return task


