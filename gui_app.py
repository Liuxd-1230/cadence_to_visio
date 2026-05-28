"""Cadence to Visio — GUI 启动器

暗色主题 tkinter 界面，一键选择文件并运行转换。
打包为 exe 后双击即可使用。
"""

from __future__ import annotations

import io
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
APP_TITLE = "Cadence → Visio"
APP_VERSION = "2.0.0"

# 暗色主题
BG_DARK = "#0d0d1a"
BG_CARD = "#1a1a2e"
BG_INPUT = "#252540"
FG_TEXT = "#e0e0e0"
FG_DIM = "#8888aa"
FG_ACCENT = "#6c63ff"
FG_GREEN = "#4ade80"
FG_RED = "#f87171"
FG_YELLOW = "#facc15"
BORDER = "#2a2a4a"
HOVER = "#2f2f55"

# 默认文件名
DEFAULT_FILES = {
    "inst_info": "inst_info.txt",
    "netlist": "netlist.txt",
    "wires": "wires.xlsx",
    "stencil": "circuit.vss",
}

# 帮助文本
HELP_TEXT = """Cadence to Visio V2.0 — 使用说明

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【功能】
将 Cadence/Virtuoso 原理图导出的器件、网表和走线坐标重建到 Microsoft Visio，生成可编辑的原理图。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【从 Virtuoso 导出数据】

1. 导出器件信息：
   在 Virtuoso CIW 中执行：
   load("/path/to/export_inst_xy_orient.il")
   c2vExportInstXYOrient("/path/to/inst_info.txt")

2. 导出走线坐标：
   load("/path/to/export_wire_lines_v4.il")
   c2vExportWireLinesV4("/path/to/wires.tsv")
   然后用 Excel 将 wires.tsv 另存为 wires.xlsx

3. CDL 网表保存为 netlist.txt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【输入文件说明】

  inst_info.txt  — 器件坐标、方向、BBox（Virtuoso SKILL 导出）
  netlist.txt    — CDL/SPICE 网表（器件→网络连接关系）
  wires.xlsx     — Virtuoso wire 坐标（group_id, seg_id, net, x1, y1, x2, y2）
  circuit.vss    — Visio stencil 模板（NMOS/PMOS/R/C 等符号）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【选项说明】

  基本选项：
  ✓ 启用附着    — 把线段端点附着到器件 pin 或共享连接点
  ✓ 绘制交汇点  — 绘制 T 形交汇处的 node 圆点
    Visio 内置连接线 — 使用 Visio Dynamic Connector（默认关闭，避免自动改线）
    绘制 MOS B 端分支线 — 是否画 MOS body 端的连线
    跳过 MOS B net   — 自动跳过所有 MOS body 连接的 net
    后台运行 Visio   — 不显示 Visio 窗口
    仅检查输入       — 只验证输入文件，不打开 Visio

  高级选项：
  跳过 net       — 逗号分隔的 net 名，如 vdd,vss
  排除 pin       — 不参与附着的 pin，如 B 或 MOS:B
  全局缩放       — 默认 1.0，放大/缩小整个图纸
  Symbol 缩放    — uniform（统一缩放）/ native（原始大小）/ stretch（拉伸）
  Wire 微调      — none（不微调）/ snap-endpoints（吸附悬空端点）
  Pin 吸附阈值   — endpoint 与 pin 匹配的最大距离，默认 0.8
  Placement 偏移 — 器件偏移规则文件（placement_offsets.tsv）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【支持器件】
  NMOS, PMOS, NPN, PNP, R（电阻）, C（电容）, PIN

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【系统要求】
  • Windows 10/11
  • Microsoft Visio 2016/2019/2021/2024（独立版或批量许可证）
  • 注意：Microsoft 365 网页版不支持 COM 自动化

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【常见问题】

Q: 报错 "无效的类字符串" / "类未注册"
A: Visio 未安装或位数不匹配。检查 Python 和 Visio 是否同为 64 位。

Q: 报错 "需要安装 pywin32"
A: 运行 pip install pywin32

Q: 器件位置偏移
A: 可通过 placement_offsets.tsv 手动校准，或调整 --scale 参数
"""


