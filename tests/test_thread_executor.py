import gc
import threading
import time
import unittest
import weakref

from PyQt6.QtCore import QCoreApplication

from src.utils.thread_executor import ThreadExecutor


class ThreadExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def pump_until(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate():
            self.app.processEvents()
            if time.monotonic() >= deadline:
                self.fail("Timed out waiting for the executor")
            time.sleep(0.001)

    def observe(self, executor):
        events = []
        executor.started.connect(lambda value: events.append(("started", value)))
        executor.success.connect(lambda value: events.append(("success", value)))
        executor.errors.connect(lambda value: events.append(("errors", value)))
        executor.failed.connect(lambda value: events.append(("failed", value)))
        return events

    def test_success_passes_arguments_and_runs_off_main_thread(self):
        calls = []
        main_thread = threading.get_ident()

        def task(value, *, suffix):
            calls.append((value + suffix, threading.get_ident()))

        executor = ThreadExecutor(task, args=("file",), kwargs={"suffix": ".txt"})
        events = self.observe(executor)
        executor.run_task()
        self.pump_until(lambda: any(name == "success" for name, _ in events))
        self.assertEqual(events, [("started", True), ("success", True)])
        self.assertEqual(calls[0][0], "file.txt")
        self.assertNotEqual(calls[0][1], main_thread)
        self.assertTrue(executor.thread.task_complete)
        self.assertNotIn(executor, ThreadExecutor._active_executors)

    def test_success_on_last_retry(self):
        calls = []

        def task():
            calls.append(None)
            if len(calls) < 3:
                raise RuntimeError("Try again")

        executor = ThreadExecutor(task)
        events = self.observe(executor)
        executor.run_task()
        self.pump_until(lambda: any(name == "success" for name, _ in events))
        self.assertEqual(len(calls), 3)
        self.assertEqual(events, [("started", True), ("success", True)])

    def test_exhaustion_reports_all_errors_once(self):
        for retries in (0, 2):
            with self.subTest(retries=retries):
                failures = []

                def task():
                    error = RuntimeError("Task failed")
                    failures.append(error)
                    raise error

                executor = ThreadExecutor(task, retries=retries)
                events = self.observe(executor)
                executor.run_task()
                self.pump_until(lambda: any(name == "failed" for name, _ in events))
                self.assertEqual(len(failures), retries + 1)
                self.assertEqual(events, [
                    ("started", True), ("errors", failures), ("failed", True)
                ])
                self.assertFalse(executor.thread.task_complete)
                self.assertNotIn(executor, ThreadExecutor._active_executors)

    def test_os_errors_are_reported_without_retry(self):
        for error_type in (OSError, PermissionError, FileNotFoundError):
            with self.subTest(error_type=error_type):
                calls = []
                def task():
                    calls.append(None)
                    raise error_type("Cannot open file")
                executor = ThreadExecutor(task, retries=5)
                events = self.observe(executor)
                executor.run_task()
                self.pump_until(lambda: any(name == "failed" for name, _ in events))
                self.assertEqual(len(calls), 1)
                errors = [value for name, value in events if name == "errors"]
                self.assertEqual(len(errors), 1)
                self.assertIsInstance(errors[0][0], error_type)

    def test_file_opener_reports_path_and_error_on_main_thread(self):
        from pathlib import Path
        from unittest.mock import patch
        from src.utils.file_opener import FileOpener
        reported = []
        path = Path("missing.txt").absolute()
        error = FileNotFoundError("Missing file")
        with patch("src.utils.file_opener.os.startfile", side_effect=error) as start:
            with self.assertLogs("src.utils.file_opener", level="ERROR"):
                FileOpener.open_file(path, on_error=lambda file, exc: reported.append(
                    (file, exc, threading.get_ident())))
                self.pump_until(lambda: bool(reported))
            start.assert_called_once_with(path)
        self.assertEqual(reported, [(path, error, threading.get_ident())])

    def test_local_executor_is_retained_then_released(self):
        # Match FileOpener: no executor is returned or stored by the caller.
        def launch():
            executor = ThreadExecutor(lambda: None)
            reference = weakref.ref(executor)
            executor.run_task()
            return reference

        reference = launch()
        gc.collect()
        self.assertIsNotNone(reference())
        self.assertIn(reference(), ThreadExecutor._active_executors)
        self.pump_until(lambda: not ThreadExecutor._active_executors)
        gc.collect()
        self.assertIsNone(reference())

    def test_duplicate_start_is_ignored_and_call_does_not_block(self):
        release = threading.Event()
        calls = []

        def task():
            calls.append(None)
            release.wait(timeout=2)

        executor = ThreadExecutor(task)
        events = self.observe(executor)
        try:
            executor.run_task()
            executor.run_task()
            self.pump_until(lambda: bool(calls))
            self.assertFalse(executor.thread.task_complete)
        finally:
            release.set()
            self.pump_until(lambda: executor not in ThreadExecutor._active_executors)
        self.assertEqual(len(calls), 1)
        self.assertEqual(events, [("started", True), ("success", True)])

    def test_reuse_resets_previous_failure(self):
        calls = []

        def task():
            calls.append(None)
            if len(calls) == 1:
                raise ValueError("First run fails")

        executor = ThreadExecutor(task, retries=0)
        events = self.observe(executor)
        executor.run_task()
        self.pump_until(lambda: any(name == "failed" for name, _ in events))
        events.clear()
        executor.run_task()
        self.pump_until(lambda: any(name == "success" for name, _ in events))
        self.assertEqual(events, [("started", True), ("success", True)])
        self.assertEqual(executor.thread.errors, [])

    def test_invalid_retry_limits(self):
        for retries in (-1, 1.5, "2"):
            with self.subTest(retries=retries):
                with self.assertRaises(ValueError):
                    ThreadExecutor(lambda: None, retries=retries)


if __name__ == "__main__":
    unittest.main()
