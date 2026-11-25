"""Path resolution in development and packaged (frozen) modes."""

import sys
from pathlib import Path

from livecut import app_paths


def test_dev_mode_uses_repository_layout(monkeypatch):
    monkeypatch.delenv("LIVECUT_HOME", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)

    repo_root = Path(app_paths.__file__).resolve().parent.parent

    assert app_paths.is_frozen() is False
    assert app_paths.project_root() == repo_root
    assert app_paths.install_dir() == repo_root
    assert app_paths.bundle_dir() == repo_root
    assert app_paths.default_config_path() == repo_root / "config" / "config.json"
    assert app_paths.bundled_default_config() == repo_root / "config" / "config.json"
    assert app_paths.components_dir() == repo_root / "components"
    assert app_paths.ffmpeg_dir() == repo_root / "components" / "ffmpeg" / "bin"
    assert app_paths.models_dir() == repo_root / "components" / "models"
    assert app_paths.default_output_dir() == repo_root / "output"


def test_user_data_dir_honours_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVECUT_HOME", str(tmp_path / "custom"))

    assert app_paths.user_data_dir() == tmp_path / "custom"
    assert app_paths.logs_dir() == tmp_path / "custom" / "logs"


def test_frozen_mode_uses_install_and_user_dirs(tmp_path, monkeypatch):
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    monkeypatch.setenv("LIVECUT_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setattr(sys, "executable", str(app_dir / "LiveCut.exe"))

    assert app_paths.is_frozen() is True
    assert app_paths.bundle_dir() == tmp_path / "bundle"
    assert app_paths.install_dir().resolve() == app_dir.resolve()
    assert app_paths.user_data_dir() == tmp_path / "data"
    assert app_paths.components_dir().resolve() == (app_dir / "components").resolve()
    assert app_paths.ffmpeg_dir().resolve() == (app_dir / "components" / "ffmpeg" / "bin").resolve()
    assert app_paths.logs_dir() == tmp_path / "data" / "logs"
    assert app_paths.default_config_path() == tmp_path / "data" / "config.json"
    assert app_paths.default_temp_dir() == tmp_path / "data" / "temp"
    assert app_paths.default_output_dir().name == "LiveCut"


def test_local_model_ref_prefers_provisioned_model(tmp_path, monkeypatch):
    models = tmp_path / "models"
    model_dir = models / "faster-whisper-small"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").write_bytes(b"x")

    monkeypatch.setattr(app_paths, "models_dir", lambda: models)

    assert app_paths.local_model_ref("small") == str(model_dir)
    assert app_paths.local_model_ref("medium") == "medium"
