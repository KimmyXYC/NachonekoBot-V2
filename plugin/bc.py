# -*- coding: utf-8 -*-
# @Time    : 2025/7/5 12:04
# @Author  : KimmyXYC
# @File    : bc.py
# @Software: PyCharm
from datetime import datetime, UTC
import aiohttp
from telebot import types
from binance.spot import Spot
from binance.error import ClientError
import xmltodict

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
            btc_usdt_data = binanceclient.klines("BTCUSDT", "1m")[:1][0]
            eth_usdt_data = binanceclient.klines("ETHUSDT", "1m")[:1][0]

            response_text = (
                f'{nowtime.strftime("%Y-%m-%d %H:%M:%S")} UTC\n'
                f'1 BTC = {btc_usdt_data[1]} USDT\n'
                f'1 ETH = {eth_usdt_data[1]} USDT'
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
                x_usdt_data = binanceclient.klines(f"{_to}USDT", "1m")[:1][0]
                crypto_amount = 1 / float(x_usdt_data[1]) * usd_number

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
            usd_number = number * data[_to] / data["USD"]
            try:
                x_usdt_data = binanceclient.klines(f"{_from}USDT", "1m")[:1][0]
                fiat_amount = float(x_usdt_data[1]) * usd_number

                await bot.edit_message_text(
                    f"{number} {_from} = {fiat_amount:.2f} {_to}\n"
                    f"1 {_from} = {float(x_usdt_data[1]):.2f} USD",
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
            from_to_data = binanceclient.klines(f"{_from}{_to}", "1m")[:1][0]
            result = float(from_to_data[1]) * number

            await bot.edit_message_text(
                f"{number} {_from} = {result} {_to}",
                message.chat.id, msg.message_id
            )
        except ClientError:
            # 尝试反向交易对
            try:
                to_from_data = binanceclient.klines(f"{_to}{_from}", "1m")[:1][0]
                result = number / float(to_from_data[1])

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
