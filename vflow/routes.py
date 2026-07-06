"""所有路由(Blueprint)。"""
import mimetypes
import shutil

from flask import (
    Blueprint, render_template, send_file, jsonify, request,
    Response, abort, session, redirect, url_for
)

from . import config, meta
from .security import safe_resolve
from .videos import scan_dir, video_obj
from .thumbnails import get_thumb_path, _PLACEHOLDER_SVG, _maybe_warm_dir, warm_one

bp = Blueprint('vflow', __name__)


def _norm(p):
    """把相对路径规范成正斜杠字符串(与 scan_dir 输出的 rel 一致)。"""
    return (p or '').replace('\\', '/').strip()


# ---------- 登录门槛 ----------
# ponytail: blueprint 级 before_request —— 一次守卫盖住所有页面与 /api/*,
# 唯一豁免登录页本身。static 由 app 直出,不在 blueprint 范围,不拦截(无敏感内容)。
@bp.before_request
def _require_login():
    if session.get('user'):
        return None
    if request.endpoint == 'vflow.login':
        return None
    return redirect(url_for('vflow.login', next=request.full_path))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = (request.form.get('username') or '').strip()
        pwd = request.form.get('password') or ''
        if user == config.AUTH_USER and pwd == config.AUTH_PASS:
            session.permanent = True              # 浏览器重启后仍保持登录(默认 31 天)
            session['user'] = user
            # 仅允许站内相对跳转,防开放重定向
            nxt = request.args.get('next') or ''
            target = nxt if (nxt.startswith('/') and not nxt.startswith('//')) else url_for('vflow.index')
            return redirect(target)
        return render_template('login.html', error='用户名或密码错误'), 401
    return render_template('login.html', error=None)


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('vflow.login'))


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/play/<path:filepath>')
def play(filepath):
    """独立播放页。"""
    target = safe_resolve(filepath)
    if not target.is_file():
        abort(404)
    return render_template('player.html', path=filepath, name=target.stem)


@bp.route('/api/browse')
def api_browse():
    rel = request.args.get('path', '').strip()
    data = scan_dir(rel)
    if data is None:
        return jsonify({'error': '文件夹不存在'}), 404
    rel_path = rel.replace('\\', '/') if rel else ''
    crumbs = [{'name': '根目录', 'path': ''}]
    if rel_path:
        parts = rel_path.split('/')
        for i in range(1, len(parts) + 1):
            crumbs.append({'name': parts[i-1], 'path': '/'.join(parts[:i])})
    data['breadcrumbs'] = crumbs
    data['current'] = rel_path
    # 附加每个视频的标签,供本文件夹标签筛选
    tag_map = meta.tags_for_paths([v['path'] for v in data.get('videos', [])])
    for v in data.get('videos', []):
        v['tags'] = tag_map.get(v['path'], [])
    _maybe_warm_dir(rel_path, data.get('videos', []))
    return jsonify(data)


@bp.route('/api/stream/<path:filepath>')
def api_stream(filepath):
    """视频流;send_file 的 conditional=True 原生处理 Range(206)/全量(200)。"""
    target = safe_resolve(filepath)
    if not target.is_file():
        abort(404)
    mime, _ = mimetypes.guess_type(str(target))
    return send_file(target, conditional=True, mimetype=mime or 'video/mp4')


@bp.route('/api/thumb/<path:filepath>')
def api_thumb(filepath):
    target = safe_resolve(filepath)
    if not target.is_file():
        abort(404)
    thumb = get_thumb_path(target)
    if not thumb.exists():
        warm_one(filepath)                       # 后台生成;前端拿到占位后会重试
        svg = Response(_PLACEHOLDER_SVG, mimetype='image/svg+xml')
        svg.headers['Cache-Control'] = 'no-store'   # 占位不缓存,重试必走网络
        return svg
    resp = send_file(str(thumb), mimetype='image/jpeg', conditional=True)
    resp.headers['Cache-Control'] = 'public, max-age=604800, immutable'
    return resp


# ---------- 元信息:标签 / 改名 / 移动 / 新建文件夹 ----------

@bp.route('/api/meta')
def api_meta():
    """单视频信息(当前标签)。"""
    rel = _norm(request.args.get('path'))
    safe_resolve(rel)                       # 越界 -> 403
    return jsonify({'tags': meta.get_tags(rel)})


@bp.route('/api/tags')
def api_tags_get():
    """全部标签 + 引用计数,供全局标签栏。"""
    return jsonify(meta.all_tags())


@bp.route('/api/tags', methods=['POST'])
def api_tags_set():
    """设置某视频标签(全量覆盖)。"""
    data = request.get_json(silent=True) or {}
    rel = _norm(data.get('path'))
    safe_resolve(rel)
    tags = data.get('tags')
    if not isinstance(tags, list):
        return jsonify({'error': 'tags 必须是数组'}), 400
    meta.set_tags(rel, tags)
    return jsonify({'ok': True})


