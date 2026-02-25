# -*- coding: utf-8 -*-
# @Time    : 2025/11/16 15:40
# @Author  : Junie (autonomous programmer by JetBrains)
# @File    : quote.py
# @Software: PyCharm
"""
- 监听形如 "/$动作 [附加语句]" 或 "\\$动作 [附加语句]" 的消息（不是标准 /command）
- 当消息回复了他人时，以被回复的人作为对象；否则支持“动作@username”语法解析用户名
- MarkdownV2 转义与 t.me 用户名解析（爬 og:title）
- 群话题消息会自动跟随原消息线程（使用 reply_to）
输出格式：
- 无附加语句:  "[发送者](uri) 动作了 [对象](uri)！"
- 有附加语句:  "[发送者](uri) 动作 [对象](uri) 附加语句！"
"""

import re
import aiohttp
from typing import Optional, Tuple
from telebot import types
from loguru import logger

from app.utils import escape_md_v2_text

# ==================== 插件元数据 ====================
__plugin_name__ = "quote_reply"
__display_name__ = "Quote Reply"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "/$ 与 \\$ 开头的动作引用插件"
__commands__ = ["$"]  # 仅用于展示，实际通过 message handler 拦截
__command_category__ = "misc"
__command_order__ = {"$": 900}
__toggleable__ = True  # 支持在群组中开关


# ==================== 工具函数 ====================
def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except Exception:
        return False


def _build_tg_user_link(user_id: int) -> str:
    return f"tg://user?id={user_id}"


def _build_tme_link(username: str) -> str:
    return f"https://t.me/{username}"


async def _get_name_by_username(username: str) -> str:
    """
    访问 https://t.me/{username} 抓取 og:title，如果 <title> 与 og:title 一致，视为不存在。
    返回显示名称；失败返回空串。
    """
    url = _build_tme_link(username)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=8) as resp:
                if resp.status != 200:
                    return ""
                html = await resp.text()
    except Exception:
        return ""

    # og:title
    m = re.search(
        r'<meta\s+property="og:title"\s+content="([^"]*)"', html, re.IGNORECASE
    )
    name = m.group(1) if m else ""

    # <title>...</title>
    m1 = re.search(r"<title>", html, re.IGNORECASE)
    m2 = re.search(r"</title>", html, re.IGNORECASE)
    page_title = (
        html[m1.end() : m2.start()] if (m1 and m2 and m1.end() <= m2.start()) else ""
    )

    if name and page_title and name == page_title:
        # 用户不存在
        return ""
    return name


def _escape_name(text: str) -> str:
    return escape_md_v2_text(text or "")


def _sender_identity(message: types.Message) -> Tuple[str, str]:
    """返回 (显示名, URI) 对。优先使用 SenderChat。"""
    if message.sender_chat:
        title = _escape_name(message.sender_chat.title)
        uri = (
            _build_tme_link(message.sender_chat.username)
            if getattr(message.sender_chat, "username", None)
            else ""
        )
        return title, uri
    # 普通用户
    first = getattr(message.from_user, "first_name", "") or ""
    last = getattr(message.from_user, "last_name", "") or ""
    name = _escape_name((first + " " + last).strip() or first or last or "")
    uri = _build_tg_user_link(message.from_user.id)
    return name, uri


def _replyto_identity(message: types.Message) -> Optional[Tuple[str, str]]:
    """如果存在 ReplyToMessage，返回其身份 (显示名, URI)，否则 None。
    兼容：当在话题里，且引用的是话题根消息（id 等于 thread id）时，视为无引用。
    """
    reply = message.reply_to_message
    if not reply:
        return None

    if getattr(message, "is_topic_message", False):
        # 如果回复的是话题根消息，清空 ReplyToMessage
        if reply.message_id == getattr(message, "message_thread_id", None):
            return None

    # 优先考虑 SenderChat（频道/匿名管理员）
    if reply.sender_chat:
        title = _escape_name(reply.sender_chat.title)
        uri = (
            _build_tme_link(reply.sender_chat.username)
            if getattr(reply.sender_chat, "username", None)
            else ""
        )
        return title, uri

    # 一般用户
    # 当被回复的是 Bot 且含 text_mention 实体时，使用实体里的用户
    if getattr(reply, "from_user", None):
        # text_mention 解析
        try:
            entities = getattr(reply, "entities", []) or []
            if getattr(reply.from_user, "is_bot", False) and len(entities) != 0:
                ent = entities[0]
                if getattr(ent, "type", "") == "text_mention" and getattr(
                    ent, "user", None
                ):
                    u = ent.user
                    first = getattr(u, "first_name", "") or ""
                    last = getattr(u, "last_name", "") or ""
                    name = _escape_name(
                        (first + " " + last).strip() or first or last or ""
                    )
                    uri = _build_tg_user_link(u.id)
                    return name, uri
        except Exception:
            pass

        first = getattr(reply.from_user, "first_name", "") or ""
        last = getattr(reply.from_user, "last_name", "") or ""
        name = _escape_name((first + " " + last).strip() or first or last or "")
        uri = _build_tg_user_link(reply.from_user.id)
        return name, uri

    return None


