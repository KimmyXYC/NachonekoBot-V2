# -*- coding: utf-8 -*-
# @Time    : 2026/2/12 19:10
# @Author  : KimmyXYC
# @File    : stats.py
# @Software: PyCharm
import re
import datetime
import pytz
import asyncpg
from loguru import logger
from telebot import types

from utils.postgres import BotDatabase

# ==================== 插件元数据 ====================
__plugin_name__ = "stats"
__display_name__ = "发言统计记录器"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "群聊发言统计排行（支持日/周/月/年与自定义时间范围）"
__commands__ = ["stats"]
__command_descriptions__ = {"stats": "查看群聊发言排行榜"}
__command_help__ = {
    "stats": "/stats - 今日统计\n"
    "/stats 5h - 5小时统计\n"
    "/stats 4d - 4日统计\n"
    "/stats 3w - 3周统计\n"
    "/stats 2m - 2月统计\n"
    "/stats 1y - 1年统计\n"
    "/stats 2026-02-25 - 指定日期统计\n"
    "/stats 2026/02/25 - 指定日期统计\n"
    "/stats 20260225 - 指定日期统计\n"
}
__toggleable__ = True
__scheduled_jobs__ = []

DAY_CUTOFF_HOUR = 4


def _get_tz():
    return pytz.timezone("Asia/Shanghai")


def _get_cycle_start(now: datetime.datetime, cutoff_hour: int = DAY_CUTOFF_HOUR):
    cycle_start = now.replace(
        hour=cutoff_hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    if now < cycle_start:
        cycle_start -= datetime.timedelta(days=1)
    return cycle_start


def _get_display_name(user: types.User) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    name = f"{first} {last}".strip()
    return name or "Unknown"


def _parse_stats_args(text: str):
    parts = (text or "").split()
    if len(parts) <= 1:
        return {"mode": "range", "n": 1, "unit": "d", "title": "今日活跃度排行"}

    arg_raw = parts[1].strip()
    target_date = _parse_stats_date_arg(arg_raw)
    if target_date:
        return {
            "mode": "date",
            "date": target_date,
            "title": f"{target_date:%Y-%m-%d} 活跃度排行",
        }

    arg = arg_raw.lower()
    m = re.match(r"^(\d+)([dhwmy])$", arg)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
    elif arg.isdigit():
        n = int(arg)
        unit = "d"
    else:
        return None

    if n <= 0:
        return None

    if unit == "h":
        title = f"近{n}小时活跃度排行"
    elif unit == "w":
        title = f"近{n}周活跃度排行"
    elif unit == "m":
        title = f"近{n}月活跃度排行"
    elif unit == "y":
        title = f"近{n}年活跃度排行"
    else:
        title = "今日活跃度排行" if n == 1 else f"近{n}天活跃度排行"

    return {"mode": "range", "n": n, "unit": unit, "title": title}


def _parse_stats_date_arg(arg: str):
    if not arg:
        return None

    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", arg)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", arg)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", arg)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    return None


def _get_time_range(n: int, unit: str):
    tz = _get_tz()
    now = datetime.datetime.now(tz)
    end_time = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(
        hours=1
    )

    if unit == "h":
        start_time = end_time - datetime.timedelta(hours=n)
    elif unit == "w":
        cycle_start = _get_cycle_start(now)
        start_time = cycle_start - datetime.timedelta(days=n * 7 - 1)
    elif unit == "m":
        cycle_start = _get_cycle_start(now)
        start_time = cycle_start - datetime.timedelta(days=n * 30 - 1)
    elif unit == "y":
        cycle_start = _get_cycle_start(now)
        start_time = cycle_start - datetime.timedelta(days=n * 365 - 1)
    else:
        cycle_start = _get_cycle_start(now)
        start_time = cycle_start - datetime.timedelta(days=n - 1)

    return start_time, end_time


def _get_date_time_range(target_date: datetime.date):
    tz = _get_tz()
    start_time = tz.localize(
        datetime.datetime(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
            hour=DAY_CUTOFF_HOUR,
            minute=0,
            second=0,
            microsecond=0,
        )
    )
    end_time = start_time + datetime.timedelta(days=1)
    return start_time, end_time


