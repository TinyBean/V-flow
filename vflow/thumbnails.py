"""缩略图生成 + 后台预热。"""
import hashlib
import subprocess
import concurrent.futures
from pathlib import Path

from . import config
from .security import safe_resolve

_thumb_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix='thumb')
_warmed_dirs = set()


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


def _placeholder_svg(name: str) -> str:
    short = (name[:20] + '…') if len(name) > 20 else name
    initial = (name.strip()[:1] or '·').upper()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270">
      <rect width="100%" height="100%" fill="#211f23"/>
      <text x="50%" y="47%" font-family="-apple-system,Segoe UI,Roboto,sans-serif"
            font-size="64" font-weight="600" fill="#d8d6d2" text-anchor="middle">{initial}</text>
      <text x="50%" y="68%" font-family="-apple-system,Segoe UI,Roboto,sans-serif"
            font-size="17" fill="#8a8786" text-anchor="middle">{short}</text>
    </svg>'''


def _warm_thumbnails(paths):
    for p in paths:
        try:
            target = safe_resolve(p)
            if target.is_file():
                thumb = get_thumb_path(target)
                if not thumb.exists():
                    generate_thumbnail(target, thumb)
        except Exception:
            pass


def _maybe_warm_dir(rel, videos):
    """每个目录只预热首批(首页可见),其余靠前端 lazy 按需生成。"""
    if not videos or rel in _warmed_dirs:
        return
    _warmed_dirs.add(rel)
    _thumb_pool.submit(_warm_thumbnails, [v['path'] for v in videos[:config.WARM_BATCH]])
