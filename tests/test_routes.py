"""元信息路由测试:Flask test client + 临时视频文件。"""
import os
import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    """视频根目录与元信息库都指向临时目录。"""
    import vflow.config as config
    root = tmp_path / 'videos'
    root.mkdir()
    monkeypatch.setattr(config, 'VIDEO_ROOT', root)
    monkeypatch.setattr(config, 'META_DB', tmp_path / 'meta.db')
    from vflow import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        # 绕过 _require_login 蓝图门槛(本地软门,鉴权本身另有 meta 层测试)
        with c.session_transaction() as s:
            s['user'] = config.AUTH_USER
        yield c


def _vid(root, name):
    p = root / name
    p.write_bytes(b'x')
    return p


# ---- 改名 ----

def test_rename_success(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    r = client.post('/api/rename', json={'path': 'a.mp4', 'new_name': 'b'})
    assert r.status_code == 200
    assert r.get_json()['path'] == 'b.mp4'
    assert (root / 'b.mp4').exists()
    assert not (root / 'a.mp4').exists()


def test_rename_moves_tags(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    client.post('/api/tags', json={'path': 'a.mp4', 'tags': ['fav']})
    client.post('/api/rename', json={'path': 'a.mp4', 'new_name': 'b'})
    r = client.get('/api/meta?path=b.mp4')
    assert r.get_json()['tags'] == ['fav']


def test_rename_illegal_name(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    r = client.post('/api/rename', json={'path': 'a.mp4', 'new_name': 'a/b'})
    assert r.status_code == 400
    assert (root / 'a.mp4').exists()  # 未改动


def test_rename_illegal_dotdot(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    r = client.post('/api/rename', json={'path': 'a.mp4', 'new_name': '..'})
    assert r.status_code == 400


def test_rename_target_exists(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    _vid(root, 'b.mp4')
    r = client.post('/api/rename', json={'path': 'a.mp4', 'new_name': 'b'})
    assert r.status_code == 409


def test_rename_traversal(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    r = client.post('/api/rename', json={'path': '../a.mp4', 'new_name': 'b'})
    assert r.status_code == 403


# ---- 移动 ----

def test_move_success_and_tags_follow(client, tmp_path):
    root = tmp_path / 'videos'
    (root / 'sub').mkdir()
    _vid(root, 'a.mp4')
    client.post('/api/tags', json={'path': 'a.mp4', 'tags': ['fav']})
    r = client.post('/api/move', json={'path': 'a.mp4', 'dest_dir': 'sub'})
    assert r.status_code == 200
    assert r.get_json()['path'] == 'sub/a.mp4'
    assert (root / 'sub' / 'a.mp4').exists()
    assert client.get('/api/meta?path=sub/a.mp4').get_json()['tags'] == ['fav']


def test_move_dest_traversal(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    r = client.post('/api/move', json={'path': 'a.mp4', 'dest_dir': '../'})
    assert r.status_code == 403


def test_move_conflict(client, tmp_path):
    root = tmp_path / 'videos'
    (root / 'sub').mkdir()
    _vid(root, 'a.mp4')
    _vid(root / 'sub', 'a.mp4')
    r = client.post('/api/move', json={'path': 'a.mp4', 'dest_dir': 'sub'})
    assert r.status_code == 409


def test_move_dest_not_dir(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    _vid(root, 'notdir')  # 不是目录
    r = client.post('/api/move', json={'path': 'a.mp4', 'dest_dir': 'notdir'})
    assert r.status_code == 400


# ---- 新建文件夹 ----

def test_mkdir_success(client, tmp_path):
    root = tmp_path / 'videos'
    r = client.post('/api/mkdir', json={'path': 'newdir'})
    assert r.status_code == 200
    assert (root / 'newdir').is_dir()


def test_mkdir_exists(client, tmp_path):
    root = tmp_path / 'videos'
    (root / 'd').mkdir()
    r = client.post('/api/mkdir', json={'path': 'd'})
    assert r.status_code == 409


def test_mkdir_traversal(client, tmp_path):
    r = client.post('/api/mkdir', json={'path': '../escape'})
    assert r.status_code == 403


# ---- 标签 ----

def test_get_meta_empty(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    r = client.get('/api/meta?path=a.mp4')
    assert r.status_code == 200
    assert r.get_json()['tags'] == []


def test_post_then_get_tags(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')
    client.post('/api/tags', json={'path': 'a.mp4', 'tags': ['x', 'y']})
    assert client.get('/api/meta?path=a.mp4').get_json()['tags'] == ['x', 'y']


def test_get_tags_counts(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4'); _vid(root, 'b.mp4'); _vid(root, 'c.mp4')
    client.post('/api/tags', json={'path': 'a.mp4', 'tags': ['x']})
    client.post('/api/tags', json={'path': 'b.mp4', 'tags': ['x', 'y']})
    counts = {t['name']: t['count'] for t in client.get('/api/tags').get_json()}
    assert counts == {'x': 2, 'y': 1}


def test_get_videos_by_tag_cross_folder(client, tmp_path):
    root = tmp_path / 'videos'
    (root / 'sub').mkdir()
    _vid(root, 'a.mp4'); _vid(root / 'sub', 'c.mp4'); _vid(root, 'o.mp4')
    client.post('/api/tags', json={'path': 'a.mp4', 'tags': ['fav']})
    client.post('/api/tags', json={'path': 'sub/c.mp4', 'tags': ['fav']})
    client.post('/api/tags', json={'path': 'o.mp4', 'tags': ['other']})
    r = client.get('/api/videos?tag=fav')
    paths = {v['path'] for v in r.get_json()['videos']}
    assert paths == {'a.mp4', 'sub/c.mp4'}


def test_get_videos_skips_deleted(client, tmp_path):
    root = tmp_path / 'videos'
    a = _vid(root, 'a.mp4')
    client.post('/api/tags', json={'path': 'a.mp4', 'tags': ['fav']})
    os.remove(a)
    r = client.get('/api/videos?tag=fav')
    assert r.get_json()['videos'] == []


# ---- 相关视频(侧栏)----

def test_related_union_and_self_exclusion(client, tmp_path):
    root = tmp_path / 'videos'
    (root / 'sub').mkdir()
    _vid(root, 'a.mp4')              # 自身:tag=fav,shared
    _vid(root, 'b.mp4')              # 同标签 fav + 同文件夹
    _vid(root / 'sub', 'c.mp4')      # 同标签 shared,不同文件夹
    _vid(root, 'o.mp4')              # 无标签,仅同文件夹
    client.post('/api/tags', json={'path': 'a.mp4', 'tags': ['fav', 'shared']})
    client.post('/api/tags', json={'path': 'b.mp4', 'tags': ['fav']})
    client.post('/api/tags', json={'path': 'sub/c.mp4', 'tags': ['shared']})
    r = client.get('/api/related?path=a.mp4')
    d = r.get_json()
    assert {v['path'] for v in d['tagged']} == {'b.mp4', 'sub/c.mp4'}
    assert {v['path'] for v in d['folder']} == {'b.mp4', 'o.mp4'}


def test_related_missing_file_404(client, tmp_path):
    r = client.get('/api/related?path=nope.mp4')
    assert r.status_code == 404


def test_related_sorted_by_shared_tag_count(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4')   # 自身: fav, shared, later
    _vid(root, 'b.mp4')   # 共享 2 标签 (fav, shared)
    _vid(root, 'c.mp4')   # 共享 1 (fav)
    _vid(root, 'd.mp4')   # 共享 1 (later)
    client.post('/api/tags', json={'path': 'a.mp4', 'tags': ['fav', 'shared', 'later']})
    client.post('/api/tags', json={'path': 'b.mp4', 'tags': ['fav', 'shared']})
    client.post('/api/tags', json={'path': 'c.mp4', 'tags': ['fav']})
    client.post('/api/tags', json={'path': 'd.mp4', 'tags': ['later']})
    paths = [v['path'] for v in client.get('/api/related?path=a.mp4').get_json()['tagged']]
    assert paths == ['b.mp4', 'c.mp4', 'd.mp4']  # 共标签数降序,同分按名字 asc


def test_browse_attaches_tags(client, tmp_path):
    root = tmp_path / 'videos'
    _vid(root, 'a.mp4'); _vid(root, 'b.mp4')
    client.post('/api/tags', json={'path': 'a.mp4', 'tags': ['x']})
    data = client.get('/api/browse?path=').get_json()
    bypath = {v['path']: v.get('tags') for v in data['videos']}
    assert bypath['a.mp4'] == ['x']
    assert bypath['b.mp4'] == []


# ---- 流式播放(send_file 原生 Range 处理)----

def test_stream_full(client, tmp_path):
    root = tmp_path / 'videos'
    (root / 'a.mp4').write_bytes(b'0123456789')
    r = client.get('/api/stream/a.mp4')
    assert r.status_code == 200
    assert r.data == b'0123456789'


def test_stream_range_returns_206(client, tmp_path):
    root = tmp_path / 'videos'
    (root / 'a.mp4').write_bytes(b'0123456789')
    r = client.get('/api/stream/a.mp4', headers={'Range': 'bytes=2-5'})
    assert r.status_code == 206
    assert r.headers['Content-Range'] == 'bytes 2-5/10'
    assert r.data == b'2345'


def test_stream_missing_404(client, tmp_path):
    r = client.get('/api/stream/nope.mp4')
    assert r.status_code == 404
