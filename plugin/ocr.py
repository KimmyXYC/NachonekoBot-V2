# -*- coding: utf-8 -*-
# @Time    : 2025/7/5 11:08
# @Author  : KimmyXYC
# @File    : ocr.py
# @Software: PyCharm
import os
import tempfile
import easyocr
from telebot import types, formatting
from loguru import logger


class OCRProcessor:
    def __init__(self):
        # Initialize the OCR reader with languages
        self.reader = None
        self.languages = ["ch_sim", "en"]  # Default languages: Simplified Chinese and English
        self.initialize_reader()

    def initialize_reader(self):
        """Initialize the EasyOCR reader with the current languages"""
        try:
            self.reader = easyocr.Reader(self.languages)
            logger.info(f"OCR reader initialized with languages: {', '.join(self.languages)}")
        except Exception as e:
            logger.error(f"Failed to initialize OCR reader: {str(e)}")
            self.reader = None

    def set_languages(self, languages):
        """Set the languages for OCR recognition"""
        self.languages = languages
        self.initialize_reader()

    async def process_image(self, image_path):
        """Process an image and return the recognized text"""
        if not self.reader:
            return "OCR reader not initialized properly."

        try:
            # Perform OCR on the image
            results = self.reader.readtext(image_path)

            # Extract and format the recognized text
            if not results:
                return "No text detected in the image."

            text_results = []
            for detection in results:
                text = detection[1]  # The recognized text
                confidence = detection[2]  # Confidence score
                # Only include results with confidence >= 0.5 and don't display confidence
                if confidence >= 0.5:
                    text_results.append(text)

            return "\n".join(text_results)
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return f"Error processing image: {str(e)}"


# Create a global instance of the OCR processor
ocr_processor = OCRProcessor()


async def handle_ocr_command(bot, message: types.Message):
    """
    Handle OCR command to set languages or provide help
    :param bot: Bot object
    :param message: Message object
    :return:
    """
    if message.reply_to_message and message.reply_to_message.photo:
        await process_photo(bot, message.reply_to_message)
        return
    else:
        help_text = formatting.format_text(
            formatting.mbold("🔍 OCR 命令使用帮助"),
            formatting.mcode("/ocr - 显示此帮助信息"),
            "",
            "使用方法:",
            formatting.mcode("直接回复图片使用 /ocr 命令可以识别图片中的文字")
        )
        await bot.reply_to(message, help_text, parse_mode="MarkdownV2")
        return


async def process_photo(bot, message: types.Message):
    """
    Process a photo message for OCR
    :param bot: Bot object
    :param message: Message object containing the photo
    :return:
    """
    if not message.photo:
        error_text = formatting.format_text(
            formatting.mitalic("请提供一张图片进行OCR识别。")
        )
        await bot.reply_to(message, error_text, parse_mode="MarkdownV2")
        return

    # Get the largest photo (best quality)
    file_id = message.photo[-1].file_id

    # Send a processing message
    processing_text = formatting.format_text(
        formatting.mitalic("正在处理图片，请稍候...")
    )
    processing_msg = await bot.reply_to(message, processing_text, parse_mode="MarkdownV2")

    try:
        # Download the photo
        file_info = await bot.get_file(file_id)
        downloaded_file = await bot.download_file(file_info.file_path)

        # Save to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(downloaded_file)
            temp_file_path = temp_file.name

        # Process the image
        result = await ocr_processor.process_image(temp_file_path)

        # Send the result
        result_text = formatting.format_text(
            formatting.mbold("🔍 OCR 识别结果:"),
            "",
            formatting.mcode(result)
        )
        await bot.edit_message_text(
            result_text,
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            parse_mode="MarkdownV2"
        )

        # Clean up the temporary file
        os.remove(temp_file_path)
    except Exception as e:
        logger.error(f"Error in OCR processing: {str(e)}")
        error_text = formatting.format_text(
            formatting.mbold("❌ 错误:"),
            formatting.mitalic("OCR处理过程中出错:"),
            formatting.mcode(str(e))
        )
        await bot.edit_message_text(
            error_text,
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            parse_mode="MarkdownV2"
        )
