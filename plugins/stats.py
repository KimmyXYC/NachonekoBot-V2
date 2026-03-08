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
from utils.i18n import _t
from utils.i18n.runtime import make_localized_bot_for_chat
from app.security.permissions import has_group_admin_permission

# ==================== 插件元数据 ====================
__plugin_name__ = "stats"
__display_name__ = "发言统计记录器"
__version__ = "1.1.0"
__author__ = "KimmyXYC"
__description__ = "群聊发言统计排行（支持日/周/月/年与自定义时间范围）"
__commands__ = ["stats", "dragon", "stats_cutoff"]
__command_category__ = "utility"
__command_order__ = {"stats": 520, "dragon": 521, "stats_cutoff": 522}
__command_descriptions__ = {
    "stats": "查看群聊发言排行榜",
    "dragon": "查看龙王总榜",
    "stats_cutoff": "设置统计日分割时间",
}
__command_help__ = {
    "stats": "/stats - 今日统计\n"
    "/stats 5h - 5小时统计\n"
    "/stats 4d - 4日统计\n"
    "/stats 3w - 3周统计\n"
    "/stats 2m - 2月统计\n"
    "/stats 1y - 1年统计\n"
    "/stats 2026-02-25 - 指定日期统计\n"
    "/stats 2026/02/25 - 指定日期统计\n"
    "/stats 20260225 - 指定日期统计\n",
    "dragon": "/dragon - 龙王总榜\n",
    "stats_cutoff": "/stats_cutoff - 设置统计日分割时间\n",
}
__toggleable__ = True
__scheduled_jobs__ = []
__scheduled_job_display_names__ = {
    "dragon_king": "job.dragon_king",
    "daily_stats": "job.daily_stats",
}

DAY_CUTOFF_HOUR = 4


# ==================== 数据库初始化 ====================
async def setup_database(conn_pool):
    """插件数据库初始化钩子：创建 stats 插件所需的表和列"""
    async with conn_pool.acquire() as conn:
        # speech_stats 表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS speech_stats (
                group_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                hour TIMESTAMPTZ NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                display_name TEXT NOT NULL,
                PRIMARY KEY (group_id, user_id, hour)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_speech_stats_group_hour
            ON speech_stats (group_id, hour)
        """)

        # dragon_king_daily 表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dragon_king_daily (
                group_id BIGINT NOT NULL,
                stat_date DATE NOT NULL,
                user_id BIGINT NOT NULL,
                display_name TEXT NOT NULL,
                total INTEGER NOT NULL,
                streak_days INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (group_id, stat_date)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dragon_king_daily_group_user_date
            ON dragon_king_daily (group_id, user_id, stat_date DESC)
        """)

        # 在 setting 表中添加 stats_cutoff_hour 列
        await conn.execute("""
            ALTER TABLE setting
            ADD COLUMN IF NOT EXISTS stats_cutoff_hour INTEGER NOT NULL DEFAULT 4
        """)

    logger.info("[Stats] 数据库表和列初始化完成")


# ==================== 分割时间数据库操作 ====================
async def _get_cutoff_hour(group_id: int) -> int:
    """获取群组的统计日分割时间，默认 4"""
    conn = BotDatabase.conn
    try:
        await BotDatabase.ensure_group_row(group_id)
        async with conn.acquire() as connection:
            val = await connection.fetchval(
                "SELECT stats_cutoff_hour FROM setting WHERE group_id = $1",
                int(group_id),
            )
            if val is None:
                return DAY_CUTOFF_HOUR
            return int(val)
    except Exception as e:
        logger.error(f"[Stats] get cutoff hour error for group {group_id}: {e}")
        return DAY_CUTOFF_HOUR


async def _set_cutoff_hour(group_id: int, hour: int) -> bool:
    """设置群组的统计日分割时间，返回是否成功"""
    if not (0 <= hour <= 23):
        return False
    conn = BotDatabase.conn
    try:
        await BotDatabase.ensure_group_row(group_id)
        async with conn.acquire() as connection:
            await connection.execute(
                "UPDATE setting SET stats_cutoff_hour = $1 WHERE group_id = $2",
                int(hour),
                int(group_id),
            )
        logger.info(f"[Stats] Set cutoff hour={hour} for group {group_id}")
        return True
    except Exception as e:
        logger.error(f"[Stats] set cutoff hour error for group {group_id}: {e}")
        return False


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


