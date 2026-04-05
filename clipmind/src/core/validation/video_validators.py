import subprocess
import os
import json

def validate_video(video_path: str = ""):
    """
    Extends basic file validation by performing deep analysis of the video's internal structure.
    Uses ffprobe to detect corruption, invalid streams, or potentially malicious file headers.
    
    Args:
        video_path (str): The absolute or relative path to the video file.
        
    Returns:
        tuple[bool, str]: A pair containing (is_valid, status_message).
    """
    
    # Check for empty input strings
    if video_path == "":
        raise ValueError("Critical: video_path must be provided for validation.")

    # File-level existence check
    if not os.path.exists(video_path):
        return False, "Validation failed: File does not exist."

    # Immediate rejection of headers with zero data
    if os.path.getsize(video_path) == 0:
        return False, "Validation failed: File is zero bytes (corrupt)."
        
    # Prepare probe command to extract JSON metadata about the stream
    cmd = [
        'ffprobe',
        '-v', 'error',          # Suppress decorative output
        '-show_streams',        # Extract stream-level details
        '-select_streams', 'v', # Focus specifically on video streams
        '-of', 'json',          # Format output as parseable JSON
        video_path
    ]

    try:
        # Run ffprobe with a conservative timeout to prevent hangs on malformed files
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            timeout=15
        )
        
        # Non-zero exit code usually indicates severe corruption or incompatible format
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            if not error_msg:
                error_msg = "Unknown binary parsing error."
            return False, f"Structural validation failed: {error_msg}"
            
        try:
            # Parse the probe results
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            
            # A valid video must contain at least one visual stream channel
            if not streams:
                return False, "Security warning: No video stream detected. File may be mislabeled or malicious."
            
            video_stream = streams[0]
            codec_name = video_stream.get('codec_name', '')
            width = video_stream.get('width', 0)
            
            # Check for essential metadata that should always be present in valid files
            if not codec_name:
                return False, "Validation failed: Missing or invalid codec identifiers."
                
            if width == 0:
                return False, "Validation failed: Corrupted video resolution metadata."

        except json.JSONDecodeError:
            # Handle cases where ffprobe output itself is garbled (extremely rare)
            return False, "Validation failed: Internal structure is unreadable."
            
        # Catch warnings that don't trigger non-zero exit codes but indicate partial corruption
        if result.stderr and "Invalid data" in result.stderr:
             return False, f"Integrity warning: File contains corrupted segments. {result.stderr[:100]}"

        return True, "Video file passed all structural and integrity checks."

    except subprocess.TimeoutExpired:
        # Protect against "zip bombs" or infinite-loop media headers
        return False, "Validation timeout: File header may be malformed or excessively complex."
    except Exception as e:
        # Generic catch-all for system or OS-level failures
        return False, f"System error during validation: {str(e)}"