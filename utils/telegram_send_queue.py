"""Telegram 发送限速队列。

按 chat_id 维护独立 FIFO worker：同一 chat 串行发送，不同 chat 可并发发送。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable


SendCoroFactory = Callable[[], Awaitable[Any]]


@dataclass(slots=True)
class _QueuedSendTask:
    send_coro_factory: SendCoroFactory
    seekables: tuple[Any, ...]
    future: asyncio.Future[Any]


class TelegramSendQueue:
    """轻量 Telegram 发送队列。

    - 每个 chat_id 使用一个 FIFO worker。
    - 同 chat 的任务串行执行，并在两次发送任务之间等待 ``send_interval`` 秒。
    - worker 空闲超过 ``idle_timeout`` 秒后自动清理。
    """

    def __init__(self, send_interval: float = 1.0, idle_timeout: float = 300.0):
        self.send_interval = send_interval
        self.idle_timeout = idle_timeout
        self._queues: dict[Any, asyncio.Queue[_QueuedSendTask]] = {}
        self._workers: dict[Any, asyncio.Task[None]] = {}

    async def enqueue(
        self,
        chat_id: Any,
        send_coro_factory: SendCoroFactory,
        seekables: Iterable[Any] | None = None,
    ) -> Any:
        """加入发送任务并等待结果。

        Args:
            chat_id: Telegram chat id；相同 chat_id 的任务会按 FIFO 串行执行。
            send_coro_factory: 无参 callable，返回实际发送用 awaitable。
            seekables: 可选的文件/BytesIO 流列表；执行发送前会尝试 ``seek(0)``。

        Returns:
            ``send_coro_factory`` 的 await 结果。

        Raises:
            透传 ``send_coro_factory`` 抛出的异常。
        """

        loop = asyncio.get_running_loop()
        queue = self._queues.get(chat_id)
        if queue is None:
            queue = asyncio.Queue()
            self._queues[chat_id] = queue

        worker = self._workers.get(chat_id)
        if worker is None or worker.done():
            self._workers[chat_id] = loop.create_task(self._worker(chat_id, queue))

        future: asyncio.Future[Any] = loop.create_future()
        await queue.put(
            _QueuedSendTask(
                send_coro_factory=send_coro_factory,
                seekables=tuple(seekables or ()),
                future=future,
            )
        )
        return await future

    async def _worker(
        self, chat_id: Any, queue: asyncio.Queue[_QueuedSendTask]
    ) -> None:
        last_finished_at: float | None = None

        while True:
            try:
                task = await asyncio.wait_for(queue.get(), timeout=self.idle_timeout)
            except asyncio.TimeoutError:
                if queue.empty() and self._workers.get(chat_id) is asyncio.current_task():
                    self._workers.pop(chat_id, None)
                    self._queues.pop(chat_id, None)
                    return
                continue

            try:
                if task.future.cancelled():
                    continue

                if last_finished_at is not None and self.send_interval > 0:
                    elapsed = time.monotonic() - last_finished_at
                    wait_seconds = self.send_interval - elapsed
                    if wait_seconds > 0:
                        await asyncio.sleep(wait_seconds)

                self._rewind_seekables(task.seekables)
                result = await task.send_coro_factory()
            except Exception as exc:
                if not task.future.done():
                    task.future.set_exception(exc)
            else:
                if not task.future.done():
                    task.future.set_result(result)
            finally:
                last_finished_at = time.monotonic()
                queue.task_done()

    @staticmethod
    def _rewind_seekables(seekables: Iterable[Any]) -> None:
        for seekable in seekables:
            seek = getattr(seekable, "seek", None)
            if seek is not None:
                seek(0)


telegram_send_queue = TelegramSendQueue()
