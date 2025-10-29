# -*- coding: utf-8 -*-
# @Time    : 2025/6/22 16:46
# @Author  : KimmyXYC
# @File    : keybox.py
# @Software: PyCharm
import aiohttp
import json
import tempfile
import time
import os
import re
import xml.etree.ElementTree as ET
from telebot import types
from loguru import logger
from datetime import datetime, timezone
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, ec
from app.utils import markdown_to_telegram_html
from utils.elaradb import BotElara

# ==================== 插件元数据 ====================
__plugin_name__ = "keybox"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "Keybox 检查工具"
__commands__ = ["check", "ban_keybox", "unban_keybox"]


# ==================== 核心功能 ====================
async def handle_keybox_check(bot, message: types.Message, document: types.Document):
    """
    Handle the Keybox check command.
    :param bot: Bot instance
    :param message: Message instance containing the command
    :param document: Document instance containing the Keybox file
    :return: None
    """
    if document.mime_type != 'application/xml' and document.mime_type != 'text/xml':
        await bot.reply_to(message, "File format error")
        return
    if document.file_size > 20 * 1024:
        await bot.reply_to(message, "File size is too large")
        return
    await keybox_check(bot, message, document)


async def load_from_url():
    """
    Load the latest keybox status from Google's API.
    :return: JSON response containing the keybox status.
    :raises Exception: If the request fails or returns an error status.
    """
    url = "https://android.googleapis.com/attestation/status"

    headers = {
        "Cache-Control": "max-age=0, no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    params = {
        "ts": int(time.time())
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                raise Exception(f"Error fetching data: {response.status}")
            return await response.json()


def get_device_ids_and_algorithms(xml_file):
    """
    Parse the XML file to extract device IDs and algorithms from Keybox elements.
    :param xml_file: Path to the XML file.
    :return: A list of dictionaries containing DeviceID and Algorithm.
    :raises Exception: If the XML file cannot be parsed or if Keybox elements are not found.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    results = []
    for keybox in root.findall('Keybox'):
        device_id = keybox.get('DeviceID')

        for key in keybox.findall('Key'):
            algorithm = key.get('algorithm')
            device_info = {
                'DeviceID': device_id if device_id else 'Unknown',
                'Algorithm': algorithm if algorithm else 'Unknown'
            }
            results.append(device_info)
    return results


def parse_number_of_certificates(xml_file):
    """
    Parse the XML file to get the number of certificates.
    :param xml_file: Path to the XML file.
    :return: The number of certificates as an integer.
    :raises Exception: If the XML file cannot be parsed or if NumberOfCertificates is not found.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    number_of_certificates = root.find('.//NumberOfCertificates')

    if number_of_certificates is not None:
        count = int(number_of_certificates.text.strip())
        return count
    else:
        raise Exception('No NumberOfCertificates found.')


def parse_certificates(xml_file, pem_number):
    """
    Parse the XML file to extract PEM formatted certificates.
    :param xml_file: Path to the XML file.
    :param pem_number: The number of PEM certificates to extract.
    :return: A list of PEM formatted certificate contents.
    :raises Exception: If the XML file cannot be parsed or if no PEM certificates are found.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    pem_certificates = root.findall('.//Certificate[@format="pem"]')

    if pem_certificates is not None:
        pem_contents = [cert.text.strip() for cert in pem_certificates[:pem_number]]
        return pem_contents
    else:
        raise Exception("No Certificate found.")


def parse_private_key(xml_file):
    """
    Parse the XML file to extract the private key.
    :param xml_file: Path to the XML file.
    :return: The private key as a string.
    :raises Exception: If the XML file cannot be parsed or if no PrivateKey is found.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    private_key = root.find('.//PrivateKey')

    if private_key is not None:
        return private_key.text.strip()
    else:
        raise Exception("No PrivateKey found.")


def load_public_key_from_file(file_path):
    """
    Load a public key from a PEM file.
    :param file_path: Path to the PEM file containing the public key.
    :return: The public key object.
    """
    with open(file_path, 'rb') as key_file:
        public_key = serialization.load_pem_public_key(
            key_file.read(),
            backend=default_backend()
        )
    return public_key


def compare_keys(public_key1, public_key2):
    """
    Compare two public keys for equality.
    :param public_key1: The first public key to compare.
    :param public_key2: The second public key to compare.
    :return: True if the keys are equal, False otherwise.
    """
    return public_key1.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ) == public_key2.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )


