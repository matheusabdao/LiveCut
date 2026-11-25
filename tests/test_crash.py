"""Crash diagnostics: the bundle contents and the GitHub issue link."""

import sys
import zipfile

from livecut import crash


def _captured_error(exc=None):
    exc = exc or ValueError("boom")
    try:
        raise exc
    except type(exc):
        return sys.exc_info()


def test_build_bundle_writes_expected_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVECUT_HOME", str(tmp_path))
    exc_type, exc_value, exc_tb = _captured_error()

    bundle = crash.build_bundle(exc_type, exc_value, exc_tb)

    assert bundle.exists()
    assert bundle.name.startswith("crash_")
    assert bundle.parent == tmp_path / "logs"

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert {"resumo.txt", "erro.txt", "log.txt"} <= names
        resumo = archive.read("resumo.txt").decode("utf-8")
        erro = archive.read("erro.txt").decode("utf-8")

    assert "Versao" in resumo
    assert "Componentes" in resumo
    assert "ValueError" in erro


def test_issue_url_targets_the_github_issue_form(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVECUT_HOME", str(tmp_path))
    exc_type, exc_value, exc_tb = _captured_error()
    bundle = crash.build_bundle(exc_type, exc_value, exc_tb)

    url = crash.issue_url(bundle, "Traceback\nValueError: boom")

    assert url.startswith(f"https://github.com/{crash.REPO}/issues/new?")
    assert "title=" in url
    assert "body=" in url


def test_latest_bundle_returns_none_when_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVECUT_HOME", str(tmp_path))

    assert crash.latest_bundle() is None
