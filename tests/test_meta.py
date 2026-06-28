"""元信息层(标签)单元测试。沿用 test_security 的 tmp_path + monkeypatch 风格。"""
import pytest


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """把元信息库指向临时目录并初始化。"""
    import vflow.config as config
    import vflow.meta as meta
    monkeypatch.setattr(config, 'META_DB', tmp_path / 'meta.db')
    meta.init_db()
    return meta


def test_set_get_tags_roundtrip(tmp_db):
    meta = tmp_db
    meta.set_tags('a.mp4', ['动作', '喜剧'])
    assert meta.get_tags('a.mp4') == ['动作', '喜剧']


def test_set_tags_is_full_overwrite(tmp_db):
    meta = tmp_db
    meta.set_tags('a.mp4', ['x', 'y'])
    meta.set_tags('a.mp4', ['y', 'z'])
    assert meta.get_tags('a.mp4') == ['y', 'z']


def test_tags_case_insensitive_dedup(tmp_db):
    meta = tmp_db
    # 同一标签不同大小写 -> 唯一一行,首拼法为规范名
    meta.set_tags('a.mp4', ['Action', 'action', 'ACTION'])
    tags = meta.get_tags('a.mp4')
    assert len(tags) == 1
    assert tags[0].lower() == 'action'


def test_tag_canonicalized_across_videos(tmp_db):
    meta = tmp_db
    meta.set_tags('a.mp4', ['Action'])
    meta.set_tags('b.mp4', ['action'])   # 复用已有规范名
    all_tags = {t['name']: t['count'] for t in meta.all_tags()}
    assert list(all_tags.keys()) == ['Action']
    assert all_tags['Action'] == 2


def test_set_tags_cleans_orphans(tmp_db):
    meta = tmp_db
    meta.set_tags('a.mp4', ['x', 'y'])
    meta.set_tags('b.mp4', ['x'])
    # y 仅 a 引用,a 清空后应消失;x 仍被 b 引用,保留
    meta.set_tags('a.mp4', [])
    counts = {t['name']: t['count'] for t in meta.all_tags()}
    assert counts == {'x': 1}


def test_all_tags_counts(tmp_db):
    meta = tmp_db
    meta.set_tags('a.mp4', ['x', 'y'])
    meta.set_tags('b.mp4', ['x'])
    meta.set_tags('c.mp4', ['y', 'z'])
    counts = {t['name']: t['count'] for t in meta.all_tags()}
    assert counts == {'x': 2, 'y': 2, 'z': 1}


def test_relocate_path_moves_tags(tmp_db):
    meta = tmp_db
    meta.set_tags('a.mp4', ['x', 'y'])
    meta.relocate_path('a.mp4', 'sub/b.mp4')
    # 标签跟随到新路径,旧路径无残留
    assert meta.get_tags('a.mp4') == []
    assert meta.get_tags('sub/b.mp4') == ['x', 'y']
    # 计数不变
    counts = {t['name']: t['count'] for t in meta.all_tags()}
    assert counts == {'x': 1, 'y': 1}


def test_get_tags_unknown_path_empty(tmp_db):
    meta = tmp_db
    assert meta.get_tags('nope.mp4') == []


def test_videos_for_tag_cross_library(tmp_db):
    meta = tmp_db
    meta.set_tags('a.mp4', ['fav'])
    meta.set_tags('sub/b.mp4', ['fav'])
    meta.set_tags('c.mp4', ['other'])
    paths = set(meta.videos_for_tag('fav'))
    assert paths == {'a.mp4', 'sub/b.mp4'}


def test_tags_for_paths_bulk(tmp_db):
    meta = tmp_db
    meta.set_tags('a.mp4', ['x', 'y'])
    meta.set_tags('b.mp4', ['x'])
    m = meta.tags_for_paths(['a.mp4', 'b.mp4', 'c.mp4'])
    assert m == {'a.mp4': ['x', 'y'], 'b.mp4': ['x']}
    assert meta.tags_for_paths([]) == {}
