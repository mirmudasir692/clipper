import ffmpeg
import tempfile
import os
import cv2
import numpy as np
from typing import Optional, Any, Union
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from ..utils.ai_utils import VULNERABILITY_PROMPT, VIDEO_SUMMARIZATION_PROMPT, SUBTITLE_GENERATION_PROMPT
import json
import re

bitrate_map = {
    240: "400k",
    360: "600k",
    480: "1000k",
    720: "2500k",
    1080: "5000k",
    1440: "10000k",
    2160: "20000k"
}

def get_preset_for_resolution(res):
    """
    Determines the optimal FFmpeg encoding preset based on the target vertical resolution.
    Higher resolutions use faster presets to maintain reasonable processing times.
    
    Args:
        res (int/str): The vertical height of the resolution (e.g., 720 or "1080").
        
    Returns:
        str: The recommended FFmpeg preset name (e.g., 'veryfast', 'fast', 'medium').
    """
    res = int(res)
    # For low resolutions, we can afford 'veryfast' for near-instant results
    if res <= 360:
        return "veryfast"
    # Mid-range resolutions use 'fast'
    if res <= 480:
        return "fast"
    # High resolutions use 'medium' to balance file size and quality
    return "medium"
def process_single_resolution(input_file, res, output_dir, encoder="libx264"):
    """
    Internal helper function that performs the actual transcoding for a single resolution.
    
    Args:
        input_file (str): Absolute or relative path to the input video file.
        res (int/str): The target resolution height (e.g., 720 or "720p").
        output_dir (str): The directory where the resulting video will be stored.
        encoder (str): The H.264 encoder to be used for the conversion. Defaults to "libx264".
        
    Returns:
        str: The path to the newly generated video file.
    """
    # Clean resolution input (remove 'p' suffix if present)
    res_int = int(str(res).replace("p", ""))
    
    # Retrieve target bitrate and encoding preset
    bitrate = bitrate_map.get(res_int, "1500k")
    preset = get_preset_for_resolution(res_int)
    
    # Construct formatting for output filename
    filename = os.path.splitext(os.path.basename(input_file))[0]
    output_path = os.path.join(output_dir, f"{filename}_{res_int}p.mp4")
    
    # Construct the raw ffmpeg command for maximum control
    command = [
        "ffmpeg",
        "-y",                   # Overwrite output files without asking
        "-i", input_file,       # Input file
        "-map", "0:v:0",        # Map the first video stream
        "-map", "0:a:0?",       # Map the first audio stream if it exists
        "-vf", f"scale=-2:{res_int}", # Scale preserving aspect ratio (must be even)
        "-c:v", encoder,        # Video codec
        "-preset", preset,      # Encoding speed/quality preset
        "-b:v", bitrate,        # Target video bitrate
        "-movflags", "+faststart", # Move metadata to start for faster web playback
        "-c:a", "copy",         # Copy audio directly without re-encoding
        output_path             # Final output destination
    ]
    
    try:
        # Run command synchronously and capture output for debugging
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        # Log failure if the ffmpeg process exits with an error
        print(f"Failed to process {res_int}p: {e.stderr.decode()}")
    
    return output_path

def convert_video_resolutions_concurrent(input_file, resolutions, output_dir="output", max_workers=None):
    """
    Efficiently transcode a single video into multiple resolutions using parallel threads.
    This significantly reduces total processing time on multi-core systems.
    
    Args:
        input_file (str): Path to the source video file.
        resolutions (list): A list of target heights (e.g., [480, 720, 1080]).
        output_dir (str): Target folder for the transcoded files. Defaults to "output".
        max_workers (int, optional): The maximum number of concurrent threads. 
                                    Defaults to the number of CPUs available.
    """
    # Verify input existence before starting heavy operations
    if not os.path.exists(input_file):
        print(f"Error: Input file {input_file} does not exist.")
        return

    # Ensure output directory structure exists
    os.makedirs(output_dir, exist_ok=True)

    # Use standard library encoder
    encoder = "libx264"

    # Manage parallel execution using a thread pool
    futures = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Schedule each resolution task
        for res in resolutions:
            futures.append(executor.submit(process_single_resolution, input_file, res, output_dir, encoder))
        
        # Wait for all tasks to complete and handle results/exceptions
        for future in as_completed(futures):
            try:
                future.result() 
            except Exception as e:
                print(f"Concurrent processing error: {e}")


