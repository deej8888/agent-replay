import logging
import os
import queue
import threading
from typing import Protocol

import httpx

from .models import Run

logger = logging.getLogger("agentreplay")


class Transport(Protocol):
    def submit(self, run: Run) -> None: ...


class MemoryTransport:
    def __init__(self) -> None:
        self.runs: list[Run] = []

    def submit(self, run: Run) -> None:
        self.runs.append(run.model_copy(deep=True))


class BufferedHTTPTransport:
    """Bounded best-effort queue. Explicitly close() before process exit to flush."""

    def __init__(
        self, url: str | None = None, api_key: str | None = None, capacity: int = 128
    ) -> None:
        self.url = (url or os.getenv("AGENTREPLAY_API_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.api_key = api_key or os.getenv("AGENTREPLAY_API_KEY") or ""
        self.queue: queue.Queue[Run | None] = queue.Queue(maxsize=capacity)
        self.dropped = 0
        self.failed = 0
        self.closed = False
        self.lock = threading.Lock()
        self.worker = threading.Thread(target=self._work, daemon=True, name="agentreplay-export")
        self.worker.start()

    def submit(self, run: Run) -> None:
        with self.lock:
            if self.closed:
                self.dropped += 1
                return
            try:
                self.queue.put_nowait(run.model_copy(deep=True))
            except queue.Full:
                self.dropped += 1
                logger.warning("AgentReplay buffer full; trace dropped")

    def _work(self) -> None:
        with httpx.Client(timeout=3, trust_env=False) as client:
            while True:
                run = self.queue.get()
                try:
                    if run is None:
                        return
                    response = client.post(
                        f"{self.url}/v1/runs",
                        json=run.model_dump(mode="json"),
                        headers={"X-API-Key": self.api_key},
                    )
                    response.raise_for_status()
                except Exception:
                    self.failed += 1
                    logger.warning("AgentReplay export failed; trace dropped (no payload logged)")
                finally:
                    self.queue.task_done()

    def close(self) -> None:
        with self.lock:
            if self.closed:
                return
            self.closed = True
        self.queue.join()
        self.queue.put(None)
        self.worker.join(timeout=5)

    def __enter__(self) -> "BufferedHTTPTransport":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
