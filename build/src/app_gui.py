# -*- coding: utf-8 -*-
"""
app_gui.py - 图形界面版主程序

打包为单个 exe 后，放到任意文件夹双击运行，即统计该文件夹下的文件。
"""

import os
import sys
import csv
import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import core


# ------------------------------------------------------------------
# 定位“程序所在目录”：打包后是 exe 所在目录，开发时是源码所在目录
# ------------------------------------------------------------------
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


class App:
    def __init__(self, root):
        self.root = root
        self.base_dir = app_dir()
        self.result = {"rows": [], "fields": list(core.DEFAULT_FIELDS),
                       "unmatched": 0, "total": 0}

        root.title("文件名统计工具")
        root.geometry("880x620")
        root.minsize(680, 460)

        self.pattern_var = tk.StringVar(value=core.DEFAULT_PATTERN)
        self.fields_var = tk.StringVar(value=",".join(core.DEFAULT_FIELDS))
        self.recursive_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="就绪")

        # 预设：显示名列表 -> 预设 dict
        self._presets = core.all_presets()
        self.preset_var = tk.StringVar(value="常用格式")
        self.load_presets()

        # 插入片段
        self._snippets = core.all_snippets()
        self.snippet_hint_var = tk.StringVar(value="")

        self._build_ui()
        self.scan()

    # ---------------- 预设 ----------------
    def load_presets(self):
        """重新载入预设（内置 + 自定义）。"""
        self._presets = core.all_presets()
        self._preset_names = [p["name"] for p in self._presets]

    def on_preset_selected(self, _evt=None):
        """选下拉框 -> 直接替换正则与字段。"""
        name = self.preset_var.get()
        preset = core.find_preset(name)
        if not preset:
            return
        # “自定义正则”项不清空输入框，仅提示
        if preset["pattern"] == "" and not preset["fields"]:
            self._update_preset_hint(preset)
            self.pattern_entry.focus_set()
            return
        self.pattern_var.set(preset["pattern"])
        self.fields_var.set(",".join(preset["fields"]))
        self._update_preset_hint(preset)
        self.scan()

    def _update_preset_hint(self, preset):
        ex = preset.get("example", "")
        self.preset_hint_var.set(f"示例: {ex}" if ex else "")

    def manage_presets(self):
        """打开“管理预设”对话框：查看/新增/删除自定义预设。"""
        PresetManager(self.root, self)

    def on_snippet_selected(self, _evt=None):
        """兼容旧接口：打开片段子窗口。"""
        self.open_snippet_picker()

    def open_snippet_picker(self):
        """打开“插入片段”子窗口：列表内每条带白话说明，点一下插入一下。"""
        SnippetPicker(self.root, self)

    def open_ai_assistant(self):
        """打开“AI 辅助”子窗口：用自然语言描述 → AI 生成正则 → 检测/插入。"""
        AIAssistant(self.root, self)

    def insert_snippet(self, snip):
        """在正则框光标处插入指定片段（供子窗口调用）。"""
        if not snip:
            return
        kind = snip.get("kind", "text")
        if kind == "custom":
            self._insert_custom_chars()
        else:
            self._insert_pattern_text(snip.get("text", ""))
        self.snippet_hint_var.set("已插入：" + snip.get("desc", snip.get("name", "")))

    def _insert_pattern_text(self, text):
        """把 text 插入正则框当前光标处。"""
        entry = self.pattern_entry
        try:
            first = entry.index("sel.first")
            last = entry.index("sel.last")
            entry.delete(first, last)
            pos = first
        except tk.TclError:
            pos = entry.index("insert")
        entry.insert(pos, text)
        entry.icursor(pos + len(text))
        entry.focus_set()

    def _insert_custom_chars(self):
        """弹小输入框，把用户输入的字面字符插入。"""
        dlg = tk.Toplevel(self.root)
        dlg.title("插入指定字符")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.grab_set()
        ttk.Label(dlg, text="要插入的字符：").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        var = tk.StringVar()
        e = ttk.Entry(dlg, textvariable=var, width=24)
        e.grid(row=0, column=1, padx=8, pady=8)
        e.focus_set()

        def ok(_e=None):
            txt = var.get()
            if txt:
                self._insert_pattern_text(txt)
            dlg.destroy()

        e.bind("<Return>", ok)
        ttk.Button(dlg, text="插入", command=ok).grid(row=1, column=1, sticky="e", padx=8, pady=(0, 8))

    # ---------------- 界面 ----------------
    def _build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        # 第 0 行：常用格式下拉框（选一个 = 直接替换下面的正则与字段）
        ttk.Label(top, text="常用格式:").grid(row=0, column=0, sticky="w")
        self.preset_box = ttk.Combobox(top, textvariable=self.preset_var,
                                       values=self._preset_names, state="readonly")
        self.preset_box.grid(row=0, column=1, sticky="ew", padx=4)
        self.preset_box.bind("<<ComboboxSelected>>", self.on_preset_selected)
        preset_btns = ttk.Frame(top)
        preset_btns.grid(row=0, column=2, sticky="e")
        ttk.Button(preset_btns, text="AI 辅助…", command=self.open_ai_assistant).pack(side="left")
        ttk.Button(preset_btns, text="管理预设…", command=self.manage_presets).pack(side="left", padx=(4, 0))

        self.preset_hint_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.preset_hint_var, foreground="#666")\
            .grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(top, text="格式正则:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.pattern_entry = ttk.Entry(top, textvariable=self.pattern_var)
        self.pattern_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=(6, 0))
        # 插入片段：点按钮弹子窗口（列表 + 白话说明，点一下插一下）
        ttk.Button(top, text="插入片段…", command=self.open_snippet_picker)\
            .grid(row=2, column=2, sticky="e", padx=(0, 4), pady=(6, 0))

        # 提示条（上次插入了什么 / 怎么用）
        ttk.Label(top, textvariable=self.snippet_hint_var, foreground="#0a6", wraplength=520)\
            .grid(row=3, column=1, columnspan=2, sticky="w", padx=4)

        ttk.Label(top, text="字段名:").grid(row=4, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(top, textvariable=self.fields_var).grid(row=4, column=1, columnspan=2, sticky="ew", padx=4, pady=(4, 0))

        ttk.Checkbutton(top, text="包含子文件夹", variable=self.recursive_var)\
            .grid(row=5, column=1, sticky="w", pady=(4, 0))
        # 当前目录（让“选择文件夹”有可见反馈）
        self.dir_var = tk.StringVar(value="当前目录: " + self.base_dir)
        ttk.Label(top, textvariable=self.dir_var, foreground="#06c", wraplength=560)\
            .grid(row=6, column=0, columnspan=3, sticky="w", padx=4, pady=(4, 0))
        top.columnconfigure(1, weight=1)

        btn = ttk.Frame(self.root, padding=(8, 0))
        btn.pack(fill="x")
        ttk.Button(btn, text="扫描 / 应用", command=self.scan).pack(side="left")
        ttk.Button(btn, text="复制到剪贴板", command=self.copy).pack(side="left", padx=6)
        ttk.Button(btn, text="导出 CSV", command=self.export_csv).pack(side="left")
        ttk.Button(btn, text="导出 Excel", command=self.export_xlsx).pack(side="left", padx=6)
        ttk.Button(btn, text="选择文件夹", command=self.choose_dir).pack(side="left")
        ttk.Button(btn, text="帮助", command=self.help).pack(side="right")

        ttk.Label(self.root,
                  text=r"正则用括号()捕获字段。右侧“插入片段…”每条带白话说明；“AI 辅助…”可用大白话描述格式让 AI 生成正则。",
                  foreground="#666", padding=(8, 4)).pack(fill="x")

        mid = ttk.Frame(self.root, padding=8)
        mid.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(mid, show="headings", selectmode="extended")
        vs = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        ttk.Label(self.root, textvariable=self.status_var,
                  relief="sunken", anchor="w").pack(fill="x", side="bottom")

    # ---------------- 扫描 ----------------
    def _update_dir_label(self):
        """刷新“当前目录”显示。"""
        try:
            self.dir_var.set("当前目录: " + self.base_dir)
        except Exception:
            pass

    def scan(self):
        pattern = self.pattern_var.get().strip()
        fields = core.parse_fields(self.fields_var.get())
        try:
            self.result = core.scan_directory(
                self.base_dir, pattern, fields,
                recursive=self.recursive_var.get())
        except ValueError as e:
            messagebox.showerror("格式错误", str(e))
            return

        self._fill_tree()
        self._update_dir_label()
        r = self.result
        self.status_var.set(
            f"共 {r['total']} 个文件，匹配 {len(r['rows'])} 个，未匹配 {r['unmatched']} 个  | 目录: {self.base_dir}")

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        r = self.result
        cols = ["序号"] + r["fields"] + ["扩展名"]
        self.tree["columns"] = cols
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=150 if c not in ("序号", "扩展名") else 60,
                             anchor="w" if c not in ("序号", "扩展名") else "center")
        for i, row in enumerate(r["rows"], 1):
            self.tree.insert("", "end", values=[i] + row["values"] + [row["ext"]])

    def choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.base_dir, title="选择要统计的文件夹")
        if not d:
            # 用户取消：明确提示，避免误以为按钮无效
            self.status_var.set("已取消选择，当前目录: " + self.base_dir)
            return
        d = os.path.normpath(d)
        self.base_dir = d
        self._update_dir_label()
        self.status_var.set("已切换目录，正在扫描: " + d)
        self.root.update_idletasks()
        self.scan()

    # ---------------- 复制 ----------------
    def copy(self):
        r = self.result
        if not r["rows"]:
            messagebox.showinfo("提示", "没有可复制的内容。")
            return
        text = core.to_tsv(r["rows"], r["fields"], include_header=True)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            self.status_var.set(f"已复制 {len(r['rows'])} 行，打开 Excel 选中 A1 直接 Ctrl+V。")
        except Exception:
            messagebox.showwarning("提示", "剪贴板写入失败，请用导出功能。")

    # ---------------- 导出 ----------------
    def _default_name(self, ext):
        return "文件名统计_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ext

    def export_csv(self):
        r = self.result
        if not r["rows"]:
            return
        p = filedialog.asksaveasfilename(initialdir=self.base_dir,
                                         initialfile=self._default_name(".csv"),
                                         defaultextension=".csv",
                                         filetypes=[("CSV", "*.csv"), ("所有文件", "*.*")])
        if not p:
            return
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(r["fields"])
            for row in r["rows"]:
                w.writerow(row["values"])
        self.status_var.set(f"已导出: {p}")
        messagebox.showinfo("完成", f"已导出:\n{p}")

    def export_xlsx(self):
        r = self.result
        if not r["rows"]:
            return
        p = filedialog.asksaveasfilename(initialdir=self.base_dir,
                                         initialfile=self._default_name(".xlsx"),
                                         defaultextension=".xlsx",
                                         filetypes=[("Excel", "*.xlsx"), ("所有文件", "*.*")])
        if not p:
            return
        try:
            from openpyxl import Workbook
        except ImportError:
            messagebox.showwarning("缺少库", "未安装 openpyxl，请改用“导出 CSV”。")
            return
        wb = Workbook()
        ws = wb.active
        ws.title = "统计"
        ws.append(r["fields"])
        for row in r["rows"]:
            ws.append(list(row["values"]))
        wb.save(p)
        self.status_var.set(f"已导出: {p}")
        messagebox.showinfo("完成", f"已导出:\n{p}")

    def help(self):
        messagebox.showinfo(
            "使用说明",
            "1. 把本程序(单个exe)放进要统计的文件夹，双击运行。\n"
            "   也可用“选择文件夹”按钮切换统计目标；选完后上方“当前目录”会立刻显示新路径，\n"
            "   并自动重新扫描。（若上一步点“取消”则保持不变。）\n\n"
            "2. 顶部“常用格式”下拉框选一个模板，会自动填好正则与字段，\n"
            "   不需要手写正则。例: 选“数字_名称”就能匹配 123_会议记录。\n\n"
            "3. “格式正则”用括号()捕获要提取的字段，逐列输出。\n"
            "   例: ^(\\d+)[\\s_\\-\\.]+(.+)$  匹配 123_文件名\n"
            "   例: ^\\d+_(.+)_v(\\d+)$        匹配 12_文档_v3\n\n"
            "4. 点“扫描/应用”出结果，点“复制到剪贴板”后到 Excel 的 A1 直接 Ctrl+V。\n\n"
            "5. 点“管理预设…”可新增/删除自定义常用格式（存为 presets.json）。\n\n"
            "6. 点“插入片段…”会弹出子窗口，列表里每条片段后面都直接写着白话说明，\n"
            "   选中后点“插入”（或双击）就插到正则框光标处；先在正则框点好位置再插，可连续插多个。\n\n"
            "7. 点“AI 辅助…”可填 base_url / api_key / 模型，两种玩法：\n"
            "   ① 描述模式：用大白话描述你的文件名格式，AI 只回一条正则；\n"
            "   ② 样本模式：不用你描述——设“样本个数”（默认 8），点“用样本自动生成”，\n"
            "      程序会读当前目录里这几个真实文件名（自动跳过本软件自身的 exe）发给 AI，\n"
            "      让 AI 自己判断该用什么正则。可先点“刷新样本预览”看取到了哪些。\n"
            "   生成后可“检测语法”→“插入到正则框”；也可“存为预设…”存进下框下次直接用。\n\n"
            "8. 也可导出 CSV / Excel。")


