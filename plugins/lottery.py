# -*- coding: utf-8 -*-
# @Time    : 2025/8/24 14:27
# @Author  : KimmyXYC
# @File    : lottery.py
# @Software: PyCharm

import asyncio
import secrets
from typing import Dict, Set

from loguru import logger
from telebot import types

# ==================== 插件元数据 ====================
__plugin_name__ = "lottery"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "抽奖系统"
__commands__ = ["lottery"]
__command_descriptions__ = {
    "lottery": "抽奖"
}
__command_help__ = {
    "lottery": "/lottery [Winners]/[Participants] [Keyword] [Title] - 抽奖"
}


# ==================== 核心功能 ====================
# 逐群维护抽奖状态，避免不同群互相影响
# chat_id -> state
_lotteries: Dict[int, dict] = {}
# chat_id -> asyncio.Lock
_locks: Dict[int, asyncio.Lock] = {}



create_text = (
    "抽奖活动 <b>{}</b> 已经创建\n"
    "奖品数量：<b>{}</b>\n"
    "参与人数达到 <b>{}</b> 人，即可开奖\n\n"
    "发送 <code>{}</code> 即可参与抽奖"
)

join_text = (
    "感谢参与 <b>{}</b> 抽奖活动\n"
    "奖品数量：<b>{}</b>\n"
    "参与人数达到 <b>{}</b> 人，即可开奖\n"
    "当前参与人数：<b>{}</b> 人"
)

end_text = (
    "<b>{}</b> 已开奖，中奖用户：\n\n" "{}\n\n" "请私聊发起者领奖，感谢其他用户的参与。"
)

end_empty_text = "<b>{}</b> 已开奖，没有中奖用户"


def _get_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _locks:
        _locks[chat_id] = asyncio.Lock()
    return _locks[chat_id]


async def _delete_message_later(bot, chat_id: int, message_id: int, seconds: int = 15):
    try:
        await asyncio.sleep(seconds)
        await bot.delete_message(chat_id, message_id)
    except Exception as e:  # noqa: B902
        logger.debug(f"Failed to delete message {message_id} in {chat_id}: {e}")


