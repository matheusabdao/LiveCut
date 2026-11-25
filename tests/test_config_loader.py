"""Tests for config loading and the pipeline/config key contract."""

import json
import sys
from pathlib import Path

from livecut.config_loader import _get_default_config, load_config

# Keys that pipeline.run_pipeline reads from cfg["clip"]. If defaults ever
# drift from these names again, this suite fails loudly.
REQUIRED_CLIP_KEYS = [
    "min_duration_seconds",
    "max_duration_seconds",
    "max_clips",
    "pre_padding_seconds",
    "post_padding_seconds",
    "target_aspect_ratio",
    "fallback_aspect_ratio",
]


def test_default_config_exposes_pipeline_clip_keys():
    clip = _get_default_config()["clip"]
    for key in REQUIRED_CLIP_KEYS:
        assert key in clip, f"default config is missing clip.{key}"


def test_missing_config_file_is_created_with_pipeline_keys(tmp_path):
    cfg_path = tmp_path / "nested" / "config.json"
    cfg = load_config(str(cfg_path))

    assert cfg_path.exists()
    for key in REQUIRED_CLIP_KEYS:
        assert key in cfg["clip"]


def test_deep_merge_keeps_defaults_and_applies_overrides(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"clip": {"max_clips": 3}}), encoding="utf-8")

    cfg = load_config(str(cfg_path))

    assert cfg["clip"]["max_clips"] == 3
    assert cfg["clip"]["min_duration_seconds"] == 20


def test_default_config_has_excitement_words():
    cfg = _get_default_config()
    assert isinstance(cfg["excitement_words"], list)
    assert "caralho" in cfg["excitement_words"]


def test_load_config_without_path_uses_development_config(monkeypatch):
    monkeypatch.delenv("LIVECUT_HOME", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)

    cfg = load_config(None)

    for key in REQUIRED_CLIP_KEYS:
        assert key in cfg["clip"]


def test_load_config_seeds_user_config_when_frozen(tmp_path, monkeypatch):
    seed_dir = tmp_path / "bundle" / "config"
    seed_dir.mkdir(parents=True)
    (seed_dir / "config.json").write_text(
        json.dumps({"clip": {"max_clips": 4}}), encoding="utf-8"
    )
    (tmp_path / "app").mkdir()

    monkeypatch.setenv("LIVECUT_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app" / "LiveCut.exe"))

    cfg = load_config(None)

    assert (tmp_path / "data" / "config.json").exists()
    assert cfg["clip"]["max_clips"] == 4
    assert cfg["clip"]["min_duration_seconds"] == 20  # merged defaults survive
    assert Path(cfg["paths"]["output_dir"]).is_absolute()
    assert Path(cfg["paths"]["temp_dir"]).is_absolute()
