"""Version parsing and the 24h update-check throttle."""

from livecut import updater


def test_parse_version_accepts_v_prefix_and_plain():
    assert updater.parse_version("v1.2.3") == (1, 2, 3)
    assert updater.parse_version("1.10.0") == (1, 10, 0)


def test_parse_version_returns_none_for_garbage():
    assert updater.parse_version("") is None
    assert updater.parse_version("sem versao") is None


def test_is_newer_compares_numerically_not_lexically():
    assert updater.is_newer("1.10.0", "1.9.9") is True
    assert updater.is_newer("v1.2.3", "1.2.3") is False
    assert updater.is_newer("1.2.2", "1.2.3") is False


def test_is_newer_is_safe_on_invalid_input():
    assert updater.is_newer("abc", "1.0.0") is False
    assert updater.is_newer("1.0.0", "abc") is False


def test_should_check_is_throttled_by_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVECUT_HOME", str(tmp_path))

    assert updater.should_check() is True

    updater.mark_checked()

    assert updater.should_check() is False