async def keybox_check(bot, message, document):
    """
    Check the validity of a Keybox file.
    :param bot: Bot instance
    :param message: Message instance containing the command
    :param document: Document instance containing the Keybox file
    :return: None
    """
    file_info = await bot.get_file(document.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(downloaded_file)
        temp_file.flush()
        temp_file.close()
        try:
            pem_number = parse_number_of_certificates(temp_file.name)
            pem_certificates = parse_certificates(temp_file.name, pem_number)
            private_key = parse_private_key(temp_file.name)
            keybox_info = get_device_ids_and_algorithms(temp_file.name)
            os.remove(temp_file.name)
        except Exception as e:
            logger.error(f"[Keybox Check][{message.chat.id}]: {e}")
            await bot.reply_to(message, e)
            os.remove(temp_file.name)
            return
    try:
        certificate = x509.load_pem_x509_certificate(
            pem_certificates[0].encode(),
            default_backend()
        )
        try:
            private_key = re.sub(re.compile(r'^\s+', re.MULTILINE), '', private_key)
            private_key = serialization.load_pem_private_key(
                private_key.encode(),
                password=None,
                backend=default_backend()
            )
            check_private_key = True
        except Exception:
            check_private_key = False
    except Exception as e:
        logger.error(f"[Keybox Check][{message.chat.id}]: {e}")
        await bot.reply_to(message, e)
        return

    # Banned Keybox Check List
    banned_sn = BotElara.get('banned_sn',[])

    # Keybox Information
    reply = f"📱 *Device ID:* `{keybox_info[0]['DeviceID']}`"
    reply += f"\n🔑 *Algorithm:* `{keybox_info[0]['Algorithm']}`"
    reply += "\n----------------------------------------"

    # Certificate Validity Verification
    serial_number = certificate.serial_number
    serial_number_string = hex(serial_number)[2:].lower()
    reply += f"\n🔐 *Serial number:* `{serial_number_string}`"
    subject = certificate.subject
    reply += "\nℹ️ *Subject:* `"
    for rdn in subject:
        reply += f"{rdn.oid._name}={rdn.value}, "
    reply = reply[:-2]
    reply += "`"
    not_valid_before = certificate.not_valid_before_utc
    not_valid_after = certificate.not_valid_after_utc
    current_time = datetime.now(timezone.utc)
    is_valid = not_valid_before <= current_time <= not_valid_after
    if is_valid:
        reply += "\n✅ Certificate within validity period"
    elif current_time > not_valid_after:
        reply += "\n❌ Expired certificate"
    else:
        reply += "\n❌ Invalid certificate"

    # Private Key Verification
    if check_private_key:
        private_key_public_key = private_key.public_key()
        certificate_public_key = certificate.public_key()
        if compare_keys(private_key_public_key, certificate_public_key):
            reply += "\n✅ Matching private key and certificate public key"
        else:
            reply += "\n❌ Mismatched private key and certificate public key"
    else:
        reply += "\n❌ Invalid private key"

    # Keychain Authentication
    flag = True
    for i in range(pem_number - 1):
        son_certificate = x509.load_pem_x509_certificate(pem_certificates[i].encode(), default_backend())
        father_certificate = x509.load_pem_x509_certificate(pem_certificates[i + 1].encode(), default_backend())

        if son_certificate.issuer != father_certificate.subject:
            flag = False
            break
        signature = son_certificate.signature
        signature_algorithm = son_certificate.signature_algorithm_oid._name
        tbs_certificate = son_certificate.tbs_certificate_bytes
        public_key = father_certificate.public_key()
        try:
            if signature_algorithm in ['sha256WithRSAEncryption', 'sha1WithRSAEncryption', 'sha384WithRSAEncryption',
                                       'sha512WithRSAEncryption']:
                hash_algorithm = {
                    'sha256WithRSAEncryption': hashes.SHA256(),
                    'sha1WithRSAEncryption': hashes.SHA1(),
                    'sha384WithRSAEncryption': hashes.SHA384(),
                    'sha512WithRSAEncryption': hashes.SHA512()
                }[signature_algorithm]
                padding_algorithm = padding.PKCS1v15()
                public_key.verify(signature, tbs_certificate, padding_algorithm, hash_algorithm)
            elif signature_algorithm in ['ecdsa-with-SHA256', 'ecdsa-with-SHA1', 'ecdsa-with-SHA384',
                                         'ecdsa-with-SHA512']:
                hash_algorithm = {
                    'ecdsa-with-SHA256': hashes.SHA256(),
                    'ecdsa-with-SHA1': hashes.SHA1(),
                    'ecdsa-with-SHA384': hashes.SHA384(),
                    'ecdsa-with-SHA512': hashes.SHA512()
                }[signature_algorithm]
                padding_algorithm = ec.ECDSA(hash_algorithm)
                public_key.verify(signature, tbs_certificate, padding_algorithm)
            else:
                raise ValueError("Unsupported signature algorithms")
        except Exception:
            flag = False
            break
    if flag:
        reply += "\n✅ Valid keychain"
    else:
        reply += "\n❌ Invalid keychain"

    # Root Certificate Validation
    root_certificate = x509.load_pem_x509_certificate(pem_certificates[-1].encode(), default_backend())
    root_public_key = root_certificate.public_key()
    google_public_key = load_public_key_from_file("res/pem/google.pem")
    aosp_ec_public_key = load_public_key_from_file("res/pem/aosp_ec.pem")
    aosp_rsa_public_key = load_public_key_from_file("res/pem/aosp_rsa.pem")
    knox_public_key = load_public_key_from_file("res/pem/knox.pem")
    if compare_keys(root_public_key, google_public_key):
        reply += "\n✅ Google hardware attestation root certificate"
    elif compare_keys(root_public_key, aosp_ec_public_key):
        reply += "\n🟡 AOSP software attestation root certificate (EC)"
    elif compare_keys(root_public_key, aosp_rsa_public_key):
        reply += "\n🟡 AOSP software attestation root certificate (RSA)"
    elif compare_keys(root_public_key, knox_public_key):
        reply += "\n✅ Samsung Knox attestation root certificate"
    else:
        reply += "\n❌ Unknown root certificate"

    # Number of Certificates in Keychain
    if pem_number >= 4:
        reply += "\n🟡 More than 3 certificates in the keychain"

    # Validation of certificate revocation
    try:
        status_json = await load_from_url()
    except Exception:
        logger.error("Failed to fetch Google's revoked keybox list")
        with open("res/json/status.json", 'r', encoding='utf-8') as file:
            status_json = json.load(file)
            reply += "\n⚠️ Using local revoked keybox list"

    status = None
    for i in range(pem_number):
        certificate = x509.load_pem_x509_certificate(pem_certificates[i].encode(), default_backend())
        serial_number = certificate.serial_number
        serial_number_string = hex(serial_number)[2:].lower()
        if status_json['entries'].get(serial_number_string, None):
            status = status_json['entries'][serial_number_string]
            break
        if banned_sn and serial_number_string in banned_sn:
            reply += "\n❌ Serial number found in banned keybox list"
            break
    if not status:
        reply += "\n✅ Serial number not found in Google's revoked keybox list"
    else:
        reply += f"\n❌ Serial number found in Google's revoked keybox list\n🔍 *Reason:* `{status['reason']}`"
    reply += f"\n⏱ *Check Time (UTC):* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    reply = markdown_to_telegram_html(reply)
    await bot.reply_to(message, reply, parse_mode='HTML')


async def ban_keybox(bot, message, sn):
    """
    Ban a keybox by its serial number.
    :param bot: Bot instance
    :param message: Message instance
    :param sn: Serial number of the keybox to ban
    :return: None
    """
    banned_sn = BotElara.get('banned_sn', [])
    if sn in banned_sn:
        await bot.reply_to(message, "This keybox has been banned.")
    else:
        banned_sn.append(sn)
        BotElara.set('banned_sn', banned_sn)
        await bot.reply_to(message, "Banned successfully.")


async def unban_keybox(bot, message, sn):
    """
    Unban a keybox by its serial number.
    :param bot: Bot instance
    :param message: Message instance
    :param sn: Serial number of the keybox to unban
    :return: None
    """
    banned_sn = BotElara.get('banned_sn')
    if banned_sn is None:
        await bot.reply_to(message, "No keybox has been banned.")
    else:
        if sn in banned_sn:
            banned_sn.remove(sn)
            BotElara.set('banned_sn', banned_sn)
            await bot.reply_to(message, "Unbanned successfully.")
        else:
            await bot.reply_to(message, "This keybox has not been banned.")


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    # 命令处理器 - 需要回复一个文件
    async def check_command_handler(bot, message: types.Message):
        if not (message.reply_to_message and message.reply_to_message.document):
            await bot.reply_to(message, "Please reply to a keybox.xml file.")
            return
        document = message.reply_to_message.document
        await handle_keybox_check(bot, message, document)

    middleware.register_command_handler(
        commands=['check'],
        callback=check_command_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=['private', 'group', 'supergroup']
    )

    # 文件处理器 - 直接处理上传的文件
    async def document_handler(bot, message: types.Message):
        if message.document:
            document = message.document
            await handle_keybox_check(bot, message, document)

    middleware.register_message_handler(
        callback=document_handler,
        plugin_name=plugin_name,
        handler_name="keybox_checker_document_handler",
        priority=50,
        stop_propagation=False,  # 不阻止其他处理器
        content_types=['document'],
        chat_types=['private']
    )

    # ban_keybox 命令处理器
    async def ban_keybox_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            sn = command_args[1].lower()
            await ban_keybox(bot, message, sn)
        else:
            await bot.reply_to(message, "Usage: /ban_keybox <serial_number>\nExample: /ban_keybox 1a2b3c4d5e6f")

    middleware.register_command_handler(
        commands=['ban_keybox'],
        callback=ban_keybox_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=['private', 'group', 'supergroup']
    )

    # unban_keybox 命令处理器
    async def unban_keybox_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            sn = command_args[1].lower()
            await unban_keybox(bot, message, sn)
        else:
            await bot.reply_to(message, "Usage: /unban_keybox <serial_number>\nExample: /unban_keybox 1a2b3c4d5e6f")

    middleware.register_command_handler(
        commands=['unban_keybox'],
        callback=unban_keybox_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=['private', 'group', 'supergroup']
    )

    logger.info(f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}")

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