class SnippetPicker:
    """“插入片段”子窗口。

    特点：
    - 列表里每一行都直接带着白话说明（片段 | 说明），不用选出来才知道什么意思；
    - 点一下“插入”或双击，就往正则框光标处插一下；
    - 子窗口是非模态的：定位前你可以先切回主窗口点好光标位置，
      再回来点片段，插到你想插的地方；
    - 插完不关闭窗口，可以连续插多个片段（用按钮或双击）。
    """

    def __init__(self, master, app):
        self.app = app
        self.top = tk.Toplevel(master)
        self.top.title("插入片段（选中一行 → 点“插入”或双击）")
        self.top.geometry("620x480")
        self.top.transient(master)
        # 非模态：方便在插入间隙点回主窗口改光标位置
        # （不 grab_set，也不设 grab）
        self.top.minsize(480, 320)

        # 顶部操作提示
        ttk.Label(
            self.top,
            text="提示：先在主窗口“格式正则”框里点好要插入的位置（光标），再到这里点片段插入。"
                 "每次插入只加一下，可连续插多个。",
            foreground="#666", wraplength=580, padding=(8, 6)
        ).pack(fill="x")

        # 中部：片段列表（两列：片段 / 说明，说明永远可见）
        mid = ttk.Frame(self.top, padding=(8, 0, 8, 0))
        mid.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(mid, columns=("snip", "desc"),
                                 show="headings", selectmode="browse")
        self.tree.heading("snip", text="片段")
        self.tree.heading("desc", text="说明（白话）")
        self.tree.column("snip", width=170, anchor="w", stretch=False)
        self.tree.column("desc", width=420, anchor="w", stretch=True)
        vs = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        # 隔行底色 + 双击插入
        self.tree.tag_configure("odd", background="#f4f7fb")
        self.tree.bind("<Double-1>", lambda e: self._insert_selected())
        self.tree.bind("<Return>", lambda e: self._insert_selected())

        # 底部：预览 + 按钮
        bottom = ttk.Frame(self.top, padding=8)
        bottom.pack(fill="x")
        self.preview_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.preview_var, foreground="#0a6",
                  wraplength=580).pack(fill="x", anchor="w")
        btns = ttk.Frame(bottom)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="插入", command=self._insert_selected).pack(side="left")
        ttk.Button(btns, text="关闭", command=self.top.destroy).pack(side="right")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._load()
        # 默认选中第一项，方便直接回车/双击插
        kids = self.tree.get_children()
        if kids:
            self.tree.selection_set(kids[0])
            self.tree.focus(kids[0])
            self.tree.see(kids[0])

    def _load(self):
        """载入全部片段到列表。"""
        self._rows = list(self.app._snippets)
        for i, s in enumerate(self._rows):
            tag = "odd" if i % 2 else ""
            self.tree.insert("", "end", iid=str(i),
                             values=(s["name"], s.get("desc", "")),
                             tags=(tag,) if tag else ())

    def _current(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return self._rows[int(sel[0])]
        except (IndexError, ValueError):
            return None

    def _on_select(self, _evt=None):
        s = self._current()
        if not s:
            return
        kind = s.get("kind", "text")
        if kind == "custom":
            text = "（弹输入框，由你现场输入字符）"
        else:
            text = s.get("text", "")
        self.preview_var.set("将插入：" + repr(text) + "   — " + s.get("desc", ""))

    def _insert_selected(self):
        s = self._current()
        if not s:
            messagebox.showinfo("提示", "请先在列表里选一个片段。", parent=self.top)
            return
        self.app.insert_snippet(s)


class AIAssistant:
    """“AI 辅助”子窗口：把自然语言描述变成正则表达式。

    功能：
    - 可设置 base_url / api_key / model / 系统提示词 / 提问模板
    - 默认系统提示词已写好：让 AI 只回一条正则，别的什么都不回
    - 点“生成正则”→ 调 AI → 抠出正则
    - “检测语法”：本地编译校验（不联网），报错/告警
    - “插入到正则框”：填入主窗口
    - “重新提问”：保留描述、重新生成
    配置保存在 ai_config.json（与程序同级，明文）。
    """

    def __init__(self, master, app):
        self.app = app
        self.top = tk.Toplevel(master)
        self.top.title("AI 辅助 · 用一句话生成正则")
        self.top.geometry("720x600")
        self.top.transient(master)
        self.top.minsize(620, 480)
        self.cfg = core.load_ai_config(app.base_dir)
        self._conn_open = tk.BooleanVar(value=False)
        self._build()

    # ---------------- 布局 ----------------
    def _build(self):
        root = self.top
        # 说明
        ttk.Label(root,
                  text="用法：在“提问”里用大白话描述你的文件名格式，点“生成正则”，"
                       "AI 会只回一条正则；再点“插入到正则框”即可。",
                  foreground="#666", wraplength=690, padding=(8, 6)).pack(fill="x")

        # ---- AI 设置（默认收起为一行，点击展开；含系统提示词） ----
        conn = ttk.LabelFrame(root, text="AI 设置", padding=8)
        conn.pack(fill="x", padx=8)
        self.url_var = tk.StringVar(value=self.cfg.get("base_url", ""))
        self.key_var = tk.StringVar(value=self.cfg.get("api_key", ""))
        self.model_var = tk.StringVar(value=self.cfg.get("model", ""))
        self.show_key = tk.BooleanVar(value=False)

        # 收起时显示的摘要行 + 展开/收起按钮
        self._conn_header = ttk.Frame(conn)
        self._conn_header.pack(fill="x")
        self._conn_toggle = ttk.Button(
            self._conn_header, width=3,
            text="▶", command=self._toggle_conn)
        self._conn_toggle.pack(side="left")
        self.conn_summary_var = tk.StringVar(value="")
        ttk.Label(self._conn_header, textvariable=self.conn_summary_var,
                  foreground="#666").pack(side="left", padx=(6, 0))

        # 收起的“详情”主体（默认不 pack）
        self._conn_body = ttk.Frame(conn)
        ttk.Label(self._conn_body, text="Base URL:").grid(row=0, column=0, sticky="w")
        ttk.Entry(self._conn_body, textvariable=self.url_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=4)
        ttk.Label(self._conn_body, text="API Key:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.key_entry = ttk.Entry(self._conn_body, textvariable=self.key_var, show="*")
        self.key_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=(4, 0))
        ttk.Checkbutton(self._conn_body, text="显示", variable=self.show_key,
                        command=self._toggle_key).grid(row=1, column=2, sticky="w", pady=(4, 0))
        ttk.Label(self._conn_body, text="模型:").grid(row=1, column=3, sticky="e", padx=(8, 0), pady=(4, 0))
        ttk.Entry(self._conn_body, textvariable=self.model_var, width=18).grid(
            row=1, column=4, sticky="w", padx=4, pady=(4, 0))
        self._conn_body.columnconfigure(1, weight=1)

        # 系统提示词（放进设置里，随设置一起展开/收起）
        ttk.Label(self._conn_body, text="系统提示词（要求 AI 只回正则；一般不用改）:").grid(
            row=2, column=0, columnspan=5, sticky="w", pady=(6, 0))
        self.sys_text = tk.Text(self._conn_body, height=6, wrap="word")
        self.sys_text.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(2, 0))
        self.sys_text.insert("1.0", self.cfg.get("system_prompt", "") or core.DEFAULT_SYSTEM_PROMPT)
        self._update_conn_summary()

        # ---- 提示词 ----
        pr = ttk.LabelFrame(root, text="提示词", padding=8)
        pr.pack(fill="both", expand=True, padx=8, pady=(6, 0))
        ttk.Label(pr, text="提问（用大白话描述你的文件名格式）:").pack(anchor="w")
        self.ask_text = tk.Text(pr, height=4, wrap="word")
        self.ask_text.pack(fill="both", expand=True, pady=(2, 0))
        self.ask_text.insert("1.0", self.cfg.get("user_prompt", "") or core.DEFAULT_USER_PROMPT)

        # ---- 样本模式：读若干真实文件名，让 AI 自己判断格式 ----
        smp = ttk.LabelFrame(
            root, text="样本模式（不用你描述：读当前目录里几个真实文件名，让 AI 自己判断该用什么正则）",
            padding=8)
        smp.pack(fill="x", padx=8, pady=(6, 0))
        row = ttk.Frame(smp)
        row.pack(fill="x")
        ttk.Label(row, text="样本个数:").pack(side="left")
        self.count_var = tk.StringVar(value=str(self.cfg.get("sample_count", 8) or 8))
        ttk.Spinbox(row, from_=1, to=50, width=5, textvariable=self.count_var).pack(side="left", padx=(2, 12))
        self.sample_recursive_var = tk.BooleanVar(value=bool(self.cfg.get("sample_recursive", False)))
        ttk.Checkbutton(row, text="含子文件夹", variable=self.sample_recursive_var).pack(side="left", padx=(0, 12))
        self.sample_strip_var = tk.BooleanVar(value=bool(self.cfg.get("sample_strip_ext", True)))
        ttk.Checkbutton(row, text="去掉扩展名", variable=self.sample_strip_var).pack(side="left")
        ttk.Button(row, text="刷新样本预览", command=self.refresh_samples).pack(side="right")
        ttk.Button(row, text="用样本自动生成", command=self.generate_from_samples).pack(side="right", padx=6)
        self.sample_hint_var = tk.StringVar(value="")
        ttk.Label(smp, textvariable=self.sample_hint_var, foreground="#0a6",
                  wraplength=690, justify="left").pack(fill="x", anchor="w", pady=(4, 0))
        # 采样提示词（可改；点“用样本自动生成”时把它 + 样本一起发给 AI）
        ttk.Label(smp, text="采样提问模板（可改；样本会附在后面）:" ).pack(anchor="w", pady=(4, 0))
        self.sample_prompt_text = tk.Text(smp, height=3, wrap="word")
        self.sample_prompt_text.pack(fill="x", pady=(2, 0))
        self.sample_prompt_text.insert(
            "1.0", self.cfg.get("sample_user_prompt", "") or core.DEFAULT_SAMPLE_USER_PROMPT)
        self.refresh_samples()

        # ---- 结果 ----
        res = ttk.LabelFrame(root, text="AI 回复 / 生成的正则", padding=8)
        res.pack(fill="both", expand=True, padx=8, pady=(6, 0))
        self.result_var = tk.StringVar(value="")
        ttk.Entry(res, textvariable=self.result_var, font=("Consolas", 11)).pack(fill="x")
        self.raw_var = tk.StringVar(value="")
        ttk.Label(res, textvariable=self.raw_var, foreground="#888",
                  wraplength=690).pack(fill="x", anchor="w", pady=(3, 0))
        self.valid_var = tk.StringVar(value="")
        ttk.Label(res, textvariable=self.valid_var, wraplength=690,
                  foreground="#0a6").pack(fill="x", anchor="w", pady=(3, 0))

        # ---- 按钮 ----
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        self.gen_btn = ttk.Button(bar, text="生成正则", command=self.generate)
        self.gen_btn.pack(side="left")
        ttk.Button(bar, text="重新提问", command=self.generate).pack(side="left", padx=6)
        ttk.Button(bar, text="检测语法", command=self.check_syntax).pack(side="left")
        ttk.Button(bar, text="插入到正则框", command=self.insert_result).pack(side="left", padx=6)
        ttk.Button(bar, text="存为预设…", command=self.save_as_preset).pack(side="left")
        ttk.Button(bar, text="保存配置", command=self.save_cfg).pack(side="right")
        ttk.Button(bar, text="关闭", command=self.top.destroy).pack(side="right", padx=6)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(root, textvariable=self.status_var, relief="sunken",
                  anchor="w").pack(fill="x", side="bottom")

    def _toggle_key(self):
        self.key_entry.configure(show="" if self.show_key.get() else "*")

    def _update_conn_summary(self):
        model = self.model_var.get().strip()
        url = self.url_var.get().strip()
        key = self.key_var.get().strip()
        key_state = "Key 已填" if key else "Key 未填"
        parts = []
        if model:
            parts.append("模型：" + model)
        if url:
            parts.append(url)
        parts.append(key_state)
        self.conn_summary_var.set("  ·  ".join(parts) or "未配置（点击▶展开填写）")

    def _toggle_conn(self):
        if self._conn_open.get():
            self._conn_body.pack_forget()
            self._conn_open.set(False)
            self._conn_toggle.configure(text="▶")
            self._update_conn_summary()
        else:
            self._conn_body.pack(fill="x", pady=(6, 0))
            self._conn_open.set(True)
            self._conn_toggle.configure(text="▼")

    # ---------------- 操作 ----------------
    def _collect_cfg(self):
        def _int(v, d):
            try:
                return int(str(v).strip())
            except Exception:
                return d
        return {
            "base_url": self.url_var.get().strip(),
            "api_key": self.key_var.get().strip(),
            "model": self.model_var.get().strip(),
            "system_prompt": self.sys_text.get("1.0", "end").strip(),
            "user_prompt": self.ask_text.get("1.0", "end").strip(),
            "sample_user_prompt": self.sample_prompt_text.get("1.0", "end").strip(),
            "sample_count": _int(self.count_var.get(), 8),
            "sample_recursive": bool(self.sample_recursive_var.get()),
            "sample_strip_ext": bool(self.sample_strip_var.get()),
            "timeout": self.cfg.get("timeout", 60),
        }

    # ---------------- 样本模式 ----------------
    def refresh_samples(self, show_dialog=False):
        """读取当前目录的若干真实文件名，更新预览（供用户确认后交给 AI）。"""
        count = self._collect_cfg().get("sample_count", 8)
        try:
            samples = core.ai_sample_filenames(
                self.app.base_dir, count=count,
                recursive=self.sample_recursive_var.get(),
                strip_ext=self.sample_strip_var.get())
        except Exception as e:
            self.sample_hint_var.set("读取样本失败：" + str(e))
            if show_dialog:
                messagebox.showerror("读取失败", str(e), parent=self.top)
            return []
        if samples:
            preview = "、".join(samples[:6]) + (" …" if len(samples) > 6 else "")
            self.sample_hint_var.set(f"已取到 {len(samples)} 个样本：{preview}")
        else:
            self.sample_hint_var.set("当前目录里没有可用的样本文件（已自动跳过本软件自身的 exe）。")
        if show_dialog:
            messagebox.showinfo("样本预览", "\n".join(samples) or "（无）", parent=self.top)
        return samples

    def generate_from_samples(self):
        """采样模式：读真实文件名 → 连同采样提示词一起发给 AI → 让 AI 自己判断格式。"""
        self.cfg = self._collect_cfg()
        samples = self.refresh_samples()
        if not samples:
            messagebox.showwarning(
                "没有样本",
                "当前目录里没读到可用的文件名样本。\n"
                "可先用主窗口“选择文件夹”切到有文件的目录，或勾选“含子文件夹”。",
                parent=self.top)
            return
        base_prompt = (self.sample_prompt_text.get("1.0", "end").strip()
                       or core.DEFAULT_SAMPLE_USER_PROMPT)
        question = core.ai_build_sample_question(samples, base_prompt)
        # 在“提问”框里显示本次实际发送的内容，透明可查
        self.ask_text.delete("1.0", "end")
        self.ask_text.insert("1.0", question)
        try:
            core.save_ai_config(self.cfg, self.app.base_dir)
        except Exception:
            pass

        self.gen_btn.configure(state="disabled")
        self.status_var.set(f"正在把 {len(samples)} 个样本发给 AI，让它自行判断格式…")
        self.top.update_idletasks()
        try:
            reply = core.ai_chat(question, self.cfg)
        except Exception as e:
            self.gen_btn.configure(state="normal")
            self.status_var.set("生成失败")
            messagebox.showerror("AI 请求失败", str(e), parent=self.top)
            return
        self.gen_btn.configure(state="normal")

        pat = core.ai_extract_pattern(reply)
        self.result_var.set(pat)
        self.raw_var.set("原始回复：" + (reply.replace("\n", " ")[:200] if reply else "（空）"))
        self.valid_var.set("")
        self.status_var.set("已根据样本生成，记得点“检测语法”确认。")
        self.check_syntax()

    def save_cfg(self, silent=False):
        self.cfg = self._collect_cfg()
        try:
            path = core.save_ai_config(self.cfg, self.app.base_dir)
            self._update_conn_summary()
            self.status_var.set("配置已保存：" + path)
            if not silent:
                messagebox.showinfo("已保存", "AI 配置已保存到\n" + path, parent=self.top)
        except Exception as e:
            messagebox.showerror("保存失败", str(e), parent=self.top)

    def generate(self):
        """调用 AI 生成正则（生成前自动保存配置）。"""
        self.cfg = self._collect_cfg()
        question = self.ask_text.get("1.0", "end").strip()
        if not question:
            messagebox.showwarning("提示", "请先在“提问”里描述你的文件名格式。", parent=self.top)
            return
        # 静默保存，方便复用
        try:
            core.save_ai_config(self.cfg, self.app.base_dir)
        except Exception:
            pass

        self.gen_btn.configure(state="disabled")
        self.status_var.set("正在请求 AI…（请稍候）")
        self.top.update_idletasks()
        try:
            reply = core.ai_chat(question, self.cfg)
        except Exception as e:
            self.gen_btn.configure(state="normal")
            self.status_var.set("生成失败")
            messagebox.showerror("AI 请求失败", str(e), parent=self.top)
            return
        self.gen_btn.configure(state="normal")

        pat = core.ai_extract_pattern(reply)
        self.result_var.set(pat)
        self.raw_var.set("原始回复：" + (reply.replace("\n", " ")[:200] if reply else "（空）"))
        self.valid_var.set("")
        self.status_var.set("已生成，记得点“检测语法”确认。")
        # 顺便自动检测一次
        self.check_syntax()

    def check_syntax(self):
        pat = self.result_var.get().strip()
        if not pat:
            messagebox.showinfo("提示", "还没有可检测的正则，请先“生成正则”。", parent=self.top)
            return
        v = core.ai_validate_pattern(pat)
        if v["ok"]:
            msg = "✓ " + v["message"]
            if v.get("warn"):
                msg += "（提醒：" + v["warn"] + "）"
                self.valid_var.set("⚠ " + msg)
            else:
                self.valid_var.set(msg)
        else:
            self.valid_var.set("✗ " + v["message"])
            messagebox.showwarning("语法错误", v["message"], parent=self.top)

    def insert_result(self):
        pat = self.result_var.get().strip()
        if not pat:
            messagebox.showinfo("提示", "还没有生成结果，请先“生成正则”。", parent=self.top)
            return
        v = core.ai_validate_pattern(pat)
        if not v["ok"]:
            if not messagebox.askyesno("语法有问题",
                                       v["message"] + "\n\n仍要插入吗？", parent=self.top):
                return
        self.app.pattern_var.set(pat)
        self.app.snippet_hint_var.set("已从 AI 插入正则（可再点“检测”或直接“扫描/应用”）")
        self.app.scan()
        self.status_var.set("已插入到主窗口正则框并重新扫描。")

    def save_as_preset(self):
        """把当前生成的正则 + 当前字段名存为一个自定义预设（presets.json）。"""
        pat = self.result_var.get().strip()
        if not pat:
            messagebox.showinfo("提示", "还没有生成结果，请先“生成正则”或用样本生成。", parent=self.top)
            return

        dlg = tk.Toplevel(self.top)
        dlg.title("存为常用格式预设")
        dlg.transient(self.top)
        dlg.grab_set()
        ttk.Label(dlg, text="预设名称:").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        name_var = tk.StringVar(value="AI 生成")
        ttk.Entry(dlg, textvariable=name_var, width=32).grid(row=0, column=1, padx=8, pady=(8, 2))
        ttk.Label(dlg, text="示例:").grid(row=1, column=0, sticky="w", padx=8, pady=2)
        ex_var = tk.StringVar(value="")
        ttk.Entry(dlg, textvariable=ex_var, width=32).grid(row=1, column=1, padx=8, pady=2)
        ttk.Label(dlg, text="字段名（逗号分隔）:").grid(row=2, column=0, sticky="w", padx=8, pady=2)
        fields_var = tk.StringVar(value=self.app.fields_var.get())
        ttk.Entry(dlg, textvariable=fields_var, width=32).grid(row=2, column=1, padx=8, pady=2)

        def _ok(_e=None):
            nm = name_var.get().strip()
            if not nm:
                messagebox.showwarning("提示", "请填写预设名称。", parent=dlg)
                return
            fields = core.parse_fields(fields_var.get()) or ["字段"]
            item = {"name": nm, "example": ex_var.get().strip(),
                    "pattern": pat, "fields": fields}
            try:
                current = core.load_custom_presets(self.app.base_dir)
                current = [p for p in current if p["name"] != nm]
                current.append(item)
                path = core.save_custom_presets(current, self.app.base_dir)
            except Exception as e:
                messagebox.showerror("保存失败", str(e), parent=dlg)
                return
            dlg.destroy()
            # 主窗口下拉框刷新
            try:
                self.app.load_presets()
                self.app.preset_box.configure(values=self.app._preset_names)
            except Exception:
                pass
            self.status_var.set("已存为预设：" + nm + "（" + path + "）")
            messagebox.showinfo("已保存",
                                "已存为常用格式预设：\n" + nm +
                                "\n\n下次在主窗口“常用格式”下拉框里直接选即可。\n" +
                                "（存在 " + os.path.basename(path) + "）", parent=self.top)

        btns = ttk.Frame(dlg)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", padx=8, pady=(4, 8))
        ttk.Button(btns, text="保存", command=_ok).pack(side="left")
        ttk.Button(btns, text="取消", command=dlg.destroy).pack(side="left", padx=6)
        dlg.bind("<Return>", _ok)


