import numpy as np
from typing import List, Dict, Tuple, Any
from pathlib import Path


_VARIATION_SCALE = 50.0


def compute_window_stats(rms_norm: np.ndarray,
                         times: np.ndarray,
                         start_time: float,
                         end_time: float,
                         peak_threshold: float) -> Dict[str, float]:
    """Compute RMS statistics for a temporal window.

    Shared by the volume analyzer and the clip selector so both agree on the
    same numbers (previously duplicated with diverging scaling constants).
    """
    start_idx = np.searchsorted(times, start_time)
    end_idx = np.searchsorted(times, end_time)

    start_idx = max(0, min(start_idx, len(rms_norm) - 1))
    end_idx = max(start_idx + 1, min(end_idx, len(rms_norm)))

    window_rms = rms_norm[start_idx:end_idx]

    if len(window_rms) == 0:
        return {"avg": 0.0, "max": 0.0, "min": 0.0, "std": 0.0,
                "peak_count": 0, "variation": 0.0}

    peak_count = int(np.sum(window_rms >= peak_threshold))

    diffs = np.diff(window_rms)
    variation = float(np.mean(np.abs(diffs))) * _VARIATION_SCALE if len(diffs) > 0 else 0.0

    return {
        "avg": float(np.mean(window_rms)),
        "max": float(np.max(window_rms)),
        "min": float(np.min(window_rms)),
        "std": float(np.std(window_rms)),
        "peak_count": peak_count,
        "variation": min(variation, 1.0),
    }


