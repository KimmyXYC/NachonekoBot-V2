# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 20:56
# @Author  : KimmyXYC
# @File    : remake.py
# @Software: PyCharm
import numpy as np
import random
import pandas as pd

from loguru import logger
from telebot import types

from utils.postgres import BotDatabase

# ==================== 插件元数据 ====================
__plugin_name__ = "remake"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "转生系统"
__commands__ = ["remake", "remake_data"]
__command_category__ = "fun"
__command_order__ = {"remake": 420, "remake_data": 421}
__command_descriptions__ = {"remake": "转生", "remake_data": "查看转生数据"}
__command_help__ = {
    "remake": "/remake - 转生",
    "remake_data": "/remake_data - 查看转生数据",
}


# ==================== 核心功能 ====================
def get_csv_data_list():
    df = pd.read_csv("res/csv/data.csv", encoding="utf-8")

    country_list = df["Country"].tolist()
    weight_list = df["Weight"].tolist()

    return country_list, weight_list


async def handle_remake_command(bot, message):
    rd_data, rd_weights = get_csv_data_list()
    country_choice = np.random.choice(rd_data, p=np.array(rd_weights) / sum(rd_weights))
    sex_choice = random.choice(
        [
            "男孩子",
            "女孩子",
            "MtF",
            "FtM",
            "MtC",
            "萝莉",
            "正太",
            "武装直升机",
            "沃尔玛购物袋",
            "星巴克",
            "太监",
            "无性别",
            "扶她",
            "死胎",
        ]
    )
    await bot.reply_to(
        message, f"转生成功！您现在是 {country_choice} 的 {sex_choice} 了。"
    )
    conn = BotDatabase.conn
    try:
        result = await conn.execute(
            """UPDATE remake 
                    SET count = count + 1,
                        country = $2,
                        gender = $3
               WHERE user_id = $1""",
            message.from_user.id,
            country_choice,
            sex_choice,
        )
        if result == "UPDATE 0":
            await conn.execute(
                """INSERT INTO remake (user_id, count, country, gender)
                   VALUES ($1, 1, $2, $3) 
                   ON CONFLICT (user_id) DO NOTHING""",
                message.from_user.id,
                country_choice,
                sex_choice,
            )
    except Exception as e:
        logger.error(f"Database error: {e}")


async def handle_remake_data_command(bot, message):
    conn = BotDatabase.conn
    try:
        result = await conn.fetch(
            """SELECT user_id, count, country, gender 
               FROM remake 
               WHERE user_id = $1""",
            message.from_user.id,
        )
        if result:
            user_data = result[0]
            await bot.reply_to(
                message,
                f"您现在是 {user_data['country']} 的 {user_data['gender']}，已转生 {user_data['count']} 次。",
            )
        else:
            await bot.reply_to(message, "您还没有 remake 过呢，快 /remake 吧")
    except Exception as e:
        logger.error(f"Database error: {e}")
        await bot.reply_to(message, "查询失败，请稍后再试。")


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def remake_handler(bot, message: types.Message):
        await handle_remake_command(bot, message)

    async def remake_data_handler(bot, message: types.Message):
        await handle_remake_data_command(bot, message)

    middleware.register_command_handler(
        commands=["remake"],
        callback=remake_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    middleware.register_command_handler(
        commands=["remake_data"],
        callback=remake_data_handler,
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
