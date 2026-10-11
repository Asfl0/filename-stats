# -*- coding: utf-8 -*-
"""
name_parser.py —— 文件名解析（纯逻辑层）

只负责"解析文件名"这件事：
  - 编译格式正则
  - 用一个文件名按正则捕获出字段值
  - 解析字段名列表

这一层不碰文件系统，是纯函数，可独立单元测试。
它只吃"名字字符串"，不认识目录、路径、文件是否存在。
"""

import os
import re

# 默认格式：数字 + 分隔符(空格/下划线/横杠/点) + 名称
DEFAULT_PATTERN = r"^(\d+)[\s_\-\.]+(.+)$"
DEFAULT_FIELDS = ["编号", "名称"]


def compile_pattern(pattern):
    """编译正则，失败抛出 ValueError。"""
    try:
        return re.compile(pattern)
    except re.error as e:
        raise ValueError(f"正则无效: {e}")


def validate_pattern(pattern):
    """检测正则语法是否正确（不抛异常，返回结构化结果）。

    返回 dict:
        {
          'ok':       bool,           # 语法是否正确
          'message':  str,            # 人性化说明
          'groups':   int,            # 捕获组个数（仅 ok 时有效）
          'group_names': [str, ...],  # 具名捕获组名字（按组序，无名处为 ''）
          'warn':     str,            # 非致命提醒（可为空）
        }
    """
    pat = pattern or ""
    if not pat.strip():
        return {"ok": False, "message": "正则为空。",
                "groups": 0, "group_names": [], "warn": ""}
    try:
        rx = re.compile(pat)
    except re.error as e:
        return {"ok": False, "message": f"语法错误：{e}",
                "groups": 0, "group_names": [], "warn": ""}
    names = list(rx.groupindex.keys())
    ordered = []
    for i in range(1, rx.groups + 1):
        ordered.append(names[i - 1] if i - 1 < len(names) else "")
    warn = ""
    if rx.groups == 0:
        warn = "能编译，但没有捕获组 ()，不会提取任何字段，只会判断是否匹配。"
    elif rx.groupindex:
        # 具名组顺序不等于编号顺序，提示一下
        pass
    return {"ok": True, "message": f"语法正确，共 {rx.groups} 个捕获组。",
            "groups": rx.groups, "group_names": ordered, "warn": warn}


def parse_fields(text):
    """把 '编号,名称' 解析成 ['编号','名称']，中英文逗号均可。"""
    fields = [x.strip() for x in re.split(r"[,，]", text or "") if x.strip()]
    return fields or list(DEFAULT_FIELDS)


def parse_name(name, rx, n_fields):
    """
    用已编译的正则 rx 解析单个文件名。

    参数:
        name      文件名（含扩展名）
        rx        compile_pattern() 返回的正则对象
        n_fields  期望的字段个数

    返回 dict 或 None（不匹配时返回 None）：
        {
          'file':    原文件名
          'ext':     扩展名（小写、无点）
          'values':  捕获到的字段值列表（长度补齐到 n_fields）
        }
    """
    base, ext = os.path.splitext(name)
    m = rx.match(base)
    if not m:
        return None
    vals = list(m.groups())
    while len(vals) < n_fields:
        vals.append("")
    return {
        "file": name,
        "ext": ext.lstrip(".").lower(),
        "values": vals[:n_fields],
    }
