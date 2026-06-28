"""路径遍历防护。"""
from pathlib import Path
from flask import abort
from . import config


def safe_resolve(rel_path: str) -> Path:
    """安全地把相对路径解析为根目录下的绝对路径,防止越界。"""
    if not rel_path or rel_path in ('.', '/', '\\'):
        return config.VIDEO_ROOT
    target = (config.VIDEO_ROOT / rel_path).resolve()
    try:
        target.relative_to(config.VIDEO_ROOT)
    except ValueError:
        abort(403)
    return target
