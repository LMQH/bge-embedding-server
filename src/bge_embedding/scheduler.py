"""One non-interruptible inference task and configured cancellable FIFO waiters."""
import asyncio
from collections import deque
from dataclasses import dataclass

from .api import APIError


@dataclass(eq=False)
class Job:
    tokens: list[list[int]]
    return_sparse: bool
    result: asyncio.Future
    timer: asyncio.TimerHandle | None = None
    enqueued_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    ahead: int = 0


class Scheduler:
    def __init__(self, infer, executor, config):
        self.infer, self.executor = infer, executor
        self.max_waiting = config.max_waiting
        self.wait_seconds = config.wait_timeout_seconds
        self.waiting = deque()
        self.active = None
        self.task = None
        self.closing = False

    def submit(self, tokens, return_sparse=False):
        if self.closing:
            raise APIError("model_unavailable")
        if self.active is not None and len(self.waiting) >= self.max_waiting:
            raise APIError("queue_full")
        loop = asyncio.get_running_loop()
        job = Job(tokens, return_sparse, loop.create_future())
        job.enqueued_at = loop.time()
        job.ahead = len(self.waiting) + (1 if self.active is not None else 0)
        if self.active is None:
            self.active = job
            self.task = asyncio.create_task(self._run())
        else:
            self.waiting.append(job)
            job.timer = loop.call_later(self.wait_seconds, self._expire, job)
        return job

    def _expire(self, job):
        if job in self.waiting:
            self.waiting.remove(job)
            job.result.set_exception(APIError("queue_timeout"))

    def abandon(self, job):
        if job in self.waiting:
            self.waiting.remove(job)
        if job.timer:
            job.timer.cancel()
        if job.result.done() and not job.result.cancelled():
            job.result.exception()  # Retrieve a failure if the connection disappeared.
        job.result.cancel()
        # An active job still owns the executor until its GPU work finishes.

    async def _run(self):
        while self.active is not None:
            job = self.active
            job.started_at = asyncio.get_running_loop().time()
            try:
                value = await asyncio.get_running_loop().run_in_executor(
                    self.executor, self.infer, job.tokens, job.return_sparse)
            except Exception:
                if not job.result.done():
                    job.result.set_exception(APIError("inference_failed"))
            else:
                if not job.result.done():
                    job.result.set_result(value)
            finally:
                job.finished_at = asyncio.get_running_loop().time()
            self.active = self.waiting.popleft() if self.waiting else None
            if self.active and self.active.timer:
                self.active.timer.cancel()

    def begin_shutdown(self):
        self.closing = True
        while self.waiting:
            job = self.waiting.popleft()
            job.timer.cancel()
            job.result.set_exception(APIError("model_unavailable"))

    async def close(self):
        self.begin_shutdown()
        if self.task:
            await asyncio.shield(self.task)
