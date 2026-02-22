# -*- coding: utf-8 -*-
from loguru import logger

from utils.yaml import BotConfig


def is_bot_admin(user_id: int) -> bool:
    admin_ids = BotConfig.get("admin", {}).get("id", [])
    return user_id in admin_ids


async def has_group_admin_permission(
    bot,
    chat_id: int,
    user_id: int,
    required_permission: str = None,
    default_when_missing: bool = True,
    allow_bot_admin: bool = True,
) -> bool:
    if allow_bot_admin and is_bot_admin(user_id):
        return True

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        status = getattr(member, "status", None)

        if status == "creator":
            return True
        if status != "administrator":
            return False

        if not required_permission:
            return True

        return bool(getattr(member, required_permission, default_when_missing))
    except Exception as e:
        logger.debug(f"检查群权限失败 chat={chat_id}, user={user_id}: {e}")
        return False
