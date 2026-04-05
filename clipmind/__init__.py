"""
clipmind: A versatile video and audio processing toolbox for Python.

This library provides high-level interfaces for common media tasks including:
- Audio extraction from video files.
- Adaptive video chunking for HLS streaming.
- Visual overlays and compositing.
- AI-powered video analysis (vulnerability, summary, subtitles).
- Structural video validation and metadata extraction.
- Concurrent and sequential resolution transcoding.
"""

# Re-export key functions to provide a clean top-level API

from .src.core.audio_extractor import get_audio_from_video, extract_audio, get_default_output_path, chunk_video_adaptive
from .src.core.video_tools import merge_videos, composite_image_over_video, convert_video_resolutions, get_video_thumbnail, detect_video_vulnerability,crop_video, generate_video_summary, generate_subtitle, video_phash, convert_video_format
from .src.utils.validation import validate_video_file, validate_ffmpeg

__version__ = "1.0.0"
__author__ = "clipmind Team"
__all__ = [
    "get_audio_from_video", 
    "extract_audio", 
    "get_default_output_path",
    "validate_video_file",
    "validate_ffmpeg",
    "merge_videos",
    "composite_image_over_video",
    "convert_video_resolutions",
    "get_video_thumbnail",
    "crop_video",
    "chunk_video_adaptive",
    "detect_video_vulnerability",
    "generate_video_summary",
    "generate_subtitle","video_phash",
    "convert_video_format"
]
