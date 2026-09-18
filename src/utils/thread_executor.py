from PyQt6.QtCore import QThread, pyqtSignal, QObject


class Thread(QThread):
    def __init__(self, task, args=(), kwargs=None):
        super().__init__()
        self.task = task
        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}

        self.task_complete = False

    def run(self):
        try:
            self.task(*self.args, **self.kwargs)
            self.task_complete = True
        except Exception as ex:
            raise ex


class ThreadExecutor(QObject):
    """
    A class for executing tasks in a separate thread.
    """

    started = pyqtSignal(bool, name="started")
    success = pyqtSignal(bool, name="success")
    failed = pyqtSignal(bool, name="failed")
    errors = pyqtSignal(list, name="errors")

    def __init__(self, task, args=(), kwargs=None):
        super().__init__()
        self.thread = Thread(task, args, kwargs)

    def run_task(self):
        try:
            self.thread.start()
            self.thread.wait()
            self.started.emit(True)
        except Exception as e:
            self.errors.emit([e])
            self.failed.emit(True)