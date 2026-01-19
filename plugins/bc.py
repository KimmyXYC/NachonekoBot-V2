# -*- coding: utf-8 -*-
# @Time    : 2025/7/5 12:04
# @Author  : KimmyXYC
# @File    : bc.py
# @Software: PyCharm
from datetime import datetime, UTC, timezone, timedelta
import asyncio
import aiohttp
import time
from telebot import types
from loguru import logger
from binance.spot import Spot
from binance.error import ClientError
import xmltodict

try:
    from curl_cffi.requests import AsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    logger.warning("curl_cffi 未安装，Mastercard 和 Visa 汇率查询可能失败。请运行: pip install curl_cffi")


# ==================== 插件元数据 ====================
__plugin_name__ = "bc"
__version__ = "1.2.0"
__author__ = "KimmyXYC"
__description__ = "货币转换工具（支持法币多汇率源+加密货币）"
__commands__ = ["bc"]
__command_descriptions__ = {
    "bc": "货币转换（支持法币多汇率源+加密货币）"
}
__command_help__ = {
    "bc": "/bc [Amount] [Currency_From] [Currency_To] - 货币转换（法币支持欧盟/银联/Mastercard/Visa多汇率源）\n"
          "Inline: @NachoNekoX_bot bc [Amount] [Currency_From] [Currency_To]"
}


# ==================== Chrome版本缓存 ====================
_chrome_version_cache = None
_chrome_version_timestamp = 0
CHROME_VERSION_TTL = 86400  # 24小时
FALLBACK_CHROME_VERSION = "136"


# ==================== 核心功能 ====================
API = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


def get_exchange_rate_date() -> datetime:
    """
    获取汇率日期（基于UTC+8时区）
    - 早上11点前使用前一天的日期
    - 11点后使用当天日期

    Returns:
        datetime: 应该使用的汇率日期
    """
    utc8_tz = timezone(timedelta(hours=8))
    now_utc8 = datetime.now(utc8_tz)

    # 如果当前时间早于11点，使用前一天的日期
    if now_utc8.hour < 11:
        rate_date = now_utc8 - timedelta(days=1)
        logger.debug("当前UTC+8时间: {} ({}:{}), 使用前一天汇率日期: {}",
                    now_utc8.strftime('%Y-%m-%d %H:%M:%S'),
                    now_utc8.hour,
                    now_utc8.minute,
                    rate_date.strftime('%Y-%m-%d'))
    else:
        rate_date = now_utc8
        logger.debug("当前UTC+8时间: {} ({}:{}), 使用当天汇率日期: {}",
                    now_utc8.strftime('%Y-%m-%d %H:%M:%S'),
                    now_utc8.hour,
                    now_utc8.minute,
                    rate_date.strftime('%Y-%m-%d'))

    return rate_date


async def fetch_chrome_version() -> str:
    """
    获取Chrome版本，使用TTL缓存
    """
    return FALLBACK_CHROME_VERSION


async def generate_headers() -> dict:
    """
    生成请求头
    """
    chrome_version = await fetch_chrome_version()
    ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36"
    client_hints_ua = f'"Google Chrome";v="{chrome_version}", "Chromium";v="{chrome_version}", "Not A(Brand";v="24"'

    headers = {
        "user-agent": ua,
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "sec-ch-ua": client_hints_ua,
        "sec-ch-ua-platform": "Windows"
    }

    logger.debug("生成请求头，Chrome版本: {}", chrome_version)
    return headers


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
            data['EUR'] = 1.0
            currencies.append('EUR')
            currencies.sort()
    return [currencies, data]


async def fetch_eu_rate(amount: float, currency_from: str, currency_to: str, eu_data: dict) -> dict:
    """
    获取欧盟汇率
    """
    try:
        if currency_from not in eu_data or currency_to not in eu_data:
            logger.error("欧盟不支持的交易对: {} -> {}", currency_from, currency_to)
            return {
                "success": False,
                "rate": None,
                "converted_amount": None,
                "error": f"不支持的交易对: {currency_from} -> {currency_to}"
            }

        rate = eu_data[currency_to] / eu_data[currency_from]
        converted_amount = amount * rate
        logger.debug("欧盟汇率转换: {} {} -> {} {}, 汇率: {}", amount, currency_from, converted_amount, currency_to, rate)

        return {
            "success": True,
            "rate": rate,
            "converted_amount": converted_amount,
            "error": None
        }

    except Exception as e:
        logger.error("欧盟汇率获取异常: {}", str(e))
        return {
            "success": False,
            "rate": None,
            "converted_amount": None,
            "error": "欧盟汇率获取失败"
        }


