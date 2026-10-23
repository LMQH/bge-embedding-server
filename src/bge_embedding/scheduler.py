"""One non-interruptible inference task and configured cancellable FIFO waiters."""
import asyncio
from collections import deque
from dataclasses import dataclass

from .api import APIError

# A short window only starts when the head of the queue can share the next run.
# The limits match one inference batch, not one client request.
_MICRO_BATCH_WINDOW_SECONDS = 0.015
_MICRO_BATCH_MAX_ITEMS = 16
_MICRO_BATCH_MAX_TOKENS = 8192


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
        self.batch_size = 0
        self.task = None
        self.closing = False

    def submit(self, tokens, return_sparse=False):
        if self.closing:
            raise APIError("model_unavailable")
        running = self.batch_size or (1 if self.active is not None else 0)
        if self.active is not None and running + len(self.waiting) >= 1 + self.max_waiting:
            raise APIError("queue_full")
        loop = asyncio.get_running_loop()
        job = Job(tokens, return_sparse, loop.create_future())
        job.enqueued_at = loop.time()
        job.ahead = running + len(self.waiting)
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

    @staticmethod
    def _items(job):
        return len(job.tokens)

    @staticmethod
    def _tokens(job):
        return sum(len(ids) for ids in job.tokens)

    def _prefix(self, anchor):
        """Return the FIFO prefix that fits, and whether it is already full."""
        items, tokens = self._items(anchor), self._tokens(anchor)
        batch = [anchor]
        for job in list(self.waiting):
            if job not in self.waiting or job.result.done():
                continue
            if job.return_sparse != anchor.return_sparse:
                break
            next_items = items + self._items(job)
            next_tokens = tokens + self._tokens(job)
            if (next_items > _MICRO_BATCH_MAX_ITEMS
                    or next_tokens > _MICRO_BATCH_MAX_TOKENS):
                break
            batch.append(job)
            items, tokens = next_items, next_tokens
        full = items >= _MICRO_BATCH_MAX_ITEMS or tokens >= _MICRO_BATCH_MAX_TOKENS
        return batch, full

    async def _collect(self, anchor):
        """Collect a FIFO prefix of compatible waiters after a short window."""
        if not self.waiting or self.closing:
            return [anchor]
        first = self.waiting[0]
        if first.return_sparse != anchor.return_sparse:
            return [anchor]
        if (self._items(anchor) >= _MICRO_BATCH_MAX_ITEMS
                or self._tokens(anchor) >= _MICRO_BATCH_MAX_TOKENS):
            return [anchor]
        batch, full = self._prefix(anchor)
        if full:
            return batch
        await asyncio.sleep(_MICRO_BATCH_WINDOW_SECONDS)
        batch, _ = self._prefix(anchor)
        return batch

    def _start(self, batch):
        self.batch_size = len(batch)
        now = asyncio.get_running_loop().time()
        for job in batch:
            job.started_at = now
            if job.timer:
                job.timer.cancel()
                job.timer = None
        for job in batch[1:]:
            if job in self.waiting:
                self.waiting.remove(job)

    def _deliver(self, batch, value):
        expected = sum(len(job.tokens) for job in batch)
        if len(value) != expected:
            raise ValueError("Inference result size mismatch.")
        offset = 0
        for job in batch:
            size = len(job.tokens)
            chunk = value[offset:offset + size]
            offset += size
            if not job.result.done():
                job.result.set_result(chunk)

    async def _retry_each(self, batch):
        loop = asyncio.get_running_loop()
        for job in batch:
            if job.result.done():
                continue
            try:
                value = await loop.run_in_executor(
                    self.executor, self.infer, job.tokens, job.return_sparse)
            except Exception:
                if not job.result.done():
                    job.result.set_exception(APIError("inference_failed"))
            else:
                if not job.result.done():
                    job.result.set_result(value)

    async def _run(self):
        loop = asyncio.get_running_loop()
        while self.active is not None:
            batch = await self._collect(self.active)
            self._start(batch)
            combined = [ids for job in batch for ids in job.tokens]
            try:
                value = await loop.run_in_executor(
                    self.executor, self.infer, combined, self.active.return_sparse)
                self._deliver(batch, value)
            except Exception:
                await self._retry_each(batch)
            finally:
                finished_at = loop.time()
                for job in batch:
                    job.finished_at = finished_at
                self.batch_size = 0
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
