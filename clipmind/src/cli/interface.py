import argparse
import sys
from pathlib import Path


def parse_arguments():
    """
    Sets up the command-line interface and parses user input.
    Provides options for input file, output file, and desired audio format.
    
    Returns:
        argparse.Namespace: An object containing the validated command-line arguments.
    """
    parser = argparse.ArgumentParser(
        prog="clipmind",
        description="clipmind - Extract audio from video files",
        # Use RawDescriptionHelpFormatter to preserve example formatting
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  clipmind -i video.mp4                    # Extract to video.mp3
  clipmind -i video.mp4 -o audio.wav       # Extract to audio.wav
  clipmind -i video.mkv -f mp3             # Extract to video.mp3
        """
    )

    # Core argument: Source video
    parser.add_argument('-i', '--input', required=True, help='Input video file path')
    # Optional argument: Destination audio path
    parser.add_argument('-o', '--output', help='Output audio file path (optional)')
    # Optional argument: Target audio codec/extension
    parser.add_argument('-f', '--format', choices=['mp3', 'wav'], default='mp3',
                       help='Output audio format (default: mp3)')

    return parser.parse_args()


def show_usage_instructions():
    """
    Prints a simple banner and basic usage guide to the terminal.
    Used when a user runs the tool incorrectly or requests help.
    """
    print("clipmind - Audio Extraction Tool")
    print("==============================")
    print("This tool extracts audio from video files using FFmpeg.")
    print()
    print("Usage: clipmind -i <input_video> [-o <output_audio>] [-f <format>]")
    print()
    print("Options:")
    # Breakdown of flags for quick reference
    print("  -i, --input   Input video file path (required)")
    print("  -o, --output  Output audio file path (optional)")
    print("  -f, --format  Output format: mp3 or wav (default: mp3)")
    print()
    print("Example: clipmind -i video.mp4 -o audio.mp3")


def validate_and_get_output_path(input_path, output_path=None, audio_format='mp3'):
    """
    Resolves the target output path for the audio file.
    If no path is provided, it generates a default based on the input filename.
    
    Args:
        input_path (str/Path): The source video path.
        output_path (str/Path, optional): Explicit destination path.
        audio_format (str): Extension for default path generation.
        
    Returns:
        Path: The resolved absolute or relative path to the output file.
    """
    # Use user-provided output if it exists
    if output_path:
        output_path = Path(output_path)
    else:
        # Default behavior: replace extension but keep everything else the same
        input_path = Path(input_path)
        output_filename = input_path.stem + '.' + audio_format
        output_path = input_path.parent / output_filename

    # Ensure the parent directory of our target actually exists
    output_dir = output_path.parent
    if not output_dir.exists():
        print(f"Error: Output directory does not exist: {output_dir}")
        sys.exit(1)

    return output_path


def main():
    """
    The main CLI entry point. Orchestrates argument parsing and high-level logic.
    """
    # Import here to avoid circular dependencies if CLI is executed directly
    from ..core.audio_extractor import get_audio_from_video
    
    # Process inputs from sys.argv
    args = parse_arguments()
    
    # Delegate core logic to the library functions
    success = get_audio_from_video(
        args.input, 
        args.output, 
        args.format
    )
    
    # Exit with appropriate status codes based on success/failure
    if success:
        print(f"Successfully extracted audio to: {args.output if args.output else 'default path'}")
        sys.exit(0)
    else:
        print("Error: Audio extraction failed.")
        sys.exit(1)
