"""What the tests share: waiting for the work the browser hands to worker threads."""
import time

from PyQt6.QtTest import QTest

from src.utils.thread_executor import ThreadExecutor


def settle(browser, timeout=10.0):
    """Wait until the folder read the browser asked for has landed.

    Call this from the test itself, never from inside a widget's handler: it spins the event
    loop, and a read landing re-renders the list, deleting rows. Waiting inside a row's own
    event handler lets that delete run with the row still on the stack, and the unwind then
    crashes. (That is why this is not wrapped around create_list_items for every test.)
    """
    deadline = time.monotonic() + timeout
    while browser._scan_pending:
        QTest.qWait(5)
        if time.monotonic() > deadline:
            raise AssertionError("the folder read never landed")


def drain_workers(timeout=10.0):
    """Wait for every worker thread to finish, so none outlives the test that started it."""
    deadline = time.monotonic() + timeout
    while ThreadExecutor._active_executors:
        QTest.qWait(5)
        if time.monotonic() > deadline:
            raise AssertionError("a worker never finished")
