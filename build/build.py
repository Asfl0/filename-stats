# -*- coding: utf-8 -*-
"""
build.py —— 构建脚本（类似 Makefile）

    python build.py           构建，把 src/ 编译成 output/ 里的两个 exe
    python build.py clean     清理构建中间文件
    python build.py rebuild   先 clean 再 build

解释器策略（全部使用 portable Python）：
  1. 优先用工程内置的便携解释器  build/python/python.exe
     （python-build-standalone 官方 MSVC 构建，避 msys2/mingw ABI 坑）
  2. 若不存在，则自动联网下载官方 MSVC 构建的便携 CPython 并解压到 build/python/
  3. 若联网失败，可用环境变量 BUILD_PYTHON 指定一个解释器兜底

它会自动：
  - 确保便携解释器装有 pyinstaller（没有就自动 pip 安装到便携环境内）
  - 调用 PyInstaller 打包 src/ 到 output/

产物：
  output/文件名统计.exe       GUI 单文件版（双击即用）
  output/文件名统计_cli.exe   命令行版
"""

import os
import sys
import shutil
import tarfile
import subprocess
import urllib.request

# ---------------------------------------------------------------
# 路径
# ---------------------------------------------------------------
BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT      = os.path.dirname(BUILD_DIR)
SRC       = os.path.join(BUILD_DIR, "src")   # 源码：与构建脚本同级放在 build/ 下
OUTPUT    = os.path.join(ROOT, "output")
TMP       = os.path.join(BUILD_DIR, "_tmp")              # 构建中间文件
PYDIR     = os.path.join(BUILD_DIR, "python")            # 内置便携 Python
ENTRY     = os.path.join(SRC, "main.py")                 # GUI / 统一入口
ENTRY_CLI = os.path.join(SRC, "app_cli.py")              # CLI 入口
APP_NAME  = "文件名统计"

# 便携 Python 下载源：python-build-standalone（astral-sh 维护）
PBS_TAG   = "20261009"
PBS_VER   = "3.12.15"
PBS_URL   = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
    "%s/cpython-%s+%s-x86_64-pc-windows-msvc-install_only.tar.gz"
    % (PBS_TAG, PBS_VER, PBS_TAG)
)


# ---------------------------------------------------------------
# 便携解释器
# ---------------------------------------------------------------
def _portable_python():
    return os.path.join(PYDIR, "python.exe")


def _usable(path):
    if not path or not os.path.exists(path):
        return False
    try:
        subprocess.run([path, "-c", "import sys"],
                       check=True, capture_output=True, timeout=30)
        return True
    except Exception:
        return False


def _download_portable():
    """下载并解压官方 MSVC 构建的便携 CPython 到 build/python/。"""
    print("[build] 未发现内置便携 Python，正在下载 %s ..." % PBS_VER)
    print("        %s" % PBS_URL)
    os.makedirs(BUILD_DIR, exist_ok=True)
    tgz = os.path.join(BUILD_DIR, "_python_portable.tar.gz")
    try:
        urllib.request.urlretrieve(PBS_URL, tgz)
        print("[build] 下载完成，正在解压 ...")
        if os.path.exists(PYDIR):
            shutil.rmtree(PYDIR, ignore_errors=True)
        with tarfile.open(tgz, "r:gz") as tf:
            # 包内顶层目录名为 python/，直接解到 BUILD_DIR
            tf.extractall(BUILD_DIR)
    finally:
        if os.path.exists(tgz):
            try:
                os.remove(tgz)
            except OSError:
                pass
    # 兼容两种解压布局
    if not os.path.exists(_portable_python()):
        inner = os.path.join(PYDIR, "python.exe")
        if os.path.exists(inner):
            return
        raise SystemExit("[build] 便携 Python 解压后未找到 python.exe：%s" % PYDIR)


def find_python():
    """返回要用于打包的便携解释器路径。"""
    # 1) 环境变量强制指定
    env = os.environ.get("BUILD_PYTHON")
    if env and _usable(env):
        print("[build] 使用 BUILD_PYTHON 指定解释器：%s" % env)
        return env
    # 2) 内置便携解释器
    if not _usable(_portable_python()):
        _download_portable()
    if not _usable(_portable_python()):
        raise SystemExit("[build] 便携 Python 不可用：%s" % _portable_python())
    return _portable_python()


# ---------------------------------------------------------------
# 依赖
# ---------------------------------------------------------------
def ensure_pyinstaller(py):
    try:
        subprocess.run([py, "-c", "import PyInstaller"],
                       check=True, capture_output=True)
        return
    except Exception:
        print("[build] 便携环境未装 PyInstaller，正在安装 ...")
    r = subprocess.run([py, "-m", "pip", "install",
                        "--upgrade", "pyinstaller"])
    if r.returncode != 0:
        raise SystemExit(
            "[build] PyInstaller 安装失败。请手动执行：\n"
            "        %s -m pip install pyinstaller" % py)


def ensure_openpyxl(py):
    """确保便携环境装了 openpyxl（GUI “导出 Excel” 需要）。"""
    try:
        subprocess.run([py, "-c", "import openpyxl"],
                       check=True, capture_output=True)
        return
    except Exception:
        print("[build] 便携环境未装 openpyxl，正在安装 ...")
    r = subprocess.run([py, "-m", "pip", "install", "--upgrade", "openpyxl"])
    if r.returncode != 0:
        raise SystemExit(
            "[build] openpyxl 安装失败。请手动执行：\n"
            "        %s -m pip install openpyxl" % py)


