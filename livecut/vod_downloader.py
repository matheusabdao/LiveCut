import os
import re
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from .ffmpeg_utils import get_ffmpeg_exe


_CHROME_131_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_VALID_PLATFORMS = ("kick", "twitch", "youtube", "facebook", "rumble", "unknown", "local")


class VodDownloader:
    """Downloads and normalizes VODs from multiple streaming platforms.

    Supports Kick via native HLS extraction and FFmpeg remux, with a
    yt-dlp-based fallback for Twitch, YouTube, Facebook, Rumble and
    other generic URLs. Local video files are accepted transparently.
    """

    def __init__(
        self,
        ffmpeg_exe: Optional[str] = None,
        output_dir: str = "temp",
        quality: str = "best",
        keep_downloaded: bool = False,
    ):
        """Initialize the VOD downloader.

        Args:
            ffmpeg_exe: Path to the ffmpeg executable. If ``None``, the
                executable is resolved automatically via
                :func:`get_ffmpeg_exe`.
            output_dir: Directory where downloaded media and temporary
                artefacts will be written. Created if missing.
            quality: Output quality preset. One of ``"best"``, ``"720p"``,
                ``"480p"``, ``"worst"``. ``"best"`` performs a lossless
                stream copy; other presets re-encode with a quality target.
            keep_downloaded: When ``True``, the raw downloaded file is kept
                even when further processing copies it elsewhere. The
                default behaviour cleans up intermediate files.
        """
        self.ffmpeg_exe = ffmpeg_exe if ffmpeg_exe is not None else get_ffmpeg_exe()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quality = quality.lower()
        self.keep_downloaded = keep_downloaded

    @staticmethod
    def is_url(input_str: str) -> bool:
        """Check whether a string represents an absolute HTTP(S) URL.

        Args:
            input_str: Arbitrary string to test.

        Returns:
            ``True`` if the value starts with ``http://`` or ``https://``
            (case-insensitive), ``False`` otherwise.
        """
        if not isinstance(input_str, str):
            return False
        lowered = input_str.strip().lower()
        return lowered.startswith("http://") or lowered.startswith("https://")

    def detect_platform(self, url: str) -> str:
        """Detect the streaming platform from a URL's hostname.

        Args:
            url: Fully qualified HTTP(S) URL.

        Returns:
            One of ``"kick"``, ``"twitch"``, ``"youtube"``, ``"facebook"``,
            ``"rumble"`` or ``"unknown"``.
        """
        try:
            parsed = urlparse(url)
        except Exception:
            return "unknown"

        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return "unknown"

        if hostname == "kick.com" or hostname.endswith(".kick.com"):
            return "kick"
        if hostname == "twitch.tv" or hostname.endswith(".twitch.tv"):
            return "twitch"
        if (
            hostname == "youtube.com"
            or hostname.endswith(".youtube.com")
            or hostname == "youtu.be"
        ):
            return "youtube"
        if "facebook" in hostname:
            return "facebook"
        if hostname == "rumble.com" or hostname.endswith(".rumble.com"):
            return "rumble"

        return "unknown"

    def _kick_extract(self, url: str) -> Dict[str, Any]:
        """Extract HLS stream URL and metadata from a Kick VOD page.

        Performs a browser-impersonating GET request using ``curl_cffi``
        and scans the returned HTML for an ``.m3u8`` playlist and
        OpenGraph meta tags.

        Args:
            url: Kick VOD or clip URL.

        Returns:
            Dictionary with keys ``m3u8_url``, ``title``, ``description``
            and ``thumbnail``.

        Raises:
            ImportError: If ``curl_cffi`` is not installed.
            RuntimeError: If the page cannot be fetched, or if no m3u8
                playlist can be located in the response body.
        """
        try:
            import curl_cffi.requests
        except ImportError as exc:
            raise ImportError(
                "curl_cffi is required for Kick VOD extraction. "
                "Install it with: pip install curl-cffi"
            ) from exc

        headers = {
            "User-Agent": _CHROME_131_UA,
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
        }

        try:
            response = curl_cffi.requests.get(
                url,
                headers=headers,
                impersonate="chrome131",
                timeout=30,
            )
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch Kick page '{url}': {exc}") from exc

        html = response.text

        m3u8_pattern = re.compile(
            r"https?://[^\s\"'<>]+\.m3u8(?:\?[^\s\"'<>]*)?",
            re.IGNORECASE,
        )
        m3u8_match = m3u8_pattern.search(html)
        if not m3u8_match:
            raise RuntimeError(
                f"No m3u8 playlist found in Kick page '{url}'. The URL may "
                "be invalid, geo-blocked, or the site layout has changed."
            )
        m3u8_url = m3u8_match.group(0)

        def _og_content(property_name: str) -> str:
            pattern = re.compile(
                rf'<meta\s+[^>]*property=["\']og:{re.escape(property_name)}["\']'
                rf'[^>]*content=["\']([^"\']*)["\']',
                re.IGNORECASE | re.DOTALL,
            )
            alt_pattern = re.compile(
                rf'<meta\s+[^>]*content=["\']([^"\']*)["\'][^>]*'
                rf'property=["\']og:{re.escape(property_name)}["\']',
                re.IGNORECASE | re.DOTALL,
            )
            match = pattern.search(html) or alt_pattern.search(html)
            return match.group(1).strip() if match else ""

        title = _og_content("title")
        description = _og_content("description")
        thumbnail = _og_content("image")

        if not title:
            title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else Path(url).stem

        return {
            "m3u8_url": m3u8_url,
            "title": title,
            "description": description,
            "thumbnail": thumbnail,
        }

    def _kick_download(
        self,
        m3u8_url: str,
        output_path: str,
        quality: Optional[str] = None,
    ) -> str:
        """Download a Kick HLS stream via FFmpeg with quality-aware encoding.

        Args:
            m3u8_url: Direct URL to the HLS master playlist.
            output_path: Filesystem path where the resulting MP4 file
                will be written. Parent directories are created if needed.
            quality: Optional override for the instance quality. When
                ``None``, the instance-level ``quality`` is used.

        Returns:
            Resolved absolute path to the downloaded file.

        Raises:
            RuntimeError: If FFmpeg terminates with a non-zero exit code.
        """
        selected_quality = (quality if quality is not None else self.quality).lower()
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        command = [
            self.ffmpeg_exe,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
            "-i", m3u8_url,
        ]

        if selected_quality == "best":
            command.extend([
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
            ])
        else:
            if selected_quality == "720p":
                target_height = 720
            elif selected_quality == "480p":
                target_height = 480
            elif selected_quality == "worst":
                target_height = 360
            else:
                target_height = 720

            vf_filter = (
                f"scale=-2:{target_height}:flags=lanczos,"
                "format=yuv420p"
            )
            command.extend([
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "18",
                "-profile:v", "high",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "256k",
                "-ar", "48000",
            ])

        command.extend([
            "-movflags", "+faststart",
            str(output),
        ])

        try:
            subprocess.run(command, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"FFmpeg failed to download Kick stream: {exc.stderr.strip()}"
            ) from exc

        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError(
                f"FFmpeg finished but produced no output at '{output}'."
            )

        return str(output.resolve())

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Return a filename-safe version of an arbitrary string."""
        if not name:
            return "untitled"
        cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip(" .")
        return cleaned[:120] if cleaned else "untitled"

    def _yt_dlp_download(self, url: str, platform: str) -> Dict[str, Any]:
        """Download a VOD using yt-dlp as a generic fallback backend.

        Args:
            url: Platform URL supported by yt-dlp.
            platform: Pre-detected platform label (for metadata only).

        Returns:
            Dictionary with ``local_path``, ``title``, ``platform`` and
            ``metadata`` keys.

        Raises:
            ImportError: If ``yt-dlp`` is not installed.
            RuntimeError: If yt-dlp reports a download error.
        """
        try:
            import yt_dlp
        except ImportError as exc:
            raise ImportError(
                "yt-dlp is required for Twitch/YouTube/Facebook/Rumble "
                "downloads. Install it with: pip install yt-dlp"
            ) from exc

        out_template = str(self.output_dir / "%(id)s.%(ext)s")

        quality_map = {
            "best": "bv*+ba/b",
            "720p": "bv*[height<=720]+ba/b[height<=720]",
            "480p": "bv*[height<=480]+ba/b[height<=480]",
            "worst": "wv*+wa/w",
        }
        format_spec = quality_map.get(self.quality, quality_map["best"])

        ydl_opts = {
            "outtmpl": out_template,
            "format": format_spec,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                info = ydl.sanitize_info(info)
                local_path = ydl.prepare_filename(info)
                local_path = os.path.splitext(local_path)[0] + ".mp4"
                if not Path(local_path).exists():
                    local_path = ydl.prepare_filename(info)
        except yt_dlp.utils.DownloadError as exc:
            raise RuntimeError(f"yt-dlp download failed: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(
                f"Unexpected yt-dlp error for '{url}': {exc}"
            ) from exc

        resolved = Path(local_path).resolve()
        if not resolved.exists():
            raise RuntimeError(
                f"yt-dlp reported success but file is missing: {resolved}"
            )

        metadata = {
            "uploader": info.get("uploader") or info.get("channel") or "",
            "upload_date": info.get("upload_date") or "",
            "duration": info.get("duration") or 0,
            "view_count": info.get("view_count") or 0,
            "thumbnail": info.get("thumbnail") or "",
            "description": info.get("description") or "",
            "webpage_url": info.get("webpage_url") or url,
        }

        return {
            "local_path": str(resolved),
            "title": info.get("title") or resolved.stem,
            "platform": platform,
            "metadata": metadata,
        }

    def download(self, url_or_path: str) -> Dict[str, Any]:
        """Download (or ingest) a VOD from a URL or a local file path.

        The behaviour depends on the input:

        * **Local file** – returns immediately with metadata pointing at
          the absolute path of the file (``platform`` is ``"local"``).
        * **Kick URL** – extracts the HLS playlist from the page and
          downloads it via FFmpeg with the configured quality preset.
        * **Any other URL** – delegates to yt-dlp (Twitch, YouTube,
          Facebook, Rumble and generic sites).

        Args:
            url_or_path: Filesystem path or HTTP(S) URL to a VOD.

        Returns:
            Dictionary containing at least the keys:

            * ``local_path`` (``str``) – absolute path to the local media.
            * ``title`` (``str``) – human-readable title for the media.
            * ``platform`` (``str``) – one of the :data:`_VALID_PLATFORMS`
              values.
            * ``metadata`` (``dict``) – additional platform-specific
              fields such as ``description``, ``thumbnail``, etc.

        Raises:
            FileNotFoundError: If a local-path input does not exist on disk.
            ValueError: If the input is neither a valid URL nor an
                existing file path.
            RuntimeError: If the download step fails for any reason.
        """
        input_value = (url_or_path or "").strip()

        if not input_value:
            raise ValueError("Input URL or path cannot be empty.")

        if not self.is_url(input_value):
            local = Path(input_value)
            if not local.exists():
                raise FileNotFoundError(f"Input file not found: {local}")
            return {
                "local_path": str(local.resolve()),
                "title": local.stem,
                "platform": "local",
                "metadata": {},
            }

        platform = self.detect_platform(input_value)

        if platform == "kick":
            extracted = self._kick_extract(input_value)
            safe_title = self._sanitize_filename(extracted["title"])
            target_path = self.output_dir / f"{safe_title}.mp4"
            final_path = self._kick_download(
                extracted["m3u8_url"], str(target_path)
            )
            return {
                "local_path": final_path,
                "title": extracted["title"],
                "platform": "kick",
                "metadata": {
                    "description": extracted["description"],
                    "thumbnail": extracted["thumbnail"],
                    "m3u8_url": extracted["m3u8_url"],
                },
            }

        return self._yt_dlp_download(input_value, platform)
