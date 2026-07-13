"""配置:视频根目录、常量、缓存目录路径。"""
import os
import sys
from pathlib import Path

# 全局视频根目录(启动时由 set_video_root 设置)
VIDEO_ROOT = Path.home()

VIDEO_EXTS = {'.mp4', '.mkv', '.webm', '.avi', '.mov', '.m4v',
              '.flv', '.wmv', '.mpg', '.mpeg', '.ts', '.3gp'}

THUMB_WIDTH = 480

# 缓存目录放在工程根(vflow 的上一级)
THUMB_DIR = Path(__file__).resolve().parent.parent / '.thumbs'
THUMB_DIR.mkdir(exist_ok=True)

# 元信息数据库(标签等),与 .thumbs 同级的 dot-目录约定
META_DIR = Path(__file__).resolve().parent.parent / '.meta'
META_DIR.mkdir(exist_ok=True)
META_DB = META_DIR / 'meta.db'

WARM_BATCH = 60

# ---------- 登录(本地软门槛;凭据写死)----------
# ponytail: 写死凭据 + 固定 SECRET_KEY —— 本地单用户、够用;要多用户/改密/注销再上数据库与口令哈希
AUTH_USER = 'admin'
AUTH_PASS = 'vflow123'
SECRET_KEY = 'vflow-local-secret-please-change'   # 仅用于 session 签名


# ---------- 网盘(经 OpenList WebDAV 桥接 115 / 夸克)----------
# ponytail: <1G 预算 → 只流式不缓存视频字节;网盘源禁 ffmpeg 缩略图。
# 全部支持 env 覆盖(Docker 友好);OPENLIST_USER 留空则网盘功能关闭。
OPENLIST_DAV = os.environ.get('OPENLIST_DAV', 'http://192.168.31.223:5244/dav')
OPENLIST_USER = os.environ.get('OPENLIST_USER', '')   # OpenList 账号(留空=禁用网盘)
OPENLIST_PASS = os.environ.get('OPENLIST_PASS', '')
NET_PREFIX = os.environ.get('NET_PREFIX', 'net')       # V-flow 路径空间里的网盘虚拟挂载点
NET_MAX_CONCURRENCY = 2   # 115 风控硬线:网盘请求全局并发上限
NET_TIMEOUT = 30          # 网盘请求超时(秒;仅作用于建连+首字节,不限长流)


def set_video_root(path: str):
    """设置并校验视频根目录。"""
    global VIDEO_ROOT
    p = Path(path).expanduser().resolve()
    if not p.exists():
        print(f'[错误] 路径不存在: {p}')
        sys.exit(1)
    if not p.is_dir():
        print(f'[错误] 不是文件夹: {p}')
        sys.exit(1)
    VIDEO_ROOT = p
    print(f'[信息] 视频根目录: {VIDEO_ROOT}')
