# 音频提取工具

从视频文件中提取音频，支持图形界面和命令行两种方式。**开箱即用**，自动获取 ffmpeg 组件，无需手动安装。

## 快速开始

### 方式一：图形界面（推荐）

双击 `启动提取工具.bat`，自动准备环境并打开界面：

- 拖入或添加视频文件
- 选择输出格式、比特率、采样率、声道
- 点击"提取音频"，支持批量处理

### 方式二：命令行

```bash
pip install imageio-ffmpeg
python extract_audio.py video.mp4              # 输出 video.mp3
python extract_audio.py video.mp4 -f wav       # 输出 WAV
python extract_audio.py video.mp4 -b 320k      # 320kbps 比特率
python extract_audio.py *.mp4 -d ./output      # 批量处理
```

## 支持的格式

| 输入（视频） | 输出（音频） |
|-------------|-------------|
| MP4, MKV, AVI, MOV | **MP3**, WAV, AAC, M4A |
| FLV, WebM, WMV, TS | OGG, FLAC, WMA, Opus |

## 命令行参数

| 参数 | 说明 |
|------|------|
| `-f` | 输出格式：mp3 / wav / aac / m4a / ogg / flac / wma / opus |
| `-b` | 比特率：64k ~ 320k（默认 192k） |
| `-r` | 采样率：44100 / 48000 / 22050 / 16000 |
| `-c` | 声道：1（单声道）/ 2（立体声） |
| `-ss` | 起始时间（HH:MM:SS） |
| `-to` | 结束时间（HH:MM:SS） |
| `-d` | 输出目录（批量模式） |
| `-o` | 输出文件路径（单文件模式） |

## 依赖

- Python 3.8+
- `imageio-ffmpeg`（启动脚本会自动安装）
