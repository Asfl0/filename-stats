# -*- coding: utf-8 -*-
"""
app_config.py —— 统一配置存取（单一 config.json）

背景：
    以前分开写两个文件——presets.json（自定义预设）+ ai_config.json（AI 设置）。
    用户希望合为一个。现在统一存到程序目录下的：

        config.json
        {
          "presets":    [ {...}, {...} ],     # 自定义预设（与旧 presets.json 结构一致）
          "ai":         { ... }               # AI 设置（与旧 ai_config.json 结构一致）
        }

设计：
    - 只做“读写一个 json 文件 + 兼容迁移旧文件”这一件事，保持单一职责；
    - 任何一层（预设 / AI）需要读自己的部分就调这里，互不干扰；
    - 首次运行若发现旧的 presets.json / ai_config.json 且还没有 config.json，
      自动把它们的内容合并进 config.json（旧文件保留不动，作为兜底备份）。
    - 路径解析：优先传进来的 dir_hint（通常是程序目录），
      否则打包后用 exe 所在目录，开发时用本文件所在目录。

不引入任何三方依赖。
"""

import os
import json

CONFIG_NAME = "config.json"
LEGACY_PRESETS = "presets.json"
LEGACY_AI = "ai_config.json"


def base_dir(dir_hint=None):
    """确定程序目录：优先 dir_hint，其次 exe 目录，再退回源码目录。"""
    if dir_hint:
        return dir_hint
    try:
        import sys
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def config_path(dir_hint=None):
    """config.json 的完整路径。"""
    return os.path.join(base_dir(dir_hint), CONFIG_NAME)


def _empty():
    return {"presets": [], "ai": {}}


def _read_json(path):
    """读取一个 json 文件；不存在/损坏返回 None。"""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _legacy_presets_list(dir_hint=None):
    """读旧 presets.json，返回预设列表（可能为空）。"""
    data = _read_json(os.path.join(base_dir(dir_hint), LEGACY_PRESETS))
    if data is None:
        return []
    items = data.get("presets", []) if isinstance(data, dict) else data
    return items if isinstance(items, list) else []


def _legacy_ai_dict(dir_hint=None):
    """读旧 ai_config.json，返回 dict（可能为空）。"""
    data = _read_json(os.path.join(base_dir(dir_hint), LEGACY_AI))
    return data if isinstance(data, dict) else {}


def load(dir_hint=None):
    """读取整份 config.json。

    - 不存在时：尝试从旧的两个文件迁移合并，并（尽量）落盘成 config.json；
    - 返回 dict，至少含 'presets'(list) 与 'ai'(dict) 两个键。
    """
    path = config_path(dir_hint)
    data = _read_json(path)
    if data is None:
        # 首次：尝试从旧文件迁移
        merged = {
            "presets": _legacy_presets_list(dir_hint),
            "ai": _legacy_ai_dict(dir_hint),
        }
        # 只有确实读到旧数据才落盘，避免凭空创建空 config.json
        if merged["presets"] or merged["ai"]:
            try:
                _write(path, merged)
            except Exception:
                pass
        return merged

    # 规整结构
    out = _empty()
    if isinstance(data, dict):
        if isinstance(data.get("presets"), list):
            out["presets"] = data["presets"]
        if isinstance(data.get("ai"), dict):
            out["ai"] = data["ai"]
    return out


def save(data, dir_hint=None):
    """把整份配置写回 config.json。data 至少含 presets / ai。"""
    path = config_path(dir_hint)
    out = _empty()
    if isinstance(data, dict):
        if isinstance(data.get("presets"), list):
            out["presets"] = data["presets"]
        if isinstance(data.get("ai"), dict):
            out["ai"] = data["ai"]
    _write(path, out)
    return path


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# 局部读写（供预设层 / AI 层各自使用，互不覆盖对方的数据）
# ------------------------------------------------------------------
def load_section(name, dir_hint=None, default=None):
    """读取 config.json 里的某个键（'presets' / 'ai'）。"""
    data = load(dir_hint)
    val = data.get(name, default)
    return val if val is not None else (default if default is not None else ([] if name == "presets" else {}))


def save_section(name, value, dir_hint=None):
    """只更新 config.json 里的某个键，保留另一个键的数据。"""
    data = load(dir_hint)
    data[name] = value
    return save(data, dir_hint)
