import subprocess
from pathlib import Path
from typing import Optional

from .ffmpeg_utils import get_ffmpeg_exe


class AudioExtractor:
    """Extracts mono PCM audio from video files using FFmpeg.

    Produces a 16-bit signed integer WAV file at the configured sample rate
    with the configured number of channels, suitable for downstream audio
    processing pipelines such as speech recognition.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        ffmpeg_exe: Optional[str] = None,
    ):
        """Initialize the audio extractor.

        Args:
            sample_rate: Target audio sample rate in Hertz. Defaults to 16000.
            channels: Target number of audio channels. Defaults to 1 (mono).
            ffmpeg_exe: Path to the ffmpeg executable. If None, the executable
                is resolved automatically via :func:`get_ffmpeg_exe`.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.ffmpeg_exe = ffmpeg_exe if ffmpeg_exe is not None else get_ffmpeg_exe()

    def extract_audio(self, video_path: str, output_audio_path: str) -> str:
        """Extract audio from a video file and save it as a WAV file.

        The output is encoded as 16-bit signed integer PCM with the sample
        rate and channel count configured on this extractor instance.

        Args:
            video_path: Filesystem path to the source video file.
            output_audio_path: Destination path for the extracted WAV audio.
                Any missing parent directories will be created automatically.

        Returns:
            The resolved absolute path to the written audio file.

        Raises:
            FileNotFoundError: If ``video_path`` does not exist.
            RuntimeError: If the FFmpeg subprocess exits with a non-zero status.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        output_audio_path = Path(output_audio_path)
        output_audio_path.parent.mkdir(parents=True, exist_ok=True)

        command = [
            self.ffmpeg_exe,
            "-y",
            "-i", str(video_path),
            "-vn",
            "-ac", str(self.channels),
            "-ar", str(self.sample_rate),
            "-sample_fmt", "s16",
            "-acodec", "pcm_s16le",
            str(output_audio_path),
        ]

        try:
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
            )
            return str(output_audio_path.resolve())
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to extract audio: {e.stderr}") from e
