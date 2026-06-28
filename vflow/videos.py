"""目录扫描。"""
from pathlib import Path

from . import config
from .security import safe_resolve


def video_obj(entry: Path) -> dict:
    """由一个视频文件路径构造与 /api/browse 同结构的视频对象。"""
    stat = entry.stat()
    rel = str(entry.relative_to(config.VIDEO_ROOT)).replace('\\', '/')
    return {
        'name': entry.stem,
        'path': rel,
        'ext': entry.suffix.lower().lstrip('.'),
        'size': stat.st_size,
    }


def scan_dir(rel_dir: str):
    """扫描目录,返回子目录和视频文件列表(带元信息)。"""
    target = safe_resolve(rel_dir)
    if not target.is_dir():
        return None

    dirs, videos = [], []
    try:
        entries = sorted(target.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        return {'error': '无权限访问该文件夹'}

    for entry in entries:
        if entry.name.startswith('.') or entry.name == '$RECYCLE.BIN':
            continue
        if entry.is_dir():
            rel = str(entry.relative_to(config.VIDEO_ROOT)).replace('\\', '/')
            dirs.append({'name': entry.name, 'path': rel})
        elif entry.is_file() and entry.suffix.lower() in config.VIDEO_EXTS:
            videos.append(video_obj(entry))
    return {'dirs': dirs, 'videos': videos, 'count': len(videos)}
