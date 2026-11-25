"""Tests for the shared window-statistics helper."""

import numpy as np

from livecut.clip_selector import HighlightClipSelector
from livecut.volume_analyzer import VolumeAnalyzer, compute_window_stats


def _energy(n: int = 600, dt: float = 0.5):
    times = np.arange(n) * dt
    rms = np.clip(0.5 + 0.4 * np.sin(times / 3.0), 0.02, 1.0)
    return {"times": times, "rms_normalized": rms}


def test_window_stats_returns_expected_keys():
    e = _energy()
    stats = compute_window_stats(e["rms_normalized"], e["times"], 10.0, 20.0, 0.5)

    assert set(stats) == {"avg", "max", "min", "std", "peak_count", "variation"}
    assert 0.0 <= stats["avg"] <= 1.0
    assert 0.0 <= stats["variation"] <= 1.0


def test_window_stats_clamps_out_of_range_window():
    e = _energy()
    stats = compute_window_stats(e["rms_normalized"], e["times"], -50.0, 10_000.0, 0.5)

    assert stats["min"] <= stats["avg"] <= stats["max"]


def test_analyzer_and_selector_agree_on_shared_metrics():
    """Regression: analyzer and selector used different scaling constants."""
    e = _energy()

    via_analyzer = VolumeAnalyzer(peak_threshold=0.55).compute_window_volume_score(
        e, 5.0, 25.0
    )
    via_selector = HighlightClipSelector()._compute_window_volume_stats(e, 5.0, 25.0)

    assert via_analyzer["avg"] == via_selector["avg"]
    assert via_analyzer["variation"] == via_selector["variation"]
