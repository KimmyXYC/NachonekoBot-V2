# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 18:21
# @Author  : KimmyXYC
# @File    : xiatou.py
# @Software: PyCharm
import re
import aiohttp
import datetime
import pytz
import asyncpg
from loguru import logger
from utils.yaml import BotConfig
from utils.postgres import BotDatabase

async def handle_xiatou(bot, message):
    if message.content_type == 'text':
        text_content = message.text
    else:
        text_content = message.caption
        if text_content is None:
            return

    pattern = r".*(?:jio|狱卒|玉足|脚丫|脚丫子|脚趾|脚趾头|嫩足|裸足|小脚|小足|脚板|脚掌|脚背|足尖|脚丫丫|放我嘴里|塞我嘴里).*"
    if re.search(pattern, text_content, re.IGNORECASE):
        count = await increment_today_count_pg()
        logger.info(f"[XiaTou][{message.chat.id}]: {text_content}")
        logger.success(f"[XiaTou][{message.chat.id}]: Regular Match Success")
        await bot.reply_to(message, f"#下头\ninb 老师，这是你今天第 {count} 次下头\n\n本次结果由正则判断")
        return
    else:
        pattern = r".*(?:脚|足|舔|嘴里|性|冲|导|萝莉|美少女|自慰).*"
        if re.search(pattern, text_content, re.IGNORECASE):
            url = f"https://api.cloudflare.com/client/v4/accounts/{BotConfig['xiatou']['cloudflare_account_id']}/ai/run/@cf/qwen/qwen1.5-14b-chat-awq"
            headers = {
                "Authorization": f"Bearer {BotConfig['xiatou']['cloudflare_auth_token']}"
            }
            data = {
                "messages": [
                    {
                        "role": "system",
                        "content":
                        '''
下面我将给你一些句子，请判断是否让人感到“下头”（即引发恶心、不适或厌恶）。仅当句子涉及以下四类内容时回答 **true**，否则回答 **false**：

**触发true的核心类型：**
1. **性暗示**（含身体部位/性行为的描述）  
2. **恋童**（明示或暗示未成年人）  
3. **物化他人**（将人视为物品/工具）  
4. **对身体部位的性化评价**（如“脚好看”“胸大”等，即使无直接性行为描述）
5. **直白的自慰描述**（如“导”“冲”“手冲”等）

**判断原则：**
- 忽略语法错误或表达风格，专注内容本质  
- 医学/职业等客观描述除外（如“模特需要脚型匀称”）  
- 针对未成年人的身体评价 **一律判 true**

**示例：**  
✅ 明确触发 **true**：  
- `今天导了10发` → 直白自慰描述
- `我每天都冲` → 直白自慰描述
- `现在 还有云漓的玉足可以舔` → 物化+性暗示  
- `算了 我还是去舔萝莉玉足吧` → 恋童+性暗示  
- `她的脚真好看，想摸` → 身体部位性化评价
- `女同事的脚香香的` → 物化+性暗示  
- `这萝莉脚丫白嫩` → 恋童+身体部位评价  
- `我只要纯纯的美少女` → 恋童+物化他人

❌ 明确触发 **false**：  
- `今天去超市买了苹果` → 中性内容  
- `过度自慰可能影响健康` → 医学建议
- `儿童节该送孩子球鞋` → 无身体评价  
- `游泳运动员脚掌宽大` → 客观身体描述（职业相关）  
- `她脚踝扭伤了` → 医学描述  
- `模特需要脚型匀称` → 职业需求
- `有水珠在里边导致的接触不良` → 技术问题描述

严格只输出 **true** 或 **false**。
                        '''
                    },
                    {
                        "role": "user",
                        "content": message.text
                    }

                ]
            }
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(url, headers=headers, json=data) as response:
                    response_json = await response.json()
            if response_json["result"]["response"] == "true":
                count = await increment_today_count_pg()
                logger.info(f"[XiaTou][{message.chat.id}]: {text_content}")
                logger.success(f"[XiaTou][{message.chat.id}]: AI Match Success")
                await bot.reply_to(message, f"#下头\ninb 老师，这是你今天第 {count} 次下头\n\n本次结果由 AI 判断")
                return
    return


async def increment_today_count_pg() -> int:
    ts = get_today_midnight_ts_utc8()
    conn = BotDatabase.conn
    try:
        result = await conn.execute(
            "UPDATE xiatou SET count = count + 1 WHERE time = $1",
            ts
        )
        if result == 'UPDATE 0':
            await conn.execute(
                "INSERT INTO xiatou (time, count) VALUES ($1, 1) ON CONFLICT (time) DO NOTHING",
                ts
            )
        row = await conn.fetchrow(
            "SELECT count FROM xiatou WHERE time = $1",
            ts
        )
        return row['count'] if row else 0
    except asyncpg.PostgresError as e:
        logger.error(f"[XiaTou][Postgres Error]: {e}")
        return 0


def get_today_midnight_ts_utc8() -> int:
    tz = pytz.timezone('Asia/Shanghai')  # UTC+8
    now = datetime.datetime.now(tz)
    midnight = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=tz)
    return int(midnight.timestamp())
