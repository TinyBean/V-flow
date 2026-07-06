# AGENTS.md

Guidance for agents working in this repo. Verified against the code at time of writing.

> `CLAUDE.md` exists but is **partially stale**: it omits login, the tags DB, the rename/move/delete APIs, Docker, tests, and `faststart_all.sh`; it also references a removed `-o/--open` flag and a `--host` default of `127.0.0.1` (now `0.0.0.0`). Trust this file and the code over `CLAUDE.md`.

## Commands

```bash
# Run the app (Hypercorn over HTTP/2 + auto self-signed HTTPS; cert warning on first visit is expected)
python app.py -d "<video dir>"            # --host defaults to 0.0.0.0 (LAN-exposed), -p defaults to 5000
python app.py -d "D:\Videos" --host 127.0.0.1 -p 8080   # lock to localhost

# Tests (pytest; fixtures monkeypatch VIDEO_ROOT + META_DB to tmp dirs)
pytest                       # or: python -m pytest
python tests/test_meta.py    # this one is ALSO runnable standalone (has a __main__ block)

# Batch maintenance: .ts→.mp4 + faststart moov front-load (bash, needs ffmpeg). Dry-run by default.
./faststart_all.sh -d "D:/Videos"                  # preview
./faststart_all.sh -d "D:/Videos" --apply -j 4     # execute, 4 parallel
./faststart_all.sh --selftest                      # sanity-check moov detector
```

There is **no lint / typecheck / formatter / CI** configured — don't invent or run any. Dependencies: `pip install -r requirements.txt` (Flask + hypercorn + cryptography, pinned). ffmpeg/ffprobe optional (thumbnails degrade to SVG placeholders when absent).

## Architecture

Flask app. Thin entry `app.py` (argparse + Hypercorn serve) → `vflow/` package: application factory `create_app()` (`vflow/__init__.py`) registers one Blueprint holding **all** routes (`vflow/routes.py`).

- **Templates & static live at repo root** (`templates/`, `static/`), not inside the package. `create_app()` sets `template_folder`/`static_folder` explicitly to the package's parent. Three vanilla-JS templates, **no framework, no build step** — edit `index.html` / `player.html` / `login.html` directly.
- **Path traversal guard**: every user-supplied path must go through `safe_resolve()` (`vflow/security.py`); it `abort(403)` on escape. All routes already do this — keep doing it.
- **Streaming**: `send_file(..., conditional=True)` gives native HTTP Range/206. Do not reimplement range parsing.
- **Thumbnails** (`vflow/thumbnails.py`): cached in `.thumbs/`, keyed by md5 of the *absolute* path. Generated via ffmpeg on a 6-worker `ThreadPoolExecutor` with an `_inflight` set to dedupe concurrent writes to the same file. Returns a 1×1 SVG placeholder while generating / when ffmpeg is missing — never let the thumbnail path crash.
- **Meta / tags** (`vflow/meta.py`, SQLite at `.meta/meta.db`): the **relative video path IS the stable key**. Any rename/move/delete MUST also call `meta.relocate_path()` / `meta.prune_paths()` so tags follow the file; ghost rows from externally-deleted files are self-healed on read in `/api/videos`. Tag names are case-insensitive unique.
- **Auth**: hardcoded `admin` / `vflow123` in `vflow/config.py` (local soft gate, by design). A Blueprint-level `before_request` (`_require_login` in `routes.py`) guards every route except `vflow.login`. `/static/*` is served by Flask outside the Blueprint and is intentionally **not** gated.

## Critical gotchas

- **Do not remove `_wsgi_nonempty_body` in `app.py`** (~line 72). It works around a Hypercorn WSGI→ASGI bug where empty-body 304/204 responses raise `UnexpectedMessageError`. `<video>` cache revalidation on `/api/stream` returns 304 and hits exactly this — removing it breaks playback.
- **Keep the UTF-8 reconfigure at the top of `app.py`**. The Windows GBK console crashes on emoji/Chinese in print statements without it.
- **The self-signed cert SAN includes the detected LAN IP** (`app.py:_ensure_self_signed_cert`) so phones reaching the box over LAN don't get their `<video>` media requests rejected. Preserve that when touching cert generation.
- **`--host` defaults to `0.0.0.0`** (LAN-exposed), not 127.0.0.1. `README.md`'s table is stale on this point.

## Generated / private paths (all gitignored, auto-created on startup — never commit)

`.certs/` (HTTPS key+cert) · `.thumbs/` (thumbnail cache) · `.meta/` (SQLite tags DB) · `.remux/` · `video/` (mounted media — **private**, never reference its filenames in code, docs, or commits).

## Docker (two-layer build)

1. `docker build -t vflow-base -f Dockerfile.base .` — env layer (python:3.12-slim + ffmpeg + pip deps). Rebuild **only** when `requirements.txt` or ffmpeg change.
2. `docker compose up -d --build` — app image layers on `vflow-base:latest`, rebuilds in seconds on code change. `docker-compose.yml` bind-mounts the host video dir → `/app/video` and persists `.thumbs` / `.meta` in named volumes.