def get_available_video_encoder():
    """
    Scans the system's FFmpeg installation to identify the best performing H.264 encoder.
    Prioritizes high quality and hardware acceleration.
    
    Priority Order:
    1. libx264     : Software (Industry Standard, Best Quality)
    2. libopenh264 : Software (Fast, Broad Compatibility)
    3. h264_vaapi  : Hardware (Intel/AMD GPU Acceleration)
    
    Returns:
        str or None: The name of the best available encoder, or None if FFmpeg is missing.
    """
    try:
        # Query FFmpeg for its list of supported encoders
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        encoders = result.stdout

        # Select the best one from our priority list
        if "libx264" in encoders:
            return "libx264"
        if "libopenh264" in encoders:
            return "libopenh264"
        if "h264_vaapi" in encoders:
            return "h264_vaapi"

    except Exception:
        # Silently fail if ffmpeg command itself fails (e.g., not installed)
        pass

    return None


def merge_videos(video1_path: Optional[str] = None, video2_path: Optional[str] = None, output_path: Optional[str] = None) -> bool:
    """
    Concatenates two video files into a single continuous video.
    Uses FFmpeg's concat demuxer for near-instant processing via stream copying.
    
    Args:
        video1_path (str): File path for the first video segment.
        video2_path (str): File path for the second video segment.
        output_path (str): Desired output path for the merged video.
        
    Returns:
        bool: True if the videos were merged successfully, False otherwise.
    """
    list_file_path = None
    
    try:
        # Basic input validation
        if video1_path is None or video2_path is None or output_path is None:
            raise ValueError("All paths (video1, video2, output) must be provided")

        v1 = Path(video1_path)
        v2 = Path(video2_path)
        out = Path(output_path)

        # File presence checks
        if not v1.exists():
            raise FileNotFoundError(f"Video 1 not found: {v1}")
        if not v2.exists():
            raise FileNotFoundError(f"Video 2 not found: {v2}")

        # Create a temporary 'input list' file required by ffmpeg's concat demuxer
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            # We use .resolve() to ensure absolute paths for FFmpeg
            f.write(f"file '{v1.resolve()}'\n")
            f.write(f"file '{v2.resolve()}'\n")
            list_file_path = f.name

        # Execute concatenation using stream copy (no re-encoding = fast)
        (
            ffmpeg
            .input(list_file_path, format='concat', safe=0)
            .output(str(out), c='copy')
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )

        return True

    except ffmpeg.Error as e:
        # FFmpeg specific failures
        return False
    except Exception as e:
        # General logic failures
        return False
    finally:
        # Ensure temporary input list is always deleted from disk
        if list_file_path and os.path.exists(list_file_path):
            os.remove(list_file_path)

def convert_video_resolutions(input_file, resolutions, output_dir="output"):
    """
    Sequentially transcodes a video into multiple resolutions.
    This is a simpler, non-concurrent alternative to convert_video_resolutions_concurrent.
    
    Args:
        input_file (str): Path to the source video.
        resolutions (list): List of target heights (e.g., [360, 480]).
        output_dir (str): Target directory for outputs. Defaults to "output".
    """
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        return

    os.makedirs(output_dir, exist_ok=True)

    # Detect best encoder available on the system
    encoder = get_available_video_encoder()
    if not encoder:
        print("No suitable video encoder found.")
        return

    filename = os.path.splitext(os.path.basename(input_file))[0]
    extension = ".mp4"

    # Iterate through resolutions one by one
    for r in resolutions:
        res_str = str(r).replace("p", "")
        bitrate = bitrate_map.get(res_str, "1500k")
        output_path = os.path.join(output_dir, f"{filename}_{res_str}p{extension}")

        # Build basic ffmpeg command
        command = [
            "ffmpeg",
            "-i", input_file,
            "-vf", f"scale=-2:{res_str}",
            "-c:v", encoder,
            "-b:v", bitrate,
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            output_path
        ]

        # Add preset if using libx264 software encoder
        if encoder == "libx264":
            command.insert(command.index("-b:v"), "-preset")
            command.insert(command.index("-b:v") + 1, "medium")

        try:
            # Execute synchronously
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"Conversion failed for {res_str}p: {e.stderr.decode()}")


