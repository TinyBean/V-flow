"""meta 层幽灵行修复的复现测试 —— 纯 assert,无框架。
直接 `python test_meta.py` 运行。覆盖:
  1. relocate_path 目标路径有幽灵行时,标签仍能跟过去(不被 UPDATE OR IGNORE 吞掉)
  2. relocate_path 目标为空时,所有标签照搬(回归护栏,防 DELETE-first 误伤)
  3. prune_paths 清指定路径关联行 + 孤儿标签(api_videos 读时自愈用)
"""
import pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from vflow import config, meta

# ponytail: 把库指到临时文件,绝不碰真实 .meta/meta.db
_tmp = pathlib.Path(tempfile.mkdtemp())
config.META_DB = _tmp / 'test.db'
meta.init_db()


def reset():
    with meta.get_db() as conn:
        conn.execute('DELETE FROM video_tags')
        conn.execute('DELETE FROM tags')
        conn.commit()


def tag_names():
    with meta.get_db() as conn:
        return {r[0] for r in conn.execute('SELECT name FROM tags')}


def test_relocate_clears_ghost_at_destination():
    reset()
    meta.set_tags('old.mp4', ['fav'])
    meta.set_tags('new.mp4', ['fav'])          # new 的幽灵行(其文件已外部删除)
    meta.relocate_path('old.mp4', 'new.mp4')
    assert meta.get_tags('old.mp4') == [], '源路径不应残留行'
    assert meta.get_tags('new.mp4') == ['fav'], '标签应跟到新路径'


def test_relocate_keeps_all_tags_when_destination_empty():
    reset()
    meta.set_tags('old.mp4', ['fav', 'work'])
    meta.relocate_path('old.mp4', 'new.mp4')
    assert meta.get_tags('old.mp4') == []
    assert meta.get_tags('new.mp4') == ['fav', 'work'], '所有标签都应跟过去'


def test_prune_paths_removes_rows_and_orphan_tags():
    reset()
    meta.set_tags('a.mp4', ['fav', 'work'])
    meta.set_tags('b.mp4', ['fav'])
    meta.prune_paths(['a.mp4'])                # a 的文件没了,清掉
    assert meta.get_tags('a.mp4') == []
    assert meta.get_tags('b.mp4') == ['fav']
    assert tag_names() == {'fav'}, 'work 无引用应作为孤儿清掉,fav 仍被 b 引用而保留'


def main():
    for fn in (test_relocate_clears_ghost_at_destination,
               test_relocate_keeps_all_tags_when_destination_empty,
               test_prune_paths_removes_rows_and_orphan_tags):
        fn()
        print('PASS', fn.__name__)
    print('ALL PASS')


if __name__ == '__main__':
    main()
