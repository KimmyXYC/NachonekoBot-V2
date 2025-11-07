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
from typing import List, Tuple
from loguru import logger
from telebot import types


async def has_change_info_permission(bot, chat_id: int, user_id: int) -> bool:
    """检查用户是否具备"更改群信息"权限（群主或管理员可更改信息）。"""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        status = getattr(member, 'status', None)
        if status == 'creator':
            return True
        if status == 'administrator':
            # TeleBot ChatMember 对象的权限字段
            return bool(getattr(member, 'can_change_info', True))
        return False
    except Exception as e:
        logger.error(f"检查群权限失败 chat={chat_id}, user={user_id}: {e}")
        return False


def build_keyboard_and_text(plugin_names: List[str], states: List[bool]) -> Tuple[str, types.InlineKeyboardMarkup]:
    """根据插件列表与状态构造文本与 InlineKeyboard。"""
    text_lines = ["🔧 插件开关状态："]
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for name, enabled in zip(plugin_names, states):
        mark = '✅' if enabled else '❌'
        text_lines.append(f"• {mark} {name}")
        btn = types.InlineKeyboardButton(
            text=f"{mark}{name}",
            callback_data=f"plg_toggle:{name}"
        )
        buttons.append(btn)
    # 两列排布，使用 add() 方法添加按钮
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            kb.add(buttons[i], buttons[i + 1])
        else:
            kb.add(buttons[i])
    # 添加关闭按钮（单独一行）
    close_btn = types.InlineKeyboardButton(
        text="❌ 关闭",
        callback_data="plg_close"
    )
    kb.add(close_btn)
    return "\n".join(text_lines), kb


async def get_toggleable_plugins(middleware) -> List[str]:
    """从中间件获取可切换插件列表。"""
    names = sorted(getattr(middleware, 'toggleable_plugins', set()))
    return names
