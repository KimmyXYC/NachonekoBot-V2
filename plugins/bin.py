# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 21:59
# @Author  : KimmyXYC
# @File    : bin.py
# @Software: PyCharm
import json
import aiohttp
from json.decoder import JSONDecodeError
from telebot import types
from loguru import logger

# ==================== 插件元数据 ====================
__plugin_name__ = "bin"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "BIN 号码查询"
__commands__ = ["bin"]


# ==================== 核心功能 ====================
async def handle_bin_command(bot, message: types.Message):
    """
    处理 BIN 查询命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    command_args = message.text.split()
    if len(command_args) != 2:
        await bot.reply_to(message, "请提供有效的BIN号码（4到8位数字）")
        return

    card_bin = command_args[1]
    if not card_bin.isdigit() or not (4 <= len(card_bin) <= 8):
        await bot.reply_to(message, "出错了呜呜呜 ~ 无效的参数。请提供4到8位数字的BIN号码。")
        return

    msg = await bot.reply_to(message, f"正在查询BIN: {card_bin} ...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://lookup.binlist.net/{card_bin}") as r:
                if r.status == 404:
                    await bot.edit_message_text("出错了呜呜呜 ~ 目标卡头不存在", message.chat.id, msg.message_id)
                    return
                if r.status == 429:
                    await bot.edit_message_text("出错了呜呜呜 ~ 每分钟限额超过，请等待一分钟再试", message.chat.id, msg.message_id)
                    return
                if r.status != 200:
                    await bot.edit_message_text(f"出错了呜呜呜 ~ 请求失败，状态码: {r.status}", message.chat.id, msg.message_id)
                    return

                content = await r.text()
                bin_json = json.loads(content)
    except aiohttp.ClientError:
        await bot.edit_message_text("出错了呜呜呜 ~ 无法访问到binlist。", message.chat.id, msg.message_id)
        return
    except JSONDecodeError:
        await bot.edit_message_text("出错了呜呜呜 ~ 无效的参数。", message.chat.id, msg.message_id)
        return
    except Exception as e:
        await bot.edit_message_text(f"出错了呜呜呜 ~ 发生错误: {str(e)}", message.chat.id, msg.message_id)
        return

    msg_out = []
    msg_out.extend([f"BIN：{card_bin}"])
    try:
        msg_out.extend([f"卡品牌：{bin_json['scheme']}"])
    except (KeyError, TypeError):
        pass
    try:
        msg_out.extend([f"卡类型：{bin_json['type']}"])
    except (KeyError, TypeError):
        pass
    try:
        msg_out.extend([f"卡种类：{bin_json['brand']}"])
    except (KeyError, TypeError):
        pass
    try:
        msg_out.extend([f"发卡行：{bin_json['bank']['name']}"])
    except (KeyError, TypeError):
        pass
    try:
        if bin_json['prepaid']:
            msg_out.extend(["是否预付：是"])
        else:
            msg_out.extend(["是否预付：否"])
    except (KeyError, TypeError):
        pass
    try:
        msg_out.extend([f"发卡国家：{bin_json['country']['name']}"])
    except (KeyError, TypeError):
        pass

    await bot.edit_message_text("\n".join(msg_out), message.chat.id, msg.message_id)


# ==================== 插件注册 ====================
async def register_handlers(bot):
    """注册插件处理器"""

    @bot.message_handler(commands=['bin'])
    async def bin_command(message: types.Message):
        await handle_bin_command(bot, message)

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
