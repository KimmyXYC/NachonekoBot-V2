# -*- coding: utf-8 -*-

import glob
import json
import os


BASE = r"C:\Users\Kimmy\PycharmProjects\NachonekoBot-V2\utils\i18n\zh-CN\plugins"


PLUGIN_META = {
    "bc": {
        "meta.description": "货币换算工具（支持多法币汇率源与加密货币）",
        "command.description.bc": "货币换算",
        "command.help.bc": "/bc [Amount] [Currency_From] [Currency_To] - 货币换算（法币支持欧盟/银联/Mastercard/Visa 多汇率源）\nInline: @NachoNekoX_bot bc [Amount] [Currency_From] [Currency_To]",
    },
    "bin": {
        "meta.description": "银行卡 BIN 查询",
        "command.description.bin": "查询银行卡 BIN 信息",
        "command.help.bin": "/bin [Card_BIN] - 查询银行卡 BIN 信息\nInline: @NachoNekoX_bot bin [Card_BIN]",
    },
    "callanyone": {
        "meta.description": "趣味呼叫功能（医生 / MTF / 警察）",
        "command.description.calldoctor": "呼叫医生",
        "command.description.callmtf": "呼叫 MTF",
        "command.description.callpolice": "呼叫警察",
    },
    "dns": {
        "meta.description": "DNS 记录查询",
        "command.description.dns": "查询 DNS 记录",
    },
    "icp": {
        "meta.description": "ICP 备案查询",
        "command.description.icp": "查询域名 ICP 备案信息",
    },
    "ip": {
        "meta.description": "IP 地址查询",
        "command.description.ip": "查询 IP/域名信息",
    },
    "keybox": {
        "meta.description": "Keybox 校验工具",
        "command.description.check": "校验 keybox.xml 文件",
        "command.help.check": "/check - 校验 keybox.xml 文件",
    },
    "lock": {
        "meta.description": "群命令锁定管理",
        "command.description.lock": "锁定群内命令",
        "command.description.unlock": "解锁群内命令",
        "command.description.list": "列出群内已锁定命令",
        "command.help.lock": "/lock [Command] - 锁定群内命令",
        "command.help.unlock": "/unlock [Command] - 解锁群内命令",
        "command.help.list": "/list - 列出群内已锁定命令",
    },
    "long_image_cutter": {
        "meta.description": "自动将长图裁切为多张 19.5:9 图片，并保留 3:19.5 纵向重叠；裁片高度基于 19.5:9，可微调以保证尺寸一致（仅对以文件方式发送的图片生效）。",
        "meta.display_name": "长图裁切器",
    },
    "lottery": {
        "meta.description": "抽奖系统",
        "command.description.lottery": "发起抽奖",
        "command.help.lottery": "/lottery [Winners]/[Participants] [Keyword] [Title] - 发起抽奖",
    },
    "mcstatus": {
        "meta.description": "Minecraft 服务器状态查询",
        "command.description.mc": "查询 Minecraft 服务器状态（自动识别 Java/基岩）",
        "command.description.mcje": "查询 Minecraft Java 版服务器状态",
        "command.description.mcbe": "查询 Minecraft 基岩版服务器状态",
        "command.help.mc": "/mcstatus [服务器地址:端口] - 查询 Minecraft 服务器状态（自动识别 Java/基岩）\nInline: @NachoNekoX_bot mc [服务器地址:端口]",
    },
    "ocr": {
        "meta.description": "OCR 文字识别（阿里云 qwen-vl-ocr）",
        "command.description.ocr": "识别图片文字",
    },
    "ping": {
        "meta.description": "Ping 连通性测试",
        "command.description.ping": "执行 Ping 测试",
    },
    "quote_reply": {
        "meta.description": "/$ 与 \\$ 动作引用插件",
        "meta.display_name": "动作引用",
    },
    "rdap": {
        "meta.description": "RDAP 查询（域名/IP/ASN）",
        "command.description.rdap": "查询 RDAP 信息",
        "command.help.rdap": "/rdap [Domain/IP/ASN] - 查询 RDAP 信息\nInline: @NachoNekoX_bot rdap [Domain/IP/ASN]\n支持格式：域名(example.com)、IP(1.1.1.1)、ASN(AS13335 或 13335)",
    },
    "remake": {
        "meta.description": "转生系统",
        "command.description.remake": "开始转生",
        "command.description.remake_data": "查看转生数据",
        "command.help.remake": "/remake - 开始转生",
        "command.help.remake_data": "/remake_data - 查看转生数据",
    },
    "shorturl": {
        "meta.description": "短链接生成工具",
        "command.description.short": "生成短链接",
    },
    "stats": {
        "meta.description": "群聊发言统计排行（支持日/周/月/年与自定义时间范围）",
        "meta.display_name": "发言统计记录器",
        "command.description.stats": "查看发言排行榜",
        "command.description.dragon": "查看龙王总榜",
        "command.help.stats": "/stats - 今日统计\n/stats 5h - 近 5 小时统计\n/stats 4d - 近 4 日统计\n/stats 3w - 近 3 周统计\n/stats 2m - 近 2 月统计\n/stats 1y - 近 1 年统计\n/stats 2026-02-25 - 指定日期统计\n/stats 2026/02/25 - 指定日期统计\n/stats 20260225 - 指定日期统计\n",
        "command.help.dragon": "/dragon - 龙王总榜\n",
    },
    "status": {
        "meta.description": "系统状态查询（仅管理员）",
        "command.description.status": "获取机器人状态信息",
    },
    "tcping": {
        "meta.description": "TCP 端口连通性测试",
        "command.description.tcping": "执行 TCP Ping 测试",
    },
    "trace": {
        "meta.description": "路由追踪工具（使用 nexttrace）",
        "command.description.trace": "追踪网络路由",
    },
    "weather": {
        "meta.description": "天气查询",
        "command.description.weather": "查询天气信息",
    },
    "whois": {
        "meta.description": "Whois 域名查询",
        "command.description.whois": "查询 Whois 信息",
    },
    "xiatou": {
        "meta.description": "下头检测系统（仅对配置用户生效）",
    },
    "xibao": {
        "meta.description": "喜报/悲报/通报/警报 生成器",
        "meta.display_name": "报告图片生成器",
    },
}


