# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 13:03
# @Author  : KimmyXYC
# @File    : ip.py
# @Software: PyCharm
import ipaddress
import socket
import aiohttp
import idna
import whoisit
import json
import asyncio
from loguru import logger
from datetime import datetime
from ipaddress import IPv4Network, IPv6Network
from utils.yaml import BotConfig


def check_url(url):
    """
    Check if the URL is an IP address or a domain name.
    If it's an IP address, return it with its version (v4 or v6).
    If it's a domain name, resolve it to an IP address.
    :param url: The URL to check.
    :return: A tuple containing the IP address and its version (v4 or v6) or None if it's a domain name.
    """
    try:
        ip = ipaddress.ip_address(url)
        if ip.version == 4:
            return url, "v4"
        elif ip.version == 6:
            return url, "v6"
    except ValueError:
        return get_ip_address(url), None


def convert_to_punycode(domain):
    """
    Convert a domain name to Punycode format.
    :param domain: The domain name to convert.
    :return: The Punycode representation of the domain name.
    If the domain name is already in ASCII format, return it as is.
    """
    try:
        domain.encode('ascii')
    except UnicodeEncodeError:
        return idna.encode(domain).decode('ascii')
    else:
        return domain


def get_ip_address(domain):
    """
    Resolve a domain name to its IP address.
    :param domain: The domain name to resolve.
    :return: The first resolved IP address or None if the resolution fails.
    """
    try:
        addr_info = socket.getaddrinfo(domain, None, socket.AF_UNSPEC)
        ip_addresses = []
        for info in addr_info:
            ip_address = info[4][0]
            ip_addresses.append(ip_address)
        return ip_addresses[0]
    except socket.gaierror as e:
        logger.error(f"Domain name resolution failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unknown error: {e}")
        return None


def format_rdap_data(data):
    """
    Format RDAP data into a more readable JSON format.
    :param data: The RDAP data to format.
    :return: A formatted JSON string or an empty string if the data is empty.
    """
    def clean_data(data):
        if isinstance(data, dict):
            cleaned_dict = {}
            for k, v in data.items():
                if k in ["url", "type", "terms_of_service_url", "whois_server"]:
                    continue
                if v in [None, "", [], {}, "DATA REDACTED"]:
                    continue

                cleaned_value = clean_data(v)

                if cleaned_value is None:
                    continue

                cleaned_dict[k] = cleaned_value

            return cleaned_dict if cleaned_dict else None
        elif isinstance(data, list):
            cleaned_list = []
            for item in data:
                if item in [None, "", [], {}, "DATA REDACTED"]:
                    continue

                cleaned_item = clean_data(item)

                if cleaned_item is None:
                    continue

                cleaned_list.append(cleaned_item)

            return cleaned_list if cleaned_list else None
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, (IPv4Network, IPv6Network)):
            return str(data)
        else:
            return data

    cleaned_data = clean_data(data)
    if not cleaned_data:
        return ""

    json_data = json.dumps(cleaned_data, indent=4, ensure_ascii=False)

    return f"```{json_data}```"


async def ali_ipcity_ip(ip_addr, appcode, is_v6=False):
    """
    Query IP information using Aliyun's IP City API.
    :param ip_addr: The IP address to query.
    :param appcode: The AppCode for authentication.
    :param is_v6: Boolean indicating if the IP address is IPv6.
    :return: A tuple containing the status and the result.
    """
    if is_v6:
        url = "https://ipv6city.market.alicloudapi.com/ip/ipv6/query"
    else:
        url = "https://ipcity.market.alicloudapi.com/ip/city/query"
    headers = {"Authorization": f"APPCODE {appcode}"}
    params = {"ip": ip_addr}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data["code"] == 200:
                    return True, data["data"]["result"]
                else:
                    return False, data["msg"]
            else:
                return False, f"Request failed with status {response.status}"


async def ipapi_ip(ip_addr):
    """
    Query IP information using ip-api.com.
    :param ip_addr: The IP address to query.
    :return: A tuple containing the status and the result.
    """
    url = f"http://ip-api.com/json/{ip_addr}"
    params = {
        "fields": "status,message,country,regionName,city,lat,lon,isp,org,as,mobile,proxy,hosting,query"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data["status"] == "success":
                    return True, data
                else:
                    return False, data
            else:
                return False, f"Request failed with status {response.status}"


async def icp_record_check(domain, retries=3):
    """
    Check if a domain has an ICP record.
    :param domain: The domain name to check.
    :param retries: The number of retry attempts.
    :return: A tuple containing the status and the result.
    """
    url = BotConfig["icp"]["url"]
    params = {"search": domain}

    for attempt in range(retries):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data["code"] == 200:
                            return True, data["params"]["list"]
                        else:
                            return False, data["msg"]
                    else:
                        logger.warning(f"Attempt {attempt + 1} failed with status {response.status}")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")

    return False, "All retry attempts failed"


async def whois_check(data, req_type, retries=3):
    """
    Perform a WHOIS check on a domain or IP address.
    :param data: The domain or IP address to check.
    :param req_type: The type of request (domain or ip).
    :param retries: The number of retry attempts.
    :return: A tuple containing the status and the result.
    """
    for attempt in range(retries):
        try:
            await asyncio.to_thread(whoisit.bootstrap)
            if not hasattr(whoisit, req_type):
                return False, f"Invalid request type: {req_type}"

            whois_method = getattr(whoisit, req_type)
            result = await asyncio.to_thread(whois_method, data)

            # Format data
            formatted_result = format_rdap_data(result)
            return True, formatted_result
        except Exception as e:
            if attempt < retries - 1:
                continue
            if "has no known RDAP endpoint" in str(e) and req_type == "domain":
                async with aiohttp.ClientSession() as session:
                    async with session.get(f'https://namebeta.com/api/search/check?query={data}') as response:
                        if response.status == 200:
                            result = await response.json()
                            if "whois" not in result:
                                return False, result
                            result = result['whois']['whois']
                            lines = result.splitlines()
                            filtered_result = [line for line in lines if
                                               'REDACTED FOR PRIVACY' not in line and 'Please query the' not in line
                                               and not line.strip().endswith(':')]
                            return True, "\n".join(filtered_result).split("For more information")[0]
                        else:
                            return False, f"Request failed with status {response.status}"
            return False, f"Failed to check whois with exception: {e}"


async def get_dns_info(domain, record_type):
    """
    Perform a DNS lookup for a given domain and record type.
    :param domain: The domain name to look up.
    :param record_type: The type of DNS record to look up (A, NS, CNAME, MX, TXT, AAAA).
    :return: A tuple containing the status and the result.
    """
    qtype = {
        "A": 1,
        "NS": 2,
        "CNAME": 5,
        "MX": 15,
        "TXT": 16,
        "AAAA": 28,
    }
    record_type = record_type.upper()
    if record_type not in qtype.keys():
        return False, "record_type error"

    url = "https://myssl.com/api/v1/tools/dns_query"
    params = {
        "qtype": qtype[record_type],
        "host": domain,
        "qmode": -1
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data["code"] == 0:
                    return True, data["data"]
                else:
                    return False, data["error"]
            else:
                return False, f"Request failed with status {response.status}"