async def _increment_speech_count(
    group_id: int, user_id: int, hour: datetime.datetime, display_name: str
):
    conn = BotDatabase.conn
    try:
        await conn.execute(
            """
            INSERT INTO speech_stats (group_id, user_id, hour, count, display_name)
            VALUES ($1, $2, $3, 1, $4)
            ON CONFLICT (group_id, user_id, hour)
            DO UPDATE SET count = speech_stats.count + 1, display_name = EXCLUDED.display_name
            """,
            group_id,
            user_id,
            hour,
            display_name,
        )
    except asyncpg.PostgresError as e:
        logger.error(f"[Stats][Postgres Error]: {e}")


async def _query_stats(
    group_id: int, start_time: datetime.datetime, end_time: datetime.datetime
):
    conn = BotDatabase.conn
    try:
        rows = await conn.fetch(
            """
            SELECT user_id,
                   MAX(display_name) AS display_name,
                   SUM(count) AS total
            FROM speech_stats
            WHERE group_id = $1 AND hour >= $2 AND hour < $3
            GROUP BY user_id
            ORDER BY total DESC, display_name ASC
            LIMIT 20
            """,
            group_id,
            start_time,
            end_time,
        )
        total = await conn.fetchval(
            """
            SELECT COALESCE(SUM(count), 0)
            FROM speech_stats
            WHERE group_id = $1 AND hour >= $2 AND hour < $3
            """,
            group_id,
            start_time,
            end_time,
        )
        return rows, int(total or 0)
    except asyncpg.PostgresError as e:
        logger.error(f"[Stats][Postgres Error]: {e}")
        return [], 0


async def _query_top_speaker(
    group_id: int, start_time: datetime.datetime, end_time: datetime.datetime
):
    conn = BotDatabase.conn
    try:
        row = await conn.fetchrow(
            """
            SELECT user_id,
                   MAX(display_name) AS display_name,
                   SUM(count) AS total
            FROM speech_stats
            WHERE group_id = $1 AND hour >= $2 AND hour < $3
            GROUP BY user_id
            ORDER BY total DESC, display_name ASC
            LIMIT 1
            """,
            group_id,
            start_time,
            end_time,
        )
        return row
    except asyncpg.PostgresError as e:
        logger.error(f"[Stats][Postgres Error]: {e}")
        return None


async def _query_dragon_king_daily(group_id: int, stat_date: datetime.date):
    conn = BotDatabase.conn
    try:
        row = await conn.fetchrow(
            """
            SELECT user_id, display_name, total, streak_days
            FROM dragon_king_daily
            WHERE group_id = $1 AND stat_date = $2
            """,
            group_id,
            stat_date,
        )
        return row
    except asyncpg.PostgresError as e:
        logger.error(f"[Stats][Postgres Error]: {e}")
        return None


async def _upsert_dragon_king_daily(
    group_id: int,
    stat_date: datetime.date,
    user_id: int,
    display_name: str,
    total: int,
    streak_days: int,
):
    conn = BotDatabase.conn
    try:
        await conn.execute(
            """
            INSERT INTO dragon_king_daily (group_id, stat_date, user_id, display_name, total, streak_days)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (group_id, stat_date)
            DO UPDATE SET
                user_id = EXCLUDED.user_id,
                display_name = EXCLUDED.display_name,
                total = EXCLUDED.total,
                streak_days = EXCLUDED.streak_days
            """,
            group_id,
            stat_date,
            user_id,
            display_name,
            total,
            streak_days,
        )
    except asyncpg.PostgresError as e:
        logger.error(f"[Stats][Postgres Error]: {e}")