GLOBAL_RUNTIME = {
    "Banned successfully.": "封禁成功。",
    "File size is too large": "文件大小超限。",
    "Local Bot API enabled but file path is not accessible.": "已启用本地 Bot API，但文件路径不可访问。",
    "No keybox has been banned.": "当前没有被封禁的 keybox。",
    "Please reply to a keybox.xml file.": "请回复一份 keybox.xml 文件。",
    "This keybox has been banned.": "该 keybox 已被封禁。",
    "This keybox has not been banned.": "该 keybox 未被封禁。",
    "Unbanned successfully.": "解除封禁成功。",
    "Usage: /ban_keybox <serial_number>\nExample: /ban_keybox 1a2b3c4d5e6f": "用法：/ban_keybox <serial_number>\n示例：/ban_keybox 1a2b3c4d5e6f",
    "Usage: /unban_keybox <serial_number>\nExample: /unban_keybox 1a2b3c4d5e6f": "用法：/unban_keybox <serial_number>\n示例：/unban_keybox 1a2b3c4d5e6f",
    "数量必须是有效的数字": "数量必须是有效数字。",
    "出错了呜呜呜 ~ 无效的参数。请提供4到8位数字的BIN号码。": "参数无效，请提供 4 到 8 位数字的 BIN 号。",
    "请提供有效的BIN号码（4到8位数字）": "请提供有效的 BIN 号（4 到 8 位数字）。",
    "您无权使用此功能": "你无权使用该功能。",
    "无法识别消息发送者": "无法识别消息发送者。",
    "本群未锁定任何命令": "本群当前未锁定任何命令。",
    "机器人配置错误：bot_id 无效": "机器人配置错误：bot_id 无效。",
    "请先将机器人设置为管理员并赋予删除消息权限": "请先将机器人设为管理员并授予删除消息权限。",
    "人数必须是整数": "人数必须为整数。",
    "只有群管理员可以使用此命令。": "仅群管理员可使用该命令。",
    "奖品数、人数、关键字和标题不能为空": "奖品数、人数、关键字和标题不能为空。",
    "奖品数、人数不能为空": "奖品数和人数不能为空。",
    "奖品数不能超过人数": "奖品数不能超过人数。",
    "强制开奖成功。": "强制开奖成功。",
    "有抽奖活动正在进行，请稍后再试": "当前有抽奖活动正在进行，请稍后再试。",
    "本群暂无正在进行的抽奖活动。": "本群暂无正在进行的抽奖活动。",
    "请在群组中使用该命令。": "请在群组中使用该命令。",
    "请输入 奖品数、人数等参数 或者 强制开奖\n\n例如 `/lottery 1/10 参加 测试`": "请输入奖品数、人数等参数，或使用“强制开奖”。\n\n例如：`/lottery 1/10 参加 测试`",
    "请提供服务器地址，格式：/mc 服务器地址:端口\n例如：/mc mc.hypixel.net": "请提供服务器地址，格式：/mc 服务器地址:端口\n例如：/mc mc.hypixel.net",
    "OCR识别中...": "OCR 识别中...",
    "格式错误，格式应为 /ocr [自定义提示词]": "格式错误，应为：/ocr [自定义提示词]",
    "请回复一张图片或图片文件后再使用 /ocr [自定义提示词]。": "请先回复一张图片或图片文件，再使用 /ocr [自定义提示词]。",
    "❌ 无效的目标地址。请提供有效的域名或IP地址。": "❌ 目标地址无效，请提供有效域名或 IP 地址。",
    "请提供要 ping 的目标地址，例如: /ping example.com": "请提供要 Ping 的目标地址，例如：/ping example.com",
    "您还没有 remake 过呢，快 /remake 吧": "你还没有转生记录，快试试 /remake 吧。",
    "查询失败，请稍后再试。": "查询失败，请稍后重试。",
    "生成失败, 后端地址未设置": "生成失败：后端地址未配置。",
    "用法：/stats [Nh|Nd|Nw|Nm|Ny|YYYY-MM-DD|YYYY/MM/DD|YYYYMMDD] 例如 /stats 1h /stats 4d /stats 3w /stats 2m /stats 4y /stats 2026-02-25 /stats 2026/02/25 /stats 20260225": "用法：/stats [Nh|Nd|Nw|Nm|Ny|YYYY-MM-DD|YYYY/MM/DD|YYYYMMDD]\n例如：/stats 1h /stats 4d /stats 3w /stats 2m /stats 4y /stats 2026-02-25 /stats 2026/02/25 /stats 20260225",
    "该统计仅支持群组使用。": "该统计仅支持在群组中使用。",
    "龙王总榜\n\n暂无龙王统计数据": "龙王总榜\n\n暂无龙王统计数据。",
    "❌ 无效的端口号。端口号应为1-65535之间的整数。": "❌ 端口号无效，应为 1-65535 之间的整数。",
    "❌ 请提供目标主机和端口，格式: /tcping 主机:端口": "❌ 请提供目标主机和端口，格式：/tcping 主机:端口",
    "❌ 无效的协议类型，请使用 T (TCP) 或 U (UDP)": "❌ 协议类型无效，请使用 T (TCP) 或 U (UDP)。",
    "❌ 无效的目标地址，请输入有效的 IP 地址或域名": "❌ 目标地址无效，请输入有效的 IP 地址或域名。",
    "❌ 未找到 nexttrace 命令，请先安装 nexttrace": "❌ 未找到 nexttrace 命令，请先安装 nexttrace。",
    "❌ 端口号必须在 1-65535 之间": "❌ 端口号必须在 1-65535 之间。",
    "❌ 端口必须是数字": "❌ 端口必须为数字。",
    "用法: /trace <目标地址> [T/U] [端口]\nT = TCP, U = UDP, 不指定则使用 ICMP\n示例: /trace 1.1.1.1\n      /trace example.com T 443": "用法：/trace <目标地址> [T/U] [端口]\nT = TCP，U = UDP，不指定则使用 ICMP\n示例：/trace 1.1.1.1\n      /trace example.com T 443",
    "发生未知错误": "发生未知错误。",
}


def main():
    for path in sorted(glob.glob(os.path.join(BASE, "*.json"))):
        plugin = os.path.basename(path)[:-5]
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for key, value in PLUGIN_META.get(plugin, {}).items():
            if key in data:
                data[key] = value

        for key, value in GLOBAL_RUNTIME.items():
            if key in data:
                data[key] = value

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    print("Polished zh-CN plugin locale files.")


if __name__ == "__main__":
    main()
