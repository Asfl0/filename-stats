# -*- coding: utf-8 -*-
"""
pattern_presets.py —— 常用格式预设（人话模板 ↔ 正则）

目的：让用户不用记正则，点/选一个"人话模板"就能插入对应格式。

结构：
    每个预设是一个 dict：
        {
          "name":    "数字_名称",              # 界面显示（人话）
          "example": "123_会议记录",           # 示例文件名，帮助理解
          "pattern": r"^(\d+)[\s_\-\.]+(.+)$",  # 实际正则
          "fields":  ["编号", "名称"],          # 字段名
        }

三层预设（谁在 exe 里、谁在 exe 外）：
    1) BUILTIN          内置预设，写死在源码里，永远在 exe 内；
    2) FROZEN_CUSTOM    固化预设，写死在源码里，随 exe 一起打包，
                        换机器 / 删掉 presets.json 都不会丢；
    3) presets.json     运行时自定义预设，与程序同目录，运行时可增删，
                        换机器会丢（除非重新构建把它固化）。

扩展：
    - 加内置预设  → 编辑 BUILTIN；
    - 默认/固化   → 编辑 FROZEN_CUSTOM，或构建时用 presets.json 自动注入
                    （见 build.py 的 inject_frozen_presets）；
    - 临时自定义  → GUI“管理预设…”保存到 presets.json。
"""

import os
import json

# 统一配置（单个 config.json：预设 + AI 设置都放里面）
try:
    import app_config
except Exception:  # 兜底
    app_config = None


# ------------------------------------------------------------------
# 固化预设（FROZEN_CUSTOM）——会被打包进 exe 的自定义预设
# ------------------------------------------------------------------
# 这里的条目会被 PyInstaller 打进 exe，因此无论把 exe 拷到哪台电脑、
# 有没有 presets.json，这些预设都在（真正意义上的“存进 exe”）。
#
# 怎么往里加：
#   1) GUI 里“管理预设…”保存的会写到 presets.json（运行时可改，换机器会丢）；
#   2) 想让某个预设“永久固化进 exe”，把它从 presets.json 复制到下面的列表，
#      然后重新构建：  build\python\python.exe build.py rebuild
#   3) 构建时若存在 presets.json，build.py 会自动合并进下面的列表（见 build.py）。
#
# 条目格式与内置预设相同：
#   {"name": "名称", "example": "示例", "pattern": r"正则", "fields": ["字段1"]}
# >>> FROZEN_CUSTOM_BEGIN
FROZEN_CUSTOM = [
    {"name": "自定义正则", "example": "手动填写下面的正则与字段", "pattern": r"(\d+)([\u4e00-\u9fa5]+)", "fields": ["数字汉字"]},
    {"name": "数字汉字", "example": "手动填写下面的正则与字段", "pattern": r"(\d+)([\u4e00-\u9fa5]+)", "fields": ["数字", "汉字"]},
]
# <<< FROZEN_CUSTOM_END


# ------------------------------------------------------------------
# 内置预设（按使用频率排序；新增一条即多一个选项）
# ------------------------------------------------------------------
BUILTIN = [
    {
        "name": "数字_名称",
        "example": "123_会议记录 · 12-合同 · 8.报告",
        "pattern": r"^(\d+)[\s_\-\.]+(.+)$",
        "fields": ["编号", "名称"],
    },
    {
        "name": "数字 空格 名称",
        "example": "123 会议记录",
        "pattern": r"^(\d+)\s+(.+)$",
        "fields": ["编号", "名称"],
    },
    {
        "name": "名称_v版本",
        "example": "报告_v3",
        "pattern": r"^(.+)_v(\d+)$",
        "fields": ["名称", "版本"],
    },
    {
        "name": "数字_名称_版本",
        "example": "12_报告_v3",
        "pattern": r"^\d+_(.+)_v(\d+)$",
        "fields": ["名称", "版本"],
    },
    {
        "name": "日期_名称",
        "example": "20240101_合同",
        "pattern": r"^(\d{8})[_\-\s]+(.+)$",
        "fields": ["日期", "名称"],
    },
    {
        "name": "括号编号 名称",
        "example": "(12) 报告",
        "pattern": r"^\((\d+)\)\s*(.+)$",
        "fields": ["编号", "名称"],
    },
    {
        "name": "名称（整串不拆分）",
        "example": "任意文件名",
        "pattern": r"^(.+)$",
        "fields": ["名称"],
    },
    {
        "name": "自定义正则",
        "example": "手动填写下面的正则与字段",
        "pattern": "",
        "fields": [],
    },
]


