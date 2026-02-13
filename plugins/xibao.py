# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 21:30
# @Author  : KimmyXYC
# @File    : xibao.py
# @Software: PyCharm
from PIL import Image, ImageDraw, ImageFont
from telebot import types
from io import BytesIO
from loguru import logger

# ==================== 插件元数据 ====================
__plugin_name__ = "xibao"
__display_name__ = "生成喜报图片"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "喜报/悲报/通报/警报生成器"
__commands__ = []  # 这个插件通过自定义过滤器触发，不是命令
__toggleable__ = True  # 支持在群组中开关


# ==================== 核心功能 ====================
async def good_news(bot, message: types.Message, news_type):
    if news_type == 0:
        pic_dir = "res/pic/xibao.png"
        fill_color = "red"
        font_size = 65
    elif news_type == 1:
        pic_dir = "res/pic/beibao.png"
        fill_color = (50, 50, 50)
        font_size = 65
    elif news_type == 2:
        pic_dir = "res/pic/tongbao.png"
        fill_color = "white"
        font_size = 100
    elif news_type == 3:
        pic_dir = "res/pic/jingbao.png"
        fill_color = "white"
        font_size = 90
    else:
        await bot.reply_to(message, "发生未知错误")
        return
    img = Image.open(pic_dir).convert("RGB")
    text = message.text[2:]
    if text.startswith(" "):
        text = text[1:]
    if text.startswith("，") or text.startswith("。") or text.startswith(",") or text.startswith("."):
        text = text[1:]

    if text == "":
        return
    draw_text_centered(
        img,
        text=text,
        font_path='res/font/MiSans-Semibold.ttf',
        font_size=font_size,
        fill_color=fill_color,
        box_ratio=0.8,
        line_spacing=8
    )
    bio = BytesIO()
    bio.name = 'image.png'  # Telegram 会根据这个名字判断类型
    img.save(bio, 'PNG')  # 把 PIL 图像写入内存
    bio.seek(0)  # 重置指针到开头

    # 发送照片
    await bot.send_photo(message.chat.id, bio)


def draw_text_centered(
    img: Image.Image,
    text: str,
    font_path: str,
    font_size: int,
    fill_color,
    box_ratio: float = 0.8,
    line_spacing: int = 4
):
    """
    使用 PIL 在图片正中央绘制自动换行并整体居中的文本，可自定义文字颜色。

    :param img:           PIL.Image 对象
    :param text:          要绘制的文本（支持多行 \n）
    :param font_path:     字体文件路径（.ttf）
    :param font_size:     字号
    :param fill_color:    文字颜色，支持：
                          - RGB 三元组，如 (255, 0, 0)
                          - 十六进制字符串，如 '#FF0000'
                          - 颜色名，如 'white'
    :param box_ratio:     文本块占图宽高的比例，默认 0.8（即留出 10% 边距）
    :param line_spacing:  行间距像素，默认为 4
    """
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    # 计算可绘制区域
    box_w = int(img.width * box_ratio)
    box_h = int(img.height * box_ratio)
    # x0 = (img.width - box_w) // 2
    y0 = (img.height - box_h) // 2

    # 处理文本换行
    lines = []

    # 处理硬换行符
    paragraphs = text.split("\n")

    for paragraph in paragraphs:
        if not paragraph:
            lines.append("")
            continue

        # 改进：针对中文等不以空格分隔的语言，进行逐字符处理
        current_line = ""

        # 将文本按空格分割，处理英文单词
        words = paragraph.split()
        if not words:
            lines.append("")
            continue

        # 处理第一个单词/字符
        if is_ascii_word(words[0]):
            # 英文单词
            current_line = words[0]
        else:
            # 中文或其他非ASCII字符，逐字处理
            for char in words[0]:
                test_line = current_line + char
                bbox = draw.textbbox((0, 0), test_line, font=font)
                w = bbox[2] - bbox[0]
                if w <= box_w:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = char

        # 处理剩余单词/字符
        for word in words[1:]:
            # 尝试添加空格和下一个单词
            if is_ascii_word(word):
                # 英文单词
                test_line = current_line + " " + word
                bbox = draw.textbbox((0, 0), test_line, font=font)
                w = bbox[2] - bbox[0]
                if w <= box_w:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            else:
                # 先添加空格
                if current_line:
                    test_line = current_line + " "
                    bbox = draw.textbbox((0, 0), test_line, font=font)
                    w = bbox[2] - bbox[0]
                    if w <= box_w:
                        current_line = test_line
                    else:
                        lines.append(current_line)
                        current_line = ""

                # 中文或其他非ASCII字符，逐字处理
                for char in word:
                    test_line = current_line + char
                    bbox = draw.textbbox((0, 0), test_line, font=font)
                    w = bbox[2] - bbox[0]
                    if w <= box_w:
                        current_line = test_line
                    else:
                        lines.append(current_line)
                        current_line = char

        # 添加最后一行
        if current_line:
            lines.append(current_line)

    # 计算总文本高度
    total_height = 0
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        h = bbox[3] - bbox[1]
        line_heights.append(h)
        total_height += h

    total_height += (len(lines) - 1) * line_spacing

    # 开始绘制文本（居中）
    current_y = y0 + (box_h - total_height) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        # 在每行文本的居中位置绘制
        draw.text(((img.width - w) // 2, current_y), line, font=font, fill=fill_color)
        current_y += line_heights[i] + line_spacing


def is_ascii_word(word):
    """
    判断是否为ASCII字符组成的单词
    """
    return all(ord(c) < 128 for c in word)


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def xibao_handler(bot, message: types.Message):
        """处理喜报/悲报/通报/警报消息"""
        type_dict = {"喜报": 0, "悲报": 1, "通报": 2, "警报": 3}
        await good_news(bot, message, type_dict[message.text[:2]])

    # 使用中间件注册，添加 starts_with 过滤器
    middleware.register_message_handler(
        callback=xibao_handler,
        plugin_name=plugin_name,
        handler_name="xibao_filter",
        priority=50,
        stop_propagation=False,
        starts_with=['喜报', '悲报', '通报', '警报']
    )

    logger.info(f"✅ {__plugin_name__} 插件已注册 - 支持喜报/悲报/通报/警报")

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
