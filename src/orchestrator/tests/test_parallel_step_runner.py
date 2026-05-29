import unittest
import time
import threading
from ..workflows.base import ParallelStepRunner


class TestParallelStepRunner(unittest.TestCase):
    def test_successful_parallel_execution(self) -> None:
        shared_list = []
        lock = threading.Lock()

        def worker(item: int, delay: float) -> None:
            time.sleep(delay)
            with lock:
                shared_list.append(item)

        with ParallelStepRunner() as runner:
            runner.add(worker, 1, 0.05)
            runner.add(worker, 2, 0.01)

        # Because worker 2 has a shorter delay, it should append first if executed in parallel
        self.assertEqual(shared_list, [2, 1])

    def test_exception_propagation(self) -> None:
        def failing_worker() -> None:
            raise ValueError("Something went wrong")

        def normal_worker() -> None:
            time.sleep(0.02)

        with self.assertRaises(ValueError) as context:
            with ParallelStepRunner() as runner:
                runner.add(failing_worker)
                runner.add(normal_worker)

        self.assertEqual(str(context.exception), "Something went wrong")

    def test_daemon_flag(self) -> None:
        with ParallelStepRunner() as runner:
            runner.add(lambda: None)
            thread = runner.threads[0]
            self.assertTrue(thread.daemon)

    def test_context_exception_priority(self) -> None:
        # If an exception is raised inside the context block of the main thread,
        # that exception should be raised, not the thread exceptions.
        with self.assertRaises(RuntimeError) as context:
            with ParallelStepRunner() as runner:
                runner.add(lambda: time.sleep(0.01))
                raise RuntimeError("Main thread error")

        self.assertEqual(str(context.exception), "Main thread error")