class PresetManager:
    """“管理预设”对话框：列出全部预设，支持新增/删除自定义预设。"""

    def __init__(self, master, app):
        self.app = app
        self.top = tk.Toplevel(master)
        self.top.title("管理常用格式预设")
        self.top.geometry("680x420")
        self.top.transient(master)
        self.top.grab_set()

        # 左：预设列表；右：编辑区
        left = ttk.Frame(self.top, padding=8)
        left.pack(side="left", fill="both", expand=True)
        self.lb = tk.Listbox(left, exportselection=False)
        self.lb.pack(fill="both", expand=True)
        self.lb.bind("<<ListboxSelect>>", self._on_select)
        ttk.Button(left, text="删除选中（仅自定义）", command=self._delete)\
            .pack(fill="x", pady=(6, 0))

        right = ttk.Frame(self.top, padding=8)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(right, text="名称:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Label(right, text="示例:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.ex_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.ex_var).grid(row=1, column=1, sticky="ew", padx=4, pady=(4, 0))

        ttk.Label(right, text="正则:").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.pt_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.pt_var).grid(row=2, column=1, sticky="ew", padx=4, pady=(4, 0))

        ttk.Label(right, text="字段:").grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.fd_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.fd_var).grid(row=3, column=1, sticky="ew", padx=4, pady=(4, 0))

        ttk.Button(right, text="保存为新自定义预设", command=self._add).grid(row=4, column=1, sticky="ew", padx=4, pady=(10, 0))
        ttk.Label(right, text="正则用括号()捕获字段，字段名逗号分隔。",
                  foreground="#666", wraplength=300).grid(row=5, column=1, sticky="w", padx=4, pady=(6, 0))
        right.columnconfigure(1, weight=1)

        self._reload()

    def _reload(self):
        self._custom = core.load_custom_presets()
        self._all = core.all_presets()
        self.lb.delete(0, tk.END)
        builtin_names = {p["name"] for p in core.PRESET_BUILTIN}
        for p in self._all:
            tag = "" if p["name"] in builtin_names else "  [自定义]"
            self.lb.insert(tk.END, p["name"] + tag)

    def _on_select(self, _evt=None):
        sel = self.lb.curselection()
        if not sel:
            return
        p = self._all[sel[0]]
        self.name_var.set(p["name"])
        self.ex_var.set(p.get("example", ""))
        self.pt_var.set(p.get("pattern", ""))
        self.fd_var.set(",".join(p.get("fields", [])))

    def _add(self):
        name = self.name_var.get().strip()
        pattern = self.pt_var.get().strip()
        fields = core.parse_fields(self.fd_var.get())
        if not name or not pattern:
            messagebox.showwarning("提示", "名称与正则不能为空。", parent=self.top)
            return
        try:
            core.compile_pattern(pattern)
        except ValueError as e:
            messagebox.showerror("正则错误", str(e), parent=self.top)
            return
        # 同名则更新，否则追加
        custom = [p for p in self._custom if p["name"] != name]
        custom.append({"name": name, "example": self.ex_var.get().strip(),
                       "pattern": pattern, "fields": fields})
        core.save_custom_presets(custom)
        self._reload()
        self.app.load_presets()
        self.app.preset_box["values"] = self.app._preset_names
        messagebox.showinfo("已保存", f"预设“{name}”已保存。", parent=self.top)

    def _delete(self):
        sel = self.lb.curselection()
        if not sel:
            return
        p = self._all[sel[0]]
        builtin_names = {x["name"] for x in core.PRESET_BUILTIN}
        if p["name"] in builtin_names:
            messagebox.showinfo("提示", "内置预设不可删除。", parent=self.top)
            return
        if not messagebox.askyesno("确认", f"删除自定义预设“{p['name']}”？", parent=self.top):
            return
        custom = [x for x in self._custom if x["name"] != p["name"]]
        core.save_custom_presets(custom)
        self._reload()
        self.app.load_presets()
        self.app.preset_box["values"] = self.app._preset_names


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
