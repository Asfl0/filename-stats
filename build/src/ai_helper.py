# -*- coding: utf-8 -*-
"""
ai_helper.py —— AI 辅助（把"人话描述的文件格式"变成正则表达式）

职责：
  - 读写 AI 配置（存在统一的 config.json 的 ai 段，与预设同一个文件）
  - 提供一个默认系统提示词：要求 AI **只回复一条正则表达式，别的什么都不回**
  - 调用 OpenAI 兼容的 /chat/completions 接口（纯标准库 urllib，无需三方依赖）
  - 从 AI 回复里稳健地抠出正则
  - 检测正则语法（复用 name_parser.validate_pattern）

设计原则：
  - 不引入任何额外依赖（requests 等都没有），只用标准库，方便打包。
  - 配置里 api_key 是明文，仅存本机；界面里做遮挡显示。
  - 任何网络/解析错误都以异常抛出，由界面层转成友好提示。
"""

import os
import re
import json
import urllib.request
import urllib.error

# 统一配置（单个 config.json：预设 + AI 设置都放里面）
try:
    import app_config
except Exception:  # 兜底
    app_config = None


# ------------------------------------------------------------------
# 默认系统提示词：让 AI 只回一条正则
# ------------------------------------------------------------------
DEFAULT_SYSTEM_PROMPT = (
    "你是文件名格式转正则表达式的助手。用户的文件名由数字、汉字、字母和分隔符组成。\n"
    "你的唯一任务：把用户描述的文件名格式，转换成一条用于 Python re 的匹配正则。\n"
    "\n"
    "严格遵守以下输出规则：\n"
    "1. 只输出一条正则表达式本身，不要输出任何其他文字。\n"
    "2. 不要解释、不要问好、不要举例、不要加编号或项目符号。\n"
    "3. 不要使用 markdown 代码块（不要 ```），不要加引号，不要加前后缀。\n"
    "4. 需要提取的字段必须用英文半角圆括号 () 捕获，一个字段一个捕获组。\n"
    "5. 正则从行首开始匹配（以 ^ 开头），末尾用 $ 锚定文件名主体（不含扩展名）。\n"
    "6. 只用 Python re 支持的语法。分隔符用字符类，例如 [\\s_\\-\\.]+。\n"
    "7. 如果用户描述不清，也要给出你认为最合理的一条正则，不要反问。\n"
    "\n"
    "示例：\n"
    "用户：文件名是 数字_名称，例如 123_会议记录\n"
    "你：^(\\d+)[\\s_\\-\\.]+(.+)$\n"
    "用户：文件名是 编号_名称_v版本，例如 12_报告_v3\n"
    "你：^(\\d+)_(.+)_v(\\d+)$\n"
)

# 默认用户提问模板（用户可在界面里改成自己的话）
DEFAULT_USER_PROMPT = (
    "请根据下面的文件名格式描述，给出匹配正则。\n"
    "文件名格式描述：\n"
)

# 采样模式的默认提问（自动附带若干真实文件名，让 AI 自己判断格式）
DEFAULT_SAMPLE_USER_PROMPT = (
    "下面列出了一些真实文件名（已去掉扩展名）。请你阅读这些样本，"
    "自己判断它们的共同命名格式，然后给出匹配正则。\n"
    "要求：\n"
    "1. 字段用 () 捕获，字段数量取你能稳定拆分出的最合理的一档。\n"
    "2. 正则以 ^ 开头、以 $ 结尾（$ 只锚定去掉扩展名后的主体）。\n"
    "3. 尽可能兼容下面所有样本；对明显不规范的样本可不强求匹配。\n"
    "文件名样本：\n"
)


# ------------------------------------------------------------------
# 采样：从目录读取若干真实文件名，供 AI 自行判断格式
# ------------------------------------------------------------------
# 无论用户选择几个样本，都至少带上这些“非本软件自身”的自我标记
# （复用 file_source.SELF_MARKERS，避免采样到本工具自己的 exe/py）
def _default_self_markers():
    try:
        from file_source import SELF_MARKERS
        return set(SELF_MARKERS)
    except Exception:
        return {"文件名统计.exe", "文件名统计_cli.exe"}