def _parse_stats_args(text: str, t_func=None):
    def _lt(key: str, **kwargs):
        if t_func:
            return t_func(key, **kwargs)
        return key

    parts = (text or "").split()
    if len(parts) <= 1:
        return {
            "mode": "range",
            "n": 1,
            "unit": "d",
            "title": _lt("title.today_activity"),
        }

    arg_raw = parts[1].strip()
    target_date = _parse_stats_date_arg(arg_raw)
    if target_date:
        return {
            "mode": "date",
            "date": target_date,
            "title": _lt("title.date_activity", date=f"{target_date:%Y-%m-%d}"),
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
        title = _lt("title.range_hours", n=n)
    elif unit == "w":
        title = _lt("title.range_weeks", n=n)
    elif unit == "m":
        title = _lt("title.range_months", n=n)
    elif unit == "y":
        title = _lt("title.range_years", n=n)
    else:
        title = _lt("title.today_activity") if n == 1 else _lt("title.range_days", n=n)

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


def _get_time_range(n: int, unit: str, cutoff_hour: int = DAY_CUTOFF_HOUR):
    tz = _get_tz()
    now = datetime.datetime.now(tz)
    end_time = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(
        hours=1
    )

    if unit == "h":
        start_time = end_time - datetime.timedelta(hours=n)
    elif unit == "w":
        cycle_start = _get_cycle_start(now, cutoff_hour)
        start_time = cycle_start - datetime.timedelta(days=n * 7 - 1)
    elif unit == "m":
        cycle_start = _get_cycle_start(now, cutoff_hour)
        start_time = cycle_start - datetime.timedelta(days=n * 30 - 1)
    elif unit == "y":
        cycle_start = _get_cycle_start(now, cutoff_hour)
        start_time = cycle_start - datetime.timedelta(days=n * 365 - 1)
    else:
        cycle_start = _get_cycle_start(now, cutoff_hour)
        start_time = cycle_start - datetime.timedelta(days=n - 1)

    return start_time, end_time


def _get_date_time_range(
    target_date: datetime.date, cutoff_hour: int = DAY_CUTOFF_HOUR
):
    tz = _get_tz()
    start_time = tz.localize(
        datetime.datetime(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
            hour=cutoff_hour,
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


async def _query_dragon_king_leaderboard(group_id: int):
    conn = BotDatabase.conn
    try:
        rows = await conn.fetch(
            """
            SELECT user_id,
                   MAX(display_name) AS display_name,
                   COUNT(*) AS total_wins,
                   MAX(streak_days) AS max_streak
            FROM dragon_king_daily
            WHERE group_id = $1
            GROUP BY user_id
            ORDER BY total_wins DESC, max_streak DESC, display_name ASC
            """,
            group_id,
        )
        total_days = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM dragon_king_daily
            WHERE group_id = $1
            """,
            group_id,
        )
        return rows, int(total_days or 0)
    except asyncpg.PostgresError as e:
        logger.error(f"[Stats][Postgres Error]: {e}")
        return [], 0


async def _send_long_reply(
    bot, message: types.Message, text: str, chunk_size: int = 4096
):
    content = text or ""
    if len(content) <= chunk_size:
        await bot.reply_to(message, content)
        return

    await bot.reply_to(message, content[:chunk_size])
    remaining = content[chunk_size:]
    while remaining:
        chunk = remaining[:chunk_size]
        remaining = remaining[chunk_size:]
        await bot.send_message(message.chat.id, chunk)


async def handle_stats_command(bot, message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        await bot.reply_to(message, _t("error.stats_group_only"))
        return

    parsed = _parse_stats_args(message.text or "", _t)
    if not parsed:
        await bot.reply_to(
            message,
            _t("prompt.stats_usage"),
        )
        return

    # 读取群组自定义分割时间
    cutoff_hour = await _get_cutoff_hour(message.chat.id)

    title = parsed["title"]
    if parsed["mode"] == "date":
        start_time, end_time = _get_date_time_range(parsed["date"], cutoff_hour)
    else:
        start_time, end_time = _get_time_range(parsed["n"], parsed["unit"], cutoff_hour)
    rows, total = await _query_stats(message.chat.id, start_time, end_time)

    display_end_time = end_time - datetime.timedelta(hours=1)
    range_text = f"{start_time:%Y-%m-%d %H:%M} ~ {display_end_time:%Y-%m-%d %H:%M}"
    if not rows:
        await bot.reply_to(
            message,
            _t("result.stats_empty", title=title, range_text=range_text),
        )
        return

    lines = [title, _t("label.stats_range", range_text=range_text), ""]

    for idx, row in enumerate(rows, start=1):
        name = row["display_name"]
        count = row["total"]
        lines.append(_t("result.stats_row", rank=idx, name=name, count=count))

    lines.extend(["", _t("result.total_messages", total=total)])
    await bot.reply_to(message, "\n".join(lines))


async def handle_dragon_command(bot, message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        await bot.reply_to(message, _t("error.stats_group_only"))
        return

    rows, total_days = await _query_dragon_king_leaderboard(message.chat.id)
    if not rows:
        await bot.reply_to(message, _t("dragon.empty"))
        return

    lines = [_t("title.dragon_leaderboard"), ""]
    for idx, row in enumerate(rows, start=1):
        name = row["display_name"]
        total_wins = int(row["total_wins"] or 0)
        max_streak = int(row["max_streak"] or 0)
        lines.append(
            _t(
                "result.dragon_row",
                rank=idx,
                name=name,
                total_wins=total_wins,
                max_streak=max_streak,
            )
        )

    lines.extend(
        [
            "",
            _t("result.total_settlement_days", total_days=total_days),
            _t("result.leaderboard_user_count", user_count=len(rows)),
        ]
    )
    await _send_long_reply(bot, message, "\n".join(lines))


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


# ==================== 分割时间设置 ====================
def _build_cutoff_keyboard(current_hour: int) -> types.InlineKeyboardMarkup:
    """构建分割时间选择键盘（24个按钮，4列排布）"""
    kb = types.InlineKeyboardMarkup(row_width=4)
    buttons = []
    for h in range(24):
        mark = " *" if h == current_hour else ""
        btn = types.InlineKeyboardButton(
            text=f"{h}:00{mark}",
            callback_data=f"stats_cutoff:{h}",
        )
        buttons.append(btn)
    # 4列排布
    for i in range(0, len(buttons), 4):
        row = buttons[i : i + 4]
        kb.add(*row)
    # 关闭按钮
    close_btn = types.InlineKeyboardButton(text="X", callback_data="stats_cutoff_close")
    kb.add(close_btn)
    return kb


def _build_cutoff_text(current_hour: int, t_func=None) -> str:
    """构建分割时间设置面板文本"""
    _tf = t_func or _t
    lines = [
        _tf("cutoff.title"),
        "",
        _tf("cutoff.current", hour=current_hour),
        "",
        _tf("cutoff.description"),
    ]
    return "\n".join(lines)


async def handle_stats_cutoff_command(bot, message: types.Message):
    """处理 /stats_cutoff 命令：打开分割时间设置面板"""
    if message.chat.type not in ("group", "supergroup"):
        await bot.reply_to(message, _t("error.stats_group_only"))
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # 权限检查：需要 can_change_info
    has_perm = await has_group_admin_permission(
        bot,
        chat_id,
        user_id,
        required_permission="can_change_info",
        default_when_missing=True,
        allow_bot_admin=True,
    )
    if not has_perm:
        await bot.reply_to(message, _t("cutoff.permission_required"))
        return

    current_hour = await _get_cutoff_hour(chat_id)
    text = _build_cutoff_text(current_hour)
    kb = _build_cutoff_keyboard(current_hour)
    await bot.reply_to(message, text, reply_markup=kb)


async def handle_stats_cutoff_callback(bot, call: types.CallbackQuery):
    """处理分割时间选择回调"""
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    # 权限检查
    has_perm = await has_group_admin_permission(
        bot,
        chat_id,
        user_id,
        required_permission="can_change_info",
        default_when_missing=True,
        allow_bot_admin=True,
    )
    if not has_perm:
        await bot.answer_callback_query(call.id, _t("cutoff.permission_required"))
        return

    # 解析小时
    try:
        hour = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await bot.answer_callback_query(call.id, "Invalid hour")
        return

    if not (0 <= hour <= 23):
        await bot.answer_callback_query(call.id, "Invalid hour")
        return

    # 保存到数据库
    ok = await _set_cutoff_hour(chat_id, hour)
    if not ok:
        await bot.answer_callback_query(call.id, "Failed to update")
        return

    # 更新消息
    text = _build_cutoff_text(hour)
    kb = _build_cutoff_keyboard(hour)
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=kb,
        )
    except Exception as e:
        logger.debug(f"[Stats] 编辑分割时间消息失败: {e}")

    await bot.answer_callback_query(call.id, _t("cutoff.updated", hour=hour))


async def handle_stats_cutoff_close_callback(bot, call: types.CallbackQuery):
    """处理分割时间面板关闭回调"""
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    # 权限检查
    has_perm = await has_group_admin_permission(
        bot,
        chat_id,
        user_id,
        required_permission="can_change_info",
        default_when_missing=True,
        allow_bot_admin=True,
    )
    if not has_perm:
        await bot.answer_callback_query(call.id, _t("cutoff.permission_required"))
        return

    try:
        await bot.delete_message(chat_id, call.message.message_id)
    except Exception as e:
        logger.debug(f"[Stats] 删除分割时间面板失败: {e}")
    await bot.answer_callback_query(call.id)


# ==================== 龙王定时任务 ====================
async def handle_dragon_king_schedule(bot):
    """龙王定时任务（每小时触发，按群组分割时间过滤）"""
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
        current_hour = now.hour

        # 读取该群组的分割时间
        cutoff_hour = await _get_cutoff_hour(group_id)

        # 仅在当前小时等于群组分割时间时执行结算
        if current_hour != cutoff_hour:
            continue

        cycle_end = _get_cycle_start(now, cutoff_hour)
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
            lbot = await make_localized_bot_for_chat(bot, __plugin_name__, group_id)
            await lbot.send_message(
                group_id,
                _t(
                    "result.dragon_congrats",
                    display_name=display_name,
                    streak_days=streak_days,
                ),
            )
        except Exception as e:
            logger.error(f"[Stats] 发送龙王消息失败 group={group_id}: {e}")


# ==================== 每日统计自动发送 ====================
async def handle_daily_stats_schedule(bot):
    """每日统计定时任务（每小时触发，按群组分割时间过滤）"""
    job_name = f"{__plugin_name__}.daily_stats"
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
        current_hour = now.hour

        # 读取该群组的分割时间
        cutoff_hour = await _get_cutoff_hour(group_id)

        # 仅在当前小时等于群组分割时间时执行
        if current_hour != cutoff_hour:
            continue

        # 计算前一天的统计区间
        cycle_end = _get_cycle_start(now, cutoff_hour)
        cycle_start = cycle_end - datetime.timedelta(days=1)

        stats_rows, total = await _query_stats(group_id, cycle_start, cycle_end)
        if not stats_rows:
            continue

        try:
            lbot = await make_localized_bot_for_chat(bot, __plugin_name__, group_id)

            title = _t("title.yesterday_activity")
            display_end = cycle_end - datetime.timedelta(hours=1)
            range_text = f"{cycle_start:%Y-%m-%d %H:%M} ~ {display_end:%Y-%m-%d %H:%M}"

            lines = [title, _t("label.stats_range", range_text=range_text), ""]
            for idx, sr in enumerate(stats_rows, start=1):
                name = sr["display_name"]
                count = sr["total"]
                lines.append(_t("result.stats_row", rank=idx, name=name, count=count))
            lines.extend(["", _t("result.total_messages", total=total)])

            await lbot.send_message(group_id, "\n".join(lines))
        except Exception as e:
            logger.error(f"[Stats] 发送每日统计失败 group={group_id}: {e}")


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""
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

    middleware.register_command_handler(
        commands=["dragon"],
        callback=handle_dragon_command,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["group", "supergroup", "private"],
    )

    middleware.register_command_handler(
        commands=["stats_cutoff"],
        callback=handle_stats_cutoff_command,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["group", "supergroup", "private"],
    )

    # 注册分割时间选择回调
    middleware.register_callback_handler(
        callback=handle_stats_cutoff_callback,
        plugin_name=plugin_name,
        handler_name="stats_cutoff_select",
        priority=50,
        stop_propagation=True,
        data_startswith="stats_cutoff:",
        chat_types=["group", "supergroup"],
    )

    # 注册分割时间面板关闭回调
    middleware.register_callback_handler(
        callback=handle_stats_cutoff_close_callback,
        plugin_name=plugin_name,
        handler_name="stats_cutoff_close",
        priority=50,
        stop_propagation=True,
        data_startswith="stats_cutoff_close",
        chat_types=["group", "supergroup"],
    )

    logger.info(
        f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}"
    )

    # 龙王定时任务：每小时触发，按群组分割时间过滤
    middleware.register_cron_job(
        plugin_name=plugin_name,
        job_id="dragon_king",
        cron_expr="0 * * * *",
        timezone="Asia/Shanghai",
        callback=handle_dragon_king_schedule,
        display_name="job.dragon_king",
    )

    # 每日统计自动发送：每小时触发，按群组分割时间过滤
    middleware.register_cron_job(
        plugin_name=plugin_name,
        job_id="daily_stats",
        cron_expr="0 * * * *",
        timezone="Asia/Shanghai",
        callback=handle_daily_stats_schedule,
        display_name="job.daily_stats",
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
