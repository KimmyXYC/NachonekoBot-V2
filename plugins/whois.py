# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 15:50
# @Author  : KimmyXYC
# @File    : whois.py
# @Software: PyCharm
import asyncio
import re
import idna
from telebot import types
from loguru import logger
from app.utils import command_error_msg
from utils.i18n import _t

# ==================== 插件元数据 ====================
__plugin_name__ = "whois"
__version__ = "1.2.0"
__author__ = "KimmyXYC"
__description__ = "Whois 域名查询"
__commands__ = ["whois"]
__command_category__ = "network"
__command_order__ = {"whois": 60}
__command_descriptions__ = {"whois": "查询 Whois 信息"}
__command_help__ = {
    "whois": "/whois [Domain] - 查询 Whois 信息\nInline: @NachoNekoX_bot whois [Domain]"
}


# ==================== 核心功能 ====================
def validate_whois_input(data: str) -> tuple[bool, str]:
    """
    验证 whois 输入，防止命令注入攻击，支持国际化域名（IDN）
    :param data: 待验证的域名或IP地址（可以是中文域名等）
    :return: (是否有效, 错误信息或转换后的ASCII域名/IP)
    """
    # 去除首尾空格
    data = data.strip()

    # 检查长度限制
    if len(data) > 255:
        return False, _t("error.input_too_long")

    if not data:
        return False, _t("error.input_empty")

    # 检查是否包含命令注入常见字符（在转换前检查）
    dangerous_chars = [
        ";",
        "&",
        "|",
        "$",
        "`",
        "(",
        ")",
        "<",
        ">",
        "\n",
        "\r",
        "\\",
        '"',
        "'",
    ]
    for char in dangerous_chars:
        if char in data:
            return False, _t("error.dangerous_char", char=char)

    # 尝试处理国际化域名（IDN）转换为 Punycode
    try:
        # 如果包含非ASCII字符，尝试转换为Punycode
        if not data.isascii():
            # 分离可能的端口或路径
            domain_part = data.split("/")[0].split(":")[0]

            # 尝试 IDN 编码
            try:
                encoded_domain = idna.encode(domain_part).decode("ascii")
                # 如果原始输入有额外部分（如端口），保留它们
                if "/" in data or ":" in data:
                    # 重建完整字符串（这里我们主要关注域名部分）
                    data = encoded_domain
                else:
                    data = encoded_domain
                logger.info(f"国际化域名已转换: {domain_part} -> {encoded_domain}")
            except idna.IDNAError as e:
                return False, _t("error.invalid_idn_format", reason=str(e))
    except Exception as e:
        logger.error(f"IDN转换错误: {e}")
        return False, _t("error.domain_conversion_failed", reason=str(e))

    # 现在检查转换后的ASCII字符
    # 只允许字母、数字、点、连字符、冒号（IPv6）、斜杠（CIDR）
    if not re.match(r"^[a-zA-Z0-9.\-:/]+$", data):
        return False, _t("error.illegal_chars")

    # 验证域名格式（简单验证）
    # 域名标签不能以连字符开头或结尾，不能连续点
    if (
        ".." in data
        or data.startswith(".")
        or data.startswith("-")
        or data.endswith("-")
    ):
        return False, _t("error.invalid_domain_format")

    # IPv4 格式验证
    ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if re.match(ipv4_pattern, data):
        parts = data.split(".")
        try:
            if all(0 <= int(part) <= 255 for part in parts):
                return True, data
            else:
                return False, _t("error.invalid_ipv4")
        except ValueError:
            return False, _t("error.invalid_ipv4_format")

    # IPv6 格式简单验证
    if ":" in data and "." not in data:  # 排除IPv4:port的情况
        # 基本的IPv6格式检查
        if data.count("::") > 1:
            return False, _t("error.invalid_ipv6_format")
        return True, data

    # 域名长度和格式检查
    labels = data.split(".")
    for label in labels:
        if len(label) > 63:
            return False, _t("error.label_too_long")
        if not label:
            return False, _t("error.label_empty")

    return True, data