@bp.route('/api/videos')
def api_videos():
    """某标签下所有视频(跨库平铺),返回与 /api/browse 同结构的视频对象。

    文件已被外部删除的条目跳过,并顺手清掉这些幽灵行(读时自愈),
    使 /api/tags 的计数与这里的筛选结果保持一致。
    """
    tag = (request.args.get('tag') or '').strip()
    videos, missing = [], []
    for p in meta.videos_for_tag(tag):
        target = safe_resolve(p)
        if target.is_file():
            videos.append(video_obj(target))
        else:
            missing.append(p)
    if missing:
        meta.prune_paths(missing)
    return jsonify({'videos': videos, 'count': len(videos)})


@bp.route('/api/related')
def api_related():
    """播放页侧栏:同标签(并集,按共标签数降序)+ 同文件夹视频,排除自身。

    同标签:当前视频各标签 videos_for_tag 的并集;每个候选累计与当前视频
    共享的标签数,按 (-共享数, 名字) 排序,最相关的在上。跳过已删除文件
    (读时自愈,同 /api/videos)。同文件夹:父目录 scan_dir 的视频减自身。
    """
    rel = _norm(request.args.get('path'))
    src = safe_resolve(rel)
    if not src.is_file():
        abort(404)

    shares = {}  # 候选路径 -> 与当前视频共享的标签数
    for t in meta.get_tags(rel):
        for p in meta.videos_for_tag(t):
            if p != rel:
                shares[p] = shares.get(p, 0) + 1

    tagged, missing = [], []
    for p, n in shares.items():
        target = safe_resolve(p)
        if target.is_file():
            tagged.append((n, video_obj(target)))
        else:
            missing.append(p)
    if missing:
        meta.prune_paths(missing)
    tagged.sort(key=lambda x: (-x[0], x[1]['name']))
    tagged = [v for _, v in tagged]

    parent_rel = '/'.join(rel.split('/')[:-1])
    folder = []
    data = scan_dir(parent_rel)
    if data and data.get('videos'):
        folder = [v for v in data['videos'] if v['path'] != rel]

    return jsonify({'tagged': tagged, 'folder': folder})


@bp.route('/api/rename', methods=['POST'])
def api_rename():
    """重命名文件(扩展名不变)+ relocate_path。"""
    data = request.get_json(silent=True) or {}
    rel = _norm(data.get('path'))
    new_name = (data.get('new_name') or '').strip()
    if not new_name or '/' in new_name or '\\' in new_name or new_name in ('.', '..'):
        return jsonify({'error': '名称不能为空,且不能含 / \\ 或为 . ..'}), 400
    src = safe_resolve(rel)
    if not src.is_file():
        abort(404)
    new_path = src.with_name(new_name + src.suffix)
    if new_path.exists():
        return jsonify({'error': '已存在'}), 409
    try:
        src.rename(new_path)
    except OSError:
        return jsonify({'error': '重命名失败:文件可能被占用或跨盘符'}), 500
    new_rel = str(new_path.relative_to(config.VIDEO_ROOT)).replace('\\', '/')
    meta.relocate_path(rel, new_rel)
    return jsonify({'ok': True, 'path': new_rel, 'name': new_path.stem})


@bp.route('/api/move', methods=['POST'])
def api_move():
    """移动文件到目标文件夹 + relocate_path。"""
    data = request.get_json(silent=True) or {}
    rel = _norm(data.get('path'))
    src = safe_resolve(rel)
    if not src.is_file():
        abort(404)
    dest_dir = safe_resolve(_norm(data.get('dest_dir')))
    if not dest_dir.is_dir():
        return jsonify({'error': '目标文件夹不存在'}), 400
    new_path = dest_dir / src.name
    if new_path.exists():
        return jsonify({'error': '已存在'}), 409
    try:
        shutil.move(str(src), str(new_path))
    except OSError:
        return jsonify({'error': '移动失败'}), 500
    new_rel = str(new_path.relative_to(config.VIDEO_ROOT)).replace('\\', '/')
    meta.relocate_path(rel, new_rel)
    return jsonify({'ok': True, 'path': new_rel, 'name': src.stem})


@bp.route('/api/mkdir', methods=['POST'])
def api_mkdir():
    """新建文件夹。"""
    data = request.get_json(silent=True) or {}
    rel = _norm(data.get('path'))
    target = safe_resolve(rel)
    if target == config.VIDEO_ROOT:
        return jsonify({'error': '名称不能为空'}), 400
    if target.exists():
        return jsonify({'error': '已存在'}), 409
    try:
        target.mkdir(parents=True)
    except OSError:
        return jsonify({'error': '新建文件夹失败'}), 500
    return jsonify({'ok': True, 'path': str(target.relative_to(config.VIDEO_ROOT)).replace('\\', '/')})


@bp.route('/api/delete', methods=['POST'])
def api_delete():
    """删除视频:文件 + 缩略图 + 标签行,一处不留。"""
    data = request.get_json(silent=True) or {}
    rel = _norm(data.get('path'))
    src = safe_resolve(rel)
    if not src.is_file():
        abort(404)
    try:
        src.unlink()
    except OSError:
        return jsonify({'error': '删除失败:文件可能被占用(关闭播放该视频的标签页后重试)'}), 500
    get_thumb_path(src).unlink(missing_ok=True)
    meta.prune_paths([rel])
    return jsonify({'ok': True})
