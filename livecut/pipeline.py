"""
Core pipeline orchestrator for LiveCut.

Wires together the 6 stages:
    1. Download / ingest   (VodDownloader)
    2. Audio extraction    (AudioExtractor)
    3. Whisper transcription (WhisperTranscriber)
    4. RMS peak detection  (VolumeAnalyzer)
    5. Clip ranking        (HighlightClipSelector)
    6. FFmpeg cutting      (VideoCutter)

Callable from both the CLI (run_cli.py) and the Tkinter GUI (run_gui.py).
Emits progress via an optional ``on_progress`` callback so the GUI can update
a log widget in real time.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


ProgressFn = Callable[[str, int, int], None]


def _noop_progress(msg: str, step: int = 0, total: int = 0) -> None:
    print(msg, flush=True)


def _default_json(o: Any) -> Any:
    try:
        import numpy as np  # type: ignore

        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.ndarray,)):
            return o.tolist()
    except Exception:
        pass
    return str(o)


@dataclass
class PipelineResult:
    ok: bool
    error_message: Optional[str] = None
    downloaded_path: Optional[Path] = None
    output_dir: Optional[Path] = None
    clips: List[Dict[str, Any]] = field(default_factory=list)
    report_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    platform: str = "local"
    title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "error_message": self.error_message,
            "downloaded_path": str(self.downloaded_path) if self.downloaded_path else None,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "clips": self.clips,
            "report_path": str(self.report_path) if self.report_path else None,
            "metadata_path": str(self.metadata_path) if self.metadata_path else None,
            "platform": self.platform,
            "title": self.title,
        }


def _sanitize_name(s: str, max_len: int = 80) -> str:
    s = re.sub(r"[^\w\s\-._]", "", s).strip()
    s = re.sub(r"\s+", "_", s)
    return s[:max_len] or "vod"


def run_pipeline(
    input_value: str,
    *,
    config_path: Optional[str] = None,
    output_dir_override: Optional[str] = None,
    quality: str = "best",
    keep_downloaded: bool = False,
    only_download: bool = False,
    skip_cut: bool = False,
    skip_transcription: bool = False,
    only_transcribe: bool = False,
    on_progress: Optional[ProgressFn] = None,
) -> PipelineResult:
    """Run the full LiveCut pipeline.

    Parameters
    ----------
    input_value:
        Either a local video path OR a VOD URL (Kick, Twitch, YouTube, ...).
    config_path:
        Path to config.json. Defaults to ``config/config.json`` relative to CWD.
    output_dir_override:
        If provided, overrides ``paths.output_dir`` from the config.
    quality:
        Download quality for VOD URLs. One of ``best``, ``720p``, ``480p``, ``worst``.
    keep_downloaded:
        If True, do not delete the downloaded VOD from ``temp_dir`` after processing.
    only_download:
        If True, stop after downloading a URL.
    skip_cut:
        If True, analyze and report on clips but do not invoke FFmpeg cut.
    skip_transcription:
        If True, skip Whisper (analysis falls back to audio-only peaks).
    only_transcribe:
        If True, download + transcribe and stop.
    on_progress:
        Optional callback ``(message, step, total_steps)``. Defaults to printing.
    """
    progress = on_progress or _noop_progress
    total_steps = 7 if not skip_transcription else 5

    # ------------------------------------------------------------------
    # 1. Load config
    # ------------------------------------------------------------------
    step = 0
    try:
        from livecut import load_config

        if config_path is None:
            config_path = os.path.join("config", "config.json")
        cfg = load_config(config_path)
    except Exception as exc:
        return PipelineResult(ok=False, error_message=f"Failed to load config: {exc}")

    try:
        clip_cfg = cfg["clip"]
        audio_cfg = cfg["audio"]
        tx_cfg = cfg["transcription"]
        sc_cfg = cfg["scoring"]
        paths_cfg = cfg["paths"]
        ff_cfg = cfg.get("ffmpeg", {})

        temp_dir = Path(paths_cfg.get("temp_dir", "temp")).resolve()
        output_dir = Path(output_dir_override or paths_cfg.get("output_dir", "output")).resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        keywords: List[str] = cfg.get("keywords", [])

        step += 1
        progress(f"[1/{total_steps}] Config loaded. Quality = {quality}. "
                 f"Temp: {temp_dir}  Output: {output_dir}", step, total_steps)

        # ------------------------------------------------------------------
        # 2. Download / locate input
        # ------------------------------------------------------------------
        step += 1
        progress(f"[2/{total_steps}] Resolving input source: {input_value[:120]}", step, total_steps)

        from livecut import VodDownloader

        downloader = VodDownloader(
            output_dir=str(temp_dir), quality=quality, keep_downloaded=keep_downloaded
        )
        download_info = downloader.download(input_value)
        video_path = Path(download_info["local_path"])
        platform = download_info.get("platform", "unknown")
        title = download_info.get("title") or video_path.stem
        base_name = _sanitize_name(title)

        if not video_path.exists():
            return PipelineResult(
                ok=False, error_message=f"Downloaded file not found at {video_path}"
            )

        size_mb = video_path.stat().st_size / (1024 * 1024)
        progress(f"    Source ready [{platform}] size={size_mb:.1f} MB → {video_path.name}",
                 step, total_steps)

        if only_download:
            return PipelineResult(
                ok=True, downloaded_path=video_path, platform=platform,
                title=title, output_dir=output_dir,
            )

        # ------------------------------------------------------------------
        # 3. Audio extraction
        # ------------------------------------------------------------------
        step += 1
        audio_path = temp_dir / f"{base_name}_audio.wav"
        progress(f"[3/{total_steps}] Extracting audio track to {audio_path.name}",
                 step, total_steps)

        from livecut import AudioExtractor

        extractor = AudioExtractor(sample_rate=audio_cfg["sample_rate"])
        audio_path = Path(extractor.extract_audio(str(video_path), str(audio_path)))
        audio_dur = extractor.probe_duration(audio_path) if hasattr(extractor, "probe_duration") else None
        # Fallback duration via ffprobe
        if audio_dur is None:
            from livecut import probe_video_info, get_ffprobe_exe
            try:
                info = probe_video_info(str(video_path), get_ffprobe_exe())
                audio_dur = info.get("duration")
            except Exception:
                audio_dur = None
        progress(f"    Audio ready {('(' + f'{audio_dur:.1f}s' + ')') if audio_dur else ''} "
                 f"size={audio_path.stat().st_size / (1024*1024):.1f} MB", step, total_steps)

        # ------------------------------------------------------------------
        # 4. Transcription (optional)
        # ------------------------------------------------------------------
        transcription: Dict[str, Any] = {"segments": [], "words": [], "language": tx_cfg.get("language", "en")}
        if not skip_transcription:
            step += 1
            progress(f"[4/{total_steps}] Transcribing with faster-whisper "
                     f"model={tx_cfg['whisper_model']} compute={tx_cfg['compute_type']} "
                     f"device={tx_cfg['device']} lang={tx_cfg['language']}", step, total_steps)
            t_start = time.perf_counter()

            from livecut import WhisperTranscriber

            transcriber = WhisperTranscriber(
                model_name=tx_cfg["whisper_model"],
                language=tx_cfg["language"],
                compute_type=tx_cfg["compute_type"],
                device=tx_cfg["device"],
                beam_size=tx_cfg.get("beam_size", 5),
            )
            transcription = transcriber.transcribe(str(audio_path))
            elapsed = time.perf_counter() - t_start
            nwords = len(transcription.get("words", []))
            progress(f"    Transcription done in {elapsed:.1f}s, {nwords} words, "
                     f"detected language = {transcription.get('language', '?')}",
                     step, total_steps)

            if only_transcribe:
                import json as _json
                meta_file = output_dir / f"transcript_{base_name}.json"
                with open(meta_file, "w", encoding="utf-8") as fp:
                    _json.dump(transcription, fp, indent=2, ensure_ascii=False, default=_default_json)
                return PipelineResult(
                    ok=True, downloaded_path=video_path, output_dir=output_dir,
                    metadata_path=meta_file, platform=platform, title=title,
                )

        # ------------------------------------------------------------------
        # 5. Volume analysis + peak detection
        # ------------------------------------------------------------------
        step += 1
        progress(f"[5/{total_steps}] Analyzing volume / detecting peaks "
                 f"(threshold={audio_cfg['volume_peak_threshold']}, "
                 f"min_distance={audio_cfg['peak_min_distance_seconds']}s)",
                 step, total_steps)

        from livecut import VolumeAnalyzer

        analyzer = VolumeAnalyzer(
            sample_rate=audio_cfg["sample_rate"],
            peak_threshold=audio_cfg["volume_peak_threshold"],
            min_distance_seconds=audio_cfg["peak_min_distance_seconds"],
            silence_threshold_db=audio_cfg.get("silence_threshold_db", -40.0),
        )
        energy_data = analyzer.compute_rms_energy(str(audio_path))
        video_duration = energy_data.get("duration") or (audio_dur or 0.0)
        peaks = analyzer.detect_peaks(str(audio_path))
        progress(f"    {len(peaks)} candidate peaks found. Video duration = "
                 f"{video_duration:.1f}s ({video_duration/60:.1f} min)",
                 step, total_steps)

        # ------------------------------------------------------------------
        # 6. Clip ranking / selection
        # ------------------------------------------------------------------
        step += 1
        progress(f"[6/{total_steps}] Ranking clip candidates "
                 f"(max={clip_cfg['max_clips']}, durations=[{clip_cfg['min_duration_seconds']}s, "
                 f"{clip_cfg['max_duration_seconds']}s])", step, total_steps)

        from livecut import HighlightClipSelector

        selector = HighlightClipSelector(
            min_duration=clip_cfg["min_duration_seconds"],
            max_duration=clip_cfg["max_duration_seconds"],
            max_clips=clip_cfg["max_clips"],
            pre_padding=clip_cfg["pre_padding_seconds"],
            post_padding=clip_cfg["post_padding_seconds"],
            keywords=keywords,
            volume_weight=sc_cfg.get("volume_weight", 0.35),
            keyword_weight=sc_cfg.get("keyword_weight", 0.30),
            speech_density_weight=sc_cfg.get("speech_density_weight", 0.15),
            excitement_weight=sc_cfg.get("excitement_words_weight", 0.20),
        )
        selected_clips = selector.select_best_clips(
            peaks, energy_data, transcription, video_duration
        )
        progress(f"    {len(selected_clips)} clips selected after anti-overlap filter.",
                 step, total_steps)
        for i, c in enumerate(selected_clips, 1):
            reasons = ", ".join(c["reasons"][:2]) if c["reasons"] else "composite score"
            progress(f"      ⭐ #{c['rank']:<2}  score={c['score']:.3f}  "
                     f"[{c['start']:7.2f}s → {c['end']:7.2f}s]  {reasons}",
                     step, total_steps)

        # Report
        report_text = selector.generate_clip_report(selected_clips)
        report_path = output_dir / f"report_{base_name}.txt"
        with open(report_path, "w", encoding="utf-8") as fp:
            fp.write(report_text)

        # ------------------------------------------------------------------
        # 7. Cut videos (optional)
        # ------------------------------------------------------------------
        step += 1
        produced: List[Dict[str, Any]] = []
        if skip_cut or not selected_clips:
            progress(f"[7/{total_steps}] Cutting stage SKIPPED (skip_cut={skip_cut}, "
                     f"selected={len(selected_clips)})", step, total_steps)
        else:
            progress(f"[7/{total_steps}] Cutting {len(selected_clips)} clips with FFmpeg "
                     f"(preset={ff_cfg.get('preset','slow')}, "
                     f"CRF={ff_cfg.get('crf', 18)}, target-ratio="
                     f"{clip_cfg['target_aspect_ratio']})", step, total_steps)

            from livecut import VideoCutter

            cutter = VideoCutter(
                output_dir=str(output_dir),
                target_aspect_ratio=clip_cfg["target_aspect_ratio"],
                fallback_aspect_ratio=clip_cfg.get("fallback_aspect_ratio", "16:9"),
                preset=ff_cfg.get("preset", "slow"),
                crf=int(ff_cfg.get("crf", 18)),
                audio_bitrate=ff_cfg.get("audio_bitrate", "256k"),
                video_codec=ff_cfg.get("video_codec", "libx264"),
                audio_codec=ff_cfg.get("audio_codec", "aac"),
            )
            t0 = time.perf_counter()
            for i, clip in enumerate(selected_clips, 1):
                safe_ts_tag = f"{int(clip['start']//60):02d}m{int(clip['start']%60):02d}s"
                clip_name = f"clip_{clip['rank']:02d}__{base_name}__{safe_ts_tag}_score{clip['score']:.2f}".replace(
                    ".", "p", 1
                ).rsplit(".", 1)[0]
                try:
                    out_path, info = cutter.cut_clip(
                        str(video_path), clip["start"], clip["end"],
                        clip_name=clip_name, rank=clip.get("rank"),
                    )
                    clip["output_path"] = str(out_path)
                    clip["cut_info"] = info
                    out_mb = Path(out_path).stat().st_size / (1024 * 1024)
                    progress(f"      ✓ Clip #{clip['rank']} → {Path(out_path).name} "
                             f"({out_mb:.1f} MB, {info.get('aspect_ratio_used','?')})",
                             step, total_steps)
                    produced.append(clip)
                except Exception as exc:
                    progress(f"      ✗ Clip #{clip['rank']} FAILED: {exc}",
                             step, total_steps)
            progress(f"    FFmpeg cutting finished in {time.perf_counter()-t0:.1f}s",
                     step, total_steps)

        # Metadata
        metadata_path = output_dir / f"metadata_{base_name}.json"
        with open(metadata_path, "w", encoding="utf-8") as fp:
            json.dump(
                {
                    "title": title,
                    "platform": platform,
                    "input_video": str(video_path),
                    "video_duration_seconds": round(video_duration, 2),
                    "quality": quality,
                    "total_peaks_detected": len(peaks),
                    "clips": produced or selected_clips,
                    "config_snapshot": {
                        "clip": clip_cfg, "audio": audio_cfg,
                        "transcription": tx_cfg, "scoring": sc_cfg,
                    },
                },
                fp, indent=2, ensure_ascii=False, default=_default_json,
            )

        # Clean up temp files if requested
        if not keep_downloaded and video_path.is_file() and platform != "local":
            try:
                video_path.unlink(missing_ok=True)
                audio_path.unlink(missing_ok=True)
            except Exception:
                pass

        progress("✅ Pipeline finished successfully.", step, total_steps)
        return PipelineResult(
            ok=True,
            downloaded_path=video_path,
            output_dir=output_dir,
            clips=produced or selected_clips,
            report_path=report_path,
            metadata_path=metadata_path,
            platform=platform,
            title=title,
        )

    except KeyboardInterrupt:
        return PipelineResult(ok=False, error_message="Interrupted by user")
    except Exception as exc:
        tb = traceback.format_exc()
        progress(f"❌ Pipeline failed: {exc}\n{tb}", step, total_steps)
        return PipelineResult(ok=False, error_message=f"{exc}\n{tb}")