# ---------------------------------------------------------------
# 构建
# ---------------------------------------------------------------
def inject_frozen_presets():
    """构建前把 presets.json 里的自定义预设合并进
    src/pattern_presets.py 的 FROZEN_CUSTOM，使其被打包进 exe。

    规则：
      - presets.json（工程根或 build/ 下）存在时，把其中每条
        合并/追加到 FROZEN_CUSTOM（同名覆盖）。
      - 已存在的 FROZEN_CUSTOM 条目保留。
      - 写回源码前先备份为 pattern_presets.py.bak（仅当发生改动）。
    可用环境变量 SKIP_FREEZE_PRESETS=1 跳过此步。
    """
    import json as _json
    if os.environ.get("SKIP_FREEZE_PRESETS") == "1":
        print("[build] 已跳过固化预设注入（SKIP_FREEZE_PRESETS=1）")
        return

    # 找预设来源：优先统一 config.json，兼容旧的 presets.json
    candidates = [
        os.path.join(ROOT, "config.json"),
        os.path.join(BUILD_DIR, "config.json"),
        os.path.join(ROOT, "output", "config.json"),
        os.path.join(ROOT, "presets.json"),
        os.path.join(BUILD_DIR, "presets.json"),
    ]
    src = os.path.join(SRC, "pattern_presets.py")
    if not os.path.isfile(src):
        return

    incoming = []
    for c in candidates:
        if os.path.isfile(c):
            try:
                with open(c, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                if isinstance(data, dict) and "presets" in data:
                    items = data.get("presets", [])
                elif isinstance(data, dict):
                    items = data  # 兼容旧格式/异常情况
                else:
                    items = data
                if isinstance(items, dict):
                    items = []
                for it in items:
                    if isinstance(it, dict) and it.get("name") and it.get("pattern"):
                        incoming.append(it)
                print("[build] 从 %s 读到 %d 条自定义预设" % (c, len(items)))
            except Exception as e:
                print("[build] 读取 %s 失败：%s" % (c, e))

    if not incoming:
        print("[build] 无 presets.json 或为空，固化预设保持不变")
        return

    # 生成新的 FROZEN_CUSTOM 源码块
    lines = ["FROZEN_CUSTOM = ["]
    for it in incoming:
        name = str(it["name"]).replace('"', '\\"')
        pattern = str(it["pattern"])
        example = str(it.get("example", "")).replace('"', '\\"')
        fields = [str(x) for x in it.get("fields", [])]
        fs = ", ".join('"' + x.replace('"', '\\"') + '"' for x in fields)
        lines.append(
            '    {"name": "%s", "example": "%s", "pattern": r"%s", "fields": [%s]},'
            % (name, example, pattern, fs))
    lines.append("]")
    block = "\n".join(lines)

    with open(src, "r", encoding="utf-8") as f:
        text = f.read()

    import re as _re
    # 用哨兵注释精确定位 FROZEN_CUSTOM 区块，避免误吞后面的 BUILTIN
    pat_re = _re.compile(
        r"# >>> FROZEN_CUSTOM_BEGIN.*?# <<< FROZEN_CUSTOM_END",
        _re.S)
    if not pat_re.search(text):
        print("[build] 未找到 FROZEN_CUSTOM 哨兵，跳过注入")
        return
    marked = ("# >>> FROZEN_CUSTOM_BEGIN\n%s\n# <<< FROZEN_CUSTOM_END"
              % block)
    new_text = pat_re.sub(lambda m: marked, text, count=1)
    if new_text == text:
        print("[build] 固化预设无变化")
        return

    bak = src + ".bak"
    if not os.path.exists(bak):
        shutil.copyfile(src, bak)
    with open(src, "w", encoding="utf-8") as f:
        f.write(new_text)
    print("[build] 已将 %d 条自定义预设写入 FROZEN_CUSTOM（备份 %s）"
          % (len(incoming), os.path.basename(bak)))

def _run_pyinstaller(py, entry, name, windowed):
    cmd = [
        py, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--windowed" if windowed else "--console",
        "--name", name,
        "--paths", SRC,
        # 显式收集工程内自建模块（相对导入，防止遗漏）
        "--hidden-import", "pattern_presets",
        "--hidden-import", "app_config",
        "--hidden-import", "ai_helper",
        "--hidden-import", "name_parser",
        "--hidden-import", "file_source",
        "--hidden-import", "core",
        # 显式收集 Excel 导出依赖（函数内 import，防止漏收）
        "--hidden-import", "openpyxl",
        "--collect-submodules", "openpyxl",
        "--distpath", OUTPUT,
        "--workpath", TMP,
        "--specpath", TMP,
        entry,
    ]
    print("[build] " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def build():
    py = find_python()
    print("[build] 使用便携解释器：%s" % py)
    # 把 presets.json 的自定义预设合并进源码（使其固化进 exe）
    inject_frozen_presets()
    ensure_pyinstaller(py)
    ensure_openpyxl(py)

    os.makedirs(OUTPUT, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)

    # 1) GUI 单文件版
    _run_pyinstaller(py, ENTRY, APP_NAME, windowed=True)
    # 2) CLI 版
    _run_pyinstaller(py, ENTRY_CLI, APP_NAME + "_cli", windowed=False)

    print("\n[build] 完成，产物：")
    for n in sorted(os.listdir(OUTPUT)):
        p = os.path.join(OUTPUT, n)
        if os.path.isfile(p):
            print("    %6.1f MB  output/%s" % (os.path.getsize(p) / 1048576, n))


def clean():
    if os.path.exists(TMP):
        shutil.rmtree(TMP, ignore_errors=True)
        print("[clean] 已删除 %s" % TMP)
    for a, d, f in os.walk(SRC):
        if os.path.basename(a) == "__pycache__":
            shutil.rmtree(a, ignore_errors=True)
    print("[clean] 完成")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "build"
    if arg == "clean":
        clean()
    elif arg == "rebuild":
        clean()
        build()
    else:
        build()
