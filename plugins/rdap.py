# -*- coding: utf-8 -*-
# @Time    : 2026/1/19 13:27
# @Author  : KimmyXYC
# @File    : rdap.py
# @Software: PyCharm
import re
import json
import idna
import aiohttp
from telebot import types
from loguru import logger
from app.utils import command_error_msg

# ==================== 插件元数据 ====================
__plugin_name__ = "rdap"
__version__ = "1.1.0"
__author__ = "KimmyXYC"
__description__ = "RDAP 域名、IP和ASN查询"
__commands__ = ["rdap"]
__command_descriptions__ = {"rdap": "查询 RDAP 信息"}
__command_help__ = {
    "rdap": "/rdap [Domain/IP/ASN] - 查询 RDAP 信息\nInline: @NachoNekoX_bot rdap [Domain/IP/ASN]\n支持格式：域名(example.com)、IP地址(1.1.1.1)、ASN(AS13335或13335)"
}

# RDAP Bootstrap服务器
RDAP_BOOTSTRAP_URL = "https://rdap-bootstrap.arin.net/bootstrap"


# ==================== 核心功能 ====================
def validate_rdap_input(data: str) -> tuple[bool, str]:
    """
    验证 RDAP 输入，防止命令注入攻击，支持国际化域名（IDN）和ASN
    :param data: 待验证的域名、IP地址或ASN（可以是中文域名等）
    :return: (是否有效, 错误信息或转换后的ASCII域名/IP/ASN)
    """
    # 去除首尾空格
    data = data.strip()

    # 检查长度限制
    if len(data) > 255:
        return False, "输入过长，域名、IP地址或ASN不应超过255个字符"

    if not data:
        return False, "输入不能为空"

    # 检查ASN格式（AS123456 或 123456）
    asn_pattern = r"^[Aa][Ss](\d+)$"
    asn_match = re.match(asn_pattern, data)
    if asn_match:
        asn_number = asn_match.group(1)
        try:
            asn_int = int(asn_number)
            if 0 <= asn_int <= 4294967295:  # 32位ASN范围
                return True, f"AS{asn_number}"
            else:
                return False, "ASN号码超出有效范围（0-4294967295）"
        except ValueError:
            return False, "无效的ASN格式"

    # 纯数字也可能是ASN
    if data.isdigit():
        try:
            asn_int = int(data)
            if 0 <= asn_int <= 4294967295:
                return True, f"AS{data}"
            else:
                return False, "ASN号码超出有效范围（0-4294967295）"
        except ValueError:
            pass

    # 检查是否包含危险字符
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
            return False, f"输入包含危险字符: {char}"

    # 尝试处理国际化域名（IDN）转换为 Punycode
    try:
        # 如果包含非ASCII字符，尝试转换为Punycode
        if not data.isascii():
            # 分离可能的端口或路径
            domain_part = data.split("/")[0].split(":")[0]

            # 尝试 IDN 编码
            try:
                encoded_domain = idna.encode(domain_part).decode("ascii")
                data = encoded_domain
                logger.info(f"国际化域名已转换: {domain_part} -> {encoded_domain}")
            except idna.IDNAError as e:
                return False, f"无效的国际化域名格式: {str(e)}"
    except Exception as e:
        logger.error(f"IDN转换错误: {e}")
        return False, f"域名转换失败: {str(e)}"

    # 现在检查转换后的ASCII字符
    # 只允许字母、数字、点、连字符、冒号（IPv6）
    if not re.match(r"^[a-zA-Z0-9.\-:]+$", data):
        return False, "输入包含非法字符，只允许字母、数字、点、连字符和冒号"

    # 验证域名格式（简单验证）
    if (
        ".." in data
        or data.startswith(".")
        or data.startswith("-")
        or data.endswith("-")
    ):
        return False, "域名格式不正确"

    # IPv4 格式验证
    ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if re.match(ipv4_pattern, data):
        parts = data.split(".")
        try:
            if all(0 <= int(part) <= 255 for part in parts):
                return True, data
            else:
                return False, "无效的IPv4地址"
        except ValueError:
            return False, "无效的IPv4地址格式"

    # IPv6 格式简单验证
    if ":" in data and "." not in data:
        if data.count("::") > 1:
            return False, "无效的IPv6地址格式"
        return True, data

    # 域名长度和格式检查
    labels = data.split(".")
    for label in labels:
        if len(label) > 63:
            return False, "域名标签不能超过63个字符"
        if not label:
            return False, "域名标签不能为空"

    return True, data


