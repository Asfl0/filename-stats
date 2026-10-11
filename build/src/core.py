# -*- coding: utf-8 -*-
"""
core.py —— 文件名统计核心逻辑（编排层，与界面解耦）

职责分层（本文件只做"编排"，把两层拼起来）：
  - file_source.py   获取文件名（IO 层：枚举目录）
  - name_parser.py   解析文件名（纯逻辑层：正则捕获字段）
  - core.py          对外统一入口 + 排序 / TSV 输出

对外 API 保持稳定（DEFAULT_PATTERN / DEFAULT_FIELDS / SELF_MARKERS /
compile_pattern / parse_fields / scan_directory / sort_rows / to_tsv），
因此 GUI / CLI / main 无需改动。
"""

# 统一配置（单个 config.json：预设 + AI 设置都在里面）
import app_config

# 重新导出，供既有调用方（GUI/CLI）继续使用，保持 API 兼容
from file_source import SELF_MARKERS, list_files
from name_parser import (
    DEFAULT_PATTERN,
    DEFAULT_FIELDS,
    compile_pattern,
    parse_fields,
    parse_name,
    validate_pattern,
)
# 常用格式预设（人话模板 ↔ 正则）
from pattern_presets import (
    BUILTIN as PRESET_BUILTIN,
    SNIPPETS as PRESET_SNIPPETS,
    all_presets,
    find_preset,
    all_snippets,
    find_snippet,
    load_custom as load_custom_presets,
    save_custom as save_custom_presets,
)
# AI 辅助（把"人话描述"变成正则）
from ai_helper import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT,
    DEFAULT_SAMPLE_USER_PROMPT,
    default_config as default_ai_config,
    load_config as load_ai_config,
    save_config as save_ai_config,
    chat as ai_chat,
    extract_pattern as ai_extract_pattern,
    validate_pattern as ai_validate_pattern,
    sample_filenames as ai_sample_filenames,
    build_sample_question as ai_build_sample_question,
)

# 统一配置文件的路径（供界面/帮助文本显示）
CONFIG_NAME = app_config.CONFIG_NAME
config_path = app_config.config_path


def scan_directory(directory, pattern=DEFAULT_PATTERN, fields=None,
                   extra_exclude=None, recursive=False):
    """
    扫描目录，按 pattern 提取字段。= 获取文件名 + 解析文件名。

    参数:
        directory     要扫描的目录
        pattern       正则（用 () 捕获字段）
        fields        字段名列表
        extra_exclude 额外要排除的文件名集合
        recursive     True 时递归扫描子目录

    返回 dict:
        {
          'rows': [{'file','relpath','ext','values':[...]}, ...],
          'fields': [...],
          'unmatched': int,      # 不满足格式的文件数
          'total': int,          # 参与统计的文件总数
        }
    """
    fields = fields or list(DEFAULT_FIELDS)
    rx = compile_pattern(pattern)
    n_fields = len(fields)

    # 1) 获取文件名（IO 层，已自动排除自身与 extra_exclude）
    files = list_files(directory, recursive=recursive, exclude=extra_exclude)

    # 2) 解析文件名（纯逻辑层）
    rows = []
    unmatched = 0
    for item in files:
        parsed = parse_name(item["name"], rx, n_fields)
        if parsed is None:
            unmatched += 1
            continue
        parsed["relpath"] = item["relpath"]
        rows.append(parsed)

    return {
        "rows": rows,
        "fields": fields,
        "unmatched": unmatched,
        "total": len(files),
    }


def sort_rows(rows, mode="number"):
    """
    排序。mode:
        'number' 按第一个字段数值排序（非数字排最后）
        'name'   按文件名
        'none'   不变
    """
    if mode == "name":
        return sorted(rows, key=lambda r: r["file"])
    if mode == "none":
        return list(rows)
    def key(r):
        v = r["values"][0] if r["values"] else ""
        num = int(v) if str(v).isdigit() else 10 ** 18
        return (num, r["file"])
    return sorted(rows, key=key)


def to_tsv(rows, fields, include_header=True):
    """输出制表符分隔文本，可直接粘贴进 Excel。"""
    lines = []
    if include_header:
        lines.append("\t".join(fields))
    for r in rows:
        lines.append("\t".join(str(v) for v in r["values"]))
    return "\r\n".join(lines)
