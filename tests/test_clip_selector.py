"""Behaviour tests for clip positioning, ranking and keyword/excitement scoring."""

import numpy as np

from livecut.clip_selector import HighlightClipSelector


def _energy(n: int = 2400, dt: float = 0.5):
    times = np.arange(n) * dt
    rms = np.clip(0.5 + 0.4 * np.sin(times / 3.0), 0.02, 1.0)
    return {"times": times, "rms_normalized": rms}


def _peak(ts: float, vol: float = 0.92, prom: float = 0.6,
          kind: str = "volume", surge: float = 0.05):
    return {
        "timestamp": ts,
        "peak_volume": vol,
        "prominence": prom,
        "type": kind,
        "surge": surge,
        "build_up": 0.15,
    }


def _transcript_at(timestamps, word: str = "caralho"):
    words, segments = [], []
    for t in timestamps:
        words.append({"word": word, "start": t, "end": t + 0.4, "probability": 0.9})
        segments.append({"start": t - 12.0, "end": t + 12.0, "text": word, "words": []})
    return {"segments": segments, "words": words}


def test_position_peak_respects_max_duration():
    sel = HighlightClipSelector(min_duration=24, max_duration=36)
    start, end = sel._position_peak_in_window(300.0, video_duration=1200.0)

    assert start <= 300.0 <= end
    assert end - start <= 36 + 1e-6


def test_position_peak_clamps_at_video_edge():
    sel = HighlightClipSelector(min_duration=24, max_duration=36)
    start, end = sel._position_peak_in_window(1199.0, video_duration=1200.0)

    assert start >= 0.0
    assert end <= 1200.0 + 1e-9
    assert end - start <= 36 + 1e-6


def test_overlap_detection_threshold():
    sel = HighlightClipSelector()
    a = {"start": 0.0, "end": 30.0, "duration": 30.0}
    b = {"start": 10.0, "end": 40.0, "duration": 30.0}
    c = {"start": 31.0, "end": 61.0, "duration": 30.0}

    assert sel._clips_overlap(a, b) is True
    assert sel._clips_overlap(a, c) is False


def test_select_best_clips_avoids_overlap_and_ranks_in_time_order():
    sel = HighlightClipSelector(min_duration=24, max_duration=36, max_clips=8)
    energy = _energy()
    transcript = _transcript_at([300.0, 900.0])

    peaks = [_peak(300.0), _peak(302.0), _peak(900.0)]
    clips = sel.select_best_clips(peaks, energy, transcript, video_duration=1200.0)

    # 300 and 302 produce near-identical windows; only one may survive.
    assert len(clips) == 2
    assert clips == sorted(clips, key=lambda c: c["start"])
    assert [c["rank"] for c in clips] == [1, 2]


def test_keyword_matching_uses_configured_keywords():
    sel = HighlightClipSelector(keywords=["caralho"])
    transcript = _transcript_at([100.0])

    matches = sel._find_keyword_matches(transcript, 90.0, 110.0)

    assert len(matches) == 1
    assert matches[0]["keyword"] == "caralho"


def test_no_keywords_means_no_matches():
    sel = HighlightClipSelector(keywords=[])
    transcript = _transcript_at([100.0])

    assert sel._find_keyword_matches(transcript, 90.0, 110.0) == []


def test_excitement_words_are_configurable():
    custom = HighlightClipSelector(excitement_words=["banana"])
    banana = [{"word": "banana", "start": 0.0, "end": 0.5, "probability": 0.9}]
    caralho = [{"word": "caralho", "start": 0.0, "end": 0.5, "probability": 0.9}]

    assert custom._calculate_excitement_score(banana) > 0.0
    assert custom._calculate_excitement_score(caralho) == 0.0


def test_default_excitement_words_are_used_when_unspecified():
    default = HighlightClipSelector()
    caralho = [{"word": "caralho", "start": 0.0, "end": 0.5, "probability": 0.9}]

    assert default._calculate_excitement_score(caralho) > 0.0
