# -*- coding: utf-8 -*-
# @Time    : 2025/5/2 12:11
# @Author  : KimmyXYC
# @File    : lock.py
# @Software: PyCharm
from venv import logger

from telebot import types

from utils.postgres import BotDatabase
from setting.telegrambot import BotSetting

async def check_permissions(bot, message: types.Message):
    """
    检查权限
    :param bot: Bot对象
    :param message: 消息对象
    :return:
    """
    bot_member = await bot.get_chat_member(message.chat.id, BotSetting.bot_id)
    if not (bot_member.status == 'administrator' and bot_member.can_delete_messages):
        await bot.reply_to(message, "请先将机器人设置为管理员并赋予删除消息权限")
        return False
    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if not ((chat_member.status == 'administrator' and chat_member.can_delete_messages) \
            or chat_member.status == 'creator'):
        await bot.reply_to(message, "您无权使用此功能")
        return False
    return True


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

    await BotDatabase.connect()
    result = await BotDatabase.batch_add_to_locklist(message.chat.id, cmd)
    await bot.reply_to(message, f"批量添加结果: 添加成功 `{result['added']}`，已存在 `{result['already_exist']}`", parse_mode='Markdown')
    await BotDatabase.close()

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

    await BotDatabase.connect()
    result = await BotDatabase.batch_remove_from_locklist(message.chat.id, cmd)
    await bot.reply_to(message, f"批量删除结果: 删除成功 `{result['removed']}`，不存在 `{result['not_found']}`", parse_mode='Markdown')
    await BotDatabase.close()

async def handle_list_command(bot, message: types.Message):
    """
    列出锁定的命令
    :param bot: Bot对象
    :param message: 消息对象
    :return:
    """
    await BotDatabase.connect()
    result = await BotDatabase.read_locklist(message.chat.id)
    if not result:
        await bot.reply_to(message, "本群未锁定任何命令")
    else:
        msg = "以下命令在本群中被锁定:\n"
        msg += "\n".join(f"- `{item}`" for item in result)
        await bot.reply_to(message, msg, parse_mode='Markdown')
    await BotDatabase.close()
