# -*- coding: utf-8 -*-
# @Time    : 2026/2/27
# @Author  : OpenCode
# @File    : ocr.py
# @Software: PyCharm
import base64
import json
import os
import re

import aiohttp
from loguru import logger
from telebot import types

from utils.i18n import _t
from utils.yaml import BotConfig

# ==================== 插件元数据 ====================
__plugin_name__ = "ocr"
__version__ = "2.0.0"
__author__ = "KimmyXYC"
__description__ = "OCR 文字识别（Paddle OCR）"
__commands__ = ["ocr"]
__command_category__ = "tool"
__command_order__ = {"ocr": 230}
__command_descriptions__ = {"ocr": "OCR 识别图片或 PDF 文字"}
__command_help__ = {
    "ocr": "/ocr - OCR 识别图片或 PDF 文字，回复图片/图片文件/PDF 文件，或在图片/PDF caption 中使用"
}

DEFAULT_API_URL = "https://h4l75ambd2ef57v5.aistudio-app.com/ocr"
DEFAULT_TOKEN = "undefined"


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _get_ocr_config() -> dict:
    conf = BotConfig.get("ocr", {}) or {}
    return {
        "api_url": conf.get("api_url", DEFAULT_API_URL),
        "token": str(conf.get("token", DEFAULT_TOKEN) or DEFAULT_TOKEN),
        "timeout": int(conf.get("timeout", 60)),
        "use_doc_orientation_classify": _as_bool(
            conf.get("use_doc_orientation_classify", False)
        ),
        "use_doc_unwarping": _as_bool(conf.get("use_doc_unwarping", False)),
        "use_textline_orientation": _as_bool(
            conf.get("use_textline_orientation", False)
        ),
    }


def _is_ocr_command(raw: str) -> bool:
    if not raw:
        return False
    return bool(re.match(r"^/ocr(?:@[A-Za-z0-9_]+)?(?:\s+[\s\S]*)?$", raw.strip()))


def _get_source_kind(message: types.Message) -> str | None:
    if getattr(message, "photo", None):
        return "image"

    doc = getattr(message, "document", None)
    if not doc:
        return None

    mime_type = (getattr(doc, "mime_type", "") or "").lower()
    file_name = (getattr(doc, "file_name", "") or "").lower()

    if mime_type == "application/pdf" or file_name.endswith(".pdf"):
        return "pdf"
    if mime_type.startswith("image/"):
        return "image"
    return None


def _is_supported_message(message: types.Message) -> bool:
    return _get_source_kind(message) is not None


def _guess_file_type(message: types.Message) -> int:
    source_kind = _get_source_kind(message)
    if source_kind == "pdf":
        return 0
    if source_kind == "image":
        return 1
    raise ValueError("不支持的文件类型，仅支持图片或 PDF")


async def _download_file_bytes(bot, source_message: types.Message) -> bytes | None:
    source_kind = _get_source_kind(source_message)
    if not source_kind:
        return None

    file_id = None
    photos = getattr(source_message, "photo", None)
    if photos:
        file_id = photos[-1].file_id
    else:
        doc = getattr(source_message, "document", None)
        if doc:
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
        with open(local_path, "rb") as file:
            return file.read()

    return await bot.download_file(file_info.file_path)


def _extract_result_text(item: dict) -> str:
    for key in ("prunedResult", "ocrText", "text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def _call_ocr_api(file_bytes: bytes, file_type: int, conf: dict) -> str:
    payload = {
        "file": base64.b64encode(file_bytes).decode("ascii"),
        "fileType": file_type,
        "useDocOrientationClassify": conf["use_doc_orientation_classify"],
        "useDocUnwarping": conf["use_doc_unwarping"],
        "useTextlineOrientation": conf["use_textline_orientation"],
    }
    headers = {
        "Authorization": f"token {conf['token']}",
        "Content-Type": "application/json",
    }

    timeout = aiohttp.ClientTimeout(total=conf["timeout"])
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            conf["api_url"], headers=headers, json=payload
        ) as response:
            body = await response.text()
            if response.status != 200:
                raise RuntimeError(f"OCR API 请求失败 ({response.status}): {body[:500]}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OCR API 返回了无法解析的 JSON") from exc

    result = data.get("result")
    if not isinstance(result, dict):
        detail = data.get("message") or data.get("msg") or body[:200]
        raise RuntimeError(f"OCR API 返回异常: {detail}")

    ocr_results = result.get("ocrResults")
    if not isinstance(ocr_results, list):
        raise RuntimeError("OCR API 返回缺少 ocrResults 字段")

    text_parts = []
    for item in ocr_results:
        if not isinstance(item, dict):
            continue
        text = _extract_result_text(item)
        if text:
            text_parts.append(text)

    return "\n\n".join(text_parts).strip()


async def _process_ocr(bot, message: types.Message, source_message: types.Message):
    progress_msg = None
    try:
        progress_msg = await bot.reply_to(message, _t("status.ocr_processing"))
    except Exception as exc:
        logger.warning(f"[OCR] 发送占位消息失败: {exc}")

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
                except Exception as exc:
                    logger.warning(f"[OCR] 编辑占位消息失败，将改为回复发送: {exc}")
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
                except Exception as exc:
                    logger.warning(f"[OCR] 分段发送失败，将改为回复发送: {exc}")

        await bot.reply_to(message, text)

    file_bytes = await _download_file_bytes(bot, source_message)
    if not file_bytes:
        await _update_result(_t("error.image_download_failed"))
        return

    try:
        conf = _get_ocr_config()
        file_type = _guess_file_type(source_message)
        result = await _call_ocr_api(file_bytes, file_type, conf)
        if not result:
            result = _t("error.ocr_empty_result")
        await _update_result(result)
    except Exception as exc:
        logger.error(f"[OCR] 识别失败: {exc}")
        await _update_result(_t("error.ocr_failed", reason=str(exc)))


async def register_handlers(bot, middleware, plugin_name):
    async def ocr_command_handler(bot, message: types.Message):
        if not _is_ocr_command(message.text or ""):
            await bot.reply_to(message, _t("error.ocr_invalid_format"))
            return

        reply = getattr(message, "reply_to_message", None)
        if not reply or not _is_supported_message(reply):
            await bot.reply_to(
                message,
                _t("prompt.ocr_reply_image_first"),
            )
            return

        await _process_ocr(bot, message, reply)

    def caption_ocr_filter(message: types.Message) -> bool:
        try:
            if message.content_type not in ("photo", "document"):
                return False
            if not _is_supported_message(message):
                return False
            caption = (getattr(message, "caption", "") or "").strip()
            return _is_ocr_command(caption)
        except Exception:
            return False

    async def ocr_caption_handler(bot, message: types.Message):
        if not _is_ocr_command((message.caption or "").strip()):
            return
        await _process_ocr(bot, message, message)

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

    logger.info("✅ ocr 插件已注册 - 支持 /ocr 与图片/PDF caption /ocr")


def get_plugin_info() -> dict:
    return {
        "name": __plugin_name__,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": __commands__,
    }


bot_instance = None
