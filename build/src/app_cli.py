# -*- coding: utf-8 -*-
"""
app_cli.py - 命令行/菜单交互版

用法：
    python app_cli.py                 # 菜单交互模式（扫描自身所在目录）
    python app_cli.py --dump          # 直接输出 TSV，便于管道/自动化
    python app_cli.py --dump --dir D --pattern "..." --fields "编号,名称"
"""

import os
import sys
import csv
import argparse
import datetime

import core


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def bootstrap_utf8():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for s in ("stdout", "stderr", "stdin"):
        st = getattr(sys, s, None)
        try:
            if st is not None and hasattr(st, "reconfigure"):
                st.reconfigure(encoding="utf-8")
        except Exception:
            pass


def disp_width(s):
    import unicodedata
    w = 0
    for ch in str(s):
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def show_table(rows, fields):
    if not rows:
        print("  没有匹配到记录。")
        return
    headers = ["序号"] + fields + ["扩展名"]
    table = [[str(i)] + [str(v) for v in r["values"]] + [r["ext"]]
             for i, r in enumerate(rows, 1)]
    widths = []
    for c in range(len(headers)):
        w = disp_width(headers[c])
        for row in table:
            w = max(w, disp_width(row[c]))
        widths.append(w)
    line = "+".join("-" * (w + 2) for w in widths)
    def fmt(cells):
        out = ""
        for c, cell in enumerate(cells):
            s = str(cell)
            out += " " + s + " " * (widths[c] - disp_width(s) + 1)
            out += "|" if c < len(cells) - 1 else ""
        return out
    print("  " + line)
    print("  " + fmt(headers))
    print("  " + line)
    for row in table:
        print("  " + fmt(row))
    print("  " + line)
    print(f"  共 {len(rows)} 条记录。")


def set_clipboard_simple(text):
    """纯命令行场景尽量用 Windows API 写剪贴板。"""
    if os.name == "nt":
        try:
            import ctypes
            CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
            u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
            data = text.encode("utf-16-le") + b"\x00\x00"
            h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            ptr = k32.GlobalLock(h)
            ctypes.memmove(ptr, data, len(data))
            k32.GlobalUnlock(h)
            if u32.OpenClipboard(0):
                u32.EmptyClipboard()
                u32.SetClipboardData(CF_UNICODETEXT, h)
                u32.CloseClipboard()
                return True
        except Exception:
            return False
    return False


def list_presets():
    """打印所有预设（编号 + 人话名 + 示例）。"""
    presets = core.all_presets()
    print("\n  常用格式预设：")
    for i, p in enumerate(presets, 1):
        ex = p.get("example", "")
        print(f"   {i:>2}) {p['name']:<16} {ex}")
    print("   0) 返回")
    return presets


def list_snippets():
    """打印所有插入片段（编号 + 名称 + 实际插入内容）。"""
    snippets = core.all_snippets()
    print("\n  可插入片段：")
    for i, s in enumerate(snippets, 1):
        tip = s["text"] if s["text"] else "（弹输入框输入）"
        print(f"   {i:>2}) {s['name']:<22} -> {tip}")
        print(f"       {s.get('desc','')}")
    print("   0) 返回")
    return snippets


def apply_preset(res, py_name):
    """应用一个预设，返回 (pattern, fields) 或 None。"""
    preset = core.find_preset(py_name)
    if not preset or (preset["pattern"] == "" and not preset["fields"]):
        return None
    return preset["pattern"], list(preset["fields"])


def run_dump(args):
    base = args.dir or app_dir()
    pattern = args.pattern
    fields = core.parse_fields(args.fields)
    # --preset 优先于 --pattern/--fields
    if getattr(args, "preset", None):
        preset = core.find_preset(args.preset)
        if not preset:
            print(f"找不到预设: {args.preset}", file=sys.stderr)
            sys.exit(2)
        pattern = preset["pattern"]
        fields = list(preset["fields"])
    res = core.scan_directory(base, pattern, fields, recursive=args.recursive)
    rows = core.sort_rows(res["rows"], "number")
    text = core.to_tsv(rows, res["fields"], include_header=not args.no_header)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(text)


