from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    max_requests: int = 28
    window_seconds: float = 60.0
    _timestamps: list[float] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._timestamps = [
                t for t in self._timestamps if now - t < self.window_seconds
            ]
            if len(self._timestamps) >= self.max_requests:
                oldest = self._timestamps[0]
                wait_time = self.window_seconds - (now - oldest)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    now = time.monotonic()
                    self._timestamps = [
                        t for t in self._timestamps if now - t < self.window_seconds
                    ]
            self._timestamps.append(time.monotonic())
