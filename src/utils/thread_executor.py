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
            self.started.emit(True)
        except Exception as e:
            self.errors.emit([str(e)])
            self.failed.emit(True)


test_task = lambda: print("[TASK] Hello from thread")
test_class = ThreadExecutor(task=test_task)


def print_started():
    print("[THREAD] Task started")


def print_success():
    print("[THREAD] Task completed successfully")


def print_fail():
    print("[THREAD] Task failed")


def print_errors(errors: list):
    print("[THREAD] Errors occurred during task execution:")
    for error in errors:
        print("———————— " + "[ThreadErrors]: " + error)

test_class.started.connect(print_started)
test_class.failed.connect(print_fail)
test_class.errors.connect(print_errors)


test_class.run_task()