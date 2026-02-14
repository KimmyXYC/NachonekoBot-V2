# -*- coding: utf-8 -*-
# @Time    : 2025/6/22 16:50
# @Author  : KimmyXYC
# @File    : get_revoke_list.py
# @Software: PyCharm

import requests
import time
import json


def load_from_url():
    url = "https://android.googleapis.com/attestation/status"

    headers = {
        "Cache-Control": "max-age=0, no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    params = {"ts": int(time.time())}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"Error fetching data: {response.status_code}")
    return response.json()


def save_to_file(data):
    file_path = "status.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Data saved to {file_path}")


def main():
    try:
        data = load_from_url()
        save_to_file(data)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
