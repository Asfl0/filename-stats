# -*- coding: utf-8 -*-
"""
main.py - 打包入口

- 无参数双击运行      → 图形界面版
- 带 --dump / --cli 等 → 命令行版
- 带 --cli             → 强制命令行菜单模式

开发运行：
    python main.py
"""

import sys


def main():
    argv = sys.argv[1:]
    # 命令行相关参数 → 走 CLI
    cli_flags = ("--dump", "--dir", "--pattern", "--fields", "--recursive",
                 "--no-header", "--cli", "--preset", "--list-presets", "--list-snippets")
    if any(a in cli_flags or any(a.startswith(f + "=") for f in cli_flags) for a in argv):
        import app_cli
        app_cli.main()
    else:
        import app_gui
        app_gui.main()


if __name__ == "__main__":
    main()
