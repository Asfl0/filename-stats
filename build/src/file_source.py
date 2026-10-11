# -*- coding: utf-8 -*-
"""
file_source.py —— 文件名来源（IO 层）

只负责"获取文件名"这件事：
  - 枚举一个目录里的文件（可递归）
  - 过滤掉程序自身 / 调用方指定的排除项
  - 返回结构化条目，交给上层做解析

这一层不关心文件名的格式，也不做任何正则解析。
把它与解析逻辑分开后，IO 与纯逻辑可各自独立测试、独立替换
（例如以后要支持从剪贴板、清单文件、网络路径取文件名，只改这里）。
"""

import os

# 需要排除的文件名（程序自身与其常见别名）
SELF_MARKERS = {
    "文件名统计.exe", "文件统计.exe", "file_stat.exe",
    "文件名统计_cli.exe", "文件统计_cli.exe", "file_stat_cli.exe",
    "文件名统计.py", "file_stat.py",
    "文件名统计_gui.py", "file_stat_gui.py",
    "文件名统计_cli.py", "file_stat_cli.py",
}


def list_files(directory, recursive=False, exclude=None):
    """
    枚举目录中的文件。

    参数:
        directory  要扫描的目录
        recursive  True 时递归扫描子目录
        exclude    额外要排除的文件名集合（与 SELF_MARKERS 合并）

    返回 list[dict]，每项：
        {
          'name':   文件名（含扩展名）
          'full':   完整路径
          'relpath':相对 directory 的路径
        }
    仅返回文件，不返回目录；按名称排序，结果稳定。
    """
    exclude_set = set(SELF_MARKERS)
    if exclude:
        exclude_set |= set(exclude)

    items = []

    def add(full, name):
        if name in exclude_set:
            return
        items.append({
            "name": name,
            "full": full,
            "relpath": os.path.relpath(full, directory),
        })

    if recursive:
        for root, _dirs, files in os.walk(directory):
            for name in sorted(files):
                add(os.path.join(root, name), name)
    else:
        try:
            entries = sorted(os.listdir(directory))
        except OSError as e:
            raise ValueError(f"无法读取目录: {e}")
        for name in entries:
            full = os.path.join(directory, name)
            if os.path.isfile(full):
                add(full, name)

    return items