def get_base_dir() -> Path:
    """获取 exe 或脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


# ---------------------------------------------------------------------------
# 帮助窗口
# ---------------------------------------------------------------------------
class HelpWindow:
    def __init__(self, parent: tk.Tk):
        self.win = tk.Toplevel(parent)
        self.win.title("使用说明")
        self.win.geometry("600x650")
        self.win.configure(bg=BG_DARK)
        self.win.transient(parent)
        self.win.grab_set()

        # 标题
        tk.Label(
            self.win,
            text="📖 使用说明",
            font=("Segoe UI", 16, "bold"),
            fg=FG_ACCENT,
            bg=BG_DARK,
        ).pack(pady=(16, 8))

        # 内容
        text = scrolledtext.ScrolledText(
            self.win,
            font=("Consolas", 10),
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief=tk.FLAT,
            wrap=tk.WORD,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        text.insert(tk.END, HELP_TEXT)
        text.configure(state=tk.DISABLED)

        # 关闭按钮
        tk.Button(
            self.win,
            text="关闭",
            font=("Segoe UI", 10),
            fg=FG_TEXT,
            bg=BG_INPUT,
            activebackground=HOVER,
            relief=tk.FLAT,
            command=self.win.destroy,
        ).pack(pady=(0, 12), ipadx=20, ipady=4)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class CadenceToVisioGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("760x820")
        self.root.minsize(640, 650)
        self.root.configure(bg=BG_DARK)

        self.base_dir = get_base_dir()
        self._running = False

        self._build_ui()
        self._load_defaults()

    # ---- UI 构建 ----
    def _build_ui(self):
        # 标题栏
        header = tk.Frame(self.root, bg=BG_DARK)
        header.pack(fill=tk.X, padx=20, pady=(16, 8))

        tk.Label(
            header,
            text="⚡ Cadence → Visio",
            font=("Segoe UI", 18, "bold"),
            fg=FG_ACCENT,
            bg=BG_DARK,
        ).pack(side=tk.LEFT)

        tk.Label(
            header,
            text=f"v{APP_VERSION}",
            font=("Segoe UI", 10),
            fg=FG_DIM,
            bg=BG_DARK,
        ).pack(side=tk.LEFT, padx=(8, 0), pady=(6, 0))

        # 右上角帮助按钮
        help_btn = tk.Button(
            header,
            text="❓",
            font=("Segoe UI", 14),
            fg=FG_ACCENT,
            bg=BG_DARK,
            activebackground=BG_CARD,
            activeforeground=FG_ACCENT,
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: HelpWindow(self.root),
        )
        help_btn.pack(side=tk.RIGHT)

        tk.Label(
            header,
            text="帮助",
            font=("Segoe UI", 9),
            fg=FG_DIM,
            bg=BG_DARK,
        ).pack(side=tk.RIGHT, padx=(0, 4), pady=(6, 0))

        # ---- 文件选择区域 ----
        file_frame = self._card("输入文件")
        self.file_vars: dict[str, tk.StringVar] = {}
        file_labels = [
            ("inst_info", "器件坐标 (inst_info.txt)"),
            ("netlist", "CDL 网表 (netlist.txt)"),
            ("wires", "走线坐标 (wires.xlsx)"),
            ("stencil", "Visio 模板 (circuit.vss)"),
        ]
        for key, label in file_labels:
            self._file_row(file_frame, key, label)

        # ---- 基本选项区域 ----
        basic_frame = self._card("基本选项")
        self.option_vars: dict[str, tk.BooleanVar | tk.StringVar] = {}

        opts = [
            ("attach", "启用附着（线端→器件 pin）", True),
            ("draw_nodes", "绘制 T 形交汇点", True),
            ("visio_connectors", "Visio 内置连接线", False),
            ("draw_mos_b_wires", "绘制 MOS B 端分支线", False),
            ("skip_mos_body_nets", "跳过 MOS B net", False),
            ("hidden", "后台运行 Visio", False),
            ("dry_run", "仅检查输入（不打开 Visio）", False),
        ]
        for key, label, default in opts:
            var = tk.BooleanVar(value=default)
            self.option_vars[key] = var
            cb = tk.Checkbutton(
                basic_frame,
                text=label,
                variable=var,
                font=("Segoe UI", 10),
                fg=FG_TEXT,
                bg=BG_CARD,
                selectcolor=BG_INPUT,
                activebackground=BG_CARD,
                activeforeground=FG_TEXT,
            )
            cb.pack(anchor=tk.W, padx=16, pady=2)

        # skip-nets 输入
        skip_row = tk.Frame(basic_frame, bg=BG_CARD)
        skip_row.pack(fill=tk.X, padx=16, pady=(6, 4))
        tk.Label(
            skip_row, text="跳过 net：", font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD
        ).pack(side=tk.LEFT)
        self.skip_nets_var = tk.StringVar(value="")
        entry = tk.Entry(
            skip_row,
            textvariable=self.skip_nets_var,
            font=("Segoe UI", 10),
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief=tk.FLAT,
            width=30,
        )
        entry.pack(side=tk.LEFT, padx=(4, 0), ipady=3)
        tk.Label(
            skip_row,
            text="vdd,vss（逗号分隔）",
            font=("Segoe UI", 8),
            fg=FG_DIM,
            bg=BG_CARD,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # ---- 高级选项区域 ----
        adv_frame = self._card("高级选项")

        # 第一行：exclude-pins + symbol-fit
        row1 = tk.Frame(adv_frame, bg=BG_CARD)
        row1.pack(fill=tk.X, padx=16, pady=(8, 4))

        tk.Label(row1, text="排除 pin：", font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD).pack(side=tk.LEFT)
        self.exclude_pins_var = tk.StringVar(value="")
        tk.Entry(
            row1, textvariable=self.exclude_pins_var,
            font=("Segoe UI", 9), bg=BG_INPUT, fg=FG_TEXT,
            insertbackground=FG_TEXT, relief=tk.FLAT, width=12,
        ).pack(side=tk.LEFT, padx=(4, 16), ipady=3)

        tk.Label(row1, text="Symbol 缩放：", font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD).pack(side=tk.LEFT)
        self.symbol_fit_var = tk.StringVar(value="native")
        symbol_fit_menu = tk.OptionMenu(row1, self.symbol_fit_var, "native", "uniform", "stretch")
        symbol_fit_menu.configure(
            font=("Segoe UI", 9), bg=BG_INPUT, fg=FG_TEXT,
            activebackground=HOVER, activeforeground=FG_TEXT,
            highlightthickness=0, relief=tk.FLAT,
        )
        symbol_fit_menu["menu"].configure(bg=BG_INPUT, fg=FG_TEXT)
        symbol_fit_menu.pack(side=tk.LEFT, padx=(4, 0), ipady=3)

        # 第二行：scale + wire-adjust
        row2 = tk.Frame(adv_frame, bg=BG_CARD)
        row2.pack(fill=tk.X, padx=16, pady=4)

        tk.Label(row2, text="全局缩放：", font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD).pack(side=tk.LEFT)
        self.scale_var = tk.StringVar(value="1.0")
        tk.Entry(
            row2, textvariable=self.scale_var,
            font=("Segoe UI", 9), bg=BG_INPUT, fg=FG_TEXT,
            insertbackground=FG_TEXT, relief=tk.FLAT, width=8,
        ).pack(side=tk.LEFT, padx=(4, 16), ipady=3)

        tk.Label(row2, text="Wire 微调：", font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD).pack(side=tk.LEFT)
        self.wire_adjust_var = tk.StringVar(value="none")
        wire_adjust_menu = tk.OptionMenu(row2, self.wire_adjust_var, "none", "snap-endpoints")
        wire_adjust_menu.configure(
            font=("Segoe UI", 9), bg=BG_INPUT, fg=FG_TEXT,
            activebackground=HOVER, activeforeground=FG_TEXT,
            highlightthickness=0, relief=tk.FLAT,
        )
        wire_adjust_menu["menu"].configure(bg=BG_INPUT, fg=FG_TEXT)
        wire_adjust_menu.pack(side=tk.LEFT, padx=(4, 0), ipady=3)

        # 第三行：pin-snap-threshold
        row3 = tk.Frame(adv_frame, bg=BG_CARD)
        row3.pack(fill=tk.X, padx=16, pady=(4, 8))

        tk.Label(row3, text="Pin 吸附阈值：", font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD).pack(side=tk.LEFT)
        self.pin_snap_var = tk.StringVar(value="0.8")
        tk.Entry(
            row3, textvariable=self.pin_snap_var,
            font=("Segoe UI", 9), bg=BG_INPUT, fg=FG_TEXT,
            insertbackground=FG_TEXT, relief=tk.FLAT, width=8,
        ).pack(side=tk.LEFT, padx=(4, 16), ipady=3)

        # preserve-absolute + flip-y
        self.preserve_abs_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            row3, text="保留绝对坐标", variable=self.preserve_abs_var,
            font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD,
            selectcolor=BG_INPUT, activebackground=BG_CARD, activeforeground=FG_TEXT,
        ).pack(side=tk.LEFT, padx=(0, 12))

        self.flip_y_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            row3, text="翻转 Y 轴", variable=self.flip_y_var,
            font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD,
            selectcolor=BG_INPUT, activebackground=BG_CARD, activeforeground=FG_TEXT,
        ).pack(side=tk.LEFT)

        # ---- 按钮 ----
        btn_frame = tk.Frame(self.root, bg=BG_DARK)
        btn_frame.pack(fill=tk.X, padx=20, pady=(12, 8))

        self.run_btn = tk.Button(
            btn_frame,
            text="▶  开始转换",
            font=("Segoe UI", 12, "bold"),
            fg="#ffffff",
            bg=FG_ACCENT,
            activebackground="#5a52e0",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_run,
        )
        self.run_btn.pack(side=tk.LEFT, ipadx=24, ipady=6)

        self.dry_run_btn = tk.Button(
            btn_frame,
            text="🔍 仅检查",
            font=("Segoe UI", 10),
            fg=FG_TEXT,
            bg=BG_INPUT,
            activebackground=HOVER,
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._on_run(force_dry_run=True),
        )
        self.dry_run_btn.pack(side=tk.LEFT, padx=(12, 0), ipadx=12, ipady=6)

        # ---- 日志 ----
        log_frame = self._card("输出日志")
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 9),
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief=tk.FLAT,
            wrap=tk.WORD,
            height=12,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 12))
        self.log_text.configure(state=tk.DISABLED)

    def _card(self, title: str) -> tk.Frame:
        outer = tk.Frame(self.root, bg=BG_DARK)
        outer.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 4))

        tk.Label(
            outer,
            text=title,
            font=("Segoe UI", 11, "bold"),
            fg=FG_DIM,
            bg=BG_DARK,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))

        inner = tk.Frame(outer, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        inner.pack(fill=tk.BOTH, expand=True)
        return inner

    def _file_row(self, parent: tk.Frame, key: str, label: str):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill=tk.X, padx=12, pady=4)

        tk.Label(
            row, text=label, font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD, width=24, anchor=tk.W
        ).pack(side=tk.LEFT)

        var = tk.StringVar(value="")
        self.file_vars[key] = var

        entry = tk.Entry(
            row,
            textvariable=var,
            font=("Segoe UI", 9),
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief=tk.FLAT,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4), ipady=3)

        btn = tk.Button(
            row,
            text="选择…",
            font=("Segoe UI", 9),
            fg=FG_TEXT,
            bg=BG_INPUT,
            activebackground=HOVER,
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda k=key: self._browse_file(k),
        )
        btn.pack(side=tk.RIGHT, ipadx=6, ipady=2)

    def _browse_file(self, key: str):
        filetypes_map = {
            "inst_info": [("文本文件", "*.txt"), ("所有文件", "*.*")],
            "netlist": [("文本文件", "*.txt"), ("所有文件", "*.*")],
            "wires": [("Excel 文件", "*.xlsx"), ("所有文件", "*.*")],
            "stencil": [("Visio 模板", "*.vss *.vssx"), ("所有文件", "*.*")],
        }
        path = filedialog.askopenfilename(
            title=f"选择 {key}",
            filetypes=filetypes_map.get(key, [("所有文件", "*.*")]),
            initialdir=str(self.base_dir),
        )
        if path:
            self.file_vars[key].set(path)

    def _load_defaults(self):
        """如果 base_dir 下有默认文件，自动填入。"""
        for key, name in DEFAULT_FILES.items():
            default = self.base_dir / name
            if default.exists() and not self.file_vars[key].get():
                self.file_vars[key].set(str(default))

    # ---- 日志 ----
    def _log(self, msg: str, color: str = FG_TEXT):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ---- 运行 ----
    def _on_run(self, force_dry_run: bool = False):
        if self._running:
            messagebox.showinfo("提示", "任务正在运行中，请等待完成。")
            return

        # 校验必填文件
        for key in ("inst_info", "netlist", "wires"):
            if not self.file_vars[key].get():
                messagebox.showwarning("缺少文件", f"请选择 {DEFAULT_FILES[key]}")
                return

        self._running = True
        self.run_btn.configure(state=tk.DISABLED, text="⏳ 运行中…")
        self._clear_log()
        self._log("▶ 开始转换…", FG_ACCENT)

        thread = threading.Thread(target=self._run_worker, args=(force_dry_run,), daemon=True)
        thread.start()

    def _run_worker(self, force_dry_run: bool):
        """在后台线程中运行转换。"""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        try:
            # 构建参数列表
            args_list = ["cadence_to_visio_v2.py"]
            args_list += ["--inst-info", self.file_vars["inst_info"].get()]
            args_list += ["--netlist", self.file_vars["netlist"].get()]
            args_list += ["--wires", self.file_vars["wires"].get()]
            if self.file_vars["stencil"].get():
                args_list += ["--stencil", self.file_vars["stencil"].get()]

            # 布尔选项
            for key, var in self.option_vars.items():
                if key == "dry_run":
                    continue
                if var.get():
                    args_list.append(f"--{key.replace('_', '-')}")

            if force_dry_run:
                args_list.append("--dry-run")
            elif self.option_vars.get("dry_run") and self.option_vars["dry_run"].get():
                args_list.append("--dry-run")

            # skip-nets
            skip = self.skip_nets_var.get().strip()
            if skip:
                args_list += ["--skip-nets", skip]

            # 高级选项
            exclude = self.exclude_pins_var.get().strip()
            if exclude:
                args_list += ["--exclude-pins", exclude]

            scale = self.scale_var.get().strip()
            if scale and scale != "1.0":
                args_list += ["--scale", scale]

            symbol_fit = self.symbol_fit_var.get()
            if symbol_fit != "native":
                args_list += ["--symbol-fit", symbol_fit]

            wire_adjust = self.wire_adjust_var.get()
            if wire_adjust != "none":
                args_list += ["--wire-adjust", wire_adjust]

            pin_snap = self.pin_snap_var.get().strip()
            if pin_snap and pin_snap != "0.8":
                args_list += ["--pin-snap-threshold", pin_snap]

            if self.preserve_abs_var.get():
                args_list.append("--preserve-absolute")
            if self.flip_y_var.get():
                args_list.append("--flip-y")

            self.root.after(0, self._log, f"  命令: python {' '.join(args_list)}", FG_DIM)

            # 模拟 sys.argv 并执行
            old_argv = sys.argv
            sys.argv = args_list

            import cadence_to_visio_v2 as v2
            v2.main()

            sys.argv = old_argv

            # 读取捕获的输出
            captured = sys.stdout.getvalue()
            err_captured = sys.stderr.getvalue()

            self.root.after(0, self._log_output, captured)
            if err_captured.strip():
                self.root.after(0, self._log, f"⚠ stderr:\n{err_captured.strip()}", FG_YELLOW)

            self.root.after(0, self._log, "✅ 转换完成！", FG_GREEN)

        except Exception as e:
            self.root.after(0, self._log, f"❌ 错误: {e}", FG_RED)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.root.after(0, self._run_done)

    def _log_output(self, text: str):
        for line in text.strip().split("\n"):
            if line.strip():
                self._log("  " + line)

    def _run_done(self):
        self._running = False
        self.run_btn.configure(state=tk.NORMAL, text="▶  开始转换")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    root = tk.Tk()

    # Windows 高 DPI 适配
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = CadenceToVisioGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