def composite_image_over_video(
    video_path: str,
    image_path: str,
    start: float | None = None,
    end: float | None = None,
    opacity: float = 1.0,         
    vcodec: str = "libopenh264", 
    use_gpu: bool = False,       
    position: str = "top-left"  
) -> bool:
    """
    Overlays a static image onto a video with advanced placement and timing controls.
    Optimized for high-speed processing with optional GPU support.

    Args:
        video_path (str): Path to the source video.
        image_path (str): Path to the overlay image (e.g., PNG/JPG).
        start (float, optional): Time in seconds when the overlay should appear.
        end (float, optional): Time in seconds when the overlay should disappear.
        opacity (float): Transparency of the overlay (0.0 to 1.0). Defaults to 1.0.
        vcodec (str): Video codec to use for the output. Defaults to "libopenh264".
        use_gpu (bool): If True, attempts to use hardware (VAAPI) acceleration.
        position (str): Positioning preset: 'top-left', 'top-right', 'bottom-left', 
                        'bottom-right', or 'center'.

    Returns:
        bool: True if the operation succeeded, False otherwise.
    """

    try:
        if not video_path or not image_path:
            raise ValueError("video_path and image_path must be provided")

        input_path = Path(video_path)
        output_path = input_path.with_name(f"{input_path.stem}_overlay.mp4")

        # Setup input streams
        video = ffmpeg.input(video_path)
        image = ffmpeg.input(image_path, loop=1) # Loop image to match video duration

        # Apply opacity filter if needed (requires RGBA conversion)
        if opacity < 1.0:
            image = image.filter("format", "rgba").filter("colorchannelmixer", aa=opacity)

        # Handle timing logic for when the overlay is visible
        enable_expr = None
        s = 0 if start is None else start
        if start is not None or end is not None:
            enable_expr = f"between(t,{s},{end})" if end is not None else f"gte(t,{s})"

        # Map position keyword to actual coordinate expressions
        pos_map = {
            "top-left":    ("0", "0"),
            "top-right":   ("main_w-overlay_w", "0"),
            "bottom-left": ("0", "main_h-overlay_h"),
            "bottom-right":("main_w-overlay_w", "main_h-overlay_h"),
            "center":      ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2")
        }
        x_expr, y_expr = pos_map.get(position, ("0", "0"))

        # Configure overlay filter parameters
        overlay_args: dict[str, Any] = {
            "x": x_expr,
            "y": y_expr,
            "enable": enable_expr,
            "eof_action": "repeat",
            "shortest": 1,
        }

        # Combine video and image layers
        video_out = ffmpeg.overlay(
            video.video,
            image,
            **{k: v for k, v in overlay_args.items() if v is not None}
        )

        # Prepare final output encoding settings
        output_args: dict[str, Any] = {
            "pix_fmt": "yuv420p",
            "c:a": "copy", # Fast audio pass-through
        }

        # Apply hardware or software codec selection
        if use_gpu:
            output_args["c:v"] = "h264_vaapi" 
        else:
            output_args["c:v"] = vcodec
            # Handle specific codec-level flags
            if vcodec == "mpeg4":
                output_args["qscale:v"] = "5" # Constant quality for mpeg4

        # Execute final render
        (
            ffmpeg
            .output(
                video_out,
                video.audio, 
                output_path.as_posix(),
                **output_args
            )
            .overwrite_output()
            .run()
        )

        return True

    except ffmpeg.Error:
        return False
    except Exception:
        return False