# ------------------------------------------------------------------
# 插入片段（snippet）：往当前正则的光标处插入一段字符 / 字符类
# ------------------------------------------------------------------
# kind:
#   "text"     直接插入 text（字面字符）
#   "regex"    插入 text（带正则含义片段）
#   "custom"   弹输入框，把用户输入的字面字符插入
SNIPPETS = [
    # 自定义字符：弹输入框，你输入什么就原样插什么
    # （下划线、横杠、点号、空格、斜杠、左右括号、反斜杠等
    #   都靠它搞定，不再单列）
    {"name": "自定义字符…",      "kind": "custom", "text": "",
     "desc": "弹输入框，你输入什么就原样插入什么（下划线 _ 、横杠 - 、点号 . 、"
             "空格、斜杠 / 、括号 () 、反斜杠 \\ 、冒号 : 等常用字面字符都可以）"},
    # 正则片段：带正则含义
    {"name": "任意空白 \\s+",     "kind": "regex", "text": r"\\s+",
     "desc": "一个或多个空格/制表符等空白（贪婪吃多处）"},
    {"name": "分隔符类 [\\s_\\.-]+", "kind": "regex", "text": r"[\\s_\\-\\.]+",
     "desc": "空格、下划线、横杠、点 任选其一或多个连续出现"},
    {"name": "数字 (\\d+)",     "kind": "regex", "text": r"(\\d+)",
     "desc": "捕获一串连续数字（如 123），作为一个字段"},
    {"name": "中文 ([\\u4e00-\\u9fa5]+)", "kind": "regex", "text": r"([\u4e00-\u9fa5]+)",
     "desc": "捕获一串连续汉字（如 会议记录），作为一个字段"},
    {"name": "字母 ([A-Za-z]+)", "kind": "regex", "text": r"([A-Za-z]+)",
     "desc": "捕获一串连续英文字母（如 abc），作为一个字段"},
    {"name": "任意字符 (.+)",    "kind": "regex", "text": r"(.+)",
     "desc": "贪婪：尽量多地吃字符，一直到本段末尾（默认用这个）"},
        {"name": "非贪婪 (.*?)",     "kind": "regex", "text": r"(.*?)",
     "desc": "少吃：尽量少地吃字符，一直少吃到能匹配上它后面那段为止。"
             "它后面紧跟的那个字符就叫“分隔符”，比如你插在下划线 _ 、横杠 - 、"
             "点号 . 、空格、斜杠 / 、撇号 ' 、左括号 ( 、汉字 等之前。"
             "例：^(.*?)_(\\d+)$ 里的 _ 就是分隔符，把 A_1_会议 拆成 A 和 1；"
             "换成贪婪 (.+) 就会吃到最后一个下划线。"},

]


def _frozen_presets():
    """返回已固化进 exe 的自定义预设（FROZEN_CUSTOM）。"""
    out = []
    for it in FROZEN_CUSTOM:
        if isinstance(it, dict) and it.get("name") and it.get("pattern"):
            out.append({
                "name": str(it["name"]),
                "example": str(it.get("example", "")),
                "pattern": str(it["pattern"]),
                "fields": [str(x) for x in it.get("fields", [])],
            })
    return out


def all_snippets():
    """返回全部插入片段（内置）。"""
    return [dict(s) for s in SNIPPETS]


def find_snippet(name):
    """按名字或序号（从1开始）找片段。找不到返回 None。"""
    for s in SNIPPETS:
        if s["name"] == name:
            return dict(s)
    if str(name).strip().isdigit():
        i = int(str(name).strip())
        if 1 <= i <= len(SNIPPETS):
            return dict(SNIPPETS[i - 1])
    return None


# ------------------------------------------------------------------
# 用户自定义预设的存放位置与读写
# ------------------------------------------------------------------
def _json_path(dir_hint=None):
    """统一配置文件 config.json 的路径。"""
    if app_config is not None:
        return app_config.config_path(dir_hint)
    base = dir_hint
    if not base:
        try:
            import sys
            if getattr(sys, "frozen", False):
                base = os.path.dirname(os.path.abspath(sys.executable))
            else:
                base = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base = os.getcwd()
    return os.path.join(base, "config.json")


