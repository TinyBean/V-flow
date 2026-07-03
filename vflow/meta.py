"""元信息层:SQLite 存视频标签。

schema 极简——路径即稳定锚点(改名/移动即真实改路径),
改名/移动时在一个事务里把 video_tags 的路径键改掉,标签自动跟随。
"""
import contextlib
import sqlite3

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tags (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS video_tags (
  video_path TEXT NOT NULL,
  tag_id     INTEGER NOT NULL,
  PRIMARY KEY (video_path, tag_id),
  FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
"""


def init_db():
    """建表、设 WAL 与外键。在 create_app() 中调用一次;幂等。"""
    conn = sqlite3.connect(str(config.META_DB))
    try:
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA foreign_keys = ON')
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextlib.contextmanager
def get_db():
    """每次操作新建连接:开 → 设外键 pragma → yield → 关。

    本地单用户 + Flask threaded=True 下无跨线程共享状态竞态。
    WAL 模式已由 init_db 持久化到库头,无需每连接重设。
    """
    conn = sqlite3.connect(str(config.META_DB))
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
    finally:
        conn.close()


def get_tags(video_path: str) -> list:
    """返回某视频的全部标签名(按名排序)。"""
    with get_db() as conn:
        rows = conn.execute(
            '''SELECT t.name FROM tags t
               JOIN video_tags v ON v.tag_id = t.id
               WHERE v.video_path = ?
               ORDER BY t.name''',
            (video_path,)).fetchall()
    return [r[0] for r in rows]


def set_tags(video_path: str, tags: list):
    """全量覆盖该视频标签;清理变为无引用的孤儿标签。

    标签名大小写不敏感唯一:已存在的标签(任意大小写)被复用,
    规范名保留首次写入的拼写。
    """
    names = list(dict.fromkeys(t.strip() for t in tags if t and t.strip()))
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('DELETE FROM video_tags WHERE video_path = ?', (video_path,))
        for name in names:
            cur.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (name,))
            tag_id = cur.execute(
                'SELECT id FROM tags WHERE name = ?', (name,)).fetchone()[0]
            cur.execute(
                'INSERT OR IGNORE INTO video_tags (video_path, tag_id) VALUES (?, ?)',
                (video_path, tag_id))
        # 级联删除不触达 tags 表(只删关联),这里清掉无引用的标签
        cur.execute(
            'DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM video_tags)')
        conn.commit()


def all_tags() -> list:
    """全部标签及引用计数(仅返回仍被引用的),供全局标签栏。"""
    with get_db() as conn:
        rows = conn.execute(
            '''SELECT t.name, COUNT(v.video_path)
               FROM tags t
               JOIN video_tags v ON v.tag_id = t.id
               GROUP BY t.id
               ORDER BY t.name''').fetchall()
    return [{'name': r[0], 'count': r[1]} for r in rows]


def videos_for_tag(name: str) -> list:
    """该标签下所有视频的相对路径(跨库),大小写不敏感。"""
    with get_db() as conn:
        rows = conn.execute(
            '''SELECT v.video_path FROM video_tags v
               JOIN tags t ON t.id = v.tag_id
               WHERE t.name = ?''',
            (name,)).fetchall()
    return [r[0] for r in rows]


def tags_for_paths(paths: list) -> dict:
    """批量取多个视频的标签,返回 {video_path: [tag,...]}(仅含有标签的)。"""
    if not paths:
        return {}
    placeholders = ','.join('?' * len(paths))
    with get_db() as conn:
        rows = conn.execute(
            f'''SELECT v.video_path, t.name FROM video_tags v
                JOIN tags t ON t.id = v.tag_id
                WHERE v.video_path IN ({placeholders})
                ORDER BY v.video_path, t.name''',
            list(paths)).fetchall()
    out = {}
    for p, name in rows:
        out.setdefault(p, []).append(name)
    return out


def relocate_path(old_rel: str, new_rel: str):
    """改名/移动成功后原子改键:把旧路径的标签搬到新路径。

    目标路径若残留幽灵行(外部删除遗留),先清掉再搬——否则 PK 冲突会被
    UPDATE OR IGNORE 吞掉,标签悄悄丢失。调用方已保证新路径无同名文件,
    故 new_rel 上的行必是幽灵,删它绝对安全。
    """
    with get_db() as conn:
        conn.execute('DELETE FROM video_tags WHERE video_path = ?', (new_rel,))
        conn.execute(
            'UPDATE video_tags SET video_path = ? WHERE video_path = ?',
            (new_rel, old_rel))
        conn.execute('DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM video_tags)')
        conn.commit()


def prune_paths(paths: list):
    """删除这些路径的 video_tags 行 + 随之产生的孤儿标签。

    文件已从磁盘消失(外部删除/移动遗留)时,由调用方发现并传入,使计数与
    筛选一致。对应 routes.api_videos 的读时自愈。
    """
    if not paths:
        return
    placeholders = ','.join('?' * len(paths))
    with get_db() as conn:
        conn.execute(
            f'DELETE FROM video_tags WHERE video_path IN ({placeholders})',
            list(paths))
        conn.execute('DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM video_tags)')
        conn.commit()
