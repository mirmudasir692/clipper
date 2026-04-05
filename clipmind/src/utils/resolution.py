"""
Standard HLS resolution profiles including target bitrates and bandwidth requirements.
Used by the adaptive video chunking tools to generate standardized output streams.
"""

RESOLUTION_PROFILES = {
    '240p': {'width': 426, 'height': 240, 'video_bitrate': '400k', 'audio_bitrate': '64k', 'bandwidth': 500000},
    '360p': {'width': 640, 'height': 360, 'video_bitrate': '800k', 'audio_bitrate': '96k', 'bandwidth': 1000000},
    '480p': {'width': 854, 'height': 480, 'video_bitrate': '1400k', 'audio_bitrate': '128k', 'bandwidth': 1600000},
    '720p': {'width': 1280, 'height': 720, 'video_bitrate': '2800k', 'audio_bitrate': '128k', 'bandwidth': 3000000},
    '1080p': {'width': 1920, 'height': 1080, 'video_bitrate': '5000k', 'audio_bitrate': '192k', 'bandwidth': 5500000},
}