async def fetch_unionpay_rate(amount: float, currency_from: str, currency_to: str) -> dict:
    """
    获取银联汇率
    """
    try:
        rate_date = get_exchange_rate_date()
        unionpay_api = f"https://m.unionpayintl.com/jfimg/{rate_date.strftime('%Y%m%d')}.json"
        logger.debug("请求银联汇率 API: {}", unionpay_api)

        async with aiohttp.ClientSession() as session:
            async with session.get(unionpay_api, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.error("银联API{}响应状态码: {}", unionpay_api, response.status)
                    return {
                        "success": False,
                        "rate": None,
                        "converted_amount": None,
                        "error": "银联汇率获取失败"
                    }
                data = await response.json()

        exchange_rates = data.get("exchangeRateJson", [])
        rate = None
        for rate_data in exchange_rates:
            if rate_data["transCur"] == currency_from and rate_data["baseCur"] == currency_to:
                rate = rate_data["rateData"]
                break

        if rate is None:
            logger.error("银联不支持的交易对: {} -> {}", currency_from, currency_to)
            return {
                "success": False,
                "rate": None,
                "converted_amount": None,
                "error": f"不支持的交易对: {currency_from} -> {currency_to}"
            }

        converted_amount = amount * rate
        logger.debug("银联汇率转换: {} {} -> {} {}, 汇率: {}", amount, currency_from, converted_amount, currency_to, rate)

        return {
            "success": True,
            "rate": rate,
            "converted_amount": converted_amount,
            "error": None
        }

    except Exception as e:
        logger.error("银联汇率获取异常: {}", str(e))
        return {
            "success": False,
            "rate": None,
            "converted_amount": None,
            "error": "银联汇率获取失败"
        }


async def fetch_mastercard_rate(amount: float, currency_from: str, currency_to: str) -> dict:
    """
    获取Mastercard汇率
    使用 curl_cffi 模拟 Chrome 浏览器的 TLS 指纹以绕过 Akamai CDN 检测
    """
    try:
        if not CURL_CFFI_AVAILABLE:
            logger.error("curl_cffi 未安装，无法请求 Mastercard API")
            return {
                "success": False,
                "rate": None,
                "converted_amount": None,
                "error": "curl_cffi 未安装"
            }

        api_endpoint = "https://www.mastercard.com/marketingservices/public/mccom-services/currency-conversions/conversion-rates"
        headers = await generate_headers()
        params = {
            "exchange_date": datetime.now().strftime('%Y-%m-%d'),
            "transaction_currency": currency_from,
            "cardholder_billing_currency": currency_to,
            "bank_fee": 0,
            "transaction_amount": amount
        }

        logger.debug("请求Mastercard汇率 API: {}, params: {}", api_endpoint, params)

        # 获取Chrome版本并构建impersonate参数
        chrome_version = await fetch_chrome_version()
        impersonate_version = f"chrome{chrome_version}"
        logger.debug("使用TLS指纹版本: {}", impersonate_version)

        # 使用 curl_cffi 的 AsyncSession 并模拟对应版本的 Chrome
        async with AsyncSession() as session:
            response = await session.get(
                api_endpoint,
                headers=headers,
                params=params,
                timeout=10,
                impersonate=impersonate_version  # 关键：模拟对应版本的 Chrome TLS 指纹
            )

            if response.status_code != 200:
                logger.error("Mastercard API响应状态码: {}", response.status_code)
                return {
                    "success": False,
                    "rate": None,
                    "converted_amount": None,
                    "error": f"Mastercard汇率获取失败 (HTTP {response.status_code})"
                }

            result = response.json()

        # 从响应中提取数据
        data = result.get("data", {})
        conversion_rate = data.get("conversionRate")
        converted_amount = data.get("crdhldBillAmt")

        if conversion_rate is None or converted_amount is None:
            logger.error("Mastercard API响应数据格式错误: {}", result)
            return {
                "success": False,
                "rate": None,
                "converted_amount": None,
                "error": "Mastercard汇率获取失败"
            }

        logger.debug("Mastercard汇率转换: {} {} -> {} {}, 汇率: {}", amount, currency_from, converted_amount, currency_to, conversion_rate)

        return {
            "success": True,
            "rate": float(conversion_rate),
            "converted_amount": float(converted_amount),
            "error": None
        }

    except Exception as e:
        logger.error("Mastercard汇率获取异常: {}", str(e))
        return {
            "success": False,
            "rate": None,
            "converted_amount": None,
            "error": "Mastercard汇率获取失败"
        }


async def fetch_visa_rate(amount: float, currency_from: str, currency_to: str) -> dict:
    """
    获取Visa汇率
    使用 curl_cffi 模拟 Chrome 浏览器的 TLS 指纹以绕过 CDN 检测
    注意: Visa API 的货币参数是反向的（fromCurr=目标货币, toCurr=来源货币）
    """
    try:
        if not CURL_CFFI_AVAILABLE:
            logger.error("curl_cffi 未安装，无法请求 Visa API")
            return {
                "success": False,
                "rate": None,
                "converted_amount": None,
                "error": "curl_cffi 未安装"
            }

        api_endpoint = "https://usa.visa.com/cmsapi/fx/rates"
        headers = await generate_headers()

        # 格式化日期为 MM/DD/YYYY
        date_str = datetime.now().strftime('%m/%d/%Y')

        # 注意: Visa API 的货币参数是反向的
        params = {
            "amount": amount,
            "fee": 0,
            "utcConvertedDate": date_str,
            "exchangedate": date_str,
            "fromCurr": currency_to,  # 反向：目标货币
            "toCurr": currency_from   # 反向：来源货币
        }

        logger.debug("请求Visa汇率 API: {}, params: {}", api_endpoint, params)

        # 获取Chrome版本并构建impersonate参数
        chrome_version = await fetch_chrome_version()
        impersonate_version = f"chrome{chrome_version}"
        logger.debug("使用TLS指纹版本: {}", impersonate_version)

        # 使用 curl_cffi 的 AsyncSession 并模拟对应版本的 Chrome
        async with AsyncSession() as session:
            response = await session.get(
                api_endpoint,
                headers=headers,
                params=params,
                timeout=10,
                impersonate=impersonate_version  # 关键：模拟对应版本的 Chrome TLS 指纹
            )

            if response.status_code != 200:
                logger.error("Visa API响应状态码: {}", response.status_code)
                return {
                    "success": False,
                    "rate": None,
                    "converted_amount": None,
                    "error": f"Visa汇率获取失败 (HTTP {response.status_code})"
                }

            result = response.json().get("originalValues")

        # 从响应中提取数据
        converted_amount = result.get("toAmountWithVisaRate")
        conversion_rate = result.get("fxRateVisa")

        if conversion_rate is None or converted_amount is None:
            logger.error("Visa API响应数据格式错误: {}", result)
            return {
                "success": False,
                "rate": None,
                "converted_amount": None,
                "error": "Visa汇率获取失败"
            }

        logger.debug("Visa汇率转换: {} {} -> {} {}, 汇率: {}", amount, currency_from, converted_amount, currency_to, conversion_rate)

        return {
            "success": True,
            "rate": float(conversion_rate),
            "converted_amount": float(converted_amount),
            "error": None
        }

    except Exception as e:
        logger.error("Visa汇率获取异常: {}", str(e))
        return {
            "success": False,
            "rate": None,
            "converted_amount": None,
            "error": "Visa汇率获取失败"
        }


def _normalize_bc_tokens(tokens: list[str]) -> list[str]:
    """将输入 tokens 规整为 bc 的参数列表。

    - 命令：['/bc', '1', 'USD', 'CNY'] -> ['1', 'USD', 'CNY']
    - Inline：['bc', '1', 'USD', 'CNY'] -> ['1', 'USD', 'CNY']
    """
    if not tokens:
        return []

    first = tokens[0]
    if first.startswith('/'):
        first = first[1:].split('@')[0]

    if first.lower() == 'bc':
        return tokens[1:]

    return tokens


async def query_bc_text(raw_tokens: list[str]) -> str:
    """生成与 `/bc` 命令一致的输出文本，用于命令与 Inline 复用。"""
    args = _normalize_bc_tokens(raw_tokens)

    # 初始化数据
    try:
        currencies, data = await init()
        binanceclient = Spot()
        nowtimestamp = binanceclient.time()
        nowtime = datetime.fromtimestamp(float(nowtimestamp['serverTime']) / 1000, UTC)
    except Exception as e:
        return f"初始化失败: {str(e)}"

    # 无参数时显示BTC和ETH的价格
    if len(args) == 0:
        try:
            btc_price_data = binanceclient.ticker_price("BTCUSDT")
            eth_price_data = binanceclient.ticker_price("ETHUSDT")

            response_text = (
                f'{nowtime.strftime("%Y-%m-%d %H:%M:%S")} UTC\n'
                f'1 BTC = {float(btc_price_data["price"]):.2f} USDT\n'
                f'1 ETH = {float(eth_price_data["price"]):.2f} USDT'
            )
            return response_text
        except Exception as e:
            return f"获取价格失败: {str(e)}"

    # 参数不足
    if len(args) < 3:
        usage_text = (
            "使用方法: /bc <数量> <币种1> <币种2>\n"
            "例如: /bc 100 USD EUR - 将100美元转换为欧元\n"
            "例如: /bc 1 BTC USD - 将1比特币转换为美元\n"
            "例如: /bc 0.5 ETH BTC - 将0.5以太坊转换为比特币"
        )
        return usage_text

    # 解析参数
    try:
        number = float(args[0])
    except ValueError:
        return "数量必须是有效的数字"

    _from = args[1].upper().strip()
    _to = args[2].upper().strip()

    # 优先尝试四种法币汇率源（欧盟/银联/Mastercard/Visa）
    # 只有当四种方式全部失败时，才尝试加密货币交易对。
    eu_result, unionpay_result, mastercard_result, visa_result = await asyncio.gather(
        fetch_eu_rate(number, _from, _to, data),
        fetch_unionpay_rate(number, _from, _to),
        fetch_mastercard_rate(number, _from, _to),
        fetch_visa_rate(number, _from, _to)
    )

    if any(r.get("success") for r in (eu_result, unionpay_result, mastercard_result, visa_result)):
        response_lines = []

        if eu_result["success"]:
            response_lines.append(
                f"欧盟: {number:.2f} {_from} ≈ {eu_result['converted_amount']:.2f} {_to} "
                f"(汇率: {eu_result['rate']:.4f})"
            )
        else:
            response_lines.append(f"欧盟: {eu_result['error']}")

        if unionpay_result["success"]:
            response_lines.append(
                f"银联: {number:.2f} {_from} ≈ {unionpay_result['converted_amount']:.2f} {_to} "
                f"(汇率: {unionpay_result['rate']:.4f})"
            )
        else:
            response_lines.append(f"银联: {unionpay_result['error']}")

        if mastercard_result["success"]:
            response_lines.append(
                f"Mastercard: {number:.2f} {_from} ≈ {mastercard_result['converted_amount']:.2f} {_to} "
                f"(汇率: {mastercard_result['rate']:.4f})"
            )
        else:
            response_lines.append(f"Mastercard: {mastercard_result['error']}")

        if visa_result["success"]:
            response_lines.append(
                f"Visa: {number:.2f} {_from} ≈ {visa_result['converted_amount']:.2f} {_to} "
                f"(汇率: {visa_result['rate']:.4f})"
            )
        else:
            response_lines.append(f"Visa: {visa_result['error']}")

        return "\n".join(response_lines)

    # 从法定货币到加密货币
    if currencies.count(_from) != 0:
        try:
            usd_number = number * data["USD"] / data[_from]
            try:
                price_data = binanceclient.ticker_price(f"{_to}USDT")
                crypto_amount = 1 / float(price_data['price']) * usd_number

                return (
                    f"{number} {_from} = {crypto_amount:.8f} {_to}\n"
                    f"{number} {_from} = {usd_number:.2f} USD"
                )
            except ClientError:
                return f"找不到交易对 {_to}USDT"
        except Exception as e:
            return f"转换失败: {str(e)}"

    # 从加密货币到法定货币
    if currencies.count(_to) != 0:
        try:
            price_data = binanceclient.ticker_price(f"{_from}USDT")
            usd_price = float(price_data['price'])
            fiat_amount = usd_price * number * data[_to] / data["USD"]

            return (
                f"{number} {_from} = {fiat_amount:.2f} {_to}\n"
                f"1 {_from} = {usd_price:.2f} USD"
            )
        except ClientError:
            return f"找不到交易对 {_from}USDT"
        except Exception as e:
            return f"转换失败: {str(e)}"

    # 两种都是加密货币
    try:
        try:
            price_data = binanceclient.ticker_price(f"{_from}{_to}")
            result = float(price_data['price']) * number
            return f"{number} {_from} = {result} {_to}"
        except ClientError:
            # 尝试反向交易对
            try:
                price_data = binanceclient.ticker_price(f"{_to}{_from}")
                result = number / float(price_data['price'])
                return f"{number} {_from} = {result} {_to}"
            except ClientError:
                return f"找不到交易对 {_from}{_to} 或 {_to}{_from}"
    except Exception as e:
        return f"转换失败: {str(e)}"


async def handle_bc_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot bc [Amount] [Currency_From] [Currency_To]"""
    query = (inline_query.query or "").strip()
    tokens = query.split()

    # 仅在 middleware 过滤后进来；此处再做一次兜底
    if not tokens or tokens[0].lower() != 'bc':
        text = (
            "使用方法: bc <数量> <币种1> <币种2>\n"
            "例如: bc 100 USD EUR"
        )
        result = types.InlineQueryResultArticle(
            id="bc_usage",
            title="货币转换 (bc)",
            description="用法：bc [Amount] [Currency_From] [Currency_To]",
            input_message_content=types.InputTextMessageContent(text)
        )
        await bot.answer_inline_query(inline_query.id, [result], cache_time=1, is_personal=True)
        return

    args = _normalize_bc_tokens(tokens)
    if len(args) not in (0, 3):
        text = (
            "使用方法: bc <数量> <币种1> <币种2>\n"
            "例如: bc 100 USD EUR"
        )
        result = types.InlineQueryResultArticle(
            id="bc_usage",
            title="货币转换 (bc)",
            description="用法：bc [Amount] [Currency_From] [Currency_To]",
            input_message_content=types.InputTextMessageContent(text)
        )
        await bot.answer_inline_query(inline_query.id, [result], cache_time=1, is_personal=True)
        return

    result_text = await query_bc_text(tokens)
    title = "bc"
    result_id = "bc_prices"
    if len(args) == 3:
        title = f"{args[0]} {args[1].upper()} -> {args[2].upper()}"
        result_id = f"bc_{args[0]}_{args[1].upper()}_{args[2].upper()}"

    result = types.InlineQueryResultArticle(
        id=result_id,
        title=title,
        description="发送转换结果",
        input_message_content=types.InputTextMessageContent(result_text)
    )
    await bot.answer_inline_query(inline_query.id, [result], cache_time=1, is_personal=True)



async def handle_bc_command(bot, message: types.Message) -> None:
    """
    处理币种转换命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    command_args = message.text.split()
    args = _normalize_bc_tokens(command_args)

    # 无参数时显示BTC和ETH的价格
    if len(args) == 0:
        response_text = await query_bc_text(command_args)
        await bot.reply_to(message, response_text)
        return

    # 参数不足
    if len(args) < 3:
        usage_text = (
            "使用方法: /bc <数量> <币种1> <币种2>\n"
            "例如: /bc 100 USD EUR - 将100美元转换为欧元\n"
            "例如: /bc 1 BTC USD - 将1比特币转换为美元\n"
            "例如: /bc 0.5 ETH BTC - 将0.5以太坊转换为比特币"
        )
        await bot.reply_to(message, usage_text)
        return

    # 解析参数（仅用于提示“正在转换”）
    try:
        number = float(args[0])
    except ValueError:
        await bot.reply_to(message, "数量必须是有效的数字")
        return

    _from = args[1].upper().strip()
    _to = args[2].upper().strip()

    msg = await bot.reply_to(message, f"正在转换 {number} {_from} 到 {_to}...")

    result_text = await query_bc_text(command_args)
    await bot.edit_message_text(result_text, message.chat.id, msg.message_id)


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

    middleware.register_inline_handler(
        callback=handle_bc_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: bool(getattr(q, 'query', None)) and q.query.strip().lower().startswith('bc')
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
