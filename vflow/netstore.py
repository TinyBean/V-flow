"""网盘后端:经 OpenList 的 WebDAV 透明消费 115 / 夸克。

为什么走 WebDAV 而非 OpenList 原生 JSON API:WebDAV 把 115(302)和夸克
(本机代理)两种下载模式对 V-flow 统一了——V-flow 只对 /dav/<path> 发 GET,
urllib 自动跟随 302 拿到字节流,无需关心哪个盘走哪种模式,OpenList 的
per-provider 配置被透明保留。

用 stdlib urllib 而非 requests:项目刻意保持 3 依赖极简,urllib 足以覆盖
PROPFIND / GET+Range / 跟随 302 / Basic 认证,不必新增依赖。

<1G 预算:不缓存视频字节,只流式;网盘源禁 ffmpeg 缩略图(否则一个缩略图
= 下一个完整视频 + 触发 115 风控)。标签零改:网盘相对路径(net/...)直接当
meta key,与本地路径同处一个键空间。
"""
import base64
import mimetypes
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote, urlparse

from flask import Response

from . import config

_NS = {'d': 'DAV:'}
_PROPFIND_BODY = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<d:propfind xmlns:d="DAV:">'
    '<d:prop><d:resourcetype/><d:getcontentlength/><d:getlastmodified/></d:prop>'
    '</d:propfind>'
)

# WebDAV 根路径(从 OPENLIST_DAV 解析,如 'http://h:5244/dav' -> '/dav'),
# 用于把 PROPFIND 回传的 href 还原成 V-flow 的 net/... 路径。
_DAV_ROOT = urlparse(config.OPENLIST_DAV).path.rstrip('/')

# ponytail: 全局并发 ≤ NET_MAX_CONCURRENCY——115 风控硬线。只闸"请求建立"
# (签名 URL 获取),不闸长流(否则一个视频堵死全部)。urlopen 在 header 到达
# 即返回,签名调用就发生在这一刻,故 with 块退出后流式不再占名额。
_sem = threading.Semaphore(getattr(config, 'NET_MAX_CONCURRENCY', 2))
_timeout = getattr(config, 'NET_TIMEOUT', 30)
_UA = 'V-flow/1.0 (+local video browser)'


# ---------- 开关 / 路径判定 ----------

def enabled() -> bool:
    return bool(config.OPENLIST_USER and config.OPENLIST_DAV)


def is_net(rel: str) -> bool:
    rel = (rel or '').replace('\\', '/').strip()
    return rel == config.NET_PREFIX or rel.startswith(config.NET_PREFIX + '/')


def _norm(rel: str) -> str:
    return (rel or '').replace('\\', '/').strip()


def _dav_path(rel: str) -> str:
    """'net/115/m/x.mp4' -> '/115/m/x.mp4';'net' 或 '' -> '/'。"""
    rel = _norm(rel)
    rest = rel[len(config.NET_PREFIX):].lstrip('/')
    return '/' + rest if rest else '/'


def _base() -> str:
    return config.OPENLIST_DAV.rstrip('/')


def _auth_header() -> str:
    if not config.OPENLIST_USER:
        return ''
    tok = base64.b64encode(f"{config.OPENLIST_USER}:{config.OPENLIST_PASS}".encode()).decode()
    return f'Basic {tok}'


def _build_request(method: str, dav_path: str, extra=None, data=None) -> urllib.request.Request:
    headers = {'User-Agent': _UA}
    auth = _auth_header()
    if auth:
        headers['Authorization'] = auth
    if extra:
        headers.update(extra)
    # ponytail: 解码形态是稳定键(meta/display),仅在此 HTTP 边界 percent-encode。
    # safe='/' 保留路径分隔符;中文/空格/()等统一编码,服务端按 RFC 3986 解。
    url = _base() + quote(dav_path, safe='/')
    return urllib.request.Request(url, data=data, method=method, headers=headers)


# ---------- PROPFIND / 解析 ----------

def _propfind(dav_path: str, depth: str = '1'):
    """返回 [{href,name,is_dir,size}](含自身);404 返回 None。"""
    req = _build_request(
        'PROPFIND', dav_path,
        extra={'Depth': depth, 'Content-Type': 'application/xml; charset=utf-8'},
        data=_PROPFIND_BODY.encode(),
    )
    try:
        with _sem:
            resp = urllib.request.urlopen(req, timeout=_timeout)
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return _parse(body)


def _parse(xml_bytes: bytes):
    """解析 multistatus,返回 [{href,name,is_dir,size}],含自身条目。"""
    root = ET.fromstring(xml_bytes)
    out = []
    for resp in root.findall('d:response', _NS):
        href_el = resp.find('d:href', _NS)
        if href_el is None or not href_el.text:
            continue
        href = unquote(href_el.text)
        prop = resp.find('d:propstat/d:prop', _NS)
        is_dir = prop is not None and prop.find('d:resourcetype/d:collection', _NS) is not None
        size = 0
        if prop is not None:
            size_el = prop.find('d:getcontentlength', _NS)
            if size_el is not None and size_el.text and size_el.text.isdigit():
                size = int(size_el.text)
        out.append({'href': href, 'name': _last_seg(href), 'is_dir': is_dir, 'size': size})
    return out


