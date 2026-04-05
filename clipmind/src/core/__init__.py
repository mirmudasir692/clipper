"""
Core processing engine for the clipmind package.
Contains low-level and mid-level tools for audio extraction, video manipulation, and transcoding.
"""
from .audio_extractor import get_audio_from_video, extract_audio, get_default_output_path
from .video_tools import merge_videos, composite_image_over_video, convert_video_resolutions, get_video_thumbnail, crop_video, video_phash
__all__ = ["get_audio_from_video", "extract_audio", "get_default_output_path", "merge_videos", "composite_image_over_video",  "convert_video_resolutions", "get_video_thumbnail", "crop_video", "video_phash"]
