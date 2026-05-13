#!/usr/bin/env python3
"""从视频文件中提取音频 — 图形化操作界面"""

import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


def _install_imageio_ffmpeg():
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "imageio-ffmpeg", "-q"],
                       check=True, capture_output=True)
        return True
    except Exception:
        return False


_ffmpeg_cache = None


def get_ffmpeg():
    """Return (exe_path, version_str) or (None, None). Cached after first call."""
    global _ffmpeg_cache
    if _ffmpeg_cache is not None:
        return _ffmpeg_cache

    # 1. Fast PATH lookup — no subprocess spawn
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            ver = subprocess.run(
                [ffmpeg, "-version"], capture_output=True, text=True, timeout=10
            ).stdout.splitlines()[0]
            _ffmpeg_cache = (ffmpeg, ver)
            return _ffmpeg_cache
        except Exception:
            pass

    # 2. imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        ver = subprocess.run(
            [exe, "-version"], capture_output=True, text=True, timeout=10
        ).stdout.splitlines()[0]
        _ffmpeg_cache = (exe, ver)
        return _ffmpeg_cache
    except ImportError:
        if _install_imageio_ffmpeg():
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            ver = subprocess.run(
                [exe, "-version"], capture_output=True, text=True, timeout=10
            ).stdout.splitlines()[0]
            _ffmpeg_cache = (exe, ver)
            return _ffmpeg_cache
    except Exception:
        pass

    _ffmpeg_cache = (None, None)
    return _ffmpeg_cache


FORMATS = {
    "MP3":  ".mp3",
    "WAV":  ".wav",
    "AAC":  ".aac",
    "M4A":  ".m4a",
    "OGG":  ".ogg",
    "FLAC": ".flac",
    "WMA":  ".wma",
    "Opus": ".opus",
}

ENCODER = {
    ".mp3": "libmp3lame", ".wav": "pcm_s16le", ".aac": "aac",
    ".m4a": "aac", ".ogg": "libvorbis", ".flac": "flac",
    ".wma": "wmav2", ".opus": "libopus",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".wmv",
    ".m4v", ".ts", ".m2ts", ".3gp", ".ogv", ".divx",
}


class AudioExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("音频提取工具")
        self.root.geometry("700x540")
        self.root.minsize(580, 440)

        self.files = []
        self.cancelled = False
        self.running = False
        self.ffmpeg = None

        self._build_ui()
        self.file_label.config(text="正在准备环境...")
        self.status_label.config(text="检查 ffmpeg 组件...")
        self.extract_btn.config(state="disabled")

        # Discover ffmpeg on a background thread so the UI appears instantly
        threading.Thread(target=self._discover_ffmpeg, daemon=True).start()

    def _discover_ffmpeg(self):
        exe, ver = get_ffmpeg()
        self.root.after(0, lambda: self._on_ffmpeg_ready(exe, ver))

    def _on_ffmpeg_ready(self, exe, ver):
        self.ffmpeg = exe
        if exe:
            self.status_label.config(text=ver)
            self.file_label.config(text="就绪 — 请添加视频文件或拖入文件")
            self.extract_btn.config(state="normal")
        else:
            self.status_label.config(
                text="未找到 ffmpeg — 请手动运行: pip install imageio-ffmpeg", foreground="red")
            self.file_label.config(text="环境准备失败，请检查依赖后重启")

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # --- 视频文件列表 ---
        file_frame = ttk.LabelFrame(self.root, text="视频文件", padding=5)
        file_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        toolbar = ttk.Frame(file_frame)
        toolbar.pack(fill="x", pady=(0, 4))
        ttk.Button(toolbar, text="添加文件", command=self._add_files).pack(side="left", padx=2)
        ttk.Button(toolbar, text="移除选中", command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(toolbar, text="清空列表", command=self._clear_all).pack(side="left", padx=2)

        cols = ("#", "filename", "path")
        self.tree = ttk.Treeview(file_frame, columns=cols, show="headings",
                                 selectmode="extended", height=8)
        self.tree.heading("#", text="#")
        self.tree.heading("filename", text="文件名")
        self.tree.heading("path", text="路径")
        self.tree.column("#", width=35, anchor="center")
        self.tree.column("filename", width=200)
        self.tree.column("path", width=400)
        self.tree.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(file_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 右键菜单
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="移除", command=self._remove_selected)
        self.tree.bind("<Button-3>", self._tree_context_menu)
        self.tree.bind("<Delete>", lambda e: self._remove_selected())

        # --- 输出设置 ---
        options_frame = ttk.LabelFrame(self.root, text="输出设置", padding=8)
        options_frame.pack(fill="x", padx=8, pady=4)

        row1 = ttk.Frame(options_frame)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="格式:").pack(side="left")
        self.format_var = tk.StringVar(value="MP3")
        fmt_combo = ttk.Combobox(row1, textvariable=self.format_var,
                                 values=list(FORMATS.keys()), state="readonly", width=6)
        fmt_combo.pack(side="left", padx=4)

        ttk.Label(row1, text="比特率:").pack(side="left", padx=(20, 0))
        self.bitrate_var = tk.StringVar(value="192k")
        br_combo = ttk.Combobox(row1, textvariable=self.bitrate_var,
                                values=["64k", "96k", "128k", "160k", "192k", "256k", "320k"],
                                state="readonly", width=6)
        br_combo.pack(side="left", padx=4)

        ttk.Label(row1, text="采样率:").pack(side="left", padx=(20, 0))
        self.rate_var = tk.StringVar(value="原始")
        rate_combo = ttk.Combobox(row1, textvariable=self.rate_var,
                                  values=["原始", "44100", "48000", "22050", "16000"],
                                  state="readonly", width=7)
        rate_combo.pack(side="left", padx=4)

        ttk.Label(row1, text="声道:").pack(side="left", padx=(20, 0))
        self.ch_var = tk.StringVar(value="立体声")
        ch_combo = ttk.Combobox(row1, textvariable=self.ch_var,
                                values=["立体声", "单声道"], state="readonly", width=6)
        ch_combo.pack(side="left", padx=4)

        # 输出目录
        row2 = ttk.Frame(options_frame)
        row2.pack(fill="x", pady=(6, 2))
        ttk.Label(row2, text="输出目录:").pack(side="left")
        self.outdir_var = tk.StringVar(value=os.getcwd())
        ttk.Entry(row2, textvariable=self.outdir_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row2, text="浏览...", command=self._browse_outdir).pack(side="left")

        # --- 进度 ---
        progress_frame = ttk.LabelFrame(self.root, text="进度", padding=8)
        progress_frame.pack(fill="x", padx=8, pady=4)

        self.file_label = ttk.Label(progress_frame, text="就绪")
        self.file_label.pack(anchor="w")

        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(fill="x", pady=4)

        # --- 底部 ---
        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")

        self.status_label = ttk.Label(bottom, text="初始化中...", foreground="gray")
        self.status_label.pack(side="left")

        self.extract_btn = ttk.Button(bottom, text="提取音频", command=self._start_extraction)
        self.extract_btn.pack(side="right")
        self.cancel_btn = ttk.Button(bottom, text="取消", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="right", padx=4)

    # ------------------------------------------------------------------
    # 文件列表管理
    # ------------------------------------------------------------------
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.mkv *.avi *.mov *.flv *.webm *.wmv *.m4v *.ts *.m2ts *.3gp *.ogv *.divx"),
                ("所有文件", "*.*"),
            ],
        )
        for p in paths:
            self._insert_file(Path(p))

    def _insert_file(self, p: Path):
        if p in self.files:
            return
        self.files.append(p)
        idx = len(self.files)
        self.tree.insert("", "end", iid=str(idx), values=(idx, p.name, str(p.parent)))

    def _remove_selected(self):
        for iid in reversed(self.tree.selection()):
            idx = int(iid) - 1
            if 0 <= idx < len(self.files):
                self.files.pop(idx)
            self.tree.delete(iid)
        self._reindex()

    def _clear_all(self):
        self.files.clear()
        self.tree.delete(*self.tree.get_children())

    def _reindex(self):
        self.tree.delete(*self.tree.get_children())
        for i, p in enumerate(self.files, 1):
            self.tree.insert("", "end", iid=str(i), values=(i, p.name, str(p.parent)))

    def _tree_context_menu(self, event):
        self.tree_menu.post(event.x_root, event.y_root)

    def _browse_outdir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.outdir_var.set(d)

    # ------------------------------------------------------------------
    # 提取
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

        self.running = True
        self.cancelled = False
        self.extract_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress["maximum"] = len(self.files)
        self.progress["value"] = 0

        threading.Thread(target=self._extract_all, daemon=True).start()

    def _extract_all(self):
        fmt_key = self.format_var.get()
        ext = FORMATS[fmt_key]
        encoder = ENCODER[ext]

        success = 0
        total = len(self.files)

        for i, in_path in enumerate(self.files):
            if self.cancelled:
                break

            out_path = Path(self.outdir_var.get()) / (in_path.stem + ext)
            self._set_file_label(f"({i+1}/{total}) {in_path.name}")

            cmd = [self.ffmpeg, "-y", "-i", str(in_path), "-vn", "-c:a", encoder,
                   "-b:a", self.bitrate_var.get()]

            rate = self.rate_var.get()
            if rate != "原始":
                cmd += ["-ar", rate]

            ch = self.ch_var.get()
            if ch == "单声道":
                cmd += ["-ac", "1"]

            cmd.append(str(out_path))

            try:
                subprocess.run(cmd, check=True, capture_output=True)
                success += 1
            except subprocess.CalledProcessError as e:
                self.root.after(0, lambda err=e, f=in_path.name:
                    self._log_error(f, err.stderr.decode(errors="replace").strip()))

            self.root.after(0, lambda v=i+1: self.progress.configure(value=v))

        if self.cancelled:
            msg = f"已取消。成功提取 {success}/{total} 个文件。"
        else:
            msg = f"完成！成功提取 {success}/{total} 个文件。"
        self.root.after(0, lambda: self._finish(msg))

    def _set_file_label(self, text):
        self.root.after(0, lambda: self.file_label.config(text=text))

    def _finish(self, msg):
        self.running = False
        self.file_label.config(text=msg)
        self.extract_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        messagebox.showinfo("完成", msg)

    def _cancel(self):
        self.cancelled = True
        self.file_label.config(text="正在取消...")

    def _log_error(self, filename, stderr):
        lines = [l for l in stderr.splitlines() if l.strip()]
        err_msg = lines[-1] if lines else stderr[:200]
        messagebox.showerror("错误", f"提取失败: {filename}\n\n{err_msg}")