async def _find_target_from_text(
    command_word: str,
) -> Tuple[Optional[str], Optional[str], str]:
    """
    从“动作@username”语法解析对象。如果存在 @username，返回 (显示名, 链接, 动作词去除@部分)。
    若解析失败，返回 (None, None, 原动作词)。
    """
    # 仅切第一处 @
    parts = command_word.split("@", 1)
    if len(parts) == 2 and parts[1]:
        username = parts[1]
        name = await _get_name_by_username(username)
        if name:
            return _escape_name(name), _build_tme_link(username), parts[0]
    return None, None, command_word


def _parse_keywords(text: str) -> list:
    """
    先删除第一个 '$'，再去掉首字符（/ 或 \\），再进行 MarkdownV2 转义，最后按空格 SplitN 2。
    """
    # 删除第一个 '$'
    cleaned = text.replace("$", "", 1)
    # 去掉开头的 / 或 \\
    if cleaned and cleaned[0] in ("/", "\\"):
        cleaned = cleaned[1:]
    # 转义后 split
    cleaned = escape_md_v2_text(cleaned)
    parts = cleaned.split(" ", 2)
    if len(parts) > 2:
        return [parts[0], " ".join(parts[1:])]
    return parts


def _is_trigger(text: str) -> bool:
    """匹配 '/$' 或 '\\$' 开头的消息。"""
    if not text or len(text) < 2:
        return False
    if text.startswith("/"):
        return (not _is_ascii(text[:2])) or text.startswith("/$")
    if text.startswith("\\"):
        return (not _is_ascii(text[:2])) or text.startswith("\\$")
    return False


# ==================== 业务核心 ====================
async def _build_reply_text(message: types.Message) -> str:
    text = message.text or ""
    if not _is_trigger(text):
        return ""

    keywords = _parse_keywords(text)
    if not keywords:
        return ""

    # 发送者身份
    sender_name, sender_uri = _sender_identity(message)

    # 目标身份
    reply_to = _replyto_identity(message)
    reply_name, reply_uri = "", ""

    # 话题中，如果 ReplyTo 是根消息，已在 _replyto_identity 中返回 None
    if reply_to:
        reply_name, reply_uri = reply_to

    # 反斜杠前缀时交换主客体
    backslash = text.startswith("\\")

    if reply_to is None:
        # 无引用时，尝试从动作词中解析 @username
        cmd_word = (keywords[0] or "").lstrip("/")  # 已处理
        found_name, found_link, pure_cmd = await _find_target_from_text(cmd_word)
        if found_name:
            reply_name, reply_uri = found_name, found_link
            # 替换动作词
            keywords[0] = pure_cmd
        else:
            # 默认“自己”
            reply_name = _escape_name("自己")
            reply_uri = sender_uri

    if backslash and reply_name:
        # 交换
        sender_name, reply_name = reply_name, sender_name
        sender_uri, reply_uri = reply_uri, sender_uri

    # 组织输出
    verb = (keywords[0] or "").strip()
    if not verb:
        return ""

    if len(keywords) < 2 or not keywords[1].strip():
        return f"[{sender_name}]({sender_uri}) {verb}了 [{reply_name}]({reply_uri})！"
    else:
        extra = keywords[1].strip()
        return f"[{sender_name}]({sender_uri}) {verb} [{reply_name}]({reply_uri}) {extra}！"


# ==================== Handler 注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册消息监听器：拦截 '/$' 与 '\\$' 前缀的消息。"""

    async def quote_handler(bot, message: types.Message):
        try:
            reply_text = await _build_reply_text(message)
            if not reply_text:
                return
            # 使用 reply_to 保持在线程内（如为话题消息）
            await bot.reply_to(
                message,
                reply_text,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"quote 插件处理失败: {e}")

    # 使用 message handler（不是标准 /command）
    middleware.register_message_handler(
        callback=quote_handler,
        plugin_name=plugin_name,
        handler_name="quote_handler",
        priority=30,
        stop_propagation=False,
        chat_types=["group", "supergroup"],
    )

    logger.info(f"✅ {__plugin_name__} 插件已注册 - 监听 '/$' 与 '\\$' 消息")


# ==================== 插件信息 ====================
def get_plugin_info() -> dict:
    return {
        "name": __plugin_name__,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": __commands__,
    }
