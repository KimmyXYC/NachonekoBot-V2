# -*- coding: utf-8 -*-
# @Time    : 2025/6/22 18:57
# @Author  : KimmyXYC
# @File    : weather.py
# @Software: PyCharm
import datetime
import aiohttp
import re
import uuid
import asyncio  # 添加 asyncio 模块用于并行处理
from telebot import types
from loguru import logger
from utils.yaml import BotConfig
from app.utils import command_error_msg

# ==================== 插件元数据 ====================
__plugin_name__ = "weather"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "天气查询"
__commands__ = ["weather"]
__command_category__ = "query"
__command_order__ = {"weather": 110}
__command_descriptions__ = {"weather": "查询天气信息"}
__command_help__ = {"weather": "/weather [City_Name] - 查询天气信息"}


# ==================== 核心功能 ====================
icons = {
    "01d": "🌞",
    "01n": "🌚",
    "02d": "⛅️",
    "02n": "⛅️",
    "03d": "☁️",
    "03n": "☁️",
    "04d": "☁️",
    "04n": "☁️",
    "09d": "🌧",
    "09n": "🌧",
    "10d": "🌦",
    "10n": "🌦",
    "11d": "🌩",
    "11n": "🌩",
    "13d": "🌨",
    "13n": "🌨",
    "50d": "🌫",
    "50n": "🌫",
}


def timestamp_to_time(timestamp, timeZoneShift):
    timeArray = datetime.datetime.fromtimestamp(
        timestamp, datetime.UTC
    ) + datetime.timedelta(seconds=timeZoneShift)
    return timeArray.strftime("%H:%M")


def calcWindDirection(windDirection):
    dirs = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    ix = round(windDirection / (360.0 / len(dirs)))
    return dirs[ix % len(dirs)]


def is_chinese(text):
    """检查文本是否包含中文字符"""
    pattern = re.compile(r"[\u4e00-\u9fff]+")
    return bool(pattern.search(text))


async def translate_chinese_to_english(text):
    """将中文文本翻译为英文（使用微软翻译API）"""
    try:
        # 使用微软翻译API
        subscription_key = BotConfig["translate"]["token"]
        endpoint = "https://api.cognitive.microsofttranslator.com"
        location = BotConfig["translate"]["location"]
        path = "/translate"
        constructed_url = endpoint + path

        params = {"api-version": "3.0", "from": "zh-Hans", "to": "en"}

        headers = {
            "Ocp-Apim-Subscription-Key": subscription_key,
            "Ocp-Apim-Subscription-Region": location,
            "Content-type": "application/json",
            "X-ClientTraceId": str(uuid.uuid4()),
        }

        body = [{"text": text}]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                constructed_url, params=params, headers=headers, json=body
            ) as resp:
                if resp.status == 200:
                    response = await resp.json()
                    # 提取翻译结果
                    translated_text = response[0]["translations"][0]["text"]
                    return translated_text
                logger.error(f"微软翻译API返回错误状态码: {resp.status}")
                return text  # 如果翻译失败，返回原始文本
    except Exception as e:
        logger.error(f"翻译过程中出错: {str(e)}")
        return text  # 出现异常时返回原始文本


async def handle_weather_command(bot, message: types.Message, city: str):
    _t = bot.t
    try:
        # 检查城市名是否为中文，如果是则翻译
        if is_chinese(city):
            city = await translate_chinese_to_english(city)

        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "appid": "973e8a21e358ee9d30b47528b43a8746",
            "units": "metric",
            "lang": "zh_cn",
            "q": city,
        }

        async with aiohttp.ClientSession() as session:
            # 创建获取天气数据的异步任务
            async def get_weather_data():
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        if resp.status == 404:
                            return {
                                "status": 404,
                                "message": _t("error.city_not_found", city=city),
                            }
                        return {
                            "status": resp.status,
                            "message": _t(
                                "error.weather_api_failed", status_code=resp.status
                            ),
                        }
                    return {"status": 200, "data": await resp.json()}

            # 创建获取天气图片的异步任务
            async def get_weather_image():
                try:
                    wttr_url = f"https://zh.wttr.in/{city}.png"
                    async with session.get(wttr_url) as img_resp:
                        if img_resp.status == 200:
                            # 如果成功获取图片，则下载图片数据
                            return await img_resp.read()
                        return None
                except Exception as e:
                    # 图片获取失败但不影响继续执行
                    logger.error(f"获取天气图片失败: {str(e)}")
                    return None

            # 并行执行获取天气数据和天气图片的任务
            weather_result, img_data = await asyncio.gather(
                get_weather_data(), get_weather_image()
            )

            # 处理天气数据结果
            if weather_result["status"] != 200:
                await bot.send_message(
                    chat_id=message.chat.id, text=weather_result["message"]
                )
                return

            # 处理天气数据
            data = weather_result["data"]
            cityName = f"{data['name']}, {data['sys']['country']}"
            timeZoneShift = data["timezone"]
            pressure = data["main"]["pressure"]
            humidity = data["main"]["humidity"]
            windSpeed = data["wind"]["speed"]
            windDirection = calcWindDirection(data["wind"]["deg"])
            sunriseTimeunix = data["sys"]["sunrise"]
            sunriseTime = timestamp_to_time(sunriseTimeunix, timeZoneShift)
            sunsetTimeunix = data["sys"]["sunset"]
            sunsetTime = timestamp_to_time(sunsetTimeunix, timeZoneShift)
            fellsTemp = data["main"]["feels_like"]
            tempInC = round(data["main"]["temp"], 2)
            tempInF = round((1.8 * tempInC) + 32, 2)
            icon = data["weather"][0]["icon"]
            desc = data["weather"][0]["description"]
            res = _t(
                "result.weather_summary",
                city_name=cityName,
                icon=icons[icon],
                description=desc,
                wind_direction=windDirection,
                wind_speed=windSpeed,
                temp_c=tempInC,
                temp_f=tempInF,
                humidity=humidity,
                feels_like=fellsTemp,
                pressure=pressure,
                sunrise=sunriseTime,
                sunset=sunsetTime,
            )

            # 尝试发送图片和文本
            try:
                if img_data:
                    await bot.send_photo(
                        chat_id=message.chat.id, photo=img_data, caption=res
                    )
                else:
                    # 如果没有图片，则发送纯文本
                    await bot.send_message(chat_id=message.chat.id, text=res)
            except Exception as send_error:
                # 如果发送图片和文本失败，但我们有图片，尝试只发送图片
                if img_data:
                    try:
                        await bot.send_photo(chat_id=message.chat.id, photo=img_data)
                    except Exception:
                        # 如果所有尝试都失败，打印错误但不中断程序
                        logger.error(f"发送天气信息完全失败: {str(send_error)}")
    except Exception as e:
        await bot.send_message(
            chat_id=message.chat.id,
            text=_t("error.weather_unavailable", reason=str(e)),
        )


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def weather_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 1:
            await bot.reply_to(
                message,
                command_error_msg(
                    "weather", "City_Name", lang=getattr(bot, "_lang", None)
                ),
            )
        else:
            city = " ".join(command_args[1:])
            await handle_weather_command(bot, message, city)

    middleware.register_command_handler(
        commands=["weather"],
        callback=weather_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    logger.info(
        f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}"
    )


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
