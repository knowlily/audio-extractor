#!/usr/bin/env python3
"""
Extract audio from video files (MP4, MKV, AVI, MOV, FLV, WebM, etc.).
Supports MP3, WAV, AAC, M4A, OGG, FLAC output formats.

Usage:
    python extract_audio.py video.mp4                        # -> video.mp3
    python extract_audio.py video.mp4 -f wav                 # -> video.wav
    python extract_audio.py video.mp4 -b 320k -o audio.mp3   # custom bitrate & name
    python extract_audio.py *.mp4                            # batch processing
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


_ffmpeg_cache = None


def get_ffmpeg():
    """Return (exe_path, version_str) or exit if ffmpeg is not found. Cached after first call."""
    global _ffmpeg_cache
    if _ffmpeg_cache is not None:
        return _ffmpeg_cache

    # 1. Fast PATH lookup without spawning a subprocess
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

    # 2. Fall back to imageio-ffmpeg's bundled binary
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        ver = subprocess.run(
            [exe, "-version"], capture_output=True, text=True, timeout=10
        ).stdout.splitlines()[0]
        _ffmpeg_cache = (exe, ver)
        return _ffmpeg_cache
    except Exception:
        pass

    sys.exit(
        "ffmpeg not found. Install it via:\n"
        "  pip install imageio-ffmpeg\n"
        "  or download from https://ffmpeg.org/download.html"
    )


EXT_TO_ENCODER = {
    ".mp3":  "libmp3lame",
    ".wav":  "pcm_s16le",
    ".aac":  "aac",
    ".m4a":  "aac",
    ".ogg":  "libvorbis",
    ".flac": "flac",
    ".wma":  "wmav2",
    ".opus": "libopus",
}

EXT_TO_MUXER = {
    ".mp3":  "mp3",
    ".wav":  "wav",
    ".aac":  "adts",
    ".m4a":  "ipod",
    ".ogg":  "ogg",
    ".flac": "flac",
    ".wma":  "asf",
    ".opus": "ogg",
}


def extract_audio(input_path, output_path, fmt, bitrate, sample_rate, channels,
                  start=None, end=None, ffmpeg="ffmpeg"):
    """Extract audio from a video file."""
    ext = fmt or Path(output_path).suffix.lower()
    encoder = EXT_TO_ENCODER.get(ext, "libmp3lame")
    muxer = EXT_TO_MUXER.get(ext)

    cmd = [ffmpeg, "-y", "-i", str(input_path), "-vn"]
    cmd += ["-c:a", encoder]

    if bitrate:
        cmd += ["-b:a", bitrate]
    if sample_rate:
        cmd += ["-ar", str(sample_rate)]
    if channels:
        cmd += ["-ac", str(channels)]
    if start:
        cmd += ["-ss", start]
    if end:
        cmd += ["-to", end]

    if muxer:
        cmd += ["-f", muxer]

    cmd.append(str(output_path))

    try:
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
        print(f"  -> {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"  Error: {e.stderr.decode().strip()}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Extract audio from video files (MP4, MKV, AVI, MOV, FLV, WebM...)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s video.mp4                  extract audio to video.mp3
  %(prog)s video.mp4 -f wav           extract to WAV format
  %(prog)s video.mp4 -b 320k          set audio bitrate to 320kbps
  %(prog)s video.mp4 -ss 01:30 -to 03:00 -o clip.mp3   extract a segment
  %(prog)s *.mp4                      batch process all mp4 files
        """,
    )
    parser.add_argument("input", nargs="+", help="input video file(s), glob patterns supported")
    parser.add_argument("-o", "--output", help="output file path (single file mode only)")
    parser.add_argument("-f", "--format", choices=["mp3", "wav", "aac", "m4a", "ogg", "flac", "wma", "opus"],
                        default="mp3", help="output audio format (default: mp3)")
    parser.add_argument("-b", "--bitrate", default="192k",
                        help="audio bitrate, e.g. 128k, 192k, 320k (default: 192k)")
    parser.add_argument("-r", "--sample-rate", type=int, help="sample rate in Hz, e.g. 44100, 48000")
    parser.add_argument("-c", "--channels", type=int, choices=[1, 2], help="audio channels: 1 (mono) or 2 (stereo)")
    parser.add_argument("-d", "--output-dir", help="output directory (batch mode)")
    parser.add_argument("-ss", help="start time offset (HH:MM:SS or seconds)")
    parser.add_argument("-to", help="end time offset (HH:MM:SS or seconds)")
    parser.add_argument("--dry-run", action="store_true", help="print commands without executing")

    args = parser.parse_args()

    # Expand glob patterns on platforms that don't auto-expand (Windows)
    inputs = []
    for pattern in args.input:
        from glob import glob
        matches = glob(pattern)
        inputs.extend(matches if matches else [pattern])

    if len(inputs) > 1 and args.output:
        sys.exit("--output can only be used with a single input file")

    ffmpeg = None if args.dry_run else get_ffmpeg()[0]
    if not args.dry_run:
        print(f"ffmpeg: {ffmpeg}")

    for path in inputs:
        if not os.path.exists(path):
            print(f"Skipping (not found): {path}", file=sys.stderr)
            continue

        in_path = Path(path)
        if args.output:
            out_path = Path(args.output)
        else:
            suffix = f".{args.format}"
            out_path = Path(args.output_dir) / (in_path.stem + suffix) if args.output_dir else in_path.with_suffix(suffix)

        out_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Extracting: {in_path.name}")
        extract_audio(
            in_path, out_path,
            fmt=f".{args.format}",
            bitrate=args.bitrate,
            sample_rate=args.sample_rate,
            channels=args.channels,
            start=getattr(args, 'ss', None),
            end=getattr(args, 'to', None),
            ffmpeg=ffmpeg or "ffmpeg",
        )


if __name__ == "__main__":
    main()
