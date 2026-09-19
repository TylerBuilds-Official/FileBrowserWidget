from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, QObject


class Thread(QThread):
    def __init__(self, task, args=(), kwargs=None, retries=2):
        super().__init__()
        if not isinstance(retries, int) or retries < 0:
            raise ValueError("retries must be a non-negative integer")

        self.task = task
        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}
        self.retries = retries
        self.task_complete = False
        self.errors = []

    def run(self):
        self.task_complete = False
        self.errors = []

        # Retries happen in the worker, so the caller's event loop stays free.
        for _ in range(self.retries + 1):
            try:
                self.task(*self.args, **self.kwargs)
            except Exception as exc:
                self.errors.append(exc)
                if isinstance(exc, OSError):
                    return

            else:
                self.task_complete = True
                return


class ThreadExecutor(QObject):
    """
    Run a task asynchronously, with two retries by default.

    Create and start executors in the application thread with a running Qt
    event loop. Active executors retain themselves until their worker finishes.
    OSError is reported after the first attempt; other errors can be retried.
    """

    _active_executors = set()

    started = pyqtSignal(bool, name="started")
    success = pyqtSignal(bool, name="success")
    failed  = pyqtSignal(bool, name="failed")
    errors  = pyqtSignal(list, name="errors")

    def __init__(self, task, args=(), kwargs=None, *, retries=2):
        super().__init__()
        self.thread = Thread(task, args, kwargs, retries)
        self.thread.started.connect(self._on_started)
        self.thread.finished.connect(self._on_finished)


    def run_task(self):
        # Also guard the interval before the queued finished handler runs.
        if self in self._active_executors:
            return

        self.thread.task_complete = False
        self.thread.errors = []
        self._active_executors.add(self)

        try:
            self.thread.start()
        except Exception as exc:
            self._active_executors.discard(self)
            self.errors.emit([exc])
            self.failed.emit(True)


    @pyqtSlot()
    def _on_started(self):
        self.started.emit(True)

    @pyqtSlot()
    def _on_finished(self):
        # finished has fired; wait only for the thread's final native cleanup.
        self.thread.wait()
        completed = self.thread.task_complete
        errors = list(self.thread.errors)
        self._active_executors.discard(self)

        if completed:
            self.success.emit(True)
        else:
            self.errors.emit(errors)
            self.failed.emit(True)
