# -*- coding: utf-8 -*-
# @Time    : 2026/2/27
# @Author  : OpenCode
# @File    : ocr.py
# @Software: PyCharm
import base64
import os
import re

import aiohttp
from loguru import logger
from telebot import types

from utils.yaml import BotConfig

# ==================== 插件元数据 ====================
__plugin_name__ = "ocr"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "OCR 文字识别（阿里云 qwen-vl-ocr）"
__commands__ = ["ocr"]
__command_category__ = "tool"
__command_order__ = {"ocr": 230}
__command_descriptions__ = {"ocr": "OCR 识别图片文字"}
__command_help__ = {
    "ocr": "/ocr [自定义提示词] - OCR 识别图片文字，回复图片/图片文件，或在图片 caption 中使用"
}

DEFAULT_PROMPT = (
    "Please output only the text content from the image without any additional "
    "descriptions or formatting."
)


def _get_ocr_config() -> dict:
    conf = BotConfig.get("ocr", {}) or {}
    return {
        "api_key": conf.get("api_key", ""),
        "base_url": conf.get(
            "base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ),
        "model": conf.get("model", "qwen-vl-ocr-latest"),
        "default_prompt": conf.get("default_prompt", DEFAULT_PROMPT),
        "timeout": int(conf.get("timeout", 60)),
        "min_pixels": conf.get("min_pixels", 32 * 32 * 3),
        "max_pixels": conf.get("max_pixels", 32 * 32 * 8192),
        "enable_rotate": bool(conf.get("enable_rotate", False)),
    }


def _extract_prompt(raw: str) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    m = re.match(r"^/ocr(?:@[A-Za-z0-9_]+)?(?:\s+([\s\S]*))?$", text)
    if not m:
        return None
    prompt = (m.group(1) or "").strip()
    return prompt


def _is_image_message(message: types.Message) -> bool:
    if getattr(message, "photo", None):
        return True
    doc = getattr(message, "document", None)
    return bool(doc and doc.mime_type and doc.mime_type.startswith("image/"))


def _guess_mime_type(message: types.Message) -> str:
    doc = getattr(message, "document", None)
    if doc and doc.mime_type and doc.mime_type.startswith("image/"):
        return doc.mime_type
    return "image/jpeg"


async def _download_image_bytes(bot, source_message: types.Message) -> bytes | None:
    file_id = None
    photos = getattr(source_message, "photo", None)
    if photos:
        file_id = photos[-1].file_id
    else:
        doc = getattr(source_message, "document", None)
        if doc and doc.mime_type and doc.mime_type.startswith("image/"):
            file_id = doc.file_id

    if not file_id:
        return None

    file_info = await bot.get_file(file_id)
    botapi_config = BotConfig.get("botapi", {})
    use_local_path = botapi_config.get("enable", False)

    if use_local_path:
        local_path = file_info.file_path
        if not local_path or not os.path.isfile(local_path):
            logger.error(f"[OCR] local file not found: {local_path}")
            return None
        with open(local_path, "rb") as f:
            return f.read()

    return await bot.download_file(file_info.file_path)


async def _call_ocr_api(
    image_bytes: bytes, mime_type: str, prompt: str, conf: dict
) -> str:
    api_key = conf["api_key"]
    if not api_key:
        raise ValueError("未配置 ocr.api_key")

    base_url = conf["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    model = conf["model"]

    encoded = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                        "min_pixels": conf["min_pixels"],
                        "max_pixels": conf["max_pixels"],
                        "enable_rotate": conf["enable_rotate"],
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    timeout = aiohttp.ClientTimeout(total=conf["timeout"])
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"OCR API 请求失败 ({resp.status}): {body[:500]}")

            data = await resp.json()

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OCR API 返回为空")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        joined = "\n".join([x for x in text_parts if x.strip()]).strip()
        if joined:
            return joined

    raise RuntimeError("OCR API 返回内容格式不支持")


async def _process_ocr(
    bot, message: types.Message, source_message: types.Message, prompt: str
):
    progress_msg = None
    try:
        progress_msg = await bot.reply_to(message, "OCR识别中...")
    except Exception as e:
        logger.warning(f"[OCR] 发送占位消息失败: {e}")

    async def _update_result(text: str):
        if progress_msg:
            if len(text) <= 4096:
                try:
                    await bot.edit_message_text(
                        text=text,
                        chat_id=progress_msg.chat.id,
                        message_id=progress_msg.message_id,
                    )
                    return
                except Exception as e:
                    logger.warning(f"[OCR] 编辑占位消息失败，将改为回复发送: {e}")
            else:
                try:
                    await bot.edit_message_text(
                        text=text[:4096],
                        chat_id=progress_msg.chat.id,
                        message_id=progress_msg.message_id,
                    )
                    remaining = text[4096:]
                    while remaining:
                        chunk = remaining[:4096]
                        remaining = remaining[4096:]
                        await bot.send_message(message.chat.id, chunk)
                    return
                except Exception as e:
                    logger.warning(f"[OCR] 分段发送失败，将改为回复发送: {e}")

        await bot.reply_to(message, text)

    conf = _get_ocr_config()
    final_prompt = (
        prompt.strip() if prompt and prompt.strip() else conf["default_prompt"]
    )

    image_bytes = await _download_image_bytes(bot, source_message)
    if not image_bytes:
        await _update_result("获取图片失败，请检查是否为图片或图片文件。")
        return

    mime_type = _guess_mime_type(source_message)

    try:
        result = await _call_ocr_api(image_bytes, mime_type, final_prompt, conf)
        if not result:
            result = "识别完成，但未提取到文本内容。"
        await _update_result(result)
    except Exception as e:
        logger.error(f"[OCR] 识别失败: {e}")
        await _update_result(f"OCR 识别失败：{e}")


async def register_handlers(bot, middleware, plugin_name):
    async def ocr_command_handler(bot, message: types.Message):
        prompt = _extract_prompt(message.text or "")
        if prompt is None:
            await bot.reply_to(message, "格式错误，格式应为 /ocr [自定义提示词]")
            return

        reply = getattr(message, "reply_to_message", None)
        if not reply or not _is_image_message(reply):
            await bot.reply_to(
                message,
                "请回复一张图片或图片文件后再使用 /ocr [自定义提示词]。",
            )
            return

        await _process_ocr(bot, message, reply, prompt)

    def caption_ocr_filter(message: types.Message) -> bool:
        try:
            if message.content_type not in ("photo", "document"):
                return False
            if not _is_image_message(message):
                return False
            caption = (getattr(message, "caption", "") or "").strip()
            return _extract_prompt(caption) is not None
        except Exception:
            return False

    async def ocr_caption_handler(bot, message: types.Message):
        prompt = _extract_prompt((message.caption or "").strip())
        if prompt is None:
            return
        await _process_ocr(bot, message, message, prompt)

    middleware.register_command_handler(
        commands=["ocr"],
        callback=ocr_command_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    middleware.register_message_handler(
        callback=ocr_caption_handler,
        plugin_name=plugin_name,
        handler_name="ocr_caption_handler",
        priority=50,
        stop_propagation=True,
        content_types=["photo", "document"],
        func=caption_ocr_filter,
    )

    logger.info("✅ ocr 插件已注册 - 支持 /ocr 与图片 caption /ocr")


def get_plugin_info() -> dict:
    return {
        "name": __plugin_name__,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": __commands__,
    }


bot_instance = None
