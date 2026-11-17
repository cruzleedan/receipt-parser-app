"""Bound CPU jobs without releasing capacity when their awaiter is cancelled."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class CapacityError(RuntimeError):
    """All parser capacity is occupied; callers should retry later."""


class BoundedWorker:
    def __init__(self):
        # One OCR predictor is shared, so serialize all image/OCR operations.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="receipt-cpu")
        self._lock = Lock()
        self._busy = False

    def _release(self, future):
        with self._lock:
            self._busy = False

    async def run(self, function, *args):
        with self._lock:
            if self._busy:
                raise CapacityError("Parser image worker is busy; retry later")
            self._busy = True
            try:
                future = self._executor.submit(function, *args)
            except BaseException:
                self._busy = False
                raise
        # Register outside the lock: add_done_callback may run immediately.
        future.add_done_callback(self._release)
        wrapped = asyncio.wrap_future(future)
        # Retrieve failures even if cancellation detaches the waiter.
        wrapped.add_done_callback(lambda f: None if f.cancelled() else f.exception())
        return await asyncio.shield(wrapped)


image_worker = BoundedWorker()
