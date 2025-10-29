# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 20:56
# @Author  : KimmyXYC
# @File    : remake.py
# @Software: PyCharm
import numpy as np
import random
import pandas as pd

from loguru import logger

from utils.postgres import BotDatabase

async def handle_remake_command(bot, message):
    rd_data, rd_weights = get_csv_data_list()
    country_choice = np.random.choice(rd_data, p=np.array(rd_weights) / sum(rd_weights))
    sex_choice = random.choice(["男孩子", "女孩子", "MtF", "FtM", "MtC", "萝莉", "正太", "武装直升机", "沃尔玛购物袋",
                                "星巴克", "太监", "无性别", "扶她", "死胎"])
    await bot.reply_to(message, f"转生成功！您现在是 {country_choice} 的 {sex_choice} 了。")
    conn = BotDatabase.conn
    try:
        result = await conn.execute(
            '''UPDATE remake 
                    SET count = count + 1,
                        country = $2,
                        gender = $3
               WHERE user_id = $1''',
            message.from_user.id, country_choice, sex_choice
        )
        if result == 'UPDATE 0':
            await conn.execute(
                '''INSERT INTO remake (user_id, count, country, gender)
                   VALUES ($1, 1, $2, $3) 
                   ON CONFLICT (user_id) DO NOTHING''',
                message.from_user.id, country_choice, sex_choice
            )
    except Exception as e:
        logger.error(f"Database error: {e}")

async def handle_remake_data_command(bot, message):
    conn = BotDatabase.conn
    try:
        result = await conn.fetch(
            '''SELECT user_id, count, country, gender 
               FROM remake 
               WHERE user_id = $1''',
            message.from_user.id
        )
        if result:
            user_data = result[0]
            await bot.reply_to(message, f"您现在是 {user_data['country']} 的 {user_data['gender']}，已转生 {user_data['count']} 次。")
        else:
            await bot.reply_to(message, "您还没有 remake 过呢，快 /remake 吧")
    except Exception as e:
        logger.error(f"Database error: {e}")
        await bot.reply_to(message, "查询失败，请稍后再试。")


def get_csv_data_list():
    df = pd.read_csv('res/csv/data.csv', encoding='utf-8')

    country_list = df['Country'].tolist()
    weight_list = df['Weight'].tolist()

    return country_list, weight_list

