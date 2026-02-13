# -*- coding: utf-8 -*-
# @Time    : 2026/2/13
# @Author  : KimmyXYC
# @File    : scheduler.py
# @Software: PyCharm
import asyncio
import datetime
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Set

import pytz
from loguru import logger


@dataclass
class CronJob:
    plugin_name: str
    job_id: str
    schedule: "CronSchedule"
    callback: Callable
    next_run_utc: Optional[datetime.datetime] = None


class CronSchedule:
    def __init__(self, cron_expr: str, tz_name: str):
        fields = (cron_expr or "").split()
        if len(fields) != 5:
            raise ValueError(f"Invalid cron expr '{cron_expr}': expected 5 fields")

        minute_field, hour_field, day_field, month_field, weekday_field = fields
        if day_field != "*" or month_field != "*" or weekday_field != "*":
            raise ValueError(f"Unsupported cron expr '{cron_expr}': only minute/hour are supported")

        self.minutes = _parse_cron_field(minute_field, 0, 59)
        self.hours = _parse_cron_field(hour_field, 0, 23)
        self.tz = pytz.timezone(tz_name)

    def next_run_utc(self, from_utc: datetime.datetime) -> datetime.datetime:
        local = from_utc.astimezone(self.tz).replace(second=0, microsecond=0)
        local += datetime.timedelta(minutes=1)

        for _ in range(60 * 24 * 366):
            if local.minute in self.minutes and local.hour in self.hours:
                return local.astimezone(pytz.utc)
            local += datetime.timedelta(minutes=1)

        raise RuntimeError("Failed to compute next run time for cron schedule")


def _parse_cron_field(field: str, min_value: int, max_value: int) -> Set[int]:
    if field == "*":
        return set(range(min_value, max_value + 1))

    values: Set[int] = set()
    for part in field.split(','):
        part = part.strip()
        if not part:
            continue

        if part.startswith("*/"):
            step = int(part[2:])
            if step <= 0:
                raise ValueError(f"Invalid cron step '{part}'")
            values.update(range(min_value, max_value + 1, step))
            continue

        if '-' in part:
            start_str, end_str = part.split('-', 1)
            start = int(start_str)
            end = int(end_str)
            if start > end:
                start, end = end, start
            values.update(range(start, end + 1))
            continue

        values.add(int(part))

    for val in values:
        if val < min_value or val > max_value:
            raise ValueError(f"Cron value {val} out of range {min_value}-{max_value}")

    return values


class CronScheduler:
    def __init__(self):
        self._jobs: Dict[str, CronJob] = {}
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._wakeup_event = asyncio.Event()
        self._bot = None

    def attach_bot(self, bot):
        self._bot = bot

    def register_cron_job(self, plugin_name: str, job_id: str, cron_expr: str, timezone: str, callback: Callable):
        schedule = CronSchedule(cron_expr, timezone)
        key = f"{plugin_name}:{job_id}"
        job = CronJob(plugin_name=plugin_name, job_id=job_id, schedule=schedule, callback=callback)
        job.next_run_utc = schedule.next_run_utc(_utc_now())
        self._jobs[key] = job
        self._wakeup_event.set()
        logger.info(f"⏱️ 注册定时任务 {key} ({cron_expr} {timezone})")

    def clear_jobs(self, plugin_name: str = None):
        if plugin_name:
            keys = [k for k, v in self._jobs.items() if v.plugin_name == plugin_name]
            for key in keys:
                self._jobs.pop(key, None)
        else:
            self._jobs.clear()
        self._wakeup_event.set()

    def start(self):
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info("⏱️ 定时任务调度器已启动")

    async def stop(self):
        self._stop_event.set()
        self._wakeup_event.set()
        if self._task:
            await self._task
            self._task = None

    async def _run(self):
        while not self._stop_event.is_set():
            if not self._jobs:
                await self._wait_for_event(60)
                continue

            now_utc = _utc_now()
            for job in self._get_due_jobs(now_utc):
                job.next_run_utc = job.schedule.next_run_utc(now_utc)
                asyncio.create_task(self._run_job(job))

            next_run = min((job.next_run_utc for job in self._jobs.values() if job.next_run_utc), default=None)
            if not next_run:
                await self._wait_for_event(60)
                continue

            delay = max(1.0, (next_run - _utc_now()).total_seconds())
            await self._wait_for_event(delay)

    async def _run_job(self, job: CronJob):
        if self._bot is None:
            logger.warning(f"⏱️ 定时任务 {job.plugin_name}:{job.job_id} 无 bot 实例，跳过执行")
            return

        try:
            await job.callback(self._bot)
        except Exception as e:
            logger.error(f"⏱️ 定时任务 {job.plugin_name}:{job.job_id} 执行失败: {e}")

    def _get_due_jobs(self, now_utc: datetime.datetime) -> Iterable[CronJob]:
        for job in self._jobs.values():
            if job.next_run_utc and job.next_run_utc <= now_utc:
                yield job

    async def _wait_for_event(self, timeout: float):
        self._wakeup_event.clear()
        try:
            await asyncio.wait_for(
                asyncio.gather(self._stop_event.wait(), self._wakeup_event.wait()),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=pytz.utc)


scheduler = CronScheduler()

