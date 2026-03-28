import ffmpeg
import tempfile
import os
from typing import Optional, Any
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from ..utils.ai_utils import PROMPT
import json

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
    res = int(res)
    if res <= 360:
        return "veryfast"
    if res <= 480:
        return "fast"
    return "medium"
def process_single_resolution(input_file, res, output_dir, encoder="libx264"):
    res_int = int(str(res).replace("p", ""))
    bitrate = bitrate_map.get(res_int, "1500k")
    preset = get_preset_for_resolution(res_int)
    
    filename = os.path.splitext(os.path.basename(input_file))[0]
    output_path = os.path.join(output_dir, f"{filename}_{res_int}p.mp4")
    
    command = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-vf", f"scale=-2:{res_int}",
        "-c:v", encoder,
        "-preset", preset,
        "-b:v", bitrate,
        "-movflags", "+faststart",
        "-c:a", "copy",
        output_path
    ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(e.stderr.decode())
    
    return output_path

def convert_video_resolutions_concurrent(input_file, resolutions, output_dir="output", max_workers=None):
    if not os.path.exists(input_file):
        return

    os.makedirs(output_dir, exist_ok=True)

    encoder = "libx264"

    futures = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for res in resolutions:
            futures.append(executor.submit(process_single_resolution, input_file, res, output_dir, encoder))
        
        for future in as_completed(futures):
            future.result() 


def get_available_video_encoder():
    """
    Returns the best available H.264 encoder on the system.
    Priority:
    1. libx264 (best quality)
    2. libopenh264 (widely available)
    3. h264_vaapi (hardware)
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        encoders = result.stdout

        if "libx264" in encoders:
            return "libx264"
        if "libopenh264" in encoders:
            return "libopenh264"
        if "h264_vaapi" in encoders:
            return "h264_vaapi"

    except Exception:
        pass

    return None


def merge_videos(video1_path: Optional[str] = None, video2_path: Optional[str] = None, output_path: Optional[str] = None) -> bool:
    """
    Merge two video files using FFmpeg via stream copy (fast method).
    """
    list_file_path = None
    
    try:
        if video1_path is None or video2_path is None or output_path is None:
            raise ValueError("All paths must be provided")

        v1 = Path(video1_path)
        v2 = Path(video2_path)
        out = Path(output_path)

        if not v1.exists():
            raise FileNotFoundError(f"Video 1 not found: {v1}")
        if not v2.exists():
            raise FileNotFoundError(f"Video 2 not found: {v2}")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(f"file '{v1.resolve()}'\n")
            f.write(f"file '{v2.resolve()}'\n")
            list_file_path = f.name

        (
            ffmpeg
            .input(list_file_path, format='concat', safe=0)
            .output(str(out), c='copy')
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )

        return True

    except ffmpeg.Error as e:
        stderr = e.stderr.decode('utf8') if e.stderr else 'Unknown error'
        return False
    except Exception as e:
        return False
    finally:
        if list_file_path and os.path.exists(list_file_path):
            os.remove(list_file_path)

def convert_video_resolutions(input_file, resolutions, output_dir="output"):
    if not os.path.exists(input_file):
        return

    os.makedirs(output_dir, exist_ok=True)

    encoder = get_available_video_encoder()
    if not encoder:
        return


    filename = os.path.splitext(os.path.basename(input_file))[0]
    extension = ".mp4"

    bitrate_map = {
        "240": "400k",
        "360": "600k",
        "480": "1000k",
        "720": "2500k",
        "1080": "5000k",
        "1440": "10000k",
        "2160": "20000k"
    }


    for r in resolutions:
        res_str = str(r).replace("p", "")
        bitrate = bitrate_map.get(res_str, "1500k")
        output_path = os.path.join(output_dir, f"{filename}_{res_str}p{extension}")

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

        if encoder == "libx264":
            command.insert(command.index("-b:v"), "-preset")
            command.insert(command.index("-b:v") + 1, "medium")

        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        except subprocess.CalledProcessError as e:
            pass


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
    High-performance image overlay (max-speed version)

    Features:
    ✔ Configurable overlay position
    ✔ Audio preserved (copy)
    ✔ Minimal CPU usage
    ✔ Optional GPU encoding
    """

    try:
        if not video_path or not image_path:
            raise ValueError("video_path and image_path must be provided")

        input_path = Path(video_path)
        output_path = input_path.with_name(f"{input_path.stem}_overlay.mp4")

        video = ffmpeg.input(video_path)
        image = ffmpeg.input(image_path, loop=1)

        if opacity < 1.0:
            image = image.filter("format", "rgba").filter("colorchannelmixer", aa=opacity)

        enable_expr = None
        s = 0 if start is None else start
        if start is not None or end is not None:
            enable_expr = f"between(t,{s},{end})" if end is not None else f"gte(t,{s})"

        pos_map = {
            "top-left":    ("0", "0"),
            "top-right":   ("main_w-overlay_w", "0"),
            "bottom-left": ("0", "main_h-overlay_h"),
            "bottom-right":("main_w-overlay_w", "main_h-overlay_h"),
            "center":      ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2")
        }
        x_expr, y_expr = pos_map.get(position, ("0", "0"))

        overlay_args: dict[str, Any] = {
            "x": x_expr,
            "y": y_expr,
            "enable": enable_expr,
            "eof_action": "repeat",
            "shortest": 1,
        }

        video_out = ffmpeg.overlay(
            video.video,
            image,
            **{k: v for k, v in overlay_args.items() if v is not None}
        )

        # Encoder settings
        output_args: dict[str, Any] = {
            "pix_fmt": "yuv420p",
            "c:a": "copy", 
        }

        if use_gpu:
            output_args["c:v"] = "h264_vaapi" 
        else:
            output_args["c:v"] = vcodec
            if vcodec == "libopenh264":
                pass
            elif vcodec == "mpeg4":
                output_args["qscale:v"] = "5"

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

    except ffmpeg.Error as e:
        return False
    except Exception as e:
        return False
