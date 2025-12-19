# -*- coding: utf-8 -*-
# @Time    : 2025/12/19 00:00
# @Author  : KimmyXYC
# @File    : bcpro.py
# @Software: PyCharm
import asyncio
import aiohttp
import time
from loguru import logger
from telebot import types
from datetime import datetime

try:
    from curl_cffi.requests import AsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    logger.warning("curl_cffi 未安装，Mastercard 汇率查询可能失败。请运行: pip install curl_cffi")

# ==================== 插件元数据 ====================
__plugin_name__ = "bcpro"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "法币转换工具（银联+Mastercard+Visa汇率）"
__commands__ = ["bcp"]
__command_descriptions__ = {
    "bcp": "法币转换（银联+Mastercard+Visa汇率）"
}
__command_help__ = {
    "bcp": "/bcp [Amount] [Currency_From] [Currency_To] - 法币转换（银联+Mastercard+Visa汇率）"
}

# ==================== Chrome版本缓存 ====================
_chrome_version_cache = None
_chrome_version_timestamp = 0
CHROME_VERSION_TTL = 86400  # 24小时
FALLBACK_CHROME_VERSION = "131"


async def fetch_chrome_version() -> str:
    """
    获取Chrome版本，使用TTL缓存
    """
    global _chrome_version_cache, _chrome_version_timestamp

    # 检查缓存是否有效
    current_time = time.time()
    if _chrome_version_cache is not None and (current_time - _chrome_version_timestamp) < CHROME_VERSION_TTL:
        logger.debug("使用缓存的Chrome版本: {}", _chrome_version_cache)
        return str(_chrome_version_cache)

    # 尝试获取最新版本
    try:
        logger.debug("从chromestatus.com获取最新Chrome版本")
        async with aiohttp.ClientSession() as session:
            async with session.get("https://chromestatus.com/api/v0/channels", timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    text = await response.text()
                    # 移除前缀 )]}'\n
                    cleaned_data = text.replace(")]}'\n", "")
                    data = await response.json()
                    # 如果已经读取了text，需要重新请求或者直接解析cleaned_data
                    import json
                    channels = json.loads(cleaned_data)
                    stable_channel = channels.get("stable", {})
                    version = str(stable_channel.get("version", FALLBACK_CHROME_VERSION))

                    # 更新缓存
                    _chrome_version_cache = version
                    _chrome_version_timestamp = current_time
                    logger.debug("获取到Chrome版本: {}", version)
                    return version
                else:
                    logger.debug("获取Chrome版本失败，状态码: {}，使用fallback版本: {}", response.status, FALLBACK_CHROME_VERSION)
                    return FALLBACK_CHROME_VERSION
    except Exception as e:
        logger.debug("获取Chrome版本异常: {}，使用fallback版本: {}", str(e), FALLBACK_CHROME_VERSION)
        return FALLBACK_CHROME_VERSION


async def generate_mastercard_headers() -> dict:
    """
    生成Mastercard API请求头
    完全匹配 TypeScript 版本的实现
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

    logger.debug("生成Mastercard请求头，Chrome版本: {}", chrome_version)
    return headers


# ==================== 核心功能 ====================
async def fetch_unionpay_rate(amount: float, currency_from: str, currency_to: str) -> dict:
    """
    获取银联汇率
    """
    try:
        unionpay_api = f"https://m.unionpayintl.com/jfimg/{datetime.now().strftime('%Y%m%d')}.json"
        logger.debug("请求银联汇率 API: {}", unionpay_api)

        async with aiohttp.ClientSession() as session:
            async with session.get(unionpay_api, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.error("银联API响应状态码: {}", response.status)
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
        headers = await generate_mastercard_headers()
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
        headers = await generate_mastercard_headers()

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

            result = response.json()

        # 从响应中提取数据
        converted_amount = result.get("convertedAmount")
        conversion_rate = result.get("fxRateWithAdditionalFee")

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
            "rate": float(converted_amount),
            "converted_amount": float(conversion_rate),
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


async def handle_bcp_command(bot, message: types.Message) -> None:
    """
    处理bcp命令
    """
    command_args = message.text.split()
    if len(command_args) < 4:
        usage_text = (
            "使用方法: /bcp <数量> <币种1> <币种2>\n"
            "例如: /bcp 100 USD CNY - 将100美元转换为人民币"
        )
        await bot.reply_to(message, usage_text)
        return

    try:
        amount = float(command_args[1])
    except ValueError:
        await bot.reply_to(message, "请输入有效的数量。")
        return

    currency_from = command_args[2].upper()
    currency_to = command_args[3].upper()
    logger.debug("处理法币转换命令: {} {} -> {}", amount, currency_from, currency_to)

    # 并行获取三个提供商的汇率
    unionpay_result, mastercard_result, visa_result = await asyncio.gather(
        fetch_unionpay_rate(amount, currency_from, currency_to),
        fetch_mastercard_rate(amount, currency_from, currency_to),
        fetch_visa_rate(amount, currency_from, currency_to)
    )

    # 构建响应消息
    response_lines = []

    # 银联结果
    if unionpay_result["success"]:
        response_lines.append(
            f"银联: {amount:.2f} {currency_from} ≈ {unionpay_result['converted_amount']:.2f} {currency_to} "
            f"(汇率: {unionpay_result['rate']:.4f})"
        )
    else:
        response_lines.append(f"银联: {unionpay_result['error']}")

    # Mastercard结果
    if mastercard_result["success"]:
        response_lines.append(
            f"Mastercard: {amount:.2f} {currency_from} ≈ {mastercard_result['converted_amount']:.2f} {currency_to} "
            f"(汇率: {mastercard_result['rate']:.4f})"
        )
    else:
        response_lines.append(f"Mastercard: {mastercard_result['error']}")

    # Visa结果
    if visa_result["success"]:
        response_lines.append(
            f"Visa: {amount:.2f} {currency_from} ≈ {visa_result['converted_amount']:.2f} {currency_to} "
            f"(汇率: {visa_result['rate']:.4f})"
        )
    else:
        response_lines.append(f"Visa: {visa_result['error']}")

    result_text = "\n".join(response_lines)
    await bot.reply_to(message, result_text)


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot
    middleware.register_command_handler(
        commands=['bcp'],
        callback=handle_bcp_command,
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

