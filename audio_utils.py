"""Shared utilities for audio extraction — ffmpeg discovery, encoder/muxer maps."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# ffmpeg discovery (cached)
# ---------------------------------------------------------------------------

_ffmpeg_cache = None


def _install_imageio_ffmpeg():
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "imageio-ffmpeg", "-q"],
            check=True, capture_output=True,
        )
        return True
    except Exception:
        return False


def _try_version(exe):
    """Run exe -version, return first stdout line or None on failure."""
    try:
        return subprocess.run(
            [exe, "-version"], capture_output=True, text=True, timeout=10,
        ).stdout.splitlines()[0]
    except Exception:
        return None


def _find_bundled_ffmpeg():
    """Search for ffmpeg in a PyInstaller / Nuitka frozen bundle."""
    if not getattr(sys, "frozen", False):
        return (None, None)
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return (None, None)
    for exe in Path(base).rglob("ffmpeg*"):
        if exe.suffix in (".exe", "") and os.access(str(exe), os.X_OK):
            ver = _try_version(str(exe))
            if ver:
                return (str(exe), ver)
    return (None, None)


def get_ffmpeg():
    """Return (exe_path, version_str) or (None, None). Cached after first call."""
    global _ffmpeg_cache
    if _ffmpeg_cache is not None:
        return _ffmpeg_cache

    # 1. PyInstaller / Nuitka frozen bundle
    exe, ver = _find_bundled_ffmpeg()
    if exe:
        _ffmpeg_cache = (exe, ver)
        return _ffmpeg_cache

    # 2. Fast PATH lookup
    exe = shutil.which("ffmpeg")
    if exe:
        ver = _try_version(exe)
        if ver:
            _ffmpeg_cache = (exe, ver)
            return _ffmpeg_cache

    # 3. imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        ver = _try_version(exe)
        if ver:
            _ffmpeg_cache = (exe, ver)
            return _ffmpeg_cache
    except ImportError:
        if _install_imageio_ffmpeg():
            try:
                import imageio_ffmpeg
                exe = imageio_ffmpeg.get_ffmpeg_exe()
                ver = _try_version(exe)
                if ver:
                    _ffmpeg_cache = (exe, ver)
                    return _ffmpeg_cache
            except Exception:
                pass
    except Exception:
        pass

    _ffmpeg_cache = (None, None)
    return _ffmpeg_cache


# ---------------------------------------------------------------------------
# Format / codec maps
# ---------------------------------------------------------------------------

FORMAT_NAMES = {
    "MP3": ".mp3", "WAV": ".wav", "AAC": ".aac", "M4A": ".m4a",
    "OGG": ".ogg", "FLAC": ".flac", "WMA": ".wma", "Opus": ".opus",
}

EXT_TO_ENCODER = {
    ".mp3": "libmp3lame", ".wav": "pcm_s16le", ".aac": "aac",
    ".m4a": "aac", ".ogg": "libvorbis", ".flac": "flac",
    ".wma": "wmav2", ".opus": "libopus",
}

EXT_TO_MUXER = {
    ".mp3": "mp3", ".wav": "wav", ".aac": "adts", ".m4a": "ipod",
    ".ogg": "ogg", ".flac": "flac", ".wma": "asf", ".opus": "ogg",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".wmv",
    ".m4v", ".ts", ".m2ts", ".3gp", ".ogv", ".divx",
}


def build_ffmpeg_cmd(ffmpeg_exe, input_path, output_path, encoder, *,
                     bitrate=None, sample_rate=None, channels=None,
                     start=None, end=None, muxer=None, metadata=True):
    """Build an ffmpeg command list for audio extraction."""
    cmd = [ffmpeg_exe, "-y", "-i", str(input_path), "-vn", "-c:a", encoder]
    for flag, val in ("-b:a", bitrate), ("-ar", sample_rate), ("-ac", channels), \
                      ("-ss", start), ("-to", end), ("-f", muxer):
        if val:
            cmd += [flag, str(val)]
    if metadata:
        cmd += ["-map_metadata", "0"]
    cmd.append(str(output_path))
    return cmd