def _last_seg(href: str) -> str:
    return href.rstrip('/').rsplit('/', 1)[-1]


def _href_to_rel(href: str) -> str:
    """OpenList href('/dav/115/m') -> V-flow rel('net/115/m')。"""
    p = href.rstrip('/')
    if _DAV_ROOT and p.startswith(_DAV_ROOT):
        p = p[len(_DAV_ROOT):]
    if not p:
        return config.NET_PREFIX
    return config.NET_PREFIX + p


# ---------- 对外 API(形状对齐 videos.scan_dir)----------

def list_dir(rel: str):
    """返回 {dirs,videos,count}(与本地 scan_dir 同构);不存在返回 None。"""
    if not enabled():
        return None
    entries = _propfind(_dav_path(rel))
    if entries is None:
        return None
    self_rel = _norm(rel) or config.NET_PREFIX
    children = [e for e in entries if _href_to_rel(e['href']) != self_rel]
    children.sort(key=lambda e: (not e['is_dir'], e['name'].lower()))
    dirs, videos = [], []
    for e in children:
        child_rel = _href_to_rel(e['href'])
        if e['is_dir']:
            # ponytail: 不递归 PROPFIND 算 video_count(N 次 RTT + 风控);按约定不计数
            dirs.append({'name': e['name'], 'path': child_rel,
                         'video_count': 0, 'subdir_count': 0})
        else:
            ext = e['name'].rsplit('.', 1)[-1].lower() if '.' in e['name'] else ''
            if ('.' + ext) in config.VIDEO_EXTS:
                stem = e['name'][:-(len(ext) + 1)] if ext else e['name']
                videos.append({'name': stem, 'path': child_rel, 'ext': ext, 'size': e['size']})
    return {'dirs': dirs, 'videos': videos, 'count': len(videos)}


def stat(rel: str):
    """单文件 PROPFIND Depth:0 -> {name,path,ext,size} 或 None(不存在/是目录)。"""
    if not enabled():
        return None
    entries = _propfind(_dav_path(rel), depth='0')
    if not entries:
        return None
    e = entries[0]
    if e['is_dir']:
        return None
    name = e['name']
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    stem = name[:-(len(ext) + 1)] if ext else name
    return {'name': stem, 'path': _norm(rel) or config.NET_PREFIX, 'ext': ext, 'size': e['size']}


def is_file(rel: str) -> bool:
    return stat(rel) is not None


def stream(rel: str, range_header=None) -> Response:
    """代理网盘视频:转发 Range,回流字节 + 关键响应头。

    urllib 跟随 302(115)或直读代理流(夸克);urlopen 在 header 到达即返回
    (签名 URL 获取在这一刻受 _sem 约束),随后流式产出字节。
    """
    extra = {'Range': range_header} if range_header else None
    req = _build_request('GET', _dav_path(rel), extra=extra)
    try:
        with _sem:
            upstream = urllib.request.urlopen(req, timeout=_timeout)
    except urllib.error.HTTPError as e:
        # ponytail: 带 body 防 Hypercorn 空 4xx 触发 UnexpectedMessageError(app.py _wsgi_nonempty_body 同款坑)
        return Response(f'netstore {e.code}', status=e.code, mimetype='text/plain')

    status = getattr(upstream, 'status', 200)

    def gen():
        try:
            while True:
                chunk = upstream.read(8192)
                if not chunk:
                    break
                yield chunk
        finally:
            upstream.close()

    resp = Response(gen(), status=status)
    for h in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges',
              'Last-Modified', 'ETag'):
        v = upstream.headers.get(h)
        if v is not None:
            resp.headers[h] = v
    # 115 返回 application/octet-stream,浏览器 <video> 可能拒播 -> 按扩展名补真实 mime
    ctype = resp.headers.get('Content-Type')
    if not ctype or ctype.split(';')[0].strip().lower() == 'application/octet-stream':
        guess, _ = mimetypes.guess_type(rel)
        if guess:
            resp.headers['Content-Type'] = guess
    return resp


def _selftest():
    """解析自检:非平凡逻辑留一个可跑的检查(纯解析,不打网络)。"""
    sample = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<d:multistatus xmlns:d="DAV:">'
        b'<d:response><d:href>/dav/115</d:href>'
        b'<d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype>'
        b'</d:prop></d:propstat></d:response>'
        b'<d:response><d:href>/dav/115/a.mp4</d:href>'
        b'<d:propstat><d:prop><d:resourcetype/>'
        b'<d:getcontentlength>12345678</d:getcontentlength>'
        b'</d:prop></d:propstat></d:response>'
        b'</d:multistatus>'
    )
    entries = _parse(sample)
    assert len(entries) == 2, entries
    assert entries[0]['is_dir'] and entries[0]['name'] == '115', entries[0]
    assert not entries[1]['is_dir'] and entries[1]['size'] == 12345678, entries[1]
    assert _href_to_rel('/dav/115') == 'net/115'
    assert _href_to_rel('/dav/115/a.mp4') == 'net/115/a.mp4'
    assert _dav_path('net/115/a.mp4') == '/115/a.mp4'
    assert _dav_path('net') == '/'
    print('netstore parse OK')


if __name__ == '__main__':
    _selftest()
