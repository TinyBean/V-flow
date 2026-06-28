"""V-flow 入口:解析参数、设置视频根目录、以 HTTP/2 + 本地 HTTPS 启动服务。"""
import sys
import argparse
import asyncio
import datetime
import ipaddress
import threading
from pathlib import Path

# Windows GBK 控制台打印 emoji/中文会崩,强制 UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

from vflow import create_app
from vflow.config import set_video_root


def _ensure_self_signed_cert(cert_path: Path, key_path: Path):
    """生成本地自签证书(localhost + 127.0.0.1,有效期 10 年);已存在则跳过。

    浏览器只在 TLS 下才允许 HTTP/2,所以本地 HTTPS 是开启多路复用的前提。
    """
    if cert_path.exists() and key_path.exists():
        return
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'vflow-local')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName('localhost'),
                x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
            ]), critical=False)
            .sign(key, hashes.SHA256()))
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _wsgi_nonempty_body(app):
    """兜底 Hypercorn WSGI→ASGI 适配器 bug:run_app 把 http.response.start 推迟到第一个
    body chunk 才发,空 body 响应(304/204)因此不发 start,随后 handle_http 收尾的
    http.response.body 抛 UnexpectedMessageError。/api/stream 的 send_file(conditional=True)
    在 <video> 缓存校验时回 304 空响应正中此 bug。这里保证 start_response 后至少产出一个
    空 chunk(对 304 语义无影响)。"""
    def wrapper(environ, start_response):
        started = False

        def _sr(status, headers, exc_info=None):
            nonlocal started
            started = True
            return start_response(status, headers, exc_info)

        produced = False
        for chunk in app(environ, _sr):
            produced = True
            yield chunk
        if started and not produced:
            yield b""

    return wrapper


def main():
    parser = argparse.ArgumentParser(description='V-flow 本地视频浏览器')
    parser.add_argument('--dir', '-d', default=str(Path.home()), help='视频文件夹路径')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址')
    parser.add_argument('--port', '-p', type=int, default=5000, help='监听端口')
    parser.add_argument('--open', '-o', action='store_true', help='自动打开浏览器')
    args = parser.parse_args()

    set_video_root(args.dir)
    app = create_app()

    try:
        from hypercorn.config import Config
        from hypercorn.asyncio import serve as hc_serve
        from hypercorn.middleware import AsyncioWSGIMiddleware
    except ImportError:
        sys.exit('[错误] 未安装 hypercorn,请先运行: pip install hypercorn')

    # 本地 HTTPS 自签证书(HTTP/2 必须走 TLS);首次自动生成到 .certs/。
    cert_dir = Path(__file__).resolve().parent / '.certs'
    cert_dir.mkdir(exist_ok=True)
    cert_path = cert_dir / 'cert.pem'
    key_path = cert_dir / 'key.pem'
    _ensure_self_signed_cert(cert_path, key_path)

    if args.open:
        import webbrowser
        url = f'https://{args.host}:{args.port}'
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    print(f'\n🎬 V-flow 已启动!  (HTTP/2 · HTTPS)')
    print(f'   打开: https://{args.host}:{args.port}')
    print(f'   首次访问浏览器会提示证书不安全,选「高级 → 继续前往」即可(仅本地自签)。')
    print(f'   按 Ctrl+C 退出\n')

    cfg = Config()
    cfg.bind = [f'{args.host}:{args.port}']
    cfg.certfile = str(cert_path)
    cfg.keyfile = str(key_path)
    cfg.alpn_protocols = ['h2', 'http/1.1']   # 协商 HTTP/2,老客户端回退 HTTP/1.1
    asyncio.run(hc_serve(AsyncioWSGIMiddleware(_wsgi_nonempty_body(app)), cfg))


if __name__ == '__main__':
    main()
