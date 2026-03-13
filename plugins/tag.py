# -*- coding: utf-8 -*-
# @Time    : 2026/3/13 00:00
# @Author  : OpenCode
# @File    : tag.py
# @Software: PyCharm

import re

from loguru import logger
from telebot import types

from setting.telegrambot import BotSetting
from utils.i18n import _t

# ==================== 插件元数据 ====================
__plugin_name__ = "tag"
__version__ = "1.0.0"
__author__ = "OpenCode"
__description__ = "群组头衔设置与删除"
__commands__ = ["t", "td"]
__command_category__ = "group"
__command_order__ = {"t": 340, "td": 341}
__command_descriptions__ = {
    "t": "设置自己或被回复用户的头衔",
    "td": "删除自己的头衔",
}
__command_help__ = {
    "t": "/t [tag] - 设置自己或被回复用户的头衔",
    "td": "/td - 删除自己的头衔",
}
__toggleable__ = True
__display_name__ = "tag"

EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "\U00002600-\U000026ff"
    "\U00002700-\U000027bf"
    "\U0000fe0f"
    "\U0000200d"
    "]+",
    flags=re.UNICODE,
)


def _strip_emojis(text: str) -> str:
    return EMOJI_PATTERN.sub("", text or "").strip()


def _extract_command_argument(text: str) -> str:
    parts = (text or "").split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _build_default_tag(user: types.User) -> str:
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    tag = f"{first} {last}".strip()
    if tag:
        return tag
    username = (getattr(user, "username", "") or "").strip()
    return username or "Unknown"


def _display_name(user: types.User) -> str:
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    name = f"{first} {last}".strip()
    if name:
        return name
    username = (getattr(user, "username", "") or "").strip()
    return username or str(getattr(user, "id", "Unknown"))


async def _get_bot_id() -> int | None:
    raw_bot_id = BotSetting.bot_id
    if raw_bot_id is None:
        return None
    try:
        return int(raw_bot_id)
    except Exception:
        return None


async def _bot_can_manage_tags(bot, chat_id: int) -> bool:
    bot_id = await _get_bot_id()
    if bot_id is None:
        return False

    try:
        member = await bot.get_chat_member(chat_id, bot_id)
        status = getattr(member, "status", None)
        if status == "creator":
            return True
        if status != "administrator":
            return False
        return bool(getattr(member, "can_manage_tags", False))
    except Exception as e:
        logger.debug(f"检查机器人 tag 权限失败 chat={chat_id}: {e}")
        return False


async def _is_admin_or_owner(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return getattr(member, "status", None) in {"creator", "administrator"}
    except Exception as e:
        logger.debug(f"检查用户身份失败 chat={chat_id}, user={user_id}: {e}")
        return False


async def handle_set_tag_command(bot, message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    sender = getattr(message, "from_user", None)
    if not sender:
        await bot.reply_to(message, _t("error.sender_unrecognized"))
        return

    if not await _bot_can_manage_tags(bot, message.chat.id):
        await bot.reply_to(message, _t("error.bot_manage_tags_permission_required"))
        return

    reply = getattr(message, "reply_to_message", None)
    target_user = getattr(reply, "from_user", None) if reply else sender
    if not target_user:
        await bot.reply_to(message, _t("error.target_user_unavailable"))
        return

    target_id = target_user.id
    if await _is_admin_or_owner(bot, message.chat.id, target_id):
        await bot.reply_to(message, _t("error.cannot_change_admin_tag"))
        return

    raw_tag = _extract_command_argument(message.text or "")
    if raw_tag:
        tag = _strip_emojis(raw_tag)
    else:
        tag = _strip_emojis(_build_default_tag(sender))

    if not tag:
        tag = _build_default_tag(sender)

    try:
        ok = await bot.set_chat_member_tag(message.chat.id, target_id, tag)
    except Exception as e:
        logger.error(f"设置 tag 失败 chat={message.chat.id}, user={target_id}: {e}")
        ok = False

    if not ok:
        await bot.reply_to(message, _t("error.set_tag_failed"))
        return

    if target_id == sender.id:
        await bot.reply_to(message, _t("result.self_set", tag=tag))
        return

    await bot.reply_to(
        message,
        _t(
            "result.other_set",
            sender=_display_name(sender),
            target=_display_name(target_user),
            tag=tag,
        ),
    )


async def handle_delete_tag_command(bot, message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    sender = getattr(message, "from_user", None)
    if not sender:
        await bot.reply_to(message, _t("error.sender_unrecognized"))
        return

    if not await _bot_can_manage_tags(bot, message.chat.id):
        await bot.reply_to(message, _t("error.bot_manage_tags_permission_required"))
        return

    if await _is_admin_or_owner(bot, message.chat.id, sender.id):
        await bot.reply_to(message, _t("error.cannot_delete_admin_tag"))
        return

    try:
        ok = await bot.set_chat_member_tag(message.chat.id, sender.id, None)
    except Exception as e:
        logger.error(f"删除 tag 失败 chat={message.chat.id}, user={sender.id}: {e}")
        ok = False

    if not ok:
        await bot.reply_to(message, _t("error.delete_tag_failed"))
        return

    await bot.reply_to(message, _t("result.self_deleted"))


async def register_handlers(bot, middleware, plugin_name):
    global bot_instance
    bot_instance = bot

    async def tag_handler(bot, message: types.Message):
        await handle_set_tag_command(bot, message)

    async def tag_delete_handler(bot, message: types.Message):
        await handle_delete_tag_command(bot, message)

    middleware.register_command_handler(
        commands=["t"],
        callback=tag_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["group", "supergroup"],
    )

    middleware.register_command_handler(
        commands=["td"],
        callback=tag_delete_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["group", "supergroup"],
    )

    logger.info("✅ tag 插件已注册 - 支持命令: t, td")


def get_plugin_info() -> dict:
    return {
        "name": __plugin_name__,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": __commands__,
    }


bot_instance = None