def format_rdap_response(rdap_data: dict) -> str:
    """
    格式化 RDAP 响应数据为可读文本
    :param rdap_data: RDAP JSON 响应
    :return: 格式化的文本
    """
    lines = []

    # 对象类名
    if "objectClassName" in rdap_data:
        lines.append(f"Object Type: {rdap_data['objectClassName']}")

    # 处理域名信息
    if "ldhName" in rdap_data:
        lines.append(f"Domain: {rdap_data['ldhName']}")

    # 处理ASN信息
    if "startAutnum" in rdap_data:
        lines.append(f"Start ASN: AS{rdap_data['startAutnum']}")
    if "endAutnum" in rdap_data:
        lines.append(f"End ASN: AS{rdap_data['endAutnum']}")
    if "name" in rdap_data and rdap_data["objectClassName"] == "autnum":
        lines.append(f"Name: {rdap_data['name']}")
    if "type" in rdap_data and rdap_data["objectClassName"] == "autnum":
        lines.append(f"Type: {rdap_data['type']}")
    if "country" in rdap_data:
        lines.append(f"Country: {rdap_data['country']}")

    # 处理IP网络信息
    if "startAddress" in rdap_data:
        lines.append(f"Start Address: {rdap_data['startAddress']}")
    if "endAddress" in rdap_data:
        lines.append(f"End Address: {rdap_data['endAddress']}")
    if "ipVersion" in rdap_data:
        lines.append(f"IP Version: v{rdap_data['ipVersion']}")
    if "cidr0_cidrs" in rdap_data:
        cidrs = [
            f"{c.get('v4prefix') or c.get('v6prefix')}/{c.get('length')}"
            for c in rdap_data["cidr0_cidrs"]
        ]
        lines.append(f"CIDR: {', '.join(cidrs)}")

    # 处理句柄
    if "handle" in rdap_data:
        lines.append(f"Handle: {rdap_data['handle']}")

    # 处理状态
    if "status" in rdap_data and rdap_data["status"]:
        lines.append(f"Status: {', '.join(rdap_data['status'])}")

    # 处理实体（注册商、注册人等）
    if "entities" in rdap_data:
        for entity in rdap_data["entities"]:
            roles = entity.get("roles", [])
            if roles:
                lines.append(f"\n[{', '.join(roles)}]")

            # vCard 信息
            if "vcardArray" in entity:
                vcard = entity["vcardArray"]
                if len(vcard) > 1:
                    for item in vcard[1]:
                        if isinstance(item, list) and len(item) >= 4:
                            field_name = item[0]
                            field_value = item[3]

                            # 格式化常见字段
                            if field_name == "fn":
                                lines.append(f"  Name: {field_value}")
                            elif field_name == "org":
                                lines.append(f"  Organization: {field_value}")
                            elif field_name == "email":
                                lines.append(f"  Email: {field_value}")
                            elif field_name == "tel":
                                lines.append(f"  Phone: {field_value}")
                            elif field_name == "adr":
                                if isinstance(field_value, list):
                                    # 展平嵌套的list，将所有元素转换为字符串
                                    def flatten_to_str(item):
                                        if isinstance(item, list):
                                            return ", ".join(
                                                flatten_to_str(sub)
                                                for sub in item
                                                if sub
                                            )
                                        return str(item) if item else ""

                                    addr = [flatten_to_str(v) for v in field_value if v]
                                    if addr:
                                        lines.append(f"  Address: {', '.join(addr)}")

    # 处理名称服务器
    if "nameservers" in rdap_data:
        lines.append("\nName Servers:")
        for ns in rdap_data["nameservers"]:
            if "ldhName" in ns:
                lines.append(f"  - {ns['ldhName']}")

    # 处理事件（创建、更新、过期等）
    if "events" in rdap_data:
        lines.append("\nEvents:")
        for event in rdap_data["events"]:
            action = event.get("eventAction", "unknown")
            date = event.get("eventDate", "N/A")
            action_map = {
                "registration": "Registration",
                "last changed": "Last Changed",
                "expiration": "Expiration",
                "last update of RDAP database": "Last Update of RDAP Database",
            }
            action_en = action_map.get(action, action)
            lines.append(f"  {action_en}: {date}")

    # 处理备注
    if "remarks" in rdap_data:
        for remark in rdap_data["remarks"]:
            if "description" in remark:
                desc = "\n    ".join(remark["description"])
                if remark.get("title"):
                    lines.append(f"\nRemarks ({remark['title']}):\n    {desc}")

    # 处理链接
    if "links" in rdap_data:
        for link in rdap_data["links"]:
            if link.get("rel") == "self" and link.get("href"):
                lines.append(f"\nRDAP Link: {link['href']}")
                break

    return "\n".join(lines) if lines else "No displayable information found"


