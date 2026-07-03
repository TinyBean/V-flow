"""目录扫描。"""
import stat as stat_mod
from pathlib import Path

from . import config
from .security import safe_resolve


def video_obj(entry: Path) -> dict:
    """由一个视频文件路径构造与 /api/browse 同结构的视频对象。"""
    return _video_obj(entry, entry.stat())


def _video_obj(entry: Path, st) -> dict:
    """已持有 stat 结果时复用,省一次系统调用。"""
    rel = str(entry.relative_to(config.VIDEO_ROOT)).replace('\\', '/')
    return {
        'name': entry.stem,
        'path': rel,
        'ext': entry.suffix.lower().lstrip('.'),
        'size': st.st_size,
    }


def scan_dir(rel_dir: str):
    """扫描目录,返回子目录和视频文件列表(带元信息)。

    每个 entry 只 stat 一次:类型判断(S_ISREG)与大小都从同一次 stat 取。
    """
    target = safe_resolve(rel_dir)
    if not target.is_dir():
        return None

    rows = []
    try:
        for entry in target.iterdir():
            if entry.name.startswith('.') or entry.name == '$RECYCLE.BIN':
                continue
            try:
                st = entry.stat()
            except OSError:
                continue
            is_file = stat_mod.S_ISREG(st.st_mode)
            rows.append((entry.name.lower(), entry, st, is_file))
    except PermissionError:
        return {'error': '无权限访问该文件夹'}

    rows.sort(key=lambda r: (r[3], r[0]))   # 目录(False)在前,再按名字

    dirs, videos = [], []
    for _, entry, st, is_file in rows:
        if is_file:
            if entry.suffix.lower() in config.VIDEO_EXTS:
                videos.append(_video_obj(entry, st))
        else:
            rel = str(entry.relative_to(config.VIDEO_ROOT)).replace('\\', '/')
            dirs.append({'name': entry.name, 'path': rel})
    return {'dirs': dirs, 'videos': videos, 'count': len(videos)}
