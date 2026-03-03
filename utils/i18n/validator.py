# -*- coding: utf-8 -*-
"""
启动时翻译 key 完整性校验。

以 DEFAULT_LANGUAGE 为基准，检查其他语言的缺失 key 和 placeholder 不一致。
"""

import re
from pathlib import Path
from typing import List

from loguru import logger

from utils.i18n.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from utils.i18n.service import _load_framework_locale, _load_plugin_locale


_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _discover_plugin_names() -> List[str]:
    """扫描 en/plugins/ 目录发现所有插件名"""
    plugins_dir = Path(__file__).resolve().parent / DEFAULT_LANGUAGE / "plugins"
    if not plugins_dir.is_dir():
        return []
    return sorted(p.stem for p in plugins_dir.glob("*.json"))


def validate_translations() -> List[str]:
    """
    校验所有语言文件的 key 完整性。

    返回问题列表（字符串），同时通过 logger.warning 输出。
    """
    issues: List[str] = []

    plugin_names = _discover_plugin_names()

    for lang in SUPPORTED_LANGUAGES:
        if lang == DEFAULT_LANGUAGE:
            continue

        # --- Framework keys ---
        en_fw = _load_framework_locale(DEFAULT_LANGUAGE)
        lang_fw = _load_framework_locale(lang)
        missing_fw = set(en_fw.keys()) - set(lang_fw.keys())
        if missing_fw:
            msg = f"[{lang}] framework: missing {len(missing_fw)} keys: {sorted(missing_fw)}"
            issues.append(msg)

        # Check placeholder consistency for framework
        for key in set(en_fw.keys()) & set(lang_fw.keys()):
            en_ph = set(_PLACEHOLDER_RE.findall(en_fw[key]))
            lang_ph = set(_PLACEHOLDER_RE.findall(lang_fw[key]))
            if en_ph != lang_ph:
                msg = f"[{lang}] framework.{key}: placeholder mismatch en={en_ph} {lang}={lang_ph}"
                issues.append(msg)

        # --- Plugin keys ---
        for plugin_name in plugin_names:
            en_map = _load_plugin_locale(DEFAULT_LANGUAGE, plugin_name)
            lang_map = _load_plugin_locale(lang, plugin_name)
            missing = set(en_map.keys()) - set(lang_map.keys())
            if missing:
                msg = f"[{lang}] {plugin_name}: missing {len(missing)} keys: {sorted(missing)}"
                issues.append(msg)

            # Check placeholder consistency for plugins
            for key in set(en_map.keys()) & set(lang_map.keys()):
                en_ph = set(_PLACEHOLDER_RE.findall(en_map[key]))
                lang_ph = set(_PLACEHOLDER_RE.findall(lang_map[key]))
                if en_ph != lang_ph:
                    msg = f"[{lang}] {plugin_name}.{key}: placeholder mismatch en={en_ph} {lang}={lang_ph}"
                    issues.append(msg)

    if issues:
        logger.warning(f"i18n validation: found {len(issues)} issue(s)")
        for issue in issues:
            logger.warning(f"  {issue}")
    else:
        logger.info("i18n validation: all translations OK")

    return issues