def load_custom(dir_hint=None):
    """读取用户自定义预设列表。

    返回值 = exe 内固化预设（FROZEN_CUSTOM） + presets.json 里的运行时预设。
    同名时以 presets.json 为准（用户当场改的优先）。
    文件不存在或损坏时也会返回固化预设，保证不影响可用性。
    """
    merged = []
    seen = {}
    for p in _frozen_presets():
        seen[p["name"]] = len(merged)
        merged.append(dict(p))

    path = _json_path(dir_hint)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("presets", []) if isinstance(data, dict) else data
            for it in items:
                if not isinstance(it, dict) or "name" not in it or "pattern" not in it:
                    continue
                p = {
                    "name": str(it["name"]),
                    "example": str(it.get("example", "")),
                    "pattern": str(it["pattern"]),
                    "fields": [str(x) for x in it.get("fields", [])],
                }
                if p["name"] in seen:
                    merged[seen[p["name"]]] = p
                else:
                    seen[p["name"]] = len(merged)
                    merged.append(p)
        except Exception:
            pass
    return merged


def save_custom(presets, dir_hint=None):
    """保存用户自定义预设列表到 presets.json。

    注意：固化预设（FROZEN_CUSTOM）不写进 json（它们本就在 exe 内），
    避免 json 删掉后固化预设也丢。
    """
    frozen_names = {p["name"] for p in _frozen_presets()}
    runtime = [p for p in presets if p["name"] not in frozen_names]
    path = _json_path(dir_hint)
    data = {"presets": [
        {"name": p["name"], "example": p.get("example", ""),
         "pattern": p["pattern"], "fields": list(p.get("fields", []))}
        for p in runtime
    ]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


# ------------------------------------------------------------------
# 合并后的完整预设列表（内置 + 自定义）
# ------------------------------------------------------------------
def all_presets(dir_hint=None):
    """内置预设 + 用户自定义预设（自定义追加在后，若有同名则覆盖内置）。"""
    merged = []
    seen = {}
    for p in BUILTIN:
        seen[p["name"]] = len(merged)
        merged.append(dict(p))
    for p in load_custom(dir_hint):
        if p["name"] in seen:
            merged[seen[p["name"]]] = dict(p)
        else:
            seen[p["name"]] = len(merged)
            merged.append(dict(p))
    return merged


def find_preset(name, dir_hint=None):
    """按名字找预设。找不到返回 None。也支持序号（字符串数字，从 1 开始）。"""
    presets = all_presets(dir_hint)
    for p in presets:
        if p["name"] == name:
            return p
    if str(name).strip().isdigit():
        i = int(str(name).strip())
        if 1 <= i <= len(presets):
            return presets[i - 1]
    return None

def load_custom(dir_hint=None):
    """读取用户自定义预设列表。

    返回值 = exe 内固化预设（FROZEN_CUSTOM） + config.json 里的运行时预设。
    同名时以 config.json 为准（用户当场改的优先）。
    旧 presets.json 仍在时由 app_config 自动迁移合并，不影响可用。
    """
    merged = []
    seen = {}
    for p in _frozen_presets():
        seen[p["name"]] = len(merged)
        merged.append(dict(p))

    if app_config is not None:
        items = app_config.load_section("presets", dir_hint, default=[])
    else:
        data = None
        path = _json_path(dir_hint)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None
        items = (data.get("presets", []) if isinstance(data, dict) else data) or []

    for it in items:
        if not isinstance(it, dict) or "name" not in it or "pattern" not in it:
            continue
        p = {
            "name": str(it["name"]),
            "example": str(it.get("example", "")),
            "pattern": str(it["pattern"]),
            "fields": [str(x) for x in it.get("fields", [])],
        }
        if p["name"] in seen:
            merged[seen[p["name"]]] = p
        else:
            seen[p["name"]] = len(merged)
            merged.append(p)
    return merged


def save_custom(presets, dir_hint=None):
    """保存用户自定义预设列表到 config.json 的 presets 段。

    固化预设（FROZEN_CUSTOM）不写进 json（它们本就在 exe 内）。
    只更新 presets 段，不会动 ai 段（AI 设置）。
    """
    frozen_names = {p["name"] for p in _frozen_presets()}
    runtime = [p for p in presets if p["name"] not in frozen_names]
    payload = [
        {"name": p["name"], "example": p.get("example", ""),
         "pattern": p["pattern"], "fields": list(p.get("fields", []))}
        for p in runtime
    ]
    if app_config is not None:
        return app_config.save_section("presets", payload, dir_hint)
    path = _json_path(dir_hint)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"presets": payload}, f, ensure_ascii=False, indent=2)
    return path