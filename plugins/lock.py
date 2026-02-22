# -*- coding: utf-8 -*-
# @Time    : 2025/5/2 12:11
# @Author  : KimmyXYC
# @File    : lock.py
# @Software: PyCharm
import asyncio

from telebot import types
from loguru import logger
from app.utils import command_error_msg
from app.security.permissions import has_group_admin_permission

from utils.elaradb import BotElara
from setting.telegrambot import BotSetting

# ==================== 插件元数据 ====================
__plugin_name__ = "lock"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "群组命令锁定管理"
__commands__ = ["lock", "unlock", "list"]
__command_descriptions__ = {
    "lock": "锁定群组中的命令",
    "unlock": "解锁群组中的命令",
    "list": "列出群组中被锁定的命令",
}
__command_help__ = {
    "lock": "/lock [Command] - 锁定群组中的命令",
    "unlock": "/unlock [Command] - 解锁群组中的命令",
    "list": "/list - 列出群组中被锁定的命令",
}

NON_LOCKABLE_COMMANDS = {"plugin_settings", "lock", "unlock", "list"}


# ==================== 核心功能 ====================
async def check_permissions(bot, message: types.Message):
    """
    检查权限
    :param bot: Bot对象
    :param message: 消息对象
    :return:
    """
    from_user = message.from_user
    if not from_user:
        await bot.reply_to(message, "无法识别消息发送者")
        return False

    raw_bot_id = BotSetting.bot_id
    if raw_bot_id is None:
        await bot.reply_to(message, "机器人配置错误：bot_id 无效")
        return False

    try:
        bot_id = int(raw_bot_id)
    except Exception:
        await bot.reply_to(message, "机器人配置错误：bot_id 无效")
        return False

    bot_can_delete = await has_group_admin_permission(
        bot,
        message.chat.id,
        bot_id,
        required_permission="can_delete_messages",
        default_when_missing=False,
        allow_bot_admin=False,
    )
    if not bot_can_delete:
        await bot.reply_to(message, "请先将机器人设置为管理员并赋予删除消息权限")
        return False

    user_can_delete = await has_group_admin_permission(
        bot,
        message.chat.id,
        from_user.id,
        required_permission="can_delete_messages",
        default_when_missing=False,
        allow_bot_admin=True,
    )
    if not user_can_delete:
        await bot.reply_to(message, "您无权使用此功能")
        return False
    return True


def _normalize_command_name(command: str) -> str:
    if not command:
        return ""
    normalized = command.strip()
    if not normalized:
        return ""
    if normalized[0] in ("/", "\\"):
        normalized = normalized[1:]
    if "@" in normalized:
        normalized = normalized.split("@", 1)[0]
    return normalized.lower()


def _get_sanitized_locklist(chat_id, persist: bool = True):
    locklist = BotElara.get(str(chat_id), []) or []
    sanitized = []
    for command in locklist:
        normalized = _normalize_command_name(str(command))
        if (
            not normalized
            or normalized in NON_LOCKABLE_COMMANDS
            or normalized in sanitized
        ):
            continue
        sanitized.append(normalized)

    if persist and sanitized != locklist:
        BotElara.set(str(chat_id), sanitized)
    return sanitized


def batch_add_to_locklist(chat_id, cmd):
    """
    批量添加命令到锁定列表
    :param chat_id: 群组ID
    :param cmd: 命令列表
    :return: 添加结果
    """
    locklist = _get_sanitized_locklist(chat_id)
    added = []
    already_exist = []
    not_lockable = []
    for command in cmd:
        normalized = _normalize_command_name(command)
        if not normalized:
            continue
        if normalized in NON_LOCKABLE_COMMANDS:
            not_lockable.append(normalized)
            continue
        if normalized not in locklist:
            locklist.append(normalized)
            added.append(normalized)
        else:
            already_exist.append(normalized)
    BotElara.set(str(chat_id), locklist)
    return {
        "added": added,
        "already_exist": already_exist,
        "not_lockable": not_lockable,
    }


def batch_remove_from_locklist(chat_id, cmd):
    """
    批量从锁定列表中删除命令
    :param chat_id: 群组ID
    :param cmd: 命令列表
    :return: 删除结果
    """
    locklist = _get_sanitized_locklist(chat_id)
    removed = []
    not_found = []
    for command in cmd:
        normalized = _normalize_command_name(command)
        if not normalized:
            continue
        if normalized in locklist:
            locklist.remove(normalized)
            removed.append(normalized)
        else:
            not_found.append(normalized)
    BotElara.set(str(chat_id), locklist)
    return {"removed": removed, "not_found": not_found}


