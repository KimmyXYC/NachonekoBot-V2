# -*- coding: utf-8 -*-
# @Time    : 2025/11/24 17:06
# @Author  : KimmyXYC
# @File    : bcup.py
# @Software: PyCharm
import aiohttp
from loguru import logger
from telebot import types
from datetime import datetime
from zoneinfo import ZoneInfo


# ==================== 插件元数据 ====================
__plugin_name__ = "bcup"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "法币转换工具（银联汇率）"
__commands__ = ["bcup"]
__command_descriptions__ = {
    "bcup": "法币转换（银联汇率）"
}
__command_help__ = {
    "bcup": "/bcup [Amount] [Currency_From] [Currency_To] - 法币转换（银联汇率）"
}

# ==================== 核心功能 ====================
async def handle_bcup_command(bot, message: types.Message) -> None:
    command_args = message.text.split()
    if len(command_args) < 4:
        usage_text = (
            "使用方法: /bcup <数量> <币种1> <币种2>\n"
            "例如: /bcup 100 USD EUR - 将100美元转换为欧元"
        )
        await bot.reply_to(message, usage_text)
        return

    amount = int(command_args[1])
    currency_from = command_args[2].upper()
    currency_to = command_args[3].upper()
    logger.debug("处理法币转换命令: {} {} -> {}", amount, currency_from, currency_to)

    UnionPayAPI = f"https://m.unionpayintl.com/jfimg/{datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y%m%d')}.json"
    logger.debug("请求银联汇率 API: {}", UnionPayAPI)
    async with aiohttp.ClientSession() as session:
        async with session.get(UnionPayAPI) as response:
            if response.status != 200:
                await bot.reply_to(message, "获取银联汇率数据失败，请稍后重试。")
                return
            data = await response.json()
    exchange_rates = data.get("exchangeRateJson", [])
    rate = None
    for rate_data in exchange_rates:
        if rate_data["transCur"] == currency_from and rate_data["baseCur"] == currency_to:
            rate = rate_data["rateData"]
    if rate is None:
        await bot.reply_to(message, f"不支持的交易对: {currency_from} -> {currency_to}")
        return
    try:
        amount_value = float(amount)
    except ValueError:
        await bot.reply_to(message, "请输入有效的数量。")
        return
    up_converted_amount = amount_value * rate
    result_text = f"银联: {amount_value:.2f} {currency_from} ≈ {up_converted_amount:.2f} {currency_to}"
    logger.debug("银联汇率转换: {} {} -> {} {}, 汇率: {}", amount_value, currency_from, up_converted_amount, currency_to, rate)
    await bot.reply_to(message, result_text)


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot
    middleware.register_command_handler(
        commands=['bcup'],
        callback=handle_bcup_command,
        plugin_name=plugin_name,
        priority=50,  # 优先级
        stop_propagation=True,  # 阻止后续处理器
        chat_types=['private', 'group', 'supergroup']  # 过滤器
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