def sample_filenames(directory, count=8, recursive=False,
                     strip_ext=True, exclude=None, unique=True):
    """从目录里取若干真实文件名作为 AI 判断格式的样本。

    参数:
        directory  要采样的目录
        count      采样个数（用户自定义，0 或负数视为默认 8）
        recursive  是否递归子目录
        strip_ext  是否去掉扩展名（默认去，因为要判断的是“文件名主体”格式）
        exclude    额外排除的文件名（会与 file_source.SELF_MARKERS 合并）
        unique     去重（不同文件去掉扩展名后可能重复）

    返回 list[str]：按目录顺序取到的文件名样本。
    """
    try:
        n = int(count)
    except Exception:
        n = 8
    if n <= 0:
        n = 8

    names = []
    ex = _default_self_markers()
    if exclude:
        ex |= set(exclude)

    try:
        if recursive:
            for root, _dirs, files in os.walk(directory):
                for name in sorted(files):
                    names.append(name)
        else:
            for name in sorted(os.listdir(directory)):
                full = os.path.join(directory, name)
                if os.path.isfile(full):
                    names.append(name)
    except OSError as e:
        raise ValueError(f"无法读取目录: {e}")

    out = []
    seen = set()
    for name in names:
        if name in ex:          # 跳过本软件自身的 exe / 源码
            continue
        # 默认不把任何 .exe 当样本（通常是程序，不是统计对象）
        if os.path.splitext(name)[1].lower() in (".exe", ".dll", ".pyc"):
            continue
        body = name
        if strip_ext:
            body, _e = os.path.splitext(name)
        if unique:
            if body in seen:
                continue
            seen.add(body)
        out.append(body)
        if len(out) >= n:
            break
    return out


def build_sample_question(filenames, base_prompt=None):
    """把样本文件名拼进提问文本（带编号，方便 AI 阅读）。"""
    head = (base_prompt or DEFAULT_SAMPLE_USER_PROMPT)
    if not head.endswith("\n"):
        head += "\n"
    lines = [f"  {i}. {nm}" for i, nm in enumerate(filenames, 1)]
    return head + "\n".join(lines)


def default_config():
    """默认 AI 配置。base_url 留空示例，用户自己填。"""
    return {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "user_prompt": DEFAULT_USER_PROMPT,
        "sample_user_prompt": DEFAULT_SAMPLE_USER_PROMPT,
        "sample_count": 8,
        "sample_recursive": False,
        "sample_strip_ext": True,
        "timeout": 60,
    }


def _config_path(dir_hint=None):
    """统一配置文件 config.json 的路径（AI 设置存在其中的 ai 段）。"""
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


def load_config(dir_hint=None):
    """读取 AI 配置；不存在/损坏时返回默认配置（缺的键用默认补齐）。"""
    cfg = default_config()
    data = None
    if app_config is not None:
        data = app_config.load_section("ai", dir_hint, default={})
    else:
        path = _config_path(dir_hint)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "ai" in data:
                    data = data.get("ai", {})
            except Exception:
                data = None
    if isinstance(data, dict):
        for k in cfg:
            if k in data and data[k] is not None:
                cfg[k] = data[k]
    return cfg


def save_config(cfg, dir_hint=None):
    """保存 AI 配置到 config.json 的 ai 段（明文，仅存本机）。

    只更新 ai 段，不会动 presets 段（自定义预设）。
    """
    data = default_config()
    data.update({k: cfg.get(k, data[k]) for k in data})
    if app_config is not None:
        return app_config.save_section("ai", data, dir_hint)
    path = _config_path(dir_hint)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ai": data}, f, ensure_ascii=False, indent=2)
    return path


# ------------------------------------------------------------------
# 调用 OpenAI 兼容接口（/chat/completions）
# ------------------------------------------------------------------
def _endpoint(base_url):
    """把 base_url 规范成 chat/completions 完整地址。"""
    b = (base_url or "").strip().rstrip("/")
    if not b:
        raise ValueError("base_url 为空，请先填写接口地址。")
    if b.endswith("/chat/completions"):
        return b
    return b + "/chat/completions"


