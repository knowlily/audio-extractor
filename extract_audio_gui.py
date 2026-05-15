#!/usr/bin/env python3
"""从视频文件中提取音频 — 图形化操作界面"""

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from audio_utils import (FORMAT_NAMES, VIDEO_EXTENSIONS, build_ffmpeg_cmd,
                         EXT_TO_ENCODER, EXT_TO_MUXER, get_ffmpeg)

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except ImportError:
    _HAS_DND = False

# ---------------------------------------------------------------------------
# settings persistence
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / ".audio_extractor_config.json"

DEFAULTS = {
    "format": "MP3", "bitrate": "192k", "sample_rate": "原始",
    "channels": "立体声", "output_dir": "",
}


def load_settings():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}
    except Exception:
        return dict(DEFAULTS)


def save_settings(settings):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def open_folder(path):
    try:
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", path], check=True)
    except Exception:
        pass


def _parse_timestamp(line, marker):
    idx = line.find(marker)
    if idx == -1:
        return None
    try:
        rest = line[idx + len(marker):].strip()
        ts = rest.split(",")[0].split()[0]
        h, m, s = ts.split(":")
        return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# color scheme
# ---------------------------------------------------------------------------

COLORS = {
    "bg":           "#f0f2f5",
    "card":         "#ffffff",
    "header":       "#2c3e50",
    "header_text":  "#ffffff",
    "primary":      "#3498db",
    "primary_hover":"#2980b9",
    "success":      "#27ae60",
    "danger":       "#e74c3c",
    "warning":      "#f39c12",
    "text":         "#2c3e50",
    "text_light":   "#7f8c8d",
    "border":       "#dce1e8",
    "row_alt":      "#f8f9fa",
}

# ---------------------------------------------------------------------------
# main application
# ---------------------------------------------------------------------------

class AudioExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("音频提取工具")
        self.root.geometry("740x680")
        self.root.minsize(600, 500)
        self.root.configure(bg=COLORS["bg"])

        self.files = []
        self.cancelled = False
        self.running = False
        self.ffmpeg = None
        self.current_process = None
        self.errors = []
        self._dnd = _HAS_DND

        self._setup_styles()
        self._build_ui()
        self._load_settings()

        self.status_text.set("检查 ffmpeg 组件...")
        self.extract_btn.config(state="disabled")

        threading.Thread(target=self._discover_ffmpeg, daemon=True).start()

    # ------------------------------------------------------------------
    # ttk styles
    # ------------------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", font=("Segoe UI", 9), background=COLORS["bg"])
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("TLabelframe", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"),
                        foreground=COLORS["header"], background=COLORS["bg"])

        # Cards: white bg frame
        style.configure("Card.TFrame", background=COLORS["card"])

        # Header
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"),
                        foreground=COLORS["header"], background=COLORS["bg"])
        style.configure("Subtitle.TLabel", font=("Segoe UI", 9),
                        foreground=COLORS["text_light"], background=COLORS["bg"])

        # Buttons
        style.configure("TButton", font=("Segoe UI", 9), padding=(12, 5))
        style.configure("Primary.TButton", background=COLORS["primary"])
        style.map("Primary.TButton",
                  background=[("active", COLORS["primary_hover"]),
                              ("disabled", "#bdc3c7")])

        style.configure("Toolbar.TButton", font=("Segoe UI", 9), padding=(8, 4))

        # Treeview
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=26,
                        background=COLORS["card"], fieldbackground=COLORS["card"])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background=COLORS["bg"], foreground=COLORS["text"])
        style.map("Treeview", background=[("selected", COLORS["primary"])])

        # Progress bar
        style.configure("TProgressbar", thickness=10, troughcolor=COLORS["border"],
                        background=COLORS["primary"])

        # Status bar
        style.configure("Status.TLabel", font=("Segoe UI", 8),
                        foreground=COLORS["text_light"], background=COLORS["bg"])

        # Separator
        style.configure("TEntry", fieldbackground=COLORS["card"])

    # ------------------------------------------------------------------
    # settings
    # ------------------------------------------------------------------
    def _load_settings(self):
        s = load_settings()
        self.format_var.set(s["format"])
        self.bitrate_var.set(s["bitrate"])
        self.rate_var.set(s["sample_rate"])
        self.ch_var.set(s["channels"])
        if s["output_dir"]:
            self.outdir_var.set(s["output_dir"])

    def _persist_settings(self):
        save_settings({
            "format": self.format_var.get(),
            "bitrate": self.bitrate_var.get(),
            "sample_rate": self.rate_var.get(),
            "channels": self.ch_var.get(),
            "output_dir": self.outdir_var.get(),
        })

    # ------------------------------------------------------------------
    # ffmpeg discovery
    # ------------------------------------------------------------------
    def _discover_ffmpeg(self):
        exe, ver = get_ffmpeg()
        self.root.after(0, lambda: self._on_ffmpeg_ready(exe, ver))

    def _on_ffmpeg_ready(self, exe, ver):
        self.ffmpeg = exe
        if exe:
            self.status_text.set(ver)
            self.status_label.configure(foreground=COLORS["success"])
            self.extract_btn.config(state="normal")
        else:
            self.status_text.set("ffmpeg 未找到 — 请运行 pip install imageio-ffmpeg")
            self.status_label.configure(foreground=COLORS["danger"])

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------
    def _build_ui(self):
        # --- bottom bar (pack first so it gets reserved space) ---
        self._build_bottom_bar()

        # --- header ---
        header = ttk.Frame(self.root)
        header.pack(fill="x", side="top")
        header_inner = tk.Frame(header, bg=COLORS["header"], padx=20, pady=14)
        header_inner.pack(fill="x")
        tk.Label(header_inner, text="音频提取工具",
                 font=("Segoe UI", 16, "bold"),
                 fg=COLORS["header_text"], bg=COLORS["header"]).pack(anchor="w")
        tk.Label(header_inner, text="从视频文件中提取音频 · 支持拖放与批量处理",
                 font=("Segoe UI", 9),
                 fg="#b0bec5", bg=COLORS["header"]).pack(anchor="w")

        # --- body (packed last so it fills remaining space) ---
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        # Card 1: video file list
        self._build_file_card(body)

        # Card 2: output settings
        self._build_settings_card(body)

        # Card 3: progress
        self._build_progress_card(body)

    def _build_file_card(self, parent):
        frame = ttk.LabelFrame(parent, text="  视频文件  ", padding=10)
        frame.pack(fill="both", expand=True, pady=(0, 8))

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 8))
        self.add_btn = ttk.Button(toolbar, text="＋ 添加文件",
                                  command=self._add_files, style="Toolbar.TButton")
        self.add_btn.pack(side="left", padx=(0, 4))
        self.remove_btn = ttk.Button(toolbar, text="－ 移除选中",
                                     command=self._remove_selected, style="Toolbar.TButton")
        self.remove_btn.pack(side="left", padx=4)
        self.clear_btn = ttk.Button(toolbar, text="清空列表",
                                    command=self._clear_all, style="Toolbar.TButton")
        self.clear_btn.pack(side="left", padx=4)

        file_count = ttk.Label(toolbar, text="", foreground=COLORS["text_light"])
        file_count.pack(side="right")
        self._file_count_label = file_count

        cols = ("#", "filename", "path")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                 selectmode="extended", height=5)
        self.tree.heading("#", text="#")
        self.tree.heading("filename", text="文件名")
        self.tree.heading("path", text="完整路径")
        self.tree.column("#", width=35, anchor="center")
        self.tree.column("filename", width=200)
        self.tree.column("path", width=420)
        self.tree.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="移除", command=self._remove_selected)
        self.tree.bind("<Button-3>", self._tree_context_menu)
        self.tree.bind("<Delete>", lambda e: self._remove_selected())

        self._dnd_over = False
        if self._dnd:
            if hasattr(frame, 'drop_target_register'):
                frame.drop_target_register(DND_FILES)
                frame.dnd_bind("<<Drop>>", self._on_drop)
                frame.dnd_bind("<<DropEnter>>", self._on_drag_enter)
                frame.dnd_bind("<<DropLeave>>", self._on_drag_leave)
            # Root as fallback: catches drops anywhere on the window
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)
            self.root.dnd_bind("<<DropEnter>>", self._on_drag_root_enter)
            self.root.dnd_bind("<<DropLeave>>", self._on_drag_leave)

    def _build_settings_card(self, parent):
        frame = ttk.LabelFrame(parent, text="  输出设置  ", padding=10)
        frame.pack(fill="x", pady=(0, 8))

        # Row 0: format / bitrate / sample rate / channels
        r0 = ttk.Frame(frame)
        r0.pack(fill="x", pady=(0, 6))
        for i in range(4):
            r0.columnconfigure(i, weight=1)

        self.format_var = tk.StringVar(value="MP3")
        self.bitrate_var = tk.StringVar(value="192k")
        self.rate_var = tk.StringVar(value="原始")
        self.ch_var = tk.StringVar(value="立体声")

        self._labeled_combo(r0, "格式", self.format_var,
                            list(FORMAT_NAMES.keys()), 0, 6)
        self._labeled_combo(r0, "比特率", self.bitrate_var,
                            ["64k", "96k", "128k", "160k", "192k", "256k", "320k"], 1, 6)
        self._labeled_combo(r0, "采样率", self.rate_var,
                            ["原始", "44100", "48000", "22050", "16000"], 2, 8)
        self._labeled_combo(r0, "声道", self.ch_var,
                            ["立体声", "单声道"], 3, 6)

        # Row 1: time range
        r1 = ttk.Frame(frame)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="起始:").pack(side="left")
        self.start_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.start_var, width=10, font=("Segoe UI", 9)).pack(side="left", padx=4)
        ttk.Label(r1, text="(可选, 如 01:30)",
                  foreground=COLORS["text_light"], font=("Segoe UI", 8)).pack(side="left", padx=(0, 16))
        ttk.Label(r1, text="结束:").pack(side="left")
        self.end_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.end_var, width=10, font=("Segoe UI", 9)).pack(side="left", padx=4)
        ttk.Label(r1, text="(可选, 如 03:00)",
                  foreground=COLORS["text_light"], font=("Segoe UI", 8)).pack(side="left")
        self.meta_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r1, text="复制元数据", variable=self.meta_var).pack(side="right")

        # Row 2: output directory
        r2 = ttk.Frame(frame)
        r2.pack(fill="x")
        ttk.Label(r2, text="输出:").pack(side="left")
        self.outdir_var = tk.StringVar(value=os.getcwd())
        ttk.Entry(r2, textvariable=self.outdir_var, font=("Segoe UI", 9)).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(r2, text="浏览", command=self._browse_outdir).pack(side="left", padx=2)
        ttk.Button(r2, text="打开", command=self._open_output).pack(side="left")

    def _labeled_combo(self, parent, label, var, values, col, width):
        grp = ttk.Frame(parent)
        grp.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 8))
        ttk.Label(grp, text=label + ":", foreground=COLORS["text_light"],
                  font=("Segoe UI", 8)).pack(anchor="w")
        cb = ttk.Combobox(grp, textvariable=var, values=values,
                          state="readonly", width=width)
        cb.pack(fill="x")

    def _build_progress_card(self, parent):
        frame = ttk.LabelFrame(parent, text="  进度  ", padding=10)
        frame.pack(fill="x", pady=(0, 8))

        self.file_label = ttk.Label(frame, text="就绪 — 请添加视频文件或拖入文件",
                                    font=("Segoe UI", 9))
        self.file_label.pack(anchor="w", pady=(0, 6))

        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.pack(fill="x")

    def _build_bottom_bar(self):
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", side="bottom")

        border = tk.Frame(bottom, height=1, bg=COLORS["border"])
        border.pack(fill="x")

        inner = tk.Frame(bottom, bg=COLORS["card"], padx=16, pady=10)
        inner.pack(fill="x")

        self.status_text = tk.StringVar(value="初始化中...")
        self.status_label = tk.Label(inner, textvariable=self.status_text,
                                     font=("Segoe UI", 8),
                                     fg=COLORS["text_light"], bg=COLORS["card"],
                                     anchor="w")
        self.status_label.pack(side="left")

        self.cancel_btn = ttk.Button(inner, text="取消", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="right", padx=(4, 0))
        self.extract_btn = ttk.Button(inner, text="提取音频",
                                      command=self._start_extraction, style="Primary.TButton")
        self.extract_btn.pack(side="right")

    # ------------------------------------------------------------------
    # file list management
    # ------------------------------------------------------------------
    def _parse_drop_paths(self, data):
        """Split tkinterdnd2 drop data into a list of file paths."""
        if not data:
            return []
        # tk splitlist handles Tcl list format: {C:/path/file.mp4} {D:/other.mkv}
        try:
            paths = self.root.tk.splitlist(data)
        except Exception:
            return []
        # Fallback: also strip braces manually for paths that splitlist missed
        cleaned = []
        for p in paths:
            p = p.strip()
            if not p:
                continue
            if p.startswith("{") and p.endswith("}"):
                p = p[1:-1]
            cleaned.append(p)
        return cleaned

    def _on_drop(self, event):
        self._dnd_highlight(False)
        if self.running:
            return
        for path in self._parse_drop_paths(event.data):
            pp = Path(path)
            if pp.is_dir():
                for root_dir, _, filenames in os.walk(pp):
                    for fn in filenames:
                        fp = Path(root_dir) / fn
                        self._insert_file(fp)
            else:
                self._insert_file(pp)
        self._update_file_count()

    def _on_drag_enter(self, event):
        if not self.running:
            self._dnd_highlight(True)

    def _on_drag_root_enter(self, event):
        if not self.running:
            self._dnd_highlight(True)

    def _on_drag_leave(self, event):
        self._dnd_highlight(False)

    def _dnd_highlight(self, on):
        self._dnd_over = on
        if on:
            self._file_count_label.configure(
                text="释放以添加文件",
                foreground=COLORS["primary"], font=("Segoe UI", 9, "bold"))
        else:
            n = len(self.files)
            self._file_count_label.configure(
                text=f"{n} 个文件" if n else "",
                foreground=COLORS["text_light"], font=("Segoe UI", 9))
    def _add_files(self):
        exts = " ".join(f"*{e}" for e in sorted(VIDEO_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[("视频文件", exts), ("所有文件", "*.*")],
        )
        for p in paths:
            pp = Path(p)
            if pp.suffix.lower() not in VIDEO_EXTENSIONS:
                if not messagebox.askyesno("确认", f"{pp.name}\n\n不是常见的视频格式，仍然添加吗？"):
                    continue
            self._insert_file(pp)
        self._update_file_count()

    def _insert_file(self, p: Path):
        rp = p.resolve()
        if any(rp == existing.resolve() for existing in self.files):
            return
        self.files.append(p)
        idx = len(self.files)
        self.tree.insert("", "end", iid=str(idx), values=(idx, p.name, str(p.parent)))

    def _remove_selected(self):
        indices = []
        for iid in self.tree.selection():
            idx = int(iid) - 1
            if 0 <= idx < len(self.files):
                indices.append(idx)
        for idx in sorted(indices, reverse=True):
            self.files.pop(idx)
        self._reindex()
        self._update_file_count()

    def _clear_all(self):
        if not self.files:
            return
        if messagebox.askyesno("确认", f"确定要清空全部 {len(self.files)} 个文件吗？"):
            self.files.clear()
            self.tree.delete(*self.tree.get_children())
            self._update_file_count()

    def _reindex(self):
        self.tree.delete(*self.tree.get_children())
        for i, p in enumerate(self.files, 1):
            self.tree.insert("", "end", iid=str(i), values=(i, p.name, str(p.parent)))

    def _update_file_count(self):
        n = len(self.files)
        self._file_count_label.config(text=f"{n} 个文件" if n else "")

    def _tree_context_menu(self, event):
        self.tree_menu.post(event.x_root, event.y_root)

    def _browse_outdir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.outdir_var.set(d)

    def _open_output(self):
        d = self.outdir_var.get()
        if d and os.path.isdir(d):
            open_folder(d)
        else:
            messagebox.showwarning("提示", "输出目录不存在。")

    # ------------------------------------------------------------------
    # extraction with live progress and cancel support
    # ------------------------------------------------------------------
    def _start_extraction(self):
        if not self.ffmpeg:
            messagebox.showwarning("提示", "ffmpeg 尚未就绪，请稍候。")
            return
        if not self.files:
            messagebox.showwarning("提示", "请先添加视频文件。")
            return
        if self.running:
            return

        self._persist_settings()

        params = {
            "files": list(self.files),
            "ffmpeg": self.ffmpeg,
            "fmt_key": self.format_var.get(),
            "bitrate": self.bitrate_var.get(),
            "rate": self.rate_var.get(),
            "ch": self.ch_var.get(),
            "start": self.start_var.get().strip() or None,
            "end": self.end_var.get().strip() or None,
            "metadata": self.meta_var.get(),
            "outdir": self.outdir_var.get(),
        }

        self.running = True
        self.cancelled = False
        self.errors.clear()
        self._set_ui_state(extracting=True)

        threading.Thread(target=self._extract_all, args=(params,), daemon=True).start()

    def _set_ui_state(self, extracting):
        state = "disabled" if extracting else "normal"
        self.add_btn.config(state=state)
        self.remove_btn.config(state=state)
        self.clear_btn.config(state=state)
        self.extract_btn.config(state="disabled" if extracting else "normal")
        self.cancel_btn.config(state="normal" if extracting else "disabled")

    def _extract_all(self, params):
        files = params["files"]
        ext = FORMAT_NAMES[params["fmt_key"]]
        encoder = EXT_TO_ENCODER[ext]
        muxer = EXT_TO_MUXER.get(ext)
        total = len(files)

        self.root.after(0, lambda: self.progress.configure(maximum=total, value=0))

        success = 0
        for i, in_path in enumerate(files):
            if self.cancelled:
                break

            out_path = Path(params["outdir"]) / (in_path.stem + ext)
            self.root.after(0, lambda t=f"({i+1}/{total}) {in_path.name}":
                            self.file_label.config(text=t))

            if out_path.exists():
                overwrite = [False]
                event = threading.Event()

                def ask():
                    ow = messagebox.askyesno(
                        "文件已存在",
                        f"{out_path.name}\n\n文件已存在，是否覆盖？")
                    overwrite[0] = ow
                    event.set()

                self.root.after(0, ask)
                event.wait()
                if not overwrite[0]:
                    self.root.after(0, lambda v=i+1: self.progress.configure(value=v))
                    continue

            cmd = build_ffmpeg_cmd(
                params["ffmpeg"], in_path, out_path, encoder,
                bitrate=params["bitrate"],
                sample_rate=None if params["rate"] == "原始" else params["rate"],
                channels=1 if params["ch"] == "单声道" else None,
                start=params["start"],
                end=params["end"],
                muxer=muxer,
                metadata=params["metadata"],
            )

            ok, err = self._run_one(cmd, i + 1, total)
            if ok:
                success += 1
            elif err:
                self.errors.append((in_path.name, err))
                self.root.after(0, lambda v=i+1: self.progress.configure(value=v))
            else:
                self.root.after(0, lambda v=i+1: self.progress.configure(value=v))

        if self.cancelled:
            msg = f"已取消。成功提取 {success}/{total} 个文件。"
        else:
            msg = f"完成。成功提取 {success}/{total} 个文件。"

        if self.errors:
            msg += f"\n\n{len(self.errors)} 个文件提取失败："
            for name, err in self.errors[:10]:
                msg += f"\n  - {name}: {err[:120]}"
            if len(self.errors) > 10:
                msg += f"\n  ... 及其他 {len(self.errors) - 10} 个"

        final_msg = msg
        self.root.after(0, lambda: self._finish(final_msg))

    def _run_one(self, cmd, file_num, total):
        try:
            p = subprocess.Popen(
                cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
                text=True, errors="replace",
            )
            self.current_process = p
        except Exception as e:
            return False, str(e)

        duration = None
        stderr_lines = []

        for line in p.stderr:
            if self.cancelled:
                self._terminate(p)
                return False, None

            stderr_lines.append(line)

            if duration is None:
                duration = _parse_timestamp(line, "Duration:")

            t = _parse_timestamp(line, "time=")
            if t is not None:
                pct = min(100, int(t / duration * 100)) if duration else 0
                status = f"({file_num}/{total}) {pct}%"
                self.root.after(0, lambda s=status: self.file_label.config(text=s))

        ret = p.wait()
        self.current_process = None

        if ret == 0:
            return True, None
        else:
            err_lines = [l.strip() for l in stderr_lines if l.strip()]
            err = err_lines[-3:] if len(err_lines) >= 3 else err_lines
            return False, "\n".join(err)

    def _terminate(self, p):
        try:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        except Exception:
            pass
        self.current_process = None

    # ------------------------------------------------------------------
    # UI callbacks (main thread only)
    # ------------------------------------------------------------------
    def _finish(self, msg):
        self.running = False
        self.current_process = None
        self.file_label.config(text=msg)
        self._set_ui_state(extracting=False)
        messagebox.showinfo("完成", msg)

    def _cancel(self):
        self.cancelled = True
        self.file_label.config(text="正在取消...")
        if self.current_process:
            self._terminate(self.current_process)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main():
    if _HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = AudioExtractorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
