import ffmpeg
from pathlib import Path


from ..utils.validation import validate_video_file, validate_ffmpeg
from ..cli.interface import validate_and_get_output_path
from ..utils.resolution import RESOLUTION_PROFILES


def extract_audio(video_path, output_path, audio_format='mp3', start=None, end=None):
    """
    Internal helper to execute the actual audio extraction using ffmpeg.
    
    Args:
        video_path (str): The absolute or relative path to the source video file.
        output_path (str): The path where the extracted audio file will be saved.
        audio_format (str): Desired audio format (currently supports 'mp3' and 'wav').
                           Defaults to 'mp3'.
        start (float/str, optional): Start time for extraction (e.g., 10.5 or "00:00:10").
        end (float/str, optional): End time for extraction (e.g., 20.0 or "00:00:20").

    Returns:
        bool: True if the ffmpeg command executed successfully, False otherwise.
    """
    try:
        # Determine the appropriate codec based on requested format
        # Use 'mp3' for MP3 files and 'pcm_s16le' for WAV/Lossless
        audio_codec = 'mp3' if audio_format.lower() == 'mp3' else 'pcm_s16le'

        # Build input parameters for cutting the video if start/end times are provided
        input_kwargs = {}
        if start is not None:
            input_kwargs['ss'] = start
        if end is not None:
            input_kwargs['to'] = end

        # Initialize the ffmpeg input stream
        stream = ffmpeg.input(str(video_path), **input_kwargs)
        
        # Configure output stream with specified codec and quiet logging
        stream = ffmpeg.output(stream, str(output_path), acodec=audio_codec, loglevel='quiet')

        # Execute the conversion process
        ffmpeg.run(stream, overwrite_output=True, quiet=True)

        return True

    except ImportError:
        # Handle cases where ffmpeg-python is not installed correctly
        return False
    except ffmpeg.Error as e:
        # Catch ffmpeg-specific errors during processing
        return False
    except Exception as e:
        # Catch any other unexpected errors
        return False

def get_default_output_path(video_path, audio_format='mp3'):
    """
    Generates a default output path for the audio file based on the video filename.
    
    Args:
        video_path (str/Path): The path to the source video file.
        audio_format (str): The file extension for the output (e.g., 'mp3').

    Returns:
        Path: A Path object pointing to the output file in the same directory as the video.
    """
    video_path = Path(video_path)
    # Append the new extension to the original filename stem
    output_filename = video_path.stem + '.' + audio_format
    return video_path.parent / output_filename


def get_audio_from_video(video_path, output_path=None, audio_format='mp3', start=None, end=None):
    """
    High-level library entry point to extract audio from a video file with validation.
    
    Args:
        video_path (str): Path to the input video file.
        output_path (str, optional): Custom path for the output file. If None, uses default.
        audio_format (str): Target format, either 'mp3' or 'wav'. Defaults to 'mp3'.
        start (float/str, optional): Start timestamp for the audio segment.
        end (float/str, optional): End timestamp for the audio segment.
        
    Returns:
        bool: True if extraction was successful and validated, False otherwise.
    """
    # Verify that the input file is a valid video format
    if not validate_video_file(video_path):
        return False
    
    # Ensure ffmpeg tool is installed and accessible in the system PATH
    if not validate_ffmpeg():
        return False
    
    # Resolve the final output path, creating directories if needed
    output_path = validate_and_get_output_path(video_path, output_path, audio_format)
    
    # Proceed with the actual extraction process
    return extract_audio(video_path, str(output_path), audio_format, start, end)