def get_video_duration(video_path: str) -> float:
    """
    Retrieves the total duration of a video file in seconds using ffprobe.
    
    Args:
        video_path (str): Path to the video file.
        
    Returns:
        float: Duration in seconds, or 0.0 if the duration couldn't be determined.
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    try:
        # Run ffprobe and parse the numeric output
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return float(result.stdout.strip())
    except Exception:
        # Handle cases where ffprobe fails or output is malformed
        return 0.0

def get_video_thumbnail(
    video_path: str, 
    shot_at= None, 
    output_path: str = "", 
    resolution= None, 
    quality: int = 2
) -> str:
    """
    Captures a single frame from a video to use as a thumbnail.
    
    Args:
        video_path (str): The video source file.
        shot_at (float, optional): The time offset (seconds). If None, a random frame is picked.
        output_path (str, optional): Target image path. Defaults to [video_name]_thumb.jpg.
        resolution (str, optional): Scaling constraint. e.g. '320' or '320:240'.
        quality (int, optional): JPEG quality level (1 to 31, lower is better quality). 
                                Default is 2.
    
    Returns:
        str: Absolute path to the generated thumbnail, or empty string on failure.
    """
    
    # Auto-generate output path if not provided
    if not output_path:
        base_name, _ = os.path.splitext(video_path)
        output_path = f"{base_name}_thumb.jpg"

    # Pick a random timestamp if none specified
    if shot_at is None:
        duration = get_video_duration(video_path)
        if duration > 0:
            # Avoid the first/last few seconds if possible
            shot_at = random.uniform(1, max(1, duration - 1))
        else:
            shot_at = 0
    
    # Prepare basic extraction command
    cmd = [
        'ffmpeg',
        '-ss', str(shot_at),  # Seek to the timestamp (fast seek BEFORE input)
        '-i', video_path,
        '-vframes', '1',      # Extract exactly one frame
        '-y',                 # Overwrite output
    ]
    
    # Apply optional scaling filter
    if resolution:
        if ':' not in str(resolution):
            resolution = f"{resolution}:-1" # Maintain aspect ratio
        cmd.extend(['-vf', f'scale={resolution}'])
    
    # Apply quality compression
    safe_quality = max(1, min(31, quality))
    cmd.extend(['-q:v', str(safe_quality)])

    cmd.append(output_path)

    try:
        # Run ffmpeg process
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    except subprocess.CalledProcessError:
        return ""

def crop_video(
    video_path: str,
    x: int = 0,
    y: int = 0,
    width: int = 640,
    height: int = 480,
    output_path: str = ""
):
    """
    Spatially crops a video to a specific rectangular region.
    
    Args:
        video_path (str): Path to the input video.
        x (int): Horizontal starting position (left).
        y (int): Vertical starting position (top).
        width (int): Target width of the cropped area.
        height (int): Target height of the cropped area.
        output_path (str, optional): Path for the resulting file.
        
    Returns:
        str: Path to the cropped video file.
    """

    if not video_path or not os.path.exists(video_path):
        raise ValueError("Invalid video path: file does not exist")

    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid crop dimensions: {width}x{height}")

    # Determine best encoder to use for the render
    encoder = get_available_video_encoder()
    
    if not output_path:
        output_path = f"cropped_{os.path.basename(video_path)}"

    # Initialize the video stream and apply the crop filter
    stream = (
        ffmpeg
        .input(video_path)
        .crop(x=x, y=y, width=width, height=height)
    )

    # Configure output with the selected encoder
    if encoder:
        stream = stream.output(
            output_path,
            vcodec=encoder,
            acodec="aac" # Re-encode audio to ensure compatibility
        )
    else:
        stream = stream.output(output_path)

    # Run the processing pipeline
    stream.overwrite_output().run()

    return output_path

def detect_video_vulnerability(message_tool, video_path, prompt=None):
    """
    Detects vulnerabilities in a video by analyzing it through an AI model.
    
    This function reads a video file and passes it to a message tool (AI model
    interface) for content analysis. The response is parsed from JSON format
    and returned as a structured result.
    
    Parameters
    ----------
    message_tool : callable
        A function that accepts (video_stream, prompt) and returns either:
        - str: Raw text response (e.g., JSON string wrapped in markdown)
        - dict: Parsed API response with structure:
            - OpenAI/OpenRouter format: {'choices': [{'message': {'content': str}}]}
            - DashScope format: {'output': {'choices': [{'message': {'content': str}}]}}
        
        Expected signature:
            def message_tool(video_stream: BinaryIO, prompt: str) -> Union[str, dict]:
                '''
                Process video and prompt through an AI model.
                
                Parameters
                ----------
                video_stream : BinaryIO
                    File-like object opened in binary read mode (rb).
                    Must support .read() method returning bytes.
                prompt : str
                    Text prompt/instruction for the AI model.
                    
                Returns
                -------
                str or dict
                    Model response as string (preferred) or raw API dict.
                '''
                pass
    
    video_path : str or Path
        Path to the video file to analyze. Must exist and be readable.
    
    prompt : str, optional
        Custom prompt for the analysis. If None, uses module-level PROMPT.
    
    Returns
    -------
    dict or str
        Parsed JSON result as dict if successful, or raw response string
        if JSON parsing fails.
    
    Examples
    --------
    Using with Gemini:
    
        def gemini_message(video_stream, prompt):
            contents = [...]  # Build Gemini contents
            response = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=contents
            )
            return response.candidates[0].content.parts[0].text
        
        result = detect_video_vulnerability(
            gemini_message, 
            "video.mp4", 
            "Analyze this video for safety issues"
        )
    
    Using with OpenRouter/Qwen:
    
        def openrouter_message(video_stream, prompt):
            video_bytes = base64.b64encode(video_stream.read()).decode()
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json={...}
            )
            return response.json()['choices'][0]['message']['content']
        
        result = detect_video_vulnerability(
            openrouter_message,
            "video.mp4"
        )
    """
    if not all([message_tool, video_path]):
        return None
    
    if not prompt:
        prompt = VULNERABILITY_PROMPT

    video = Path(video_path)
    if not video.exists():
        print("Video file not found")
        return None

    with open(video, "rb") as video_stream:
        response = message_tool(video_stream, prompt)
    
    if isinstance(response, dict):
        if 'output' in response and 'choices' in response['output']:
            response_text = response['output']['choices'][0]['message']['content']
        elif 'choices' in response:
            response_text = response['choices'][0]['message']['content']
        else:
            print("API Response:", json.dumps(response, indent=2))
            return response
    else:
        response_text = response
    
    if "```json" in response_text:
        json_str = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        json_str = response_text.split("```")[1].split("```")[0].strip()
    else:
        json_str = response_text
    
    try:
        result = json.loads(json_str)
        return result
    except json.JSONDecodeError:
        return response_text
def generate_video_summary(message_tool, video_path, prompt=None):
    """
    Generates a concise summary of a video's content using an AI model.
    
    Args:
        message_tool (callable): The AI model interface function.
        video_path (str): Path to the video file to be summarized.
        prompt (str, optional): Custom instructions for the summary. 
                               Defaults to VIDEO_SUMMARIZATION_PROMPT.
                               
    Returns:
        dict or str: The summarized content as a dictionary (if JSON) or raw text.
    """
    if not all([message_tool, video_path]):
        return None
    
    # Use default prompt if none provided
    if not prompt:
        prompt = VIDEO_SUMMARIZATION_PROMPT

    video = Path(video_path)
    if not video.exists():
        print(f"Error: Summary target {video_path} not found.")
        return None

    # Open video as binary stream for the AI tool
    with open(video, "rb") as video_stream:
        response = message_tool(video_stream, prompt)
    
    # Standardize different API response formats
    if isinstance(response, dict):
        if 'output' in response and 'choices' in response['output']:
            response_text = response['output']['choices'][0]['message']['content']
        elif 'choices' in response:
            response_text = response['choices'][0]['message']['content']
        else:
            return response
    else:
        response_text = response
    
    # Extract JSON block from markdown if present
    if "```json" in response_text:
        json_str = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        json_str = response_text.split("```")[1].split("```")[0].strip()
    else:
        json_str = response_text
    
    try:
        # Attempt to parse into a structured dictionary
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback to returning raw text if not valid JSON
        return response_text
def generate_subtitle(message_tool, video_path, prompt=None):
    """
    Transcribes audio and generates subtitles for a video using an AI vision/audio model.
    
    Args:
        message_tool (callable): Function to interact with the AI model.
        video_path (str): The video to be captioned.
        prompt (str, optional): Prompt to guide subtitle generation.
        
    Returns:
        dict or str: The generated subtitles in structured format (if JSON) or raw text.
    """
    if not all([message_tool, video_path]):
        return None
    
    if not prompt:
        prompt = SUBTITLE_GENERATION_PROMPT

    video = Path(video_path)
    if not video.exists():
        print(f"Error: Subtitle source {video_path} not found.")
        return None

    # Binary read session for model upload/processing
    with open(video, "rb") as video_stream:
        response = message_tool(video_stream, prompt)
    
    # Normalize varied response structures from different AI providers
    if isinstance(response, dict):
        if 'output' in response and 'choices' in response['output']:
            response_text = response['output']['choices'][0]['message']['content']
        elif 'choices' in response:
            response_text = response['choices'][0]['message']['content']
        else:
            return response
    else:
        response_text = response
    
    # Clean up markdown formatting to isolate JSON strings
    if "```json" in response_text:
        json_str = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        json_str = response_text.split("```")[1].split("```")[0].strip()
    else:
        json_str = response_text
    
    try:
        # Load string into Python object
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Return as-is if parsing fails
        return response_text

def video_phash(video_path, hash_size=16, num_frames=5):
    """
    Computes a Perceptual Hash (pHash) for a video to enable similarity detection.
    Unlike standard md5/sha256, pHash detects videos that look visually similar
    even if they have different encodings or resolutions.
    
    Args:
        video_path (str): The video to be hashed.
        hash_size (int): Dimensions for the internal grayscale frame (e.g., 16x16).
        num_frames (int): Number of frames to sample across the video duration.
        
    Returns:
        numpy.ndarray: A concatenated binary hash representing the entire video.
    """
    video_path = str(video_path)

    # Resolve video duration for smart sampling
    try:
        duration = float(subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]).decode().strip())
    except Exception:
        # Return zero-hash if metadata cannot be read
        return np.zeros(hash_size * hash_size * num_frames, dtype=np.uint8)

    if duration <= 0:
        return np.zeros(hash_size * hash_size * num_frames, dtype=np.uint8)

    # Spread sampling points across the video (skipping first/last 10% for stability)
    start = max(duration * 0.1, 0)
    end = max(duration * 0.9, start + 0.1)
    timestamps = np.linspace(start, end, num_frames)

    hashes = []

    for t in timestamps:
        # Use FFmpeg to pipe a specific grayscale frame directly into memory
        cmd = [
            "ffmpeg",
            "-ss", str(t),
            "-i", video_path,
            "-frames:v", "1",
            "-vf", f"scale={hash_size}:{hash_size+1},format=gray",
            "-f", "image2pipe",
            "-vcodec", "rawvideo",
            "-"
        ]

        frame_size = hash_size * (hash_size + 1)
        pipe = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        stdout = pipe.stdout
        if stdout is None:
            pipe.kill()
            continue

        # Read raw pixel values
        raw = stdout.read(frame_size)
        pipe.wait()

        if len(raw) != frame_size:
            continue

        # Convert raw bits to numpy array and reshape
        img = np.frombuffer(raw, dtype=np.uint8).reshape((hash_size + 1, hash_size))
        img = np.ascontiguousarray(img, dtype=np.float32)

        # Apply Discrete Cosine Transform (DCT) for frequency analysis
        dct = cv2.dct(img)

        # Focus on the low-frequency components (most stable features)
        dct_low = dct[:hash_size, 1:hash_size + 1]

        # Calculate binary hash based on whether frequency is above/below mean
        avg = dct_low.mean()
        binary_hash = (dct_low > avg).astype(np.uint8).flatten()

        hashes.append(binary_hash)

    # Final result is the sequence of hashes from all sampled frames
    if not hashes:
        return np.zeros(hash_size * hash_size * num_frames, dtype=np.uint8)

    return np.concatenate(hashes)

def convert_video_format(input_path: str, output_path: str, video_codec= None, audio_codec= None) -> bool:
    """
    Robustly converts a video from one container/codec to another.
    Automatically detects and falls back to optimal encoders based on system capabilities.
    
    Args:
        input_path (str): The source file path.
        output_path (str): The target file path with the desired extension (e.g., .webm, .mkv).
        video_codec (str, optional): Specific video encoder name.
        audio_codec (str, optional): Specific audio encoder name.
        
    Returns:
        bool: True if conversion was successful, False otherwise.
    """
    if not os.path.exists(input_path):
        print(f"Error: Conversion input {input_path} not found.")
        return False
    
    # Normalize empty inputs
    if video_codec == "":
        video_codec = None
    if audio_codec == "":
        audio_codec = None
    
    try:
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
        
        # Query system encoders for intelligent selection
        encoders_list = subprocess.run(
            ["ffmpeg", "-encoders"], 
            capture_output=True, text=True
        ).stdout
        
        def has_encoder(name):
            # Utility to check if an encoder is supported
            return name in encoders_list
        
        ext = os.path.splitext(output_path)[1].lower()
        
        # Intelligent Video Codec Resolution
        if video_codec is None:
            if ext in [".mpg", ".mpeg", ".vob"]:
                video_codec = "mpeg2video"
            elif ext == ".webm":
                video_codec = "libvpx-vp9"
            else:
                # Default to H.264 family
                if has_encoder("libopenh264"):
                    video_codec = "libopenh264"
                elif has_encoder("libx264"):
                    video_codec = "libx264"
                elif has_encoder("mpeg4"):
                    video_codec = "mpeg4"
                else:
                    video_codec = "copy"
        
        # Fallback logic for unsupported video encoders
        if video_codec != "copy" and not has_encoder(video_codec):
            print(f"Warning: Video encoder '{video_codec}' unavailable. Falling back.")
            video_codec = "mpeg4" if has_encoder("mpeg4") else "copy"
        
        # Intelligent Audio Codec Resolution
        if audio_codec is None:
            if ext in [".mpg", ".mpeg", ".vob"]:
                # Classic formats
                audio_codec = "mp2" if has_encoder("mp2") else "copy"
            elif ext == ".avi":
                audio_codec = "libmp3lame" if has_encoder("libmp3lame") else "ac3"
            elif ext == ".webm":
                audio_codec = "libopus" if has_encoder("libopus") else "libvorbis"
            else:
                # Modern formats
                if has_encoder("aac"):
                    audio_codec = "aac"
                elif has_encoder("libmp3lame"):
                    audio_codec = "libmp3lame"
                else:
                    audio_codec = "copy"
        
        # Fallback for unsupported audio encoders
        if audio_codec != "copy" and not has_encoder(audio_codec):
            audio_codec = "copy"
        
        # Build the conversion command
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-map", "0:v:0?",   # Map first video stream if available
            "-map", "0:a:0?",   # Map first audio stream if available
            "-c:v", video_codec,
            "-c:a", audio_codec,
            "-map_metadata", "0" # Preserve metadata (tags, dates, etc.)
        ]
        
        # Apply specific tuning for chosen encoders
        if video_codec in ["libx264", "libopenh264"]:
            cmd.extend(["-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p"])
        elif video_codec == "mpeg2video":
            cmd.extend(["-b:v", "3000k", "-maxrate", "3500k", "-bufsize", "4000k", "-g", "15"])
        elif video_codec == "mpeg4":
            cmd.extend(["-q:v", "3", "-pix_fmt", "yuv420p"])
        elif video_codec == "libvpx-vp9":
            cmd.extend(["-b:v", "0", "-crf", "31", "-deadline", "good"])
        
        # Audio tuning
        if audio_codec in ["mp2", "ac3", "aac"]:
            cmd.extend(["-b:a", "192k"])
        elif audio_codec == "libmp3lame":
            cmd.extend(["-q:a", "2"])
        
        # MP4-family optimization (faststart)
        if ext in [".mp4", ".m4v", ".mov"]:
            cmd.extend(["-movflags", "+faststart"])
        
        # Handling for subtitles based on container support
        if ext in [".mp4", ".m4v", ".mov"]:
            cmd.extend(["-c:s", "mov_text"]) # QuickTime format
        elif ext == ".mkv":
            cmd.extend(["-c:s", "copy"])     # Keep existing subtitles
        else:
            cmd.extend(["-sn"])              # No subtitles for other formats
        
        cmd.append(output_path)
        
        # Execute the process
        subprocess.run(cmd, check=True, capture_output=True)
        return True
        
    except subprocess.CalledProcessError as e:
        # Parse and log specific ffmpeg error messages
        err = e.stderr.decode()
        for line in err.split('\n'):
            if "Error" in line:
                print(f"FFmpeg conversion error: {line.strip()}")
        # Cleanup incomplete output files
        if os.path.exists(output_path):
            os.remove(output_path)
        return False
    except Exception as e:
        print(f"General conversion failure: {e}")
        return False