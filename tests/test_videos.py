"""scan_dir 子目录统计字段测试。"""
import pytest


@pytest.fixture
def root(tmp_path, monkeypatch):
    import vflow.config as config
    r = tmp_path / 'videos'
    r.mkdir()
    monkeypatch.setattr(config, 'VIDEO_ROOT', r)
    return r


def test_scan_dir_counts_direct_children(root):
    """子目录的 video_count / subdir_count 只数直接子层。"""
    (root / '电影').mkdir()
    (root / '电影' / 'a.mp4').write_bytes(b'x')
    (root / '电影' / 'b.mkv').write_bytes(b'x')
    (root / '电影' / 'notavid.txt').write_bytes(b'x')
    (root / '电影' / '子夹').mkdir()
    (root / '电影' / '子夹' / 'deep.mp4').write_bytes(b'x')  # 不计入

    from vflow.videos import scan_dir
    data = scan_dir('')
    d = data['dirs'][0]
    assert d['name'] == '电影'
    assert d['video_count'] == 2
    assert d['subdir_count'] == 1


def test_scan_dir_counts_empty_subdir(root):
    """空文件夹计数为 0 / 0。"""
    (root / '空夹').mkdir()
    from vflow.videos import scan_dir
    d = scan_dir('')['dirs'][0]
    assert d['video_count'] == 0
    assert d['subdir_count'] == 0


def test_scan_dir_ignores_hidden(root):
    """隐藏文件 / $RECYCLE.BIN 不计入。"""
    (root / 'f').mkdir()
    (root / 'f' / '.hidden.mp4').write_bytes(b'x')
    (root / 'f' / '$RECYCLE.BIN').mkdir()
    (root / 'f' / 'real.mp4').write_bytes(b'x')
    from vflow.videos import scan_dir
    d = scan_dir('')['dirs'][0]
    assert d['video_count'] == 1
    assert d['subdir_count'] == 0
