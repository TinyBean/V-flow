import pytest
from pathlib import Path
from werkzeug.exceptions import Forbidden


def test_safe_resolve_normal(tmp_path, monkeypatch):
    import vflow.config as config
    import vflow.security as security
    (tmp_path / 'a.mp4').touch()
    monkeypatch.setattr(config, 'VIDEO_ROOT', tmp_path)
    assert security.safe_resolve('a.mp4') == (tmp_path / 'a.mp4').resolve()


def test_safe_resolve_root(tmp_path, monkeypatch):
    import vflow.config as config
    import vflow.security as security
    monkeypatch.setattr(config, 'VIDEO_ROOT', tmp_path)
    assert security.safe_resolve('') == tmp_path
    assert security.safe_resolve('.') == tmp_path


def test_safe_resolve_traversal_aborts(tmp_path, monkeypatch):
    import vflow.config as config
    import vflow.security as security
    monkeypatch.setattr(config, 'VIDEO_ROOT', tmp_path)
    with pytest.raises(Forbidden):
        security.safe_resolve('../secret')
    with pytest.raises(Forbidden):
        security.safe_resolve('sub/../../etc/passwd')
