# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 12:47
# @Author  : KimmyXYC
# @File    : __init__.py.py
# @Software: PyCharm

import importlib
import os

__all__ = []

module_dir = os.path.dirname(__file__)

for file in os.listdir(module_dir):
    if file.endswith(".py") and file not in ("__init__.py",):
        module_name = file[:-3]
        module = importlib.import_module(f".{module_name}", package=__name__)
        globals()[module_name] = module
        __all__.append(module_name)