def chat(user_content, cfg, system_prompt=None):
    """调用 AI。返回助手回复文本（已 strip）。

    参数:
        user_content  本次提问（用户描述的文件格式）
        cfg           dict，含 base_url / api_key / model / system_prompt
        system_prompt 可选覆盖（默认用 cfg 里的）

    异常:
        ValueError     配置问题（缺 base_url / api_key）
        RuntimeError   网络或接口错误（带可读信息）
    """
    base_url = (cfg.get("base_url") or "").strip()
    api_key = (cfg.get("api_key") or "").strip()
    model = (cfg.get("model") or "").strip() or "gpt-4o-mini"
    if not base_url:
        raise ValueError("base_url 为空，请先在“AI 设置”里填写。")
    if not api_key:
        raise ValueError("api_key 为空，请先在“AI 设置”里填写。")
    sysp = system_prompt if system_prompt is not None else cfg.get("system_prompt", "")
    sysp = sysp or DEFAULT_SYSTEM_PROMPT

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sysp},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _endpoint(base_url), data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        })
    timeout = cfg.get("timeout", 60) or 60
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"接口返回 HTTP {e.code}：{detail or e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络连接失败：{e.reason}")
    except Exception as e:
        raise RuntimeError(f"请求异常：{e}")

    try:
        data = json.loads(raw)
    except Exception:
        raise RuntimeError(f"接口返回不是合法 JSON：{raw[:300]}")

    # 兼容 OpenAI 格式
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        # 有些兼容接口放在 choices[0].text
        try:
            content = data["choices"][0]["text"]
        except Exception:
            err = data.get("error", data)
            raise RuntimeError(f"无法解析响应：{str(err)[:300]}")
    return (content or "").strip()


# ------------------------------------------------------------------
# 从回复里抠出正则
# ------------------------------------------------------------------
def extract_pattern(text):
    """从 AI 回复里稳健地抠出正则主体。

    处理：```code``` 围栏、首尾引号、前缀 '正则：'、多余空行。
    返回 str（可能为空）。
    """
    if not text:
        return ""
    s = text.strip()

    # 1) 去 markdown 代码围栏 ```...```
    m = re.search(r"```(?:regex|re|python)?\s*\n?(.*?)```", s, re.S | re.I)
    if m:
        s = m.group(1).strip()

    # 2) 逐行取：优先含 ^ 或以 ( 开头的行
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    cand = ""
    for ln in lines:
        if ln.startswith("^") or (ln.startswith("(") and ")" in ln):
            cand = ln
            break
    if not cand:
        # 3) 去掉 '正则：' / 'regex:' 之类前缀
        cand = lines[0] if lines else s
        cand = re.sub(r"^\s*(正则(表达式)?|regex|pattern)\s*[:：]\s*", "",
                      cand, flags=re.I)

    # 4) 去首尾引号 / 反引号
    cand = cand.strip().strip("`").strip()
    cand = cand.strip("\"'").strip()
    # 5) 去掉可能的行尾分号
    cand = cand.rstrip(";").strip()

    # 6) 兜底：若上面结果里仍夹着废话（如“好的，正则：^(\d+)_(.+)$ 请查收”），
    #    从整段文字里找出最像“一条完整正则”的片段（以 ^ 开头、以 $ 结尾）。
    if not _looks_like_pattern(cand):
        m = re.search(r"(\^.*?\$)", s, re.S)
        if m:
            cand = m.group(1).strip().strip("`").strip("\"'").strip()
    # 7) 再兜底：整段里找以 ^ 开头的片段（末尾可能没写 $）
    if not _looks_like_pattern(cand):
        m = re.search(r"(\^[^\s\u4e00-\u9fa5]\S*)", s)
        if m:
            cand = m.group(1).strip().strip("`").strip("\"'").strip()
    return cand


def _looks_like_pattern(s):
    """粗略判断一段文本是否像正则：不含中文/中文标点、不含空格、不含英文单词。"""
    if not s or len(s) < 3:
        return False
    if re.search(r"[\u4e00-\u9fa5，。：：（）“”]", s):
        return False
    # 含空格或至少两个连续字母单词，基本就是“句子”而不是正则
    if " " in s:
        return False
    if re.search(r"[A-Za-z]{3,}", s):
        return False
    return "^" in s or "(" in s


def validate_pattern(pattern):
    """检测正则语法（委托 name_parser，避免重复实现）。"""
    from name_parser import validate_pattern as _v
    return _v(pattern)