def run_menu(args):
    base = args.dir or app_dir()
    pattern = args.pattern
    fields = core.parse_fields(args.fields)

    def do_scan():
        res = core.scan_directory(base, pattern, fields, recursive=args.recursive)
        print(f"\n  扫描完成: 共 {res['total']} 个文件，匹配 {len(res['rows'])} 个，"
              f"未匹配 {res['unmatched']} 个。")
        return res

    res = do_scan()

    while True:
        print("\n" + "=" * 52)
        print("            文件名统计工具")
        print("=" * 52)
        print(f"  当前目录: {base}")
        print(f"  当前格式: {pattern}")
        print(f"  字段    : {', '.join(fields)}")
        print("-" * 52)
        print("  1) 扫描当前文件夹")
        print("  2) 显示结果表")
        print("  3) 排序")
        print("  4) 复制到剪贴板")
        print("  5) 导出 CSV")
        print("  6) 设置/修改格式（手写正则）")
        print("  7) 常用格式预设")
        print("  8) 插入片段到当前正则")
        print("  0) 退出")
        print("-" * 52)
        try:
            c = input("  请选择操作: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  已退出。")
            break

        if c == "1":
            res = do_scan()
        elif c == "2":
            show_table(res["rows"], res["fields"])
        elif c == "3":
            print("\n  1) 按编号  2) 按文件名  3) 不变")
            m = {"1": "number", "2": "name", "3": "none"}.get(
                (input("  选择 [1-3] (默认1): ").strip() or "1"), "number")
            res["rows"] = core.sort_rows(res["rows"], m)
            print("  已排序。")
        elif c == "4":
            if not res["rows"]:
                print("  无内容。")
                continue
            print("\n  1) 带表头  2) 纯数据  3) 仅第一列  4) 仅第二列")
            k = input("  选择 [1-4] (默认1): ").strip() or "1"
            if k == "2":
                text = core.to_tsv(res["rows"], res["fields"], False)
            elif k == "3":
                text = "\r\n".join(str(r["values"][0]) for r in res["rows"] if r["values"])
            elif k == "4":
                text = "\r\n".join(str(r["values"][1]) for r in res["rows"] if len(r["values"]) > 1)
            else:
                text = core.to_tsv(res["rows"], res["fields"], True)
            if set_clipboard_simple(text):
                print(f"\n  已复制到剪贴板！共 {text.count(chr(13)+chr(10))+1} 行。")
                print("  打开 Excel，选中 A1，Ctrl+V 粘贴。")
            else:
                print("  剪贴板写入失败（无窗口环境），请用导出。")
        elif c == "5":
            if not res["rows"]:
                print("  无内容。")
                continue
            default = "文件名统计_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
            p = input(f"  导出文件名 (默认 {default}): ").strip() or default
            if not os.path.isabs(p):
                p = os.path.join(base, p)
            with open(p, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, delimiter="\t")
                w.writerow(res["fields"])
                for r in res["rows"]:
                    w.writerow(r["values"])
            print(f"  已导出: {p}")
        elif c == "6":
            p = input("  输入新的正则 (回车取消): ").strip()
            if p:
                try:
                    core.compile_pattern(p)
                except ValueError as e:
                    print(f"  {e}")
                    continue
                fn = input("  字段名,逗号分隔 (如 编号,名称): ").strip()
                pattern = p
                fields = core.parse_fields(fn)
                print("  已更新。")
                res = do_scan()
        elif c == "7":
            presets = list_presets()
            k = input("  选择预设编号 (回车取消): ").strip()
            if not k:
                continue
            preset = core.find_preset(k)
            if not preset:
                print("  无效编号。")
                continue
            if preset["pattern"] == "" and not preset["fields"]:
                print("  该项为“自定义正则”，请用菜单 6) 手写。")
                continue
            if preset.get("example"):
                print(f"  已选: {preset['name']}  （示例: {preset['example']}）")
            pattern = preset["pattern"]
            fields = list(preset["fields"])
            res = do_scan()
        elif c == "8":
            list_snippets()
            k = input("  选择片段编号 (回车取消): ").strip()
            if not k:
                continue
            snip = core.find_snippet(k)
            if not snip:
                print("  无效编号。")
                continue
            if snip["kind"] == "custom":
                txt = input("  要插入的字符: ")
            else:
                txt = snip["text"]
            if not txt:
                continue
            pos = input("  插入位置：1) 末尾  2) 开头 (默认1): ").strip() or "1"
            if pos == "2":
                pattern = txt + pattern
            else:
                pattern = pattern + txt
            print(f"  当前正则: {pattern}")
            fn = input("  字段名,逗号分隔（回车保持不变）: ").strip()
            if fn:
                fields = core.parse_fields(fn)
            res = do_scan()
        elif c == "0":
            print("\n  已退出。")
            break
        else:
            print("  无效选项。")


