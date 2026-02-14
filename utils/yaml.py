# -*- coding: utf-8 -*-
# @Time    : 2025/4/30 20:41
# @Author  : KimmyXYC
# @File    : yaml.py
# @Software: PyCharm

import yaml


def load_yaml_file():
    """
    Load the YAML configuration file.
    :return: A dictionary containing the configuration data.
    """
    with open("conf_dir/config.yaml", "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data


BotConfig = load_yaml_file()