async def _is_admin(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return getattr(member, "status", None) in ("creator", "administrator")
    except Exception as e:
        logger.debug(f"get_chat_member failed: {e}")
        return False


async def _lottery_end(bot, chat_id: int):
    state = _lotteries.get(chat_id)
    if not state:
        return

    state["start"] = False
    participants: Set[int] = state.get("participants", set())
    all_user = list(participants)

    secret_generator = secrets.SystemRandom()
    win_user = []
    win_user_num = min(state["win"], len(all_user))

    if all_user and win_user_num > 0:
        # 抽取不重复的中奖者
        while len(win_user) < win_user_num:
            temp = secret_generator.choice(all_user)
            if temp not in win_user:
                win_user.append(temp)

    if win_user:
        winners_text = "\n".join(
            f'<a href="tg://user?id={uid}">@{uid}</a>' for uid in win_user
        )
        win_text = end_text.format(state["title"], winners_text)
    else:
        win_text = end_empty_text.format(state["title"])

    # 在发送开奖结果之前，先尝试取消之前的置顶
    try:
        pin_mid = state.get("pin_message_id")
        if pin_mid:
            try:
                await bot.unpin_chat_message(chat_id, pin_mid)
            except Exception as e:
                logger.debug(f"Unpin lottery create message failed: {e}")
    except Exception:
        pass

    # 发送开奖结果并尝试置顶（无提醒）
    try:
        result_msg = await bot.send_message(chat_id, win_text, parse_mode="HTML")
        try:
            await bot.pin_chat_message(chat_id, result_msg.message_id, disable_notification=True)
        except Exception as e:
            logger.debug(f"Pin lottery result message failed: {e}")
    except Exception as e:
        logger.debug(f"Send lottery end message failed: {e}")

    # 清理状态
    _lotteries.pop(chat_id, None)


async def _create_lottery(bot, chat_id: int, num: int, win: int, title: str, keyword: str):
    if chat_id in _lotteries and _lotteries[chat_id].get("start"):
        raise FileExistsError

    _lotteries[chat_id] = {
        "start": True,
        "chat_id": chat_id,
        "num": num,
        "win": win,
        "title": title,
        "keyword": keyword,
        "participants": set(),
    }

    try:
        msg = await bot.send_message(chat_id, create_text.format(title, win, num, keyword), parse_mode="HTML")
        # 记录创建消息的 message_id，便于开奖后取消置顶
        _lotteries[chat_id]["pin_message_id"] = msg.message_id
        # 自动置顶抽奖创建消息（无提醒置顶）
        try:
            await bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
        except Exception as e:
            logger.debug(f"Pin lottery create message failed: {e}")
    except Exception as e:
        logger.debug(f"Send lottery create message failed: {e}")


def should_pass_lottery_filter(message: types.Message) -> bool:
    """精确判断消息是否应进入抽奖处理：
    - 来自群组/超级群组
    - 本群存在正在进行的抽奖
    - 文本与抽奖关键词完全匹配
    - 发送者不是机器人
    """
    try:
        if message is None:
            return False
        chat = getattr(message, "chat", None)
        if not chat or getattr(chat, "type", None) not in ["group", "supergroup"]:
            return False
        text = getattr(message, "text", None)
        if not isinstance(text, str):
            return False
        from_user = getattr(message, "from_user", None)
        if not from_user or getattr(from_user, "is_bot", False):
            return False
        state = _lotteries.get(chat.id)
        if not state or not state.get("start"):
            return False
        return text == state.get("keyword")
    except Exception:
        return False


async def process_lottery_message(bot, message: types.Message):
    """在群聊中监听文本消息，处理抽奖参与逻辑。"""
    if message is None or not getattr(message, "text", None):
        return
    if getattr(message, "chat", None) is None:
        return
    if message.chat.type not in ["group", "supergroup"]:
        return
    if not getattr(message, "from_user", None):
        return
    if getattr(message.from_user, "is_bot", False):
        return

    chat_id = message.chat.id
    state = _lotteries.get(chat_id)
    if not state or not state.get("start"):
        return

    # 必须是完全匹配关键词
    if message.text != state["keyword"]:
        return

    lock = _get_lock(chat_id)
    async with lock:
        # 可能状态已在加锁前被改变
        state = _lotteries.get(chat_id)
        if not state or not state.get("start"):
            return

        participants: Set[int] = state.get("participants", set())
        uid = message.from_user.id
        if uid in participants:
            return

        participants.add(uid)
        state["participants"] = participants
        all_join = len(participants)

        # 如果超过目标人数，立即开奖
        if all_join > state["num"]:
            state["start"] = False
            await _lottery_end(bot, chat_id)
            return

        try:
            reply_msg = await bot.reply_to(
                message,
                join_text.format(state["title"], state["win"], state["num"], all_join),
                parse_mode="HTML",
            )
            # 15 秒后删除提示
            asyncio.create_task(_delete_message_later(bot, chat_id, reply_msg.message_id, 15))
        except Exception as e:
            logger.debug(f"Reply join message failed: {e}")

        if all_join >= state["num"]:
            state["start"] = False
            await _lottery_end(bot, chat_id)


async def handle_lottery_command(bot, message: types.Message):
    """处理 /lottery 命令：创建抽奖或强制开奖。"""
    if message.chat.type not in ["group", "supergroup"]:
        await bot.reply_to(message, "请在群组中使用该命令。")
        return

    # 仅群管理员可用
    if not await _is_admin(bot, message.chat.id, message.from_user.id):
        await bot.reply_to(message, "只有群管理员可以使用此命令。")
        return

    parts = message.text.split()
    if len(parts) == 1:
        await bot.reply_to(message, "请输入 奖品数、人数等参数 或者 强制开奖\n\n例如 `/lottery 1/10 参加 测试`", parse_mode="Markdown")
        return

    # 强制开奖
    if len(parts) == 2 and parts[1] == "强制开奖":
        # 仅结束当前群的抽奖
        if message.chat.id in _lotteries and _lotteries[message.chat.id].get("start"):
            await bot.reply_to(message, "强制开奖成功。")
            await _lottery_end(bot, message.chat.id)
        else:
            await bot.reply_to(message, "本群暂无正在进行的抽奖活动。")
        return

    if len(parts) < 4:
        await bot.reply_to(message, "奖品数、人数、关键字和标题不能为空")
        return

    num_list = parts[1].split("/")
    if len(num_list) != 2:
        await bot.reply_to(message, "奖品数、人数不能为空")
        return

    try:
        num = int(num_list[1])
        win = int(num_list[0])
        if win > num:
            await bot.reply_to(message, "奖品数不能超过人数")
            return
    except ValueError:
        await bot.reply_to(message, "人数必须是整数")
        return

    keyword = parts[2]
    title = parts[3]

    if not (keyword and title):
        await bot.reply_to(message, "奖品数、人数、关键字和标题不能为空")
        return

    try:
        await _create_lottery(bot, message.chat.id, num, win, title, keyword)
        # 尝试删除命令消息，需机器人具备删除权限
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
    except FileExistsError:
        await bot.reply_to(message, "有抽奖活动正在进行，请稍后再试")
        return


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    # 命令处理器 - 使用中间件
    async def lottery_handler(bot, message: types.Message):
        await handle_lottery_command(bot, message)

    middleware.register_command_handler(
        commands=['lottery'],
        callback=lottery_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=['group', 'supergroup']
    )

    # 抽奖参与处理器 - 使用中间件
    async def lottery_join_handler(bot, message: types.Message):
        await process_lottery_message(bot, message)

    middleware.register_message_handler(
        callback=lottery_join_handler,
        plugin_name=plugin_name,
        handler_name="lottery_join",
        priority=50,
        stop_propagation=False,
        content_types=['text'],
        chat_types=['group', 'supergroup'],
        func=should_pass_lottery_filter
    )

    logger.info(f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}")

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
