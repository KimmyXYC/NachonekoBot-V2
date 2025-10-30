# -*- coding: utf-8 -*-
# @Time    : 2025/7/5 12:04
# @Author  : KimmyXYC
# @File    : bc.py
# @Software: PyCharm
from datetime import datetime, UTC
import aiohttp
from telebot import types
from loguru import logger
from binance.spot import Spot
from binance.error import ClientError
import xmltodict


# ==================== 插件元数据 ====================
__plugin_name__ = "bc"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "币种转换工具"
__commands__ = ["bc"]
__command_descriptions__ = {
    "bc": "货币转换"
}
__command_help__ = {
    "bc": "/bc [Amount] [Currency_From] [Currency_To] - 货币转换"
}


# ==================== 核心功能 ====================
API = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


async def init() -> list:
    """ 初始化货币数据 """
    async with aiohttp.ClientSession() as session:
        async with session.get(API) as response:
            result = await response.read()
            currencies = []
            data = {}
            rate_data = xmltodict.parse(result)
            rate_data = rate_data['gesmes:Envelope']['Cube']['Cube']['Cube']
            for i in rate_data:
                currencies.append(i['@currency'])
                data[i['@currency']] = float(i['@rate'])
            currencies.sort()
    return [currencies, data]


async def handle_bc_command(bot, message: types.Message) -> None:
    """
    处理币种转换命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    command_args = message.text.split()

    # 初始化数据
    try:
        currencies, data = await init()
        binanceclient = Spot()
        nowtimestamp = binanceclient.time()
        nowtime = datetime.fromtimestamp(float(nowtimestamp['serverTime']) / 1000, UTC)
    except Exception as e:
        await bot.reply_to(message, f"初始化失败: {str(e)}")
        return

    # 无参数时显示BTC和ETH的价格
    if len(command_args) == 1:
        try:
            btc_price_data = binanceclient.ticker_price("BTCUSDT")
            eth_price_data = binanceclient.ticker_price("ETHUSDT")

            response_text = (
                f'{nowtime.strftime("%Y-%m-%d %H:%M:%S")} UTC\n'
                f'1 BTC = {float(btc_price_data["price"]):.2f} USDT\n'
                f'1 ETH = {float(eth_price_data["price"]):.2f} USDT'
            )

            await bot.reply_to(message, response_text)
            return
        except Exception as e:
            await bot.reply_to(message, f"获取价格失败: {str(e)}")
            return

    # 参数不足
    if len(command_args) < 4:
        usage_text = (
            "使用方法: /bc <数量> <币种1> <币种2>\n"
            "例如: /bc 100 USD EUR - 将100美元转换为欧元\n"
            "例如: /bc 1 BTC USD - 将1比特币转换为美元\n"
            "例如: /bc 0.5 ETH BTC - 将0.5以太坊转换为比特币"
        )
        await bot.reply_to(message, usage_text)
        return

    # 解析参数
    try:
        number = float(command_args[1])
    except ValueError:
        await bot.reply_to(message, "数量必须是有效的数字")
        return

    _from = command_args[2].upper().strip()
    _to = command_args[3].upper().strip()

    msg = await bot.reply_to(message, f"正在转换 {number} {_from} 到 {_to}...")

    # 两种都是法定货币
    if (currencies.count(_from) != 0) and (currencies.count(_to) != 0):
        result = number * data[_to] / data[_from]
        await bot.edit_message_text(
            f"{number} {_from} = {result:.2f} {_to}",
            message.chat.id, msg.message_id
        )
        return

    # 从法定货币到加密货币
    if currencies.count(_from) != 0:
        try:
            usd_number = number * data["USD"] / data[_from]
            try:
                price_data = binanceclient.ticker_price(f"{_to}USDT")
                crypto_amount = 1 / float(price_data['price']) * usd_number

                await bot.edit_message_text(
                    f"{number} {_from} = {crypto_amount:.8f} {_to}\n"
                    f"{number} {_from} = {usd_number:.2f} USD",
                    message.chat.id, msg.message_id
                )
            except ClientError:
                await bot.edit_message_text(
                    f"找不到交易对 {_to}USDT",
                    message.chat.id, msg.message_id
                )
        except Exception as e:
            await bot.edit_message_text(
                f"转换失败: {str(e)}",
                message.chat.id, msg.message_id
            )
        return

    # 从加密货币到法定货币
    if currencies.count(_to) != 0:
        try:
            price_data = binanceclient.ticker_price(f"{_from}USDT")
            usd_price = float(price_data['price'])
            fiat_amount = usd_price * number * data[_to] / data["USD"]

            await bot.edit_message_text(
                f"{number} {_from} = {fiat_amount:.2f} {_to}\n"
                f"1 {_from} = {usd_price:.2f} USD",
                message.chat.id, msg.message_id
            )
        except ClientError:
            await bot.edit_message_text(
                f"找不到交易对 {_from}USDT",
                message.chat.id, msg.message_id
            )
        except Exception as e:
            await bot.edit_message_text(
                f"转换失败: {str(e)}",
                message.chat.id, msg.message_id
            )
        return

    # 两种都是加密货币
    try:
        try:
            price_data = binanceclient.ticker_price(f"{_from}{_to}")
            result = float(price_data['price']) * number

            await bot.edit_message_text(
                f"{number} {_from} = {result} {_to}",
                message.chat.id, msg.message_id
            )
        except ClientError:
            # 尝试反向交易对
            try:
                price_data = binanceclient.ticker_price(f"{_to}{_from}")
                result = number / float(price_data['price'])

                await bot.edit_message_text(
                    f"{number} {_from} = {result} {_to}",
                    message.chat.id, msg.message_id
                )
            except ClientError:
                await bot.edit_message_text(
                    f"找不到交易对 {_from}{_to} 或 {_to}{_from}",
                    message.chat.id, msg.message_id
                )
    except Exception as e:
        await bot.edit_message_text(
            f"转换失败: {str(e)}",
            message.chat.id, msg.message_id
        )


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot
    middleware.register_command_handler(
        commands=['bc'],
        callback=handle_bc_command,
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
