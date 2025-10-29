# -*- coding: utf-8 -*-
# @Time    : 2025/5/2 12:11
# @Author  : KimmyXYC
# @File    : lock.py
# @Software: PyCharm
from telebot import types

from utils.elaradb import BotElara
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
    if not ((chat_member.status == 'administrator' and chat_member.can_delete_messages)
            or chat_member.status == 'creator'):
        await bot.reply_to(message, "您无权使用此功能")
        return False
    return True


def batch_add_to_locklist(chat_id, cmd):
    """
    批量添加命令到锁定列表
    :param chat_id: 群组ID
    :param cmd: 命令列表
    :return: 添加结果
    """
    locklist = BotElara.get(str(chat_id), [])
    added = []
    already_exist = []
    for command in cmd:
        if command not in locklist:
            locklist.append(command)
            added.append(command)
        else:
            already_exist.append(command)
    BotElara.set(str(chat_id), locklist)
    return {'added': added, 'already_exist': already_exist}

def batch_remove_from_locklist(chat_id, cmd):
    """
    批量从锁定列表中删除命令
    :param chat_id: 群组ID
    :param cmd: 命令列表
    :return: 删除结果
    """
    locklist = BotElara.get(str(chat_id), [])
    removed = []
    not_found = []
    for command in cmd:
        if command in locklist:
            locklist.remove(command)
            removed.append(command)
        else:
            not_found.append(command)
    BotElara.set(str(chat_id), locklist)
    return {'removed': removed, 'not_found': not_found}


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
    await bot.reply_to(message, f"批量添加结果: 添加成功 `{result['added']}`，已存在 `{result['already_exist']}`", parse_mode='Markdown')

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
    await bot.reply_to(message, f"批量删除结果: 删除成功 `{result['removed']}`，不存在 `{result['not_found']}`", parse_mode='Markdown')

async def handle_list_command(bot, message: types.Message):
    """
    列出锁定的命令
    :param bot: Bot对象
    :param message: 消息对象
    :return:
    """
    result = await BotElara.get(str(message.chat.id))
    if not result:
        await bot.reply_to(message, "本群未锁定任何命令")
    else:
        msg = "以下命令在本群中被锁定:\n"
        msg += "\n".join(f"- `{item}`" for item in result)
        await bot.reply_to(message, msg, parse_mode='Markdown')