def main():
    root = tk.Tk()
    app = AudioExtractorApp(root)

    # Windows 拖放支持 (WM_DROPFILES)
    try:
        import ctypes
        from ctypes import wintypes

        WS_EX_ACCEPTFILES = 0x10
        GWL_EXSTYLE = -20

        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
            ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_ACCEPTFILES)
        ctypes.windll.shell32.DragAcceptFiles(hwnd, True)

        WM_DROPFILES = 0x0233
        old_proc = ctypes.windll.user32.GetWindowLongW(hwnd, -4)

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_wintypes.WPARAM, ctypes.c_wintypes.LPARAM,
        )

        @WNDPROC
        def drop_proc(hwnd, msg, wparam, lparam):
            if msg == WM_DROPFILES:
                hdrop = wparam
                count = ctypes.windll.shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
                buf = ctypes.create_unicode_buffer(260)
                for i in range(count):
                    ctypes.windll.shell32.DragQueryFileW(hdrop, i, buf, 260)
                    filepath = buf.value
                    if Path(filepath).suffix.lower() in VIDEO_EXTENSIONS:
                        app._insert_file(Path(filepath))
                ctypes.windll.shell32.DragFinish(hdrop)
                return 0
            return ctypes.windll.user32.CallWindowProcW(old_proc, hwnd, msg, wparam, lparam)

        ctypes.windll.user32.SetWindowLongW(hwnd, -4, drop_proc)
        app._old_proc = old_proc
    except Exception:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()
