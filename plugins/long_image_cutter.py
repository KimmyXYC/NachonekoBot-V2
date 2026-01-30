# -*- coding: utf-8 -*-
# @Time    : 2025/11/06 15:10
# @Author  : KimmyXYC / Junie
# @File    : long_image_cutter.py
# @Software: PyCharm
"""
捕获以文件形式发送的图片：当图片为长图（高宽比 > 3:1）时，自动裁切为多个 19.5:9（竖屏）片段。
相邻两张之间保留 3:19.5 的重叠区域（约等于每张高度的 15.38% 作为上下重叠）。
裁切完成后，按每 9 张打包为一组发送（使用媒体组），不再发送事先提示消息。
"""
import io
from typing import List, Tuple

from loguru import logger
from telebot import types
from PIL import Image

# ==================== 插件元数据 ====================
__plugin_name__ = "long_image_cutter"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "长图自动裁切为多个 19.5:9，并带 3:19.5 重叠；切片高度以 19.5:9 为标准可微调，保证所有切片大小一致（仅对以文件形式发送的图片生效）"
__commands__ = []  # 非命令型插件
__toggleable__ = True  # 支持在群组中开关


# ==================== 工具函数 ====================
def calc_slices(w: int, h: int) -> Tuple[int, int, int, List[Tuple[int, int, int, int]]]:
    """
    计算裁切窗口并返回所有裁切框坐标列表（等高切片 + 固定重叠比例）。
    - 目标比例：19.5:9（竖屏），基准切片高度 h0 = round(w * 19.5/9)
    - 重叠高度：3:19.5（约 15.38% 的切片高度）
    - 要求：所有切片的尺寸完全相同；允许上下留白浮动，但保证最后一张贴合底部

    返回：segment_h, overlap_h, step, crop_boxes[(l, t, r, b)...]
    """
    # 基准切片高度（竖屏，19.5:9 => 高/宽 = 19.5/9）
    h0 = max(1, round(w * (19.5 / 9.0)))
    if h0 >= h:
        # 图片本身不足一片，直接整张返回
        return h, 0, h, [(0, 0, w, h)]

    # 重叠比例（3:19.5）
    ro = 3.0 / 19.5  # ≈ 0.153846...

    # 估算步进与片数
    overlap0 = round(ro * h0)
    step0 = max(1, h0 - overlap0)

    # 估算需要的片数（向上取整）
    # 覆盖高度约：h0 + (n-1)*step0 >= h
    n0 = int((max(0, h - h0) + step0 - 1) // step0) + 1

    MAX_SLICES = 30

    # 构建候选片数集合（围绕 n0 微调，受上限约束）
    candidates = []
    for dn in (-2, -1, 0, 1, 2, 3):
        n = n0 + dn
        if 1 <= n <= MAX_SLICES:
            candidates.append(n)
    # 边界兜底
    if 1 not in candidates:
        candidates.append(1)
    if MAX_SLICES not in candidates:
        candidates.append(MAX_SLICES)
    candidates = sorted(set(candidates))

    best = None  # (score, n, seg_h, overlap_h, step, total_cov)

    for n in candidates:
        # 通过近似公式解出理想切片高度（忽略四舍五入影响）
        denom = (n - (n - 1) * ro)
        if denom <= 0:
            continue
        s_float = h / denom
        s = max(1, round(s_float))

        # 调整 s 以确保总覆盖不超过 h，且步进有效
        for _ in range(3):
            overlap_h = round(ro * s)
            step = s - overlap_h
            if step < 1:
                s += 1  # 增大切片以获得有效步进
                continue
            total = n * s - (n - 1) * overlap_h
            if total > h and s > 1:
                s -= 1  # 轻调降低覆盖
                continue
            break
        # 终值计算
        overlap_h = round(ro * s)
        step = s - overlap_h
        total = n * s - (n - 1) * overlap_h
        if step < 1 or total > h:
            continue

        # 评分：优先接近 h0，其次覆盖接近 h、步进更大
        score = (abs(s - h0), abs(h - total), -step)
        pack = (score, n, s, overlap_h, step, total)
        if (best is None) or (score < best[0]):
            best = pack

    # 如果未找到有效解，回退到旧策略（等步进滚动，尾部贴底）
    if best is None:
        # 旧策略
        segment_h = h0
        overlap_h = max(1, round(segment_h * (3.0 / 19.5)))
        step = max(1, segment_h - overlap_h)
        boxes: List[Tuple[int, int, int, int]] = []
        top = 0
        while top + segment_h <= h:
            boxes.append((0, top, w, top + segment_h))
            top += step
        if boxes:
            last_top = h - segment_h
            if last_top > boxes[-1][1]:
                boxes.append((0, last_top, w, last_top + segment_h))
        else:
            boxes.append((0, 0, w, min(segment_h, h)))
        # 去重
        dedup = []
        seen = set()
        for b in boxes:
            if b in seen:
                continue
            seen.add(b)
            dedup.append(b)
        return segment_h, overlap_h, step, dedup

    # 使用最优解构建等高切片，底部对齐
    _, n, segment_h, overlap_h, step, total = best
    first_top = h - total  # >= 0，上方留白

    boxes: List[Tuple[int, int, int, int]] = []
    for k in range(n):
        t = first_top + k * step
        l, r = 0, w
        b = t + segment_h
        # 保护性裁剪（理论上不需要，但以防浮点/取整误差）
        t_i = int(max(0, min(h - segment_h, t)))
        b_i = t_i + segment_h
        boxes.append((l, t_i, r, b_i))

    return segment_h, overlap_h, step, boxes


def image_to_bytes(img: Image.Image, preferred_fmt: str = "PNG") -> io.BytesIO:
    bio = io.BytesIO()
    fmt = preferred_fmt.upper()
    # JPEG 不支持 alpha，若原图有 alpha 则强制 PNG
    if fmt in ("JPG", "JPEG"):
        if img.mode in ("RGBA", "LA"):
            fmt = "PNG"
        else:
            fmt = "JPEG"
    img.save(bio, format=fmt, quality=95)
    bio.name = f"slice.{fmt.lower()}"
    bio.seek(0)
    return bio


# ==================== 核心功能 ====================
async def handle_document_image(bot, message: types.Message, document: types.Document):
    try:
        # 仅处理图片 MIME
        if not document.mime_type or not document.mime_type.startswith("image/"):
            return

        # 拉取文件字节
        file_info = await bot.get_file(document.file_id)
        file_bytes = await bot.download_file(file_info.file_path)

        # 打开图片
        with Image.open(io.BytesIO(file_bytes)) as im:
            im.load()
            w, h = im.size
            if h / max(1, w) <= 3.0:
                # 非长图（比例不超过 3:1），按需求静默忽略
                return

            # 计算裁切片段
            segment_h, overlap_h, step, boxes = calc_slices(w, h)
            logger.info(
                f"[LongImageCutter][{message.chat.id}] size={w}x{h} seg_h={segment_h} overlap={overlap_h} step={step} boxes={len(boxes)}"
            )

            # 选择输出格式：沿用原文件扩展（如可）
            preferred_fmt = "PNG"
            if document.file_name and "." in document.file_name:
                ext = document.file_name.rsplit(".", 1)[-1].lower()
                if ext in ("jpg", "jpeg"):
                    preferred_fmt = "JPEG"
                elif ext in ("png", "webp"):
                    preferred_fmt = ext

            # 安全阈值：最多 30 片，超过则按最后一片贴底后截断
            MAX_SLICES = 30
            if len(boxes) > MAX_SLICES:
                logger.warning(f"[LongImageCutter] slices too many: {len(boxes)} > {MAX_SLICES}, truncating")
                boxes = boxes[:MAX_SLICES - 1] + [
                    (0, max(0, h - (boxes[0][3] - boxes[0][1])), w, h)
                ]

            # 分组发送：每组最多 9 张；Telegram 媒体组需要 2-10 项
            total = len(boxes)
            BATCH = 9
            sent = 0
            from telebot import types as tb_types

            def batch_iter(seq, size):
                for i in range(0, len(seq), size):
                    yield i, seq[i:i+size]

            for start_idx, batch in batch_iter(boxes, BATCH):
                try:
                    if len(batch) == 1:
                        # 单张时用 send_photo（媒体组最少 2 项）
                        l, t, r, b = batch[0]
                        crop = im.crop((l, t, r, b))
                        bio = image_to_bytes(crop, preferred_fmt=preferred_fmt)
                        caption = f"第 {start_idx + 1}/{total} 张"
                        await _send_with_retry(lambda: bot.send_photo(
                            chat_id=message.chat.id,
                            photo=bio,
                            caption=caption,
                            reply_to_message_id=message.message_id,
                        ))
                        sent += 1
                        continue

                    media = []
                    for j, (l, t, r, b) in enumerate(batch):
                        crop = im.crop((l, t, r, b))
                        bio = image_to_bytes(crop, preferred_fmt=preferred_fmt)
                        file_obj = tb_types.InputFile(bio)
                        # 仅给本组第一张添加简短说明，避免多条 caption 干扰
                        if j == 0:
                            end_no = start_idx + len(batch)
                            cap = f"第 {start_idx + 1}-{end_no} / {total} 张"
                            media.append(tb_types.InputMediaPhoto(media=file_obj, caption=cap))
                        else:
                            media.append(tb_types.InputMediaPhoto(media=file_obj))

                    await _send_with_retry(lambda: bot.send_media_group(
                        chat_id=message.chat.id,
                        media=media,
                        reply_to_message_id=message.message_id,
                    ))
                    sent += len(batch)
                except Exception as ex:
                    logger.warning(f"[LongImageCutter] media group failed at {start_idx}: {ex}")

    except Exception as e:
        logger.error(f"[LongImageCutter][{message.chat.id}] error: {e}")
        try:
            await bot.reply_to(message, f"裁切失败：{e}")
        except Exception:
            pass


async def _send_with_retry(send_coro_factory, max_retries: int = 3):
    """
    通用发送重试：当遇到 Telegram 429（Too Many Requests）错误时，读取 retry_after 秒等待后重试。
    send_coro_factory: 一个无参可调用，返回一个 awaitable（即调用具体的 bot 发送方法）。
    """
    from asyncio import sleep
    from loguru import logger as _lg
    import re

    for attempt in range(1, max_retries + 1):
        try:
            return await send_coro_factory()
        except Exception as e:
            # 仅在 429 错误时重试，其余异常直接抛出
            text = str(e)
            if "Too Many Requests" in text or "429" in text:
                # 尝试解析 "retry after X" 或 "retry_after X"
                m = re.search(r"retry(?:\s|_)?after\s(\d+)", text, re.IGNORECASE)
                retry_sec = int(m.group(1)) + 1 if m else 5
                _lg.warning(f"[Retry] Telegram 429; waiting {retry_sec}s and retrying (attempt {attempt}/{max_retries})")
                await sleep(retry_sec)
                continue
            # 非 429，直接抛出
            raise
    # 超过重试次数，最后再尝试一次，若失败则抛出
    return await send_coro_factory()


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""
    global bot_instance
    bot_instance = bot

    def image_document_filter(message: types.Message) -> bool:
        try:
            if message.content_type != 'document':
                return False
            doc: types.Document = message.document
            if not doc:
                return False
            if not doc.mime_type or not doc.mime_type.startswith("image/"):
                return False
            return True
        except Exception:
            return False

    async def image_doc_handler(bot, message: types.Message):
        await handle_document_image(bot, message, message.document)

    # 仅处理以文件形式发送的图片
    middleware.register_message_handler(
        callback=image_doc_handler,
        plugin_name=plugin_name,
        handler_name="long_image_cutter",
        priority=50,
        stop_propagation=False,
        content_types=['document'],
        func=image_document_filter,
    )

    logger.info(f"✅ {__plugin_name__} 插件已注册 - 长图裁切")


# ==================== 插件信息 ====================
def get_plugin_info() -> dict:
    return {
        "name": __plugin_name__,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": __commands__,
    }


# 保持全局 bot 引用
bot_instance = None