def get_video_duration(video_path: str) -> float:
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return float(result.stdout.strip())
    except Exception as e:
        return 0.0

def get_video_thumbnail(
    video_path: str, 
    shot_at= None, 
    output_path: str = "", 
    resolution= None, 
    quality: int = 2
) -> str:
    """
    Extracts a thumbnail from a video.
    
    Args:
        video_path (str): Path to the input video file.
        shot_at (float, optional): Time in seconds to capture the frame. 
        output_path (str, optional): Path to save the image.
        resolution (str, optional): Desired resolution. Can be '320:240' or just '320' (keeps aspect ratio).
        quality (int, optional): JPEG compression quality (1-31). Note: PNG ignores this.
    """
    
    if not output_path:
        base_name, _ = os.path.splitext(video_path)
        output_path = f"{base_name}_thumb.jpg"

    if shot_at is None:
        duration = get_video_duration(video_path)
        if duration > 0:
            shot_at = random.uniform(1, duration)
        else:
            shot_at = 0
    
    cmd = [
        'ffmpeg',
        '-ss', str(shot_at),
        '-i', video_path,
        '-vframes', '1',
        '-y',
    ]
    if resolution:
        if ':' not in str(resolution):
            resolution = f"{resolution}:-1"
        cmd.extend(['-vf', f'scale={resolution}'])
    safe_quality = max(1, min(31, quality))
    cmd.extend(['-q:v', str(safe_quality)])

    cmd.append(output_path)

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    except subprocess.CalledProcessError as e:
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
    Crop the full video spatially.
    """

    if not video_path or not os.path.exists(video_path):
        raise ValueError("Invalid video path")

    if width <= 0 or height <= 0:
        raise ValueError("Invalid crop dimensions")

    encoder = get_available_video_encoder()
    if not output_path:
        output_path = f"cropped_{os.path.basename(video_path)}"

    stream = (
        ffmpeg
        .input(video_path)
        .crop(x=x, y=y, width=width, height=height)
    )

    if encoder:
        stream = stream.output(
            output_path,
            vcodec=encoder,
            acodec="aac"
        )
    else:
        stream = stream.output(output_path)

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
        prompt = PROMPT

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