async def handle_stats_command(bot, message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        await bot.reply_to(message, "该统计仅支持群组使用。")
        return

    parsed = _parse_stats_args(message.text or "")
    if not parsed:
        await bot.reply_to(
            message,
            "用法：/stats [Nh|Nd|Nw|Nm|Ny|YYYY-MM-DD|YYYY/MM/DD|YYYYMMDD] 例如 /stats 1h /stats 4d /stats 3w /stats 2m /stats 4y /stats 2026-02-25 /stats 2026/02/25 /stats 20260225",
        )
        return

    title = parsed["title"]
    if parsed["mode"] == "date":
        start_time, end_time = _get_date_time_range(parsed["date"])
    else:
        start_time, end_time = _get_time_range(parsed["n"], parsed["unit"])
    rows, total = await _query_stats(message.chat.id, start_time, end_time)

    display_end_time = end_time - datetime.timedelta(hours=1)
    range_text = f"{start_time:%Y-%m-%d %H:%M} ~ {display_end_time:%Y-%m-%d %H:%M}"
    if not rows:
        await bot.reply_to(message, f"{title}\n统计区间: {range_text}\n\n暂无统计数据")
        return

    lines = [title, f"统计区间: {range_text}", ""]

    for idx, row in enumerate(rows, start=1):
        name = row["display_name"]
        count = row["total"]
        lines.append(f"{idx}. {name} - {count}")

    lines.extend(["", f"总计发言: {total}"])
    await bot.reply_to(message, "\n".join(lines))


async def handle_stats_message(bot, message: types.Message):
    if not getattr(message, "chat", None) or message.chat.type not in (
        "group",
        "supergroup",
    ):
        return
    if not getattr(message, "from_user", None) or message.from_user.is_bot:
        return

    tz = _get_tz()
    msg_time = datetime.datetime.fromtimestamp(message.date, tz=tz)
    hour = msg_time.replace(minute=0, second=0, microsecond=0)
    display_name = _get_display_name(message.from_user)
    await _increment_speech_count(
        message.chat.id, message.from_user.id, hour, display_name
    )


async def handle_dragon_king_schedule(bot):
    job_name = f"{__plugin_name__}.dragon_king"
    rows = await BotDatabase.get_enabled_scheduled_groups(job_name)
    if not rows:
        return

    for row in rows:
        group_id = row["group_id"]
        tz_name = row.get("timezone") or "Asia/Shanghai"
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = _get_tz()
        now = datetime.datetime.now(tz)
        cycle_end = _get_cycle_start(now)
        cycle_start = cycle_end - datetime.timedelta(days=1)
        stat_date = cycle_start.date()

        top_row = await _query_top_speaker(group_id, cycle_start, cycle_end)
        if not top_row:
            continue

        display_name = top_row["display_name"]
        user_id = int(top_row["user_id"])
        total = int(top_row["total"] or 0)
        if total <= 0:
            continue

        prev_row = await _query_dragon_king_daily(
            group_id, stat_date - datetime.timedelta(days=1)
        )
        streak_days = 1
        if prev_row and int(prev_row["user_id"]) == user_id:
            streak_days = int(prev_row["streak_days"] or 0) + 1

        await _upsert_dragon_king_daily(
            group_id,
            stat_date,
            user_id,
            display_name,
            total,
            streak_days,
        )

        try:
            await bot.send_message(
                group_id,
                f"恭喜 {display_name} 获得本群🐉龙王标志（已连任{streak_days}天）",
            )
        except Exception as e:
            logger.error(f"[Stats] 发送龙王消息失败 group={group_id}: {e}")


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""
    global bot_instance
    bot_instance = bot

    middleware.register_message_handler(
        callback=handle_stats_message,
        plugin_name=plugin_name,
        handler_name="speech_stats_recorder",
        priority=1,
        stop_propagation=False,
        chat_types=["group", "supergroup"],
    )

    middleware.register_command_handler(
        commands=["stats"],
        callback=handle_stats_command,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["group", "supergroup", "private"],
    )

    logger.info(
        f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}"
    )

    middleware.register_cron_job(
        plugin_name=plugin_name,
        job_id="dragon_king",
        cron_expr="0 4 * * *",
        timezone="Asia/Shanghai",
        callback=handle_dragon_king_schedule,
        display_name="龙王标志",
    )


def get_plugin_info() -> dict:
    """获取插件信息"""
    return {
        "name": __plugin_name__,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": __commands__,
    }


bot_instance = None
