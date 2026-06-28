# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

V-flow is a Flask app serving a local video browser, organized as a `vflow` package (application factory `create_app()` + Blueprint) with `app.py` as a thin entry point (argparse + Hypercorn over HTTP/2 + HTTPS). Backend logic is split by responsibility:

- `vflow/config.py` — VIDEO_ROOT + set_video_root(), constants (VIDEO_EXTS / THUMB_* / WARM_BATCH), cache dir paths
- `vflow/security.py` — safe_resolve() path-traversal guard
- `vflow/videos.py` — scan_dir() directory listing
- `vflow/thumbnails.py` — thumbnail generation + background warming
- `vflow/routes.py` — Blueprint with all routes: / , /play/<path>, /api/browse, /api/stream, /api/thumb

Frontend: two vanilla-JS templates, no framework/build step — `templates/index.html` (browsing/pagination/search) and `templates/player.html` (standalone playback page opened in a new tab: long-press 2x, ←/→ seek, space pause).

## Serving (HTTP/2 + local HTTPS)

`app.py` serves the app via **Hypercorn** over **HTTP/2** on a local **HTTPS** self-signed cert (auto-generated into `.certs/` on first run, valid for localhost/127.0.0.1). HTTP/2 multiplexes every request over a single connection, so there is no per-origin connection limit — concurrent video streams, thumbnails, and API calls never queue behind each other. Browsers require TLS for HTTP/2, hence the self-signed cert (accept the warning on first visit). `alpn_protocols = ['h2','http/1.1']` lets clients fall back to HTTP/1.1.

## Commands

```bash
# Start the app
python app.py --dir "D:\Videos"

# With auto-open browser and custom port
python app.py -d "D:\Movies" -p 8080 -o

# Allow LAN access (phone/etc.)
python app.py -d "D:\Videos" --host 0.0.0.0 -p 8080
```

## Dependencies

- Python 3.8+
- Flask (`pip install flask`)
- Hypercorn (`pip install hypercorn`) — HTTP/2-capable WSGI server used by `app.py`
- cryptography (`pip install cryptography`) — generates the local self-signed HTTPS cert
- FFmpeg/ffprobe on PATH (optional — thumbnails degrade gracefully to SVG placeholders when absent)