async def query_whois_text(data: str) -> str:
    """生成与 `/whois` 命令一致的输出文本，用于命令与 Inline 复用（MarkdownV2）。"""
    status, result = await whois_check(data)
    if not status:
        return _t("error.request_failed", reason=result)
    return f"`{result}`"


async def handle_whois_command(bot, message: types.Message):
    """
    处理 Whois 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    data = message.text.split()[1]
    msg = await bot.reply_to(
        message,
        _t("status.whois_querying", target=data),
        disable_web_page_preview=True,
    )
    text = await query_whois_text(data)
    await bot.edit_message_text(
        text, message.chat.id, msg.message_id, parse_mode="MarkdownV2"
    )


async def handle_whois_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot whois [Domain]"""
    query = (inline_query.query or "").strip()
    tokens = query.split()

    if len(tokens) != 2 or tokens[0].lower() != "whois":
        usage = _t("inline.usage_text")
        result = types.InlineQueryResultArticle(
            id="whois_usage",
            title=_t("inline.usage_title"),
            description=_t("inline.usage_description"),
            input_message_content=types.InputTextMessageContent(usage),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    domain = tokens[1]
    result_text = await query_whois_text(domain)
    result = types.InlineQueryResultArticle(
        id=f"whois_{domain}",
        title=_t("inline.result_title", domain=domain),
        description=_t("inline.send_result_description"),
        input_message_content=types.InputTextMessageContent(
            result_text, parse_mode="MarkdownV2"
        ),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


async def whois_check(data):
    """
    Perform a WHOIS check on a domain or IP address using command-line whois.
    :param data: The domain or IP address to check.
    :return: A tuple containing the status and the result.
    """
    # 验证输入，防止命令注入
    is_valid, validated_data = validate_whois_input(data)
    if not is_valid:
        return False, _t("error.validation_failed", reason=validated_data)

    try:
        # Run whois command asynchronously with validated input
        process = await asyncio.create_subprocess_exec(
            "whois",
            validated_data,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="ignore").strip()
            return (
                False,
                _t(
                    "error.whois_command_failed",
                    reason=error_msg if error_msg else "Unknown error",
                ),
            )

        result = stdout.decode("utf-8", errors="ignore").strip()

        if not result or "No match" in result or "NOT FOUND" in result:
            return False, _t("error.no_whois_data")

        # Clean up the result - remove redacted info and common footer text
        lines = result.splitlines()
        filtered_result = []
        for line in lines:
            stripped = line.strip()
            # 跳过包含 REDACTED 的行
            if "REDACTED" in line:
                continue
            # 跳过包含特定提示文本的行
            if "Please query the" in line:
                continue
            # 跳过空行后面的冒号行（即只有标签没有内容的行）
            # 例如: "Admin Name:" 后面没有任何内容
            if ":" in stripped:
                # 分割标签和值
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    # 如果值为空，跳过这一行
                    if not value:
                        continue

            filtered_result.append(line)

        cleaned = "\n".join(filtered_result)

        # Remove common footer sections
        cleaned = cleaned.split("For more information")[0]
        cleaned = cleaned.split("RDAP TERMS OF SERVICE:")[0]
        cleaned = cleaned.split("TERMS OF SERVICE:")[0]
        cleaned = cleaned.split(">>> Last update of")[0]
        cleaned = cleaned.split("% This is the")[0]

        return True, cleaned.strip()

    except FileNotFoundError:
        return False, _t("error.whois_not_installed")
    except Exception as e:
        logger.error(f"Whois query error: {e}")
        return False, _t("error.whois_exec_failed", reason=str(e))


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def whois_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            await handle_whois_command(bot, message)
        else:
            await bot.reply_to(
                message,
                command_error_msg("whois", "Domain"),
            )

    middleware.register_command_handler(
        commands=["whois"],
        callback=whois_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    middleware.register_inline_handler(
        callback=handle_whois_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: (
            bool(getattr(q, "query", None))
            and q.query.strip().lower().startswith("whois")
        ),
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
