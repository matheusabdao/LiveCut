"""Component provisioning: detection, idempotency and failure tolerance."""

import zipfile

import pytest

from livecut import app_paths, provisioning


@pytest.fixture
def components(tmp_path, monkeypatch):
    ffmpeg_bin = tmp_path / "ffmpeg" / "bin"
    models = tmp_path / "models"
    monkeypatch.setattr(app_paths, "ffmpeg_dir", lambda: ffmpeg_bin)
    monkeypatch.setattr(app_paths, "models_dir", lambda: models)
    return ffmpeg_bin, models


def _fake_archive(dest, prefix="ffmpeg-7.0-essentials_build"):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w") as archive:
        archive.writestr(f"{prefix}/bin/{provisioning._FFMPEG_EXE}", b"ffmpeg")
        archive.writestr(f"{prefix}/bin/{provisioning._FFPROBE_EXE}", b"ffprobe")


def test_missing_components_reports_both(components):
    assert provisioning.missing_components() == ["ffmpeg", "model"]


def test_install_ffmpeg_extracts_binaries(components, monkeypatch):
    ffmpeg_bin, _ = components
    monkeypatch.setattr(
        provisioning, "_download", lambda url, dest, progress: _fake_archive(dest)
    )

    provisioning.install_ffmpeg()

    assert provisioning.ffmpeg_ready()
    assert (ffmpeg_bin / provisioning._FFMPEG_EXE).exists()
    assert (ffmpeg_bin / provisioning._FFPROBE_EXE).exists()


def test_install_ffmpeg_is_idempotent(components, monkeypatch):
    ffmpeg_bin, _ = components
    ffmpeg_bin.mkdir(parents=True)
    (ffmpeg_bin / provisioning._FFMPEG_EXE).write_bytes(b"x")
    (ffmpeg_bin / provisioning._FFPROBE_EXE).write_bytes(b"x")

    downloads = []
    monkeypatch.setattr(
        provisioning, "_download", lambda *args, **kwargs: downloads.append(args)
    )

    provisioning.install_ffmpeg()

    assert downloads == []


def test_ensure_components_survives_network_failure(components, monkeypatch):
    messages = []

    def boom(*args, **kwargs):
        raise OSError("sem rede")

    monkeypatch.setattr(provisioning, "install_ffmpeg", boom)
    monkeypatch.setattr(provisioning, "install_model", lambda *a, **k: None)

    assert provisioning.ensure_components(messages.append) is False
    assert any("FFmpeg" in message for message in messages)


def test_ensure_components_success(components, monkeypatch):
    monkeypatch.setattr(provisioning, "install_ffmpeg", lambda *a, **k: None)
    monkeypatch.setattr(provisioning, "install_model", lambda *a, **k: None)

    assert provisioning.ensure_components(lambda *_: None) is True
