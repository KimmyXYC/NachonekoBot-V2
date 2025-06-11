# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 12:58
# @Author  : KimmyXYC
# @File    : callanyone.py
# @Software: PyCharm

import random


async def handle_call_command(bot, message):
    """
    处理 /callanyone 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    anyone_msg = ""
    if "/calldoctor" in message.text:
        anyone_list = ["👨‍⚕️", "👩‍⚕️", "🚑", "🏥", "💊"]
    elif "/callmtf" in message.text:
        anyone_list = ["🏳️‍⚧️", "🍥"]
    elif "/callpolice" in message.text:
        anyone_list = ["🚨", "👮", "🚔", "🚓"]
    else:
        anyone_list = ["🔧"]
    max_repeats = 5
    consecutive_count = 0
    count = 0
    while count <= random.randint(20, 80):
        emoji = random.choice(anyone_list)
        if emoji == anyone_msg[-1:]:
            consecutive_count += 1
            if consecutive_count > max_repeats:
                continue
        else:
            consecutive_count = 1
        anyone_msg += emoji
        count += 1
    await bot.reply_to(message, anyone_msg)
