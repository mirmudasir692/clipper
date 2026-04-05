# 🧠 ClipMind

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-green.svg)](https://ffmpeg.org/)

**ClipMind** is a powerful and efficient Python toolbox for video and audio processing. Whether you need to extract audio, transcode resolutions, generate HLS streams, or leverage AI for video analysis, ClipMind provides a high-level, easy-to-use interface with modern features including Redis integration and specialized Urdu support.

---

## ⚡ Quick Start

Get started with **ClipMind** in under a minute!

### 1. Install via pip
```bash
# Ensure you have FFmpeg installed on your system first
pip install -r requirements.txt
pip install -e .
```

### 2. Basic Audio Extraction (CLI)
```bash
# Extract high-quality MP3 from any video
clipmind -i video.mp4
```

### 3. Basic Library Usage (Python)
```python
from clipmind import get_audio_from_video

# Extract to a specific output path
get_audio_from_video("tutorial.mp4", output_path="audio/lesson1.wav", audio_format="wav")
```

---

## 🚀 Features

### 🎵 Audio Extraction
- **Multi-format Support**: Extract audio to `mp3` or `wav`.
- **Segment Extraction**: Extract audio from specific time ranges (start/end).
- **Validation**: Built-in verification for video files and FFmpeg availability.

### 🎥 Video Processing
- **Transcoding**: Convert between formats (MP4, MKV, WebM, AVI, etc.) with intelligent encoder selection.
- **Resolution Scaling**: Scale videos to standard resolutions (`240p` to `4K`) sequentially or concurrently.
- **Manipulation**: Merge videos, crop regions, and capture thumbnails.
- **Compositing**: Overlay images on videos with control over opacity, position, and timing.

### 📶 Adaptive Streaming (HLS)
- **Adaptive Bitrate**: Generate HLS (HTTP Live Streaming) manifests (`.m3u8`) and segments (`.ts`).
- **Multi-Resolution**: Automatically produce quality variants.

### 🤖 AI-Powered Analysis
- **Summarization**: Generate intelligent, temporally-aware text summaries.
- **Vulnerability Detection**: Detect safety violations (violence, nudity, hate speech) across visual and auditory channels.
- **Subtitle Generation**: Accurate, time-synchronized subtitles with support for non-speech annotations.
- **Urdu Language Support**: Dedicated printing and processing for Urdu content (`print_urdu`).
- **Perceptual Hashing (pHash)**: Detect visually similar videos regardless of encoding or resolution changes.

### 🏗️ Infrastructure & Scaling
- **Redis Integration**: Built-in support for caching and processing management via Redis.
- **Concurrent Processing**: Multi-threaded resolution transcoding for maximum efficiency.

---

## ⚙️ Installation

### 1. Prerequisites
- **Python 3.6+**
- **FFmpeg**: Must be installed and accessible in your system's `PATH`.

### 2. Install Package
```bash
# Method A: Via requirements.txt
pip install -r requirements.txt

# Method B: Local editable install (recommended for developers)
pip install -e .
```

---

## 🏗️ Building & Packaging (`pyproject.toml`)

ClipMind uses `pyproject.toml` for modern, standard-compliant packaging and build management. You can build the project for distribution:

```bash
# Build the distribution packages
pip install build wheel
python -m build
```

The configuration includes metadata about developers, keywords, classifiers, and the core scripts like the `clipmind` CLI.

---

## 🛠️ Usage

### Command Line Interface (CLI)
The primary use case is simple audio extraction via the `clipmind` command.

```bash
# Basic extraction (defaults to .mp3 in same directory)
clipmind -i video.mp4

# Custom output path and format
clipmind -i input.mkv -o output/audio.wav -f wav
```

### Python Library API
ClipMind is designed to be used as a library for more complex workflows.

```python
import clipmind

# 1. Extract Audio
clipmind.get_audio_from_video("tutorial.mp4", "audio.mp3")

# 2. Merge Videos
clipmind.merge_videos("intro.mp4", "content.mp4", "final.mp4")

# 3. Generate HLS Chunks (Adaptive Bitrate)
result = clipmind.chunk_video_adaptive("movie.mp4", output_dir="hls_output")
print(f"Master manifest created at: {result['master_manifest']}")

# 4. AI Video Subtitles with Urdu Support
from clipmind import generate_subtitle, print_urdu

def my_ai_tool(video_stream, prompt):
    # Gemini implementation
    return "This is my subtitle result in Urdu..."

subtitles = clipmind.generate_subtitle(my_ai_tool, "video.mp4")
print(print_urdu(subtitles))

# 5. Redis Integration
from clipmind.src import configure_redis
redis = configure_redis("redis://127.0.0.1:6379/0")
```

---

## 📄 Configuration (`clipmind.toml`)

ClipMind can be configured using a `clipmind.toml` file in your project root. This allows you to set default behaviors without changing your code.

```toml
[general]
default_audio_format = "mp3"
output_directory = "output"

[video]
default_resolution = "720p"
encoder_priority = ["libx264", "libopenh264", "h264_vaapi"]

[ai]
provider = "openai"
model = "gpt-4-vision-preview"

[hls]
segment_duration = 10
enabled_resolutions = ["360p", "720p", "1080p"]
```

---

## 📂 Project Structure

- `clipmind/`: Core package containing implementations.
  - `__init__.py`: Clean top-level API exports.
  - `src/core/`: Audio extraction, video tools, and HLS logic.
  - `src/cli/`: Command-line interface logic.
  - `src/utils/`: AI prompts, validation, and resolution profiles.
- `clipmind.toml`: Global project configuration.
- `main.py`: Entry point for quick execution and AI demo.
- `pyproject.toml`: Package build and dependency metadata.

---

## 📜 License

This project is licensed under the **MIT License**. Check the `LICENSE` file for details.