def run_ai_sample(args):
    """AI 样本模式：读目录里 N 个真实文件名，让 AI 自己判断该用什么正则。"""
    base = args.dir or app_dir()
    cfg = core.load_ai_config(base)
    if getattr(args, "base_url", None):
        cfg["base_url"] = args.base_url
    if getattr(args, "api_key", None):
        cfg["api_key"] = args.api_key
    if getattr(args, "model", None):
        cfg["model"] = args.model
    try:
        samples = core.ai_sample_filenames(
            base, count=args.sample_count, recursive=args.recursive,
            strip_ext=not args.keep_ext)
    except Exception as e:
        print("读取样本失败：" + str(e), file=sys.stderr)
        sys.exit(2)
    if not samples:
        print("目录里没有可用样本（已跳过本软件自身的 exe）。", file=sys.stderr)
        sys.exit(2)
    print("采样 %d 个文件名：" % len(samples))
    for i, s in enumerate(samples, 1):
        print(f"  {i}. {s}")
    question = core.ai_build_sample_question(samples)
    try:
        reply = core.ai_chat(question, cfg)
    except Exception as e:
        print("AI 请求失败：" + str(e), file=sys.stderr)
        sys.exit(3)
    pat = core.ai_extract_pattern(reply)
    print("\nAI 生成的正则：")
    print(pat)
    v = core.ai_validate_pattern(pat)
    print(("✓ " if v["ok"] else "✗ ") + v["message"])
    if v.get("warn"):
        print("⚠ " + v["warn"])
    print("\n套用命令：--pattern \"" + pat + "\" --fields " + ",".join(
        (v.get("group_names") or ["字段%d" % i for i in range(1, (v.get("groups") or 1) + 1)])))


def run_ai_desc(args):
    """AI 描述模式：用一句大白话让 AI 给正则。"""
    base = args.dir or app_dir()
    cfg = core.load_ai_config(base)
    if getattr(args, "base_url", None):
        cfg["base_url"] = args.base_url
    if getattr(args, "api_key", None):
        cfg["api_key"] = args.api_key
    if getattr(args, "model", None):
        cfg["model"] = args.model
    question = core.DEFAULT_USER_PROMPT + args.ai_desc
    try:
        reply = core.ai_chat(question, cfg)
    except Exception as e:
        print("AI 请求失败：" + str(e), file=sys.stderr)
        sys.exit(3)
    pat = core.ai_extract_pattern(reply)
    print("AI 生成的正则：")
    print(pat)
    v = core.ai_validate_pattern(pat)
    print(("✓ " if v["ok"] else "✗ ") + v["message"])


def main():
    bootstrap_utf8()
    ap = argparse.ArgumentParser(description="文件名统计工具")
    ap.add_argument("--dump", action="store_true", help="直接输出 TSV")
    ap.add_argument("--dir", default=None, help="要扫描的目录（默认程序所在目录）")
    ap.add_argument("--pattern", default=core.DEFAULT_PATTERN, help="格式正则")
    ap.add_argument("--fields", default=",".join(core.DEFAULT_FIELDS), help="字段名，逗号分隔")
    ap.add_argument("--preset", default=None,
                    help="常用格式预设名（如 数字_名称）或编号，优先于 --pattern/--fields；--list-presets 可查看")
    ap.add_argument("--list-presets", action="store_true", help="列出所有常用格式预预设后退出")
    ap.add_argument("--list-snippets", action="store_true", help="列出所有可插入片段后退出")
    ap.add_argument("--ai-sample", action="store_true",
                    help="AI 样本模式：读目录里 N 个真实文件名，让 AI 自己判断正则")
    ap.add_argument("--sample-count", type=int, default=8, help="样本模式读取的文件名个数（默认8）")
    ap.add_argument("--keep-ext", action="store_true", help="样本模式保留扩展名（默认去掉）")
    ap.add_argument("--ai-desc", default=None, help="AI 描述模式：直接传一句大白话格式描述")
    ap.add_argument("--base-url", default=None, help="临时覆盖 AI base_url")
    ap.add_argument("--api-key", default=None, help="临时覆盖 AI api_key")
    ap.add_argument("--model", default=None, help="临时覆盖 AI 模型名")
    ap.add_argument("--recursive", action="store_true", help="包含子文件夹")
    ap.add_argument("--no-header", action="store_true", help="TSV 不含表头")
    args = ap.parse_args()

    if getattr(args, "list_presets", False):
        list_presets()
        return

    if getattr(args, "list_snippets", False):
        list_snippets()
        return

    if getattr(args, "ai_sample", False):
        run_ai_sample(args)
        return

    if getattr(args, "ai_desc", None):
        run_ai_desc(args)
        return

    if args.dump:
        run_dump(args)
    else:
        run_menu(args)


if __name__ == "__main__":
    main()
