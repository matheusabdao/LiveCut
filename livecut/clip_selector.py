import re
import numpy as np
from typing import List, Dict, Any, Tuple


class HighlightClipSelector:
    def __init__(self, min_duration: int = 20, max_duration: int = 50,
                 max_clips: int = 8, pre_padding: int = 5, post_padding: int = 3,
                 keywords: List[str] = None,
                 volume_weight: float = 0.35,
                 keyword_weight: float = 0.30,
                 speech_density_weight: float = 0.15,
                 excitement_weight: float = 0.20):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.max_clips = max_clips
        self.pre_padding = pre_padding
        self.post_padding = post_padding
        self.keywords = keywords or []
        self.volume_weight = volume_weight
        self.keyword_weight = keyword_weight
        self.speech_density_weight = speech_density_weight
        self.excitement_weight = excitement_weight

    def _normalize_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _find_keyword_matches(self, transcription: Dict[str, Any],
                              start: float, end: float) -> List[Dict]:
        matches = []
        normalized_keywords = [self._normalize_text(kw) for kw in self.keywords]

        multi_keywords = []
        single_keywords = []
        for i, kw in enumerate(normalized_keywords):
            if not kw:
                continue
            if " " in kw:
                multi_keywords.append((i, kw))
            else:
                single_keywords.append((i, kw))

        words_in_window = []
        for word in transcription.get("words", []):
            if word["end"] < start or word["start"] > end:
                continue
            words_in_window.append(word)

        seen_pairs = set()
        for word in words_in_window:
            word_norm = self._normalize_text(word["word"])
            if not word_norm or len(word_norm) <= 1:
                continue
            for i, kw in single_keywords:
                if kw == word_norm:
                    key = (i, round(word["start"], 1))
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    matches.append({
                        "keyword": self.keywords[i],
                        "matched_word": word["word"],
                        "timestamp": word["start"],
                        "confidence": word.get("probability", 0.9),
                    })

        text_window = self._normalize_text(
            self._get_transcript_excerpt(transcription, start, end, 4000)
        )
        if text_window:
            for i, kw in multi_keywords:
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, text_window):
                    ts = start
                    for w in words_in_window:
                        wn = self._normalize_text(w["word"])
                        if wn and wn == kw.split()[0]:
                            ts = w["start"]
                            break
                    key = (i, "multi")
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    matches.append({
                        "keyword": self.keywords[i],
                        "matched_word": f"[phrase] {self.keywords[i]}",
                        "timestamp": ts,
                        "confidence": 0.95,
                    })

        return matches

    def _calculate_speech_density(self, transcription: Dict[str, Any],
                                  start: float, end: float) -> float:
        duration = end - start
        if duration <= 0:
            return 0.0

        speech_duration = 0.0
        for seg in transcription.get("segments", []):
            seg_start = max(seg["start"], start)
            seg_end = min(seg["end"], end)
            if seg_end > seg_start:
                speech_duration += (seg_end - seg_start)

        return min(speech_duration / duration, 1.0)

    def _calculate_excitement_score(self, words: List[Dict]) -> float:
        if not words:
            return 0.0

        excitement_words = [
            "caralho", "porra", "foda", "cu", "merda",
            "uau", "wow", "nossa", "caraca", "insano", "doido",
            "louco", "surreal", "incrivel", "impressionante",
            "cacilda", "sacanagem", "puta",
        ]

        count = 0
        valid_words = 0
        for word_info in words:
            word_norm = self._normalize_text(word_info["word"])
            if not word_norm or len(word_norm) <= 1:
                continue
            valid_words += 1
            for exc_word in excitement_words:
                if word_norm == exc_word:
                    count += 1
                    break

        if valid_words == 0:
            return 0.0
        return min(count / max(valid_words, 1) * 7.0, 1.0)

    def _keyword_score_curve(self, n: int) -> float:
        if n == 0:
            return 0.0
        if n == 1:
            return 0.42
        if n == 2:
            return 0.72
        if n == 3:
            return 0.88
        return min(1.0, 0.88 + (n - 3) * 0.05)

    def _position_peak_in_window(self, peak_time: float, video_duration: float) -> Tuple[float, float]:
        pre_ratio = 0.62
        target_duration = (self.min_duration + self.max_duration) / 2.0

        pre_window = max(self.pre_padding, target_duration * pre_ratio)
        post_window = max(self.post_padding, target_duration * (1.0 - pre_ratio))

        start = max(0.0, peak_time - pre_window)
        end = min(video_duration, peak_time + post_window)

        actual_duration = end - start

        if actual_duration < self.min_duration:
            deficit = self.min_duration - actual_duration
            add_pre = min(peak_time - start, deficit * 0.65)
            start -= add_pre
            remaining = deficit - add_pre
            end = min(video_duration, end + remaining)

            start = max(0.0, start)
            if (end - start) < self.min_duration:
                end = min(video_duration, start + self.min_duration)
                if (end - start) < self.min_duration:
                    start = max(0.0, end - self.min_duration)

        if actual_duration > self.max_duration:
            peak_rel = (peak_time - start) / max(actual_duration, 0.001)
            peak_rel = min(max(peak_rel, 0.35), 0.82)
            start = peak_time - self.max_duration * peak_rel
            end = start + self.max_duration
            start = max(0.0, start)
            end = min(video_duration, end)
            if (end - start) > self.max_duration:
                if start > 0:
                    start = end - self.max_duration
                else:
                    end = start + self.max_duration

        return max(0.0, start), min(video_duration, end)

    def _score_clip_candidate(self, peak: Dict[str, Any],
                              energy_data: Dict[str, Any],
                              transcription: Dict[str, Any],
                              video_duration: float) -> Dict[str, Any]:
        peak_time = peak["timestamp"]

        start, end = self._position_peak_in_window(peak_time, video_duration)
        actual_duration = end - start

        win_stats = self._compute_window_volume_stats(energy_data, start, end)
        volume_stats = {
            "avg": win_stats["avg"],
            "max": win_stats["max"],
            "std": win_stats["std"],
        }
        volume_score = self._calculate_volume_score(peak, volume_stats)
        volume_variation = win_stats.get("variation", 0.0)

        silence_penalty = 0.0
        if win_stats["avg"] < 0.12:
            silence_penalty += (0.12 - win_stats["avg"]) * 2.0
        if win_stats.get("peak_count", 0) == 0 and volume_score < 0.25:
            silence_penalty += 0.15

        keyword_matches = self._find_keyword_matches(transcription, start, end)
        keyword_score = self._keyword_score_curve(len(keyword_matches))

        speech_density = self._calculate_speech_density(transcription, start, end)

        words_in_window = [
            w for w in transcription.get("words", [])
            if w["start"] >= start and w["end"] <= end
        ]
        excitement_score = self._calculate_excitement_score(words_in_window)

        adjusted_volume = max(0.0, volume_score * 0.88 + volume_variation * 0.12 - silence_penalty)

        final_score = (
            adjusted_volume * self.volume_weight +
            keyword_score * self.keyword_weight +
            speech_density * self.speech_density_weight +
            excitement_score * self.excitement_weight
        )

        final_score = max(0.0, min(1.0, final_score - silence_penalty * 0.5))

        reasons = []
        if volume_score > 0.45:
            reasons.append(f"High volume peak ({volume_score:.2f})")
        if volume_variation > 0.35:
            reasons.append(f"High audio dynamic range/variation ({volume_variation:.2f})")
        if peak.get("surge", 0) > 0.02:
            reasons.append(f"Sudden volume increase (type: {peak.get('type', 'volume')})")
        if keyword_matches:
            kw_list = ", ".join(sorted(set(m["keyword"] for m in keyword_matches[:4])))
            reasons.append(f"Keywords detected: {kw_list} ({len(keyword_matches)} matches)")
        if speech_density > 0.7:
            reasons.append(f"High speech density ({speech_density:.0%})")
        if excitement_score > 0.25:
            reasons.append(f"Excited tone/reactions detected ({excitement_score:.2f})")

        if not reasons:
            reasons.append("Momentum identified through composite analysis (context + volume)")

        peak_pos_rel = (peak_time - start) / max(actual_duration, 0.001)

        return {
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(actual_duration, 2),
            "peak_time": round(peak_time, 2),
            "peak_position_ratio": round(peak_pos_rel, 3),
            "scores": {
                "final": round(final_score, 4),
                "volume": round(volume_score, 4),
                "volume_variation": round(volume_variation, 4),
                "silence_penalty": round(silence_penalty, 4),
                "keyword": round(keyword_score, 4),
                "speech_density": round(speech_density, 4),
                "excitement": round(excitement_score, 4),
            },
            "keyword_matches": keyword_matches,
            "peak_type": peak.get("type", "volume"),
            "peak_build_up": peak.get("build_up", 0),
            "reasons": reasons,
            "transcript_excerpt": self._get_transcript_excerpt(transcription, start, end)
        }

    def _compute_window_volume_stats(self, energy_data: Dict[str, Any],
                                     start_time: float,
                                     end_time: float) -> Dict[str, float]:
        times = energy_data["times"]
        rms_norm = energy_data["rms_normalized"]

        start_idx = np.searchsorted(times, start_time)
        end_idx = np.searchsorted(times, end_time)

        start_idx = max(0, min(start_idx, len(rms_norm) - 1))
        end_idx = max(start_idx + 1, min(end_idx, len(rms_norm)))

        window_rms = rms_norm[start_idx:end_idx]

        if len(window_rms) == 0:
            return {"avg": 0.0, "max": 0.0, "min": 0.0, "std": 0.0, "peak_count": 0, "variation": 0.0}

        peak_count = int(np.sum(window_rms >= self._estimate_peak_threshold(rms_norm)))

        diffs = np.diff(window_rms)
        variation = float(np.mean(np.abs(diffs))) * 48 if len(diffs) > 0 else 0.0

        return {
            "avg": float(np.mean(window_rms)),
            "max": float(np.max(window_rms)),
            "min": float(np.min(window_rms)),
            "std": float(np.std(window_rms)),
            "peak_count": peak_count,
            "variation": min(variation, 1.0),
        }

    def _estimate_peak_threshold(self, rms_norm: np.ndarray) -> float:
        valid = rms_norm[rms_norm > 0.02]
        if len(valid) == 0:
            return 0.5
        return max(0.4, float(np.percentile(valid, 80)))

    def _calculate_volume_score(self, peak: Dict, stats: Dict) -> float:
        peak_vol = peak.get("peak_volume", 0)
        prominence = peak.get("prominence", 0)
        avg_window = stats.get("avg", 0)
        max_window = stats.get("max", 0)
        build_up = peak.get("build_up", 0)

        score = (
            peak_vol * 0.30 +
            prominence * 0.22 +
            avg_window * 0.18 +
            max_window * 0.15 +
            min(build_up * 2.2, 1.0) * 0.15
        )
        return min(score, 1.0)

    def _get_transcript_excerpt(self, transcription: Dict[str, Any],
                                start: float, end: float,
                                max_chars: int = 280) -> str:
        words_list = []
        used_word_times = set()

        for w in transcription.get("words", []):
            ws = w.get("start", 0.0)
            we = w.get("end", 0.0)
            if we < start or ws > end:
                continue
            key = (round(ws, 2), round(we, 2), w.get("word", "")[:20])
            if key in used_word_times:
                continue
            used_word_times.add(key)
            words_list.append(w.get("word", "").strip())

        if not words_list:
            for seg in transcription.get("segments", []):
                seg_start = seg.get("start", 0.0)
                seg_end = seg.get("end", 0.0)
                if seg_end < start or seg_start > end:
                    continue
                words_list.append(seg.get("text", "").strip())

        excerpt = " ".join(w for w in words_list if w).strip()
        if len(excerpt) > max_chars:
            excerpt = excerpt[:max_chars] + "..."
        return excerpt

    def _clips_overlap(self, c1: Dict, c2: Dict, threshold: float = 0.28) -> bool:
        latest_start = max(c1["start"], c2["start"])
        earliest_end = min(c1["end"], c2["end"])
        overlap = max(0, earliest_end - latest_start)

        if overlap <= 0:
            return False

        min_duration = min(c1["duration"], c2["duration"])
        return (overlap / min_duration) > threshold

    def select_best_clips(self, peaks: List[Dict[str, Any]],
                          energy_data: Dict[str, Any],
                          transcription: Dict[str, Any],
                          video_duration: float) -> List[Dict[str, Any]]:
        if not peaks:
            return []

        candidates = []
        for peak in peaks:
            candidate = self._score_clip_candidate(
                peak, energy_data, transcription, video_duration
            )
            if candidate["duration"] >= self.min_duration * 0.75:
                candidates.append(candidate)

        for candidate in candidates:
            candidate["score"] = candidate["scores"]["final"]

        candidates.sort(key=lambda x: x["score"], reverse=True)

        min_score_cutoff = 0.18
        candidates = [c for c in candidates if c["score"] >= min_score_cutoff]

        if len(candidates) > self.max_clips * 6:
            candidates = candidates[:self.max_clips * 6]

        selected_clips = []
        for candidate in candidates:
            if len(selected_clips) >= self.max_clips:
                break

            overlaps = False
            for selected in selected_clips:
                if self._clips_overlap(candidate, selected):
                    overlaps = True
                    break

            if not overlaps:
                selected_clips.append(candidate)

        for i, clip in enumerate(selected_clips, 1):
            clip["rank"] = i

        selected_clips.sort(key=lambda x: x["start"])

        return selected_clips

    def generate_clip_report(self, clips: List[Dict[str, Any]]) -> str:
        lines = []
        lines.append("=" * 80)
        lines.append("SELECTED HIGHLIGHT CLIPS REPORT")
        lines.append("=" * 80)
        lines.append("")

        for clip in clips:
            lines.append(f"📹 Clip #{clip['rank']}")
            lines.append(f"  FINAL Score: {clip['scores']['final']:.4f}")
            lines.append(f"  Time Range: {self._format_timestamp(clip['start'])} → {self._format_timestamp(clip['end'])}")
            lines.append(f"  Duration: {clip['duration']:.1f}s")
            lines.append(f"  Primary Peak At: {self._format_timestamp(clip['peak_time'])} "
                         f"(position ~{int(clip.get('peak_position_ratio', 0.5)*100)}% of clip)")
            lines.append(f"  Peak Type: {clip.get('peak_type', 'volume')} | "
                         f"Build-up: {clip.get('peak_build_up', 0):.3f}")
            lines.append("")
            lines.append(f"  Component Scores:")
            lines.append(f"    - Volume: {clip['scores']['volume']:.4f}")
            lines.append(f"    - Audio Variation: {clip['scores'].get('volume_variation', 0):.4f}")
            lines.append(f"    - Keywords: {clip['scores']['keyword']:.4f} "
                         f"({len(clip['keyword_matches'])} matches)")
            lines.append(f"    - Speech Density: {clip['scores']['speech_density']:.4f}")
            lines.append(f"    - Excitement: {clip['scores']['excitement']:.4f}")
            lines.append(f"    - Silence Penalty: -{clip['scores'].get('silence_penalty', 0):.4f}")
            lines.append("")
            lines.append(f"  Selection Rationale:")
            for reason in clip["reasons"]:
                lines.append(f"    ✅ {reason}")
            lines.append("")
            if clip["transcript_excerpt"]:
                lines.append(f"  Transcript Excerpt: {clip['transcript_excerpt']}")
                lines.append("")
            lines.append("-" * 80)
            lines.append("")

        return "\n".join(lines)

    def _format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 100)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:02d}"
        return f"{minutes:02d}:{secs:02d}.{ms:02d}"
