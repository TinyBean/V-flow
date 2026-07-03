"""缩略图生成 + 后台预热。"""
import hashlib
import threading
import subprocess
import concurrent.futures
from pathlib import Path

from . import config
from .security import safe_resolve

# ponytail: 6 并发——翻页时一批未命中缩略图同时进来,3 太少要排队;6 在本地 CPU 上仍从容
_thumb_pool = concurrent.futures.ThreadPoolExecutor(max_workers=6, thread_name_prefix='thumb')
_warmed_dirs = set()
_inflight = set()
_inflight_lock = threading.Lock()


def get_thumb_path(video_path: Path) -> Path:
    key = hashlib.md5(str(video_path).encode()).hexdigest()[:16]
    return config.THUMB_DIR / f'{key}.jpg'


def generate_thumbnail(video_path: Path, thumb_path: Path) -> bool:
    """用 ffmpeg 生成缩略图,成功返回 True。"""
    if thumb_path.exists():
        return True
    try:
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
            capture_output=True, text=True, timeout=15
        )
        duration = float(probe.stdout.strip() or '0')
    except Exception:
        duration = 0
    seek = min(max(duration * 0.1, 1), 3) if duration > 0 else 3
    cmd = [
        'ffmpeg', '-y', '-ss', f'{seek:.1f}', '-i', str(video_path),
        '-frames:v', '1', '-vf', f'scale={config.THUMB_WIDTH}:-2',
        '-q:v', '4', str(thumb_path)
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=30)
        return r.returncode == 0 and thumb_path.exists()
    except Exception:
        return False


def warm_one(rel_path: str):
    """后台生成单个视频缩略图;已存在或正在生成则跳过。

    _inflight 去重保证同一文件任意时刻只有一个 ffmpeg 在写它,避免并发写坏。
    """
    target = safe_resolve(rel_path)
    if not target.is_file():
        return
    thumb = get_thumb_path(target)
    if thumb.exists():
        return
    with _inflight_lock:
        if rel_path in _inflight:
            return
        _inflight.add(rel_path)

    def task():
        try:
            generate_thumbnail(target, thumb)
        finally:
            with _inflight_lock:
                _inflight.discard(rel_path)

    _thumb_pool.submit(task)


def _maybe_warm_dir(rel, videos):
    """每个目录只预热首批(首页可见),其余靠前端按需触发 warm_one。"""
    if not videos or rel in _warmed_dirs:
        return
    _warmed_dirs.add(rel)
    for v in videos[:config.WARM_BATCH]:
        warm_one(v['path'])


def _placeholder_svg() -> str:
    """1x1 透明占位:naturalWidth<100 是前端识别「生成中」的暗号;
    真正的字母占位由前端的 .tile__monogram 层显示。"""
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