async def handle_lock_command(bot, message: types.Message, cmd: list):
    """
    锁定命令
    :param bot: Bot对象
    :param message: 消息对象
    :param cmd: 命令列表
    :return:
    """
    if not await check_permissions(bot, message):
        return

    result = batch_add_to_locklist(message.chat.id, cmd)
    await bot.reply_to(
        message,
        "批量添加结果: "
        f"添加成功 `{result['added']}`，已存在 `{result['already_exist']}`，"
        f"不可锁定 `{result['not_lockable']}`",
        parse_mode="Markdown",
    )


async def handle_unlock_command(bot, message: types.Message, cmd: list):
    """
    解锁命令
    :param bot: Bot对象
    :param message: 消息对象
    :param cmd: 命令列表
    :return:
    """
    if not await check_permissions(bot, message):
        return

    result = batch_remove_from_locklist(message.chat.id, cmd)
    await bot.reply_to(
        message,
        f"批量删除结果: 删除成功 `{result['removed']}`，不存在 `{result['not_found']}`",
        parse_mode="Markdown",
    )


async def handle_list_command(bot, message: types.Message):
    """
    列出锁定的命令
    :param bot: Bot对象
    :param message: 消息对象
    :return:
    """
    result = _get_sanitized_locklist(message.chat.id)
    if not result:
        await bot.reply_to(message, "本群未锁定任何命令")
    else:
        msg = "以下命令在本群中被锁定:\n"
        msg += "\n".join(f"- `{item}`" for item in result)
        await bot.reply_to(message, msg, parse_mode="Markdown")


def _extract_command_name(text: str) -> str:
    if not text or not text.startswith("/"):
        return ""
    raw_command = text.split()[0][1:]
    if not raw_command:
        return ""
    if "@" in raw_command:
        raw_command = raw_command.split("@", 1)[0]
    return _normalize_command_name(raw_command)


async def _safe_delete_message_later(
    bot, chat_id: int, message_id: int, delay_seconds: float = 0.5
):
    try:
        await asyncio.sleep(delay_seconds)
        await bot.delete_message(chat_id, message_id)
    except Exception as e:  # noqa: B902
        logger.debug(f"删除消息失败 chat_id={chat_id}, message_id={message_id}: {e}")


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def lock_handler(bot, message: types.Message):
        command_args = (message.text or "").split()
        if len(command_args) == 1:
            await bot.reply_to(message, command_error_msg("lock", "Command"))
        else:
            lock_list = command_args[1:]
            await handle_lock_command(bot, message, lock_list)

    async def unlock_handler(bot, message: types.Message):
        command_args = (message.text or "").split()
        if len(command_args) == 1:
            await bot.reply_to(message, command_error_msg("unlock", "Command"))
        else:
            unlock_list = command_args[1:]
            await handle_unlock_command(bot, message, unlock_list)

    async def list_handler(bot, message: types.Message):
        await handle_list_command(bot, message)

    async def lock_guard_handler(bot, message: types.Message):
        command_name = _extract_command_name(message.text or "")
        if not command_name:
            return True

        if command_name in NON_LOCKABLE_COMMANDS:
            return True

        lock_list = _get_sanitized_locklist(message.chat.id)
        if command_name not in lock_list:
            return True

        asyncio.create_task(
            _safe_delete_message_later(bot, message.chat.id, message.message_id, 0.5)
        )
        return False

    middleware.register_command_handler(
        commands=["lock"],
        callback=lock_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["group", "supergroup"],
    )

    middleware.register_command_handler(
        commands=["unlock"],
        callback=unlock_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["group", "supergroup"],
    )

    middleware.register_command_handler(
        commands=["list"],
        callback=list_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["group", "supergroup"],
    )

    middleware.register_command_handler(
        commands=["*"],
        callback=lock_guard_handler,
        plugin_name=plugin_name,
        priority=100,
        stop_propagation=False,
        chat_types=["group", "supergroup"],
    )

    logger.info(
        f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}"
    )


# ==================== 插件信息 ====================
def get_plugin_info() -> dict:
    """
    获取插件信息
    """
    return {
        "name": __plugin_name__,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": __commands__,
    }


# 保持全局 bot 引用
bot_instance = None