async def rdap_query(data: str) -> tuple[bool, str]:
    """
    执行 RDAP 查询
    :param data: 域名、IP地址或ASN
    :return: (是否成功, 结果信息)
    """
    # 验证输入
    is_valid, validated_data = validate_rdap_input(data)
    if not is_valid:
        return False, f"输入验证失败: {validated_data}"

    try:
        # 判断查询类型
        is_asn = validated_data.startswith("AS")
        is_ipv4 = re.match(r"^(\d{1,3}\.){3}\d{1,3}$", validated_data)
        is_ipv6 = ":" in validated_data and "." not in validated_data

        # 构建RDAP查询URL
        if is_asn:
            # ASN查询，提取数字部分
            asn_number = validated_data[2:]  # 去掉"AS"前缀
            query_url = f"{RDAP_BOOTSTRAP_URL}/autnum/{asn_number}"
        elif is_ipv4 or is_ipv6:
            # IP查询
            query_url = f"{RDAP_BOOTSTRAP_URL}/ip/{validated_data}"
        else:
            # 域名查询
            query_url = f"{RDAP_BOOTSTRAP_URL}/domain/{validated_data}"

        # 发送HTTP请求
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(query_url) as response:
                if response.status == 404:
                    return False, "未找到RDAP记录"
                elif response.status != 200:
                    return False, f"RDAP查询失败: HTTP {response.status}"

                # 解析JSON响应
                rdap_data = await response.json()

                # 格式化输出
                formatted_result = format_rdap_response(rdap_data)
                return True, formatted_result

    except aiohttp.ClientError as e:
        logger.error(f"RDAP查询网络错误: {e}")
        return False, f"网络请求失败: {str(e)}"
    except json.JSONDecodeError as e:
        logger.error(f"RDAP响应解析错误: {e}")
        return False, "无法解析RDAP响应"
    except Exception as e:
        logger.error(f"RDAP查询错误: {e}")
        return False, f"查询失败: {str(e)}"


async def query_rdap_text(data: str) -> str:
    """生成与 `/rdap` 命令一致的输出文本，用于命令与 Inline 复用（MarkdownV2）。"""
    status, result = await rdap_query(data)
    if not status:
        return f"请求失败: `{result}`"
    return f"```\n{result}\n```"


async def handle_rdap_command(bot, message: types.Message):
    """
    处理 RDAP 命令
    :param bot: Bot 对象
    :param message: 消息对象
    """
    data = message.text.split()[1]
    msg = await bot.reply_to(
        message, f"正在查询 {data} RDAP 信息...", disable_web_page_preview=True
    )
    text = await query_rdap_text(data)
    await bot.edit_message_text(
        text, message.chat.id, msg.message_id, parse_mode="MarkdownV2"
    )


async def handle_rdap_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot rdap [Domain/IP/ASN]"""
    query = (inline_query.query or "").strip()
    tokens = query.split()

    if len(tokens) != 2 or tokens[0].lower() != "rdap":
        usage = (
            "用法：rdap [Domain/IP/ASN]\n支持格式：域名、IP地址、ASN(AS13335或13335)"
        )
        result = types.InlineQueryResultArticle(
            id="rdap_usage",
            title="RDAP 查询",
            description="用法：rdap [Domain/IP/ASN]",
            input_message_content=types.InputTextMessageContent(usage),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    target = tokens[1]
    result_text = await query_rdap_text(target)
    result = types.InlineQueryResultArticle(
        id=f"rdap_{target}",
        title=f"RDAP：{target}",
        description="发送查询结果",
        input_message_content=types.InputTextMessageContent(
            result_text, parse_mode="MarkdownV2"
        ),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def rdap_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            await handle_rdap_command(bot, message)
        else:
            await bot.reply_to(message, command_error_msg("rdap", "Domain/IP/ASN"))

    middleware.register_command_handler(
        commands=["rdap"],
        callback=rdap_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    middleware.register_inline_handler(
        callback=handle_rdap_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: (
            bool(getattr(q, "query", None))
            and q.query.strip().lower().startswith("rdap")
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
