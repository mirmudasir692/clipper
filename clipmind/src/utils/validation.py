import os
import subprocess
from pathlib import Path


def validate_video_file(video_path):
    """
    Validates if the provided path points to a supported video file.
    Checks for existence, file type, and extension compatibility.
    
    Args:
        video_path (str/Path): The path to the video file to be validated.
        
    Returns:
        bool: True if the file exists and is a supported video format, False otherwise.
    """
    video_path = Path(video_path)
    
    # Check if the path actually exists on the filesystem
    if not video_path.exists():
        print(f"Error: Video file '{video_path}' does not exist.")
        return False

    # Ensure it's a file and not a directory or symlink
    if not video_path.is_file():
        print(f"Error: '{video_path}' is not a file.")
        return False

    # Define a comprehensive set of common video formats
    supported_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.f4v'}
    file_extension = video_path.suffix.lower()

    # Verify the extension matches our supported list
    if file_extension not in supported_extensions:
        print(f"Warning: File extension '{file_extension}' might not be supported.")
        print(f"Supported extensions: {', '.join(sorted(supported_extensions))}")
        return False

    return True


def validate_ffmpeg():
    """
    Checks if the 'ffmpeg' command-line tool is installed and accessible in the system PATH.
    
    Returns:
        bool: True if ffmpeg is available and functional, False otherwise.
    """
    try:
        # Attempt to run ffmpeg with the -version flag to verify installation
        result = subprocess.run(['ffmpeg', '-version'],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              text=True)
        return result.returncode == 0
    except FileNotFoundError:
        # Specifically handle the case where the command is missing from the system
        print("Error: ffmpeg is not installed or not found in system PATH.")
        print("Please install ffmpeg before running this script.")
        return False
    except Exception as e:
        # Catch unexpected errors during the process check
        print(f"Error checking ffmpeg state: {e}")
        return False