def chunk_video_adaptive(video_path, output_dir=None, resolutions=None, segment_duration=10):
    """
    Segments a video into HLS chunks at multiple resolutions for adaptive bitrate streaming.
    Supports both local files and network URLs.
    
    Args:
        video_path (str): Source path or URL of the video to be processed.
        output_dir (str, optional): Target directory for output files. 
                                   Defaults to folder named after the video.
        resolutions (list, optional): List of target resolutions (e.g., ['360p', '720p']). 
                                     Defaults to ['360p', '720p', '1080p'].
        segment_duration (int): Target length of each HLS segment in seconds. Defaults to 10.
        
    Returns:
        dict or False: A dictionary metadata about generated manifests and segments on success,
                      or False if processing failed.
    """
    try:
        # Check for ffmpeg availability
        if not validate_ffmpeg():
            return False
        
        # Resolve output directory naming
        video_path_str = str(video_path)
        if output_dir is None:
            # Clean up URL parameters if present to get a clean base filename
            base_name = Path(video_path_str.split('?')[0]).stem or 'video'
            output_dir = Path(f"{base_name}_chunks")
        else:
            output_dir = Path(output_dir)
        
        # Create output root directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize default resolutions if none provided
        if resolutions is None:
            resolutions = ['360p', '720p', '1080p']
        
        # Ensure all requested resolutions are supported by our profiles
        for res in resolutions:
            if res not in RESOLUTION_PROFILES:
                return False
        
        variants = {}
        
        # Iterate through each resolution to generate specific HLS variants
        for res_key in resolutions:
            profile = RESOLUTION_PROFILES[res_key]
            
            # Organize each resolution into its own subdirectory
            res_dir = output_dir / res_key
            res_dir.mkdir(exist_ok=True)
            
            manifest_path = res_dir / "playlist.m3u8"
            segment_pattern = str(res_dir / "segment_%03d.ts")
            
            # Setup the processing stream for this specific resolution
            stream = ffmpeg.input(video_path_str)
            
            # Apply scaling filters to match target resolution
            stream = ffmpeg.filter(stream, 'scale', profile['width'], profile['height'])
            
            # Configure HLS output parameters
            stream = ffmpeg.output(
                stream,
                str(manifest_path),
                format='hls',
                start_number=0,
                hls_time=segment_duration,
                hls_playlist_type='vod',
                hls_segment_filename=segment_pattern,
                hls_base_url=f"{res_key}/",  # Relative path for sub-playlists
                vcodec='h264',               # Use industry standard H.264
                acodec='aac',                # High quality AAC audio
                video_bitrate=profile['video_bitrate'],
                audio_bitrate=profile['audio_bitrate'],
                preset='fast',               # Balance between speed and efficiency
                pix_fmt='yuv420p',
                loglevel='quiet'
            )
            
            # Run the ffmpeg process
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            # Verify and count segments for this variant
            segments = list(res_dir.glob("segment_*.ts"))
            
            variants[res_key] = {
                'manifest': manifest_path,
                'segments_dir': res_dir,
                'segment_count': len(segments)
            }
        
        # Create the top-level master manifest linking all variants together
        master_manifest = output_dir / "master.m3u8"
        _write_master_playlist(master_manifest, resolutions, variants)
        
        return {
            'master_manifest': master_manifest,
            'output_dir': output_dir,
            'variants': variants
        }
        
    except ImportError:
        return False
    except ffmpeg.Error:
        return False
    except Exception:
        return False


def _write_master_playlist(master_path, resolutions, variants):
    """
    Generates a master M3U8 HLS playlist that references all resolution variants.
    
    Args:
        master_path (Path): Path to the master manifest file.
        resolutions (list): List of resolution identifiers.
        variants (dict): Dictionary containing details about generated variants.
    """
    lines = ["#EXTM3U"] # M3U Header
    
    for res_key in resolutions:
        profile = RESOLUTION_PROFILES[res_key]
        # Calculate relative path to the specific variant playlist
        variant_path = f"{res_key}/playlist.m3u8"
        
        # Append metadata for this stream variant
        lines.append(
            f"#EXT-X-STREAM-INF:"
            f"BANDWIDTH={profile['bandwidth']},"
            f"RESOLUTION={profile['width']}x{profile['height']},"
            f"NAME=\"{res_key}\""
        )
        # Add the path to the variant itself
        lines.append(variant_path)
    
    # Write the complete manifest to disk
    master_path.write_text('\n'.join(lines) + '\n')


def chunk_video_single(video_path, output_dir=None, resolution='720p', segment_duration=10):
    """
    A simplified version of adaptive chunking that processes only a single resolution.
    
    Args:
        video_path (str): Source path or URL of the video.
        output_dir (str, optional): Target directory for output.
        resolution (str): The desired resolution key (e.g., '1080p'). Defaults to '720p'.
        segment_duration (int): Duration for segments in seconds. Defaults to 10.
        
    Returns:
        dict or False: Metadata for the single variant on success, False on failure.
    """
    # Reuse the adaptive logic but restrict it to one resolution
    result = chunk_video_adaptive(
        video_path=video_path,
        output_dir=output_dir,
        resolutions=[resolution],
        segment_duration=segment_duration
    )
    
    if result:
        # Extract and return only the relevant part of the adaptive result
        return {
            'manifest': result['variants'][resolution]['manifest'],
            'segments_dir': result['variants'][resolution]['segments_dir'],
            'output_dir': result['output_dir']
        }
    return False