# -*- coding: utf-8 -*-
# @Time    : 2025/11/07 18:45
# @Author  : Junie (JetBrains)
# @File    : plugin_settings.py
# @Software: PyCharm
"""
插件设置面板（Dashboard）工具方法

- 仅用于控制器中的核心命令与回调，不作为插件通过中间件注册。
- 提供：权限检查、面板文本与键盘构建、可切换插件列表获取。
"""

from typing import List, Tuple, Dict
from loguru import logger
from telebot import types
from app.security.permissions import has_group_admin_permission


async def has_change_info_permission(bot, chat_id: int, user_id: int) -> bool:
    """检查用户是否具备"更改群信息"权限（群主或管理员可更改信息）。"""
    try:
        return await has_group_admin_permission(
            bot,
            chat_id,
            user_id,
            required_permission="can_change_info",
            default_when_missing=True,
            allow_bot_admin=True,
        )
    except Exception as e:
        logger.error(f"检查群权限失败 chat={chat_id}, user={user_id}: {e}")
        return False


def build_keyboard_and_text(
    items: List[Dict[str, object]],
) -> Tuple[str, types.InlineKeyboardMarkup]:
    """根据项目列表与状态构造文本与 InlineKeyboard。"""
    text_lines = ["🔧 插件/定时任务开关状态："]
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for item in items:
        enabled = bool(item.get("enabled"))
        label = str(item.get("label"))
        kind = str(item.get("kind"))
        key = str(item.get("key"))
        mark = "✅" if enabled else "❌"
        text_lines.append(f"• {mark} {label}")
        btn = types.InlineKeyboardButton(
            text=f"{mark}{label}", callback_data=f"plg_toggle:{kind}:{key}"
        )
        buttons.append(btn)
    # 两列排布，使用 add() 方法添加按钮
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            kb.add(buttons[i], buttons[i + 1])
        else:
            kb.add(buttons[i])
    # 添加关闭按钮（单独一行）
    close_btn = types.InlineKeyboardButton(text="❌ 关闭", callback_data="plg_close")
    kb.add(close_btn)
    return "\n".join(text_lines), kb


async def get_toggleable_plugins(middleware) -> List[Tuple[str, str]]:
    """从中间件获取可切换插件列表。"""
    plugins = list(getattr(middleware, "toggleable_plugins", {}).items())
    plugins.sort(key=lambda item: item[0])
    return plugins


async def get_toggleable_jobs(middleware) -> List[Tuple[str, str]]:
    """从中间件获取可切换定时任务列表。"""
    jobs = list(getattr(middleware, "scheduled_jobs", {}).items())
    jobs.sort(key=lambda item: item[0])
    return jobs