class VolumeAnalyzer:
    """Analyzes audio volume characteristics to detect peaks, silence, and dynamic changes.

    This class provides tools for extracting RMS energy from audio files,
    detecting significant volume peaks (including both sustained high-volume
    regions and sudden volume surges), computing per-window volume statistics,
    and identifying silence periods. It is designed for content analysis
    pipelines such as highlight detection and scene boundary estimation.
    """

    def __init__(self, sample_rate: int = 16000,
                 peak_threshold: float = 0.55,
                 min_distance_seconds: float = 6.0,
                 silence_threshold_db: float = -40.0):
        """Initialize the volume analyzer.

        Args:
            sample_rate: Target sample rate in Hertz for audio loading.
                Defaults to 16000.
            peak_threshold: Baseline normalized RMS threshold (0.0 to 1.0)
                used for peak detection. The effective threshold is refined
                adaptively on a per-file basis. Defaults to 0.55.
            min_distance_seconds: Minimum separation in seconds between
                detected peaks. Peaks closer than this interval are merged
                or suppressed. Defaults to 6.0.
            silence_threshold_db: Loudness threshold in decibels (dBFS,
                relative to the file's maximum) below which a frame is
                considered silent. Defaults to -40.0.
        """
        self.sample_rate = sample_rate
        self.peak_threshold = peak_threshold
        self.min_distance_seconds = min_distance_seconds
        self.silence_threshold_db = silence_threshold_db

    def _load_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """Load and resample an audio file to mono at the configured sample rate.

        Args:
            audio_path: Filesystem path to the source audio file.

        Returns:
            A tuple ``(y, sr)`` where ``y`` is the mono audio time series as a
            numpy float array and ``sr`` is the effective sample rate.

        Raises:
            ImportError: If librosa is not installed in the environment.
            FileNotFoundError: If ``audio_path`` does not exist on disk.
        """
        try:
            import librosa
        except ImportError:
            raise ImportError(
                "librosa is not installed. "
                "Install it with: pip install librosa"
            )

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        y, sr = librosa.load(str(audio_path), sr=self.sample_rate, mono=True)
        return y, sr

    def compute_rms_energy(self, audio_path: str,
                           frame_length: int = 2048,
                           hop_length: int = 512) -> Dict[str, Any]:
        """Compute per-frame RMS energy and related metrics for an audio file.

        The RMS (root-mean-square) energy is computed on short overlapping
        frames. Three representations are returned: raw RMS, RMS normalized
        to the file's peak (0.0 to 1.0), and RMS converted to decibels
        relative to the file's maximum amplitude.

        Args:
            audio_path: Filesystem path to the source audio file.
            frame_length: Number of samples per analysis frame.
                Defaults to 2048.
            hop_length: Number of samples between successive frame onsets.
                Defaults to 512.

        Returns:
            A dictionary containing:
                - ``rms`` (np.ndarray): Raw RMS energy per frame.
                - ``rms_normalized`` (np.ndarray): RMS normalized to [0, 1]
                  relative to the file's peak RMS.
                - ``db`` (np.ndarray): RMS converted to dBFS relative to the
                  file's maximum.
                - ``times`` (np.ndarray): Timestamp in seconds for each frame.
                - ``sample_rate`` (int): Effective sample rate used.
                - ``duration`` (float): Total audio duration in seconds.
                - ``hop_length`` (int): Hop length used for framing.
                - ``frame_length`` (int): Frame length used for framing.

        Raises:
            ImportError: If librosa is not installed in the environment.
            FileNotFoundError: If ``audio_path`` does not exist.
        """
        try:
            import librosa
        except ImportError:
            raise ImportError("librosa is not installed.")

        y, sr = self._load_audio(audio_path)

        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

        rms_normalized = rms / (np.max(rms) + 1e-10)

        db = librosa.amplitude_to_db(rms, ref=np.max)

        return {
            "rms": rms,
            "rms_normalized": rms_normalized,
            "db": db,
            "times": times,
            "sample_rate": sr,
            "duration": len(y) / sr,
            "hop_length": hop_length,
            "frame_length": frame_length,
        }

    def _adaptive_threshold(self, rms_norm: np.ndarray) -> float:
        """Compute an adaptive volume threshold based on signal statistics.

        The threshold is derived from three estimators and clamped to a
        sensible floor:

        * ``median + 1.8 * std`` — captures regions significantly above the
          typical volume level.
        * ``P90 * 0.85`` — anchors to the 90th percentile so that quiet
          recordings still produce usable thresholds.
        * A hard floor of ``0.35`` prevents the threshold from collapsing on
          extremely uniform or noisy signals.

        Args:
            rms_norm: Normalized RMS energy array (values in [0, 1]).

        Returns:
            The adaptive threshold as a float in the range [0.35, 1.0).
        """
        valid = rms_norm[rms_norm > 0.02]
        if len(valid) == 0:
            return self.peak_threshold

        median = float(np.median(valid))
        std = float(np.std(valid))
        p90 = float(np.percentile(valid, 90))

        adaptive = max(median + 1.8 * std, p90 * 0.85, 0.35)
        return min(adaptive, max(self.peak_threshold, 0.5))

    def detect_peaks(self, audio_path: str) -> List[Dict[str, Any]]:
        """Detect notable volume peaks in an audio file.

        Detection runs two complementary passes:

        1. **Volume-based peaks** on the normalized RMS signal, using the
           adaptive height threshold, a minimum distance constraint, and a
           prominence requirement to filter out small bumps.
        2. **Surge-based peaks** on the first-order difference of RMS, which
           captures sudden jumps in loudness (e.g., impacts, crowd cheers,
           or scene transitions) that may not produce the highest absolute
           volume.

        Candidate peaks from both passes are merged when they fall within the
        minimum-distance window, and a composite score is computed for each
        retained peak as a weighted combination of:

        * absolute peak volume (30%),
        * prominence against neighboring valleys (22%),
        * magnitude of the clamped volume surge (23%),
        * pre-peak build-up gradient scaled (15%),
        * local standard deviation reflecting temporal dynamics (10%).

        Args:
            audio_path: Filesystem path to the source audio file.

        Returns:
            A list of peak dictionaries, sorted in descending order of
            composite score. Each entry contains:

            - ``timestamp`` (float): Time in seconds of the peak frame.
            - ``peak_volume`` (float): Normalized RMS at the peak.
            - ``prominence`` (float): Prominence of the volume peak.
            - ``type`` (str): One of ``"volume"``, ``"surge"``, or
              ``"volume+surge"`` indicating which detector(s) contributed.
            - ``surge`` (float): Magnitude of the RMS derivative at the peak.
            - ``avg_volume_window`` (float): Mean normalized RMS in a local
              window around the peak.
            - ``std_volume_window`` (float): Standard deviation of normalized
              RMS in the local window.
            - ``build_up`` (float): Estimated pre-peak volume ramp magnitude.
            - ``score`` (float): Composite score in approximately [0, 1].

        Raises:
            ImportError: If scipy or librosa is not installed.
            FileNotFoundError: If ``audio_path`` does not exist.
        """
        try:
            from scipy.signal import find_peaks
        except ImportError:
            raise ImportError(
                "scipy is not installed. "
                "Install it with: pip install scipy"
            )

        energy_data = self.compute_rms_energy(audio_path)
        rms_norm = energy_data["rms_normalized"]
        times = energy_data["times"]

        adaptive_thresh = self._adaptive_threshold(rms_norm)
        final_thresh = min(self.peak_threshold, adaptive_thresh) if self.peak_threshold else adaptive_thresh

        min_distance_samples = int(self.min_distance_seconds * self.sample_rate / 512)

        peaks, properties = find_peaks(
            rms_norm,
            height=final_thresh,
            distance=min_distance_samples,
            prominence=max(0.06, final_thresh * 0.18)
        )

        diff = np.diff(rms_norm, prepend=rms_norm[0])
        diff_thresh = float(np.percentile(diff[diff > 0], 92)) if np.any(diff > 0) else 0.1
        surge_peaks, surge_props = find_peaks(
            diff,
            height=max(0.06, diff_thresh * 0.65),
            distance=max(1, min_distance_samples // 2)
        )

        merged_peaks: Dict[int, Dict[str, Any]] = {}
        for i, peak_idx in enumerate(peaks):
            peak_time = float(times[peak_idx])
            peak_height = float(rms_norm[peak_idx])
            prominence = float(properties.get("prominences", [0])[i])
            merged_peaks[peak_idx] = {
                "timestamp": peak_time,
                "peak_volume": peak_height,
                "prominence": prominence,
                "type": "volume",
                "surge": 0.0,
            }

        for j, peak_idx in enumerate(surge_peaks):
            peak_idx = int(peak_idx)
            if peak_idx >= len(rms_norm):
                continue
            peak_time = float(times[peak_idx])
            surge_height = float(surge_props.get("peak_heights", [0])[j])
            volume_at_peak = float(rms_norm[peak_idx])

            closest = None
            closest_dist = float("inf")
            for existing_idx in merged_peaks.keys():
                dist = abs(peak_idx - existing_idx)
                if dist < closest_dist:
                    closest_dist = dist
                    closest = existing_idx

            if closest is not None and closest_dist <= min_distance_samples:
                merged_peaks[closest]["surge"] = max(merged_peaks[closest]["surge"], surge_height)
                merged_peaks[closest]["type"] = "volume+surge"
                merged_peaks[closest]["peak_volume"] = max(
                    merged_peaks[closest]["peak_volume"], volume_at_peak
                )
            else:
                if volume_at_peak >= final_thresh * 0.7 or surge_height >= diff_thresh * 0.9:
                    merged_peaks[peak_idx] = {
                        "timestamp": peak_time,
                        "peak_volume": volume_at_peak,
                        "prominence": 0.0,
                        "type": "surge",
                        "surge": surge_height,
                    }

        peak_list: List[Dict[str, Any]] = []
        for peak_idx, data in merged_peaks.items():
            window_start = max(0, peak_idx - 15)
            window_end = min(len(rms_norm), peak_idx + 15)
            avg_volume = float(np.mean(rms_norm[window_start:window_end]))
            std_volume = float(np.std(rms_norm[window_start:window_end]))

            volume_nearby = rms_norm[max(0, peak_idx - 30):peak_idx]
            build_up = 0.0
            if len(volume_nearby) > 5:
                first_half = np.mean(volume_nearby[:len(volume_nearby) // 2])
                second_half = np.mean(volume_nearby[len(volume_nearby) // 2:])
                build_up = max(0.0, second_half - first_half)

            score = (
                data["peak_volume"] * 0.30 +
                data["prominence"] * 0.22 +
                min(data["surge"] * 3.0, 1.0) * 0.23 +
                build_up * 1.8 * 0.15 +
                std_volume * 0.10
            )

            peak_list.append({
                **data,
                "avg_volume_window": avg_volume,
                "std_volume_window": std_volume,
                "build_up": round(build_up, 4),
                "score": round(score, 4),
            })

        peak_list.sort(key=lambda x: x["score"], reverse=True)
        return peak_list

    def get_volume_at_time(self, energy_data: Dict[str, Any], timestamp: float) -> float:
        """Retrieve the normalized RMS volume at a given timestamp.

        The nearest frame whose timestamp is greater than or equal to
        ``timestamp`` is returned, clamped to the valid frame range.

        Args:
            energy_data: Energy dictionary returned by
                :meth:`compute_rms_energy`.
            timestamp: Query time in seconds.

        Returns:
            Normalized RMS volume in [0, 1] at the queried timestamp (or its
            closest valid neighbor).
        """
        times = energy_data["times"]
        rms_norm = energy_data["rms_normalized"]

        idx = np.searchsorted(times, timestamp)
        idx = min(max(idx, 0), len(rms_norm) - 1)
        return float(rms_norm[idx])

    def compute_window_volume_score(self, energy_data: Dict[str, Any],
                                    start_time: float,
                                    end_time: float) -> Dict[str, float]:
        """Compute volume statistics for a temporal window.

        Args:
            energy_data: Energy dictionary returned by
                :meth:`compute_rms_energy`.
            start_time: Window start time in seconds.
            end_time: Window end time in seconds.

        Returns:
            A dictionary of per-window statistics:

            - ``avg`` (float): Mean normalized RMS in the window.
            - ``max`` (float): Peak normalized RMS in the window.
            - ``min`` (float): Lowest normalized RMS in the window.
            - ``std`` (float): Standard deviation of normalized RMS.
            - ``peak_count`` (int): Number of frames whose normalized RMS
              meets or exceeds the configured ``peak_threshold``.
            - ``variation`` (float): Mean absolute frame-to-frame difference
              multiplied by 50, clamped to [0, 1].
        """
        times = energy_data["times"]
        rms_norm = energy_data["rms_normalized"]

        return compute_window_stats(
            rms_norm, times, start_time, end_time, self.peak_threshold
        )

    def detect_silence_periods(self, audio_path: str,
                               min_silence_duration: float = 1.0) -> List[Dict[str, float]]:
        """Detect contiguous silence regions based on the dBFS threshold.

        A frame is considered silent when its RMS in dBFS (relative to the
        file's maximum amplitude) falls below the configured
        ``silence_threshold_db``. Consecutive silent frames are grouped into
        periods, and only periods whose duration meets or exceeds
        ``min_silence_duration`` are reported.

        Args:
            audio_path: Filesystem path to the source audio file.
            min_silence_duration: Minimum duration in seconds for a silence
                period to be included. Defaults to 1.0.

        Returns:
            A list of silence dictionaries in chronological order, each
            containing:

            - ``start`` (float): Onset time in seconds.
            - ``end`` (float): Offset time in seconds.
            - ``duration`` (float): Length of the silence in seconds.

        Raises:
            ImportError: If librosa is not installed.
            FileNotFoundError: If ``audio_path`` does not exist.
        """
        energy_data = self.compute_rms_energy(audio_path)
        db = energy_data["db"]
        times = energy_data["times"]

        is_silent = db < self.silence_threshold_db

        silence_periods: List[Dict[str, float]] = []
        in_silence = False
        silence_start = 0.0

        for i, silent in enumerate(is_silent):
            if silent and not in_silence:
                silence_start = float(times[i])
                in_silence = True
            elif not silent and in_silence:
                silence_end = float(times[i])
                duration = silence_end - silence_start
                if duration >= min_silence_duration:
                    silence_periods.append({
                        "start": silence_start,
                        "end": silence_end,
                        "duration": duration
                    })
                in_silence = False

        return silence_periods
