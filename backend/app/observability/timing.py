"""High-precision monotonic timing utilities for NexaRAG observability."""

import time
from types import TracebackType


class Timer:
    """Monotonic clock timer for measuring stage and request latencies in milliseconds.

    Uses time.perf_counter() to ensure clock-drift resilience and avoid wall-clock shifts.
    Supports both explicit start/stop calls and Python context manager protocol.
    """

    def __init__(self, autostart: bool = True):
        self._start_time: float | None = None
        self._stop_time: float | None = None
        if autostart:
            self.start()

    def start(self) -> "Timer":
        """Start or restart the monotonic timer."""
        self._start_time = time.perf_counter()
        self._stop_time = None
        return self

    def stop(self) -> float:
        """Stop the timer and return the elapsed time in milliseconds."""
        if self._start_time is None:
            raise RuntimeError("Timer was never started.")
        self._stop_time = time.perf_counter()
        return self.elapsed_ms

    @property
    def is_running(self) -> bool:
        """Return True if timer is currently running, False otherwise."""
        return self._start_time is not None and self._stop_time is None

    @property
    def elapsed_ms(self) -> float:
        """Return elapsed duration in milliseconds.

        If the timer is currently running, returns elapsed time from start up to now.
        If stopped, returns the recorded duration between start and stop.
        """
        if self._start_time is None:
            return 0.0
        end = self._stop_time if self._stop_time is not None else time.perf_counter()
        return round((end - self._start_time) * 1000.0, 2)

    def __enter__(self) -> "Timer":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop()
