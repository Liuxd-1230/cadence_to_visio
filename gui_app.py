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


def get_base_dir() -> Path:
    """获取 exe 或脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class CadenceToVisioGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("720x760")
        self.root.minsize(600, 600)
        self.root.configure(bg=BG_DARK)

        self.base_dir = get_base_dir()
        self._running = False

        self._build_ui()
        self._load_defaults()

    # ---- UI 构建 ----
    def _build_ui(self):
        # 标题
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

        # ---- 选项区域 ----
        opt_frame = self._card("选项")
        self.option_vars: dict[str, tk.BooleanVar | tk.StringVar] = {}

        opts = [
            ("attach", "启用附着 (线端→器件 pin)", True),
            ("draw_nodes", "绘制 T 形交汇点", True),
            ("visio_connectors", "Visio 内置连接线", False),
            ("draw_mos_b_wires", "绘制 MOS B 端分支线", False),
            ("skip_mos_body_nets", "跳过 MOS B net", False),
            ("hidden", "后台运行 Visio", False),
            ("dry_run", "仅检查输入 (不打开 Visio)", False),
        ]
        for key, label, default in opts:
            var = tk.BooleanVar(value=default)
            self.option_vars[key] = var
            cb = tk.Checkbutton(
                opt_frame,
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
        skip_row = tk.Frame(opt_frame, bg=BG_CARD)
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
            height=14,
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
