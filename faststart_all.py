#!/usr/bin/env python3
"""批量维护脚本:把 .ts 转成 faststart MP4,并把所有 MP4 系文件的 moov atom 前置。

- .ts          -> 同目录同名 .mp4(-c copy 无损 + faststart),校验通过后删除原 .ts
- .mp4/.m4v/.mov -> 若 moov 在 mdat 之后,原地重封装为 faststart(已前置则跳过)
- .mkv/.webm/.avi 等其它容器没有 moov atom,无法"前置",跳过

默认 dry-run 只打印计划,加 --apply 才真正执行。失败永远不删原文件。

用法:
    python faststart_all.py --dir "D:\\Videos"              # 预览
    python faststart_all.py --dir "D:\\Videos" --apply      # 执行
    python faststart_all.py --dir "D:\\Videos" --apply -j 4 # 4 进程并发
"""
import argparse
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# MP4 系容器的 moov atom 检测:mdat 在前 -> moov 在后 -> 需 faststart。
# (运行时已不再转封装,脚本自带此判定,不依赖 vflow 包。)
def needs_faststart(path: Path) -> bool:
    """MP4 的 moov atom 在 mdat 之后 -> 需要 faststart(返回 True)。
    已 faststart / 非 mp4 / 无法解析 -> False(保守不动)。"""
    try:
        with open(path, 'rb') as f:
            while True:
                header = f.read(8)
                if len(header) < 8:
                    return False
                size = int.from_bytes(header[:4], 'big')
                btype = header[4:8]
                hdr = 8
                if size == 1:                       # 64-bit largesize
                    large = f.read(8)
                    if len(large) < 8:
                        return False
                    size = int.from_bytes(large, 'big')
                    hdr = 16
                if btype == b'moov':
                    return False                    # moov 在前 -> 已 faststart
                if btype == b'mdat':
                    return True                     # mdat 在前 -> moov 在后
                if size == 0:                       # box 延伸到 EOF
                    return False
                if size < hdr:                      # 异常,保守不动
                    return False
                f.seek(size - hdr, 1)               # 跳到下一个 box
    except (OSError, ValueError):
        return False

TS_EXTS = {'.ts'}
FASTSTART_EXTS = {'.mp4', '.m4v', '.mov'}   # moov atom 适用的 MP4 系容器
FFMPEG_TIMEOUT = 1800                        # 单文件最长 30 分钟


def _container_fmt(path: Path) -> str:
    """输出容器格式名,供 ffmpeg -f 显式指定。

    临时文件以 .part 结尾,ffmpeg 无法从扩展名推断格式,必须显式给 -f。
    """
    return 'mov' if path.suffix.lower() == '.mov' else 'mp4'


def remux(src: Path, dst: Path):
    """无损 -c copy + faststart 重封装 src -> dst;先写 .part 再原子改名。

    返回 (ok, err):成功 (True, '');失败 (False, 末行错误)。
    """
    tmp = dst.with_name(dst.name + '.part')
    tmp.unlink(missing_ok=True)
    cmd = ['ffmpeg', '-y', '-i', str(src),
           '-c', 'copy', '-movflags', '+faststart',
           '-f', _container_fmt(dst), str(tmp)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=FFMPEG_TIMEOUT)
    except subprocess.TimeoutExpired:
        tmp.unlink(missing_ok=True)
        return False, '超时'
    if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
        tmp.replace(dst)
        return True, ''
    tmp.unlink(missing_ok=True)
    err_lines = r.stderr.decode('utf-8', 'ignore').strip().splitlines()
    return False, err_lines[-1] if err_lines else f'exit {r.returncode}'


def classify(path: Path):
    """返回 'ts' | 'faststart' | 'ok' | None。"""
    suf = path.suffix.lower()
    if suf in TS_EXTS:
        return 'ts'
    if suf in FASTSTART_EXTS:
        return 'faststart' if needs_faststart(path) else 'ok'
    return None          # 其它容器,不处理


def collect(root: Path):
    """递归遍历 root,产出工作项 [(kind, src, dst), ...];'ok' 的不计入。"""
    items = []
    for p in sorted(root.rglob('*')):
        if not p.is_file():
            continue
        kind = classify(p)
        if kind in (None, 'ok'):
            continue
        dst = p.with_suffix('.mp4') if kind == 'ts' else p
        items.append((kind, p, dst))
    return items


def process(kind: str, src: Path, dst: Path):
    """执行单个工作项,返回 (status, msg)。失败绝不删原文件。"""
    if kind == 'ts':
        if dst.exists():
            return 'skip', f'目标已存在,跳过: {dst.name}'
        ok, err = remux(src, dst)
        if not ok:
            return 'fail', f'转封装失败({err}): {src.name}'
        if needs_faststart(dst):     # 产物校验:moov 必须已前置才删原 .ts
            return 'fail', f'产物校验失败(moov 未前置),保留原文件: {src.name}'
        src.unlink(missing_ok=True)
        return 'done', f'ts -> mp4: {src.name}'
    if kind == 'faststart':
        ok, err = remux(src, dst)
        if not ok:
            return 'fail', f'faststart 失败({err}): {src.name}'
        return 'done', f'moov 前置: {src.name}'
    return 'skip', ''


def main():
    ap = argparse.ArgumentParser(
        description='把 .ts 转成 faststart MP4,并把所有 MP4 的 moov atom 前置。')
    ap.add_argument('-d', '--dir', required=True, help='视频文件夹(递归)')
    ap.add_argument('-j', '--jobs', type=int, default=1,
                    help='并发 ffmpeg 进程数(默认 1)')
    ap.add_argument('--apply', action='store_true',
                    help='真正执行(默认仅 dry-run 预览)')
    args = ap.parse_args()

    if not shutil.which('ffmpeg'):
        sys.exit('[错误] 未找到 ffmpeg,请先安装并加入 PATH。')

    root = Path(args.dir).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f'[错误] 不是文件夹: {root}')

    items = collect(root)
    ts_n = sum(1 for k, _, _ in items if k == 'ts')
    fs_n = sum(1 for k, _, _ in items if k == 'faststart')

    print(f'目录: {root}')
    print(f'待处理: {ts_n} 个 .ts(转 MP4 + 删原文件) | {fs_n} 个 MP4(moov 前置)')
    if not items:
        print('没有需要处理的文件(.ts 全已转、MP4 全已 faststart)。')
        return

    if not args.apply:
        print('\n[dry-run] 仅预览,加 --apply 才真正执行。计划:')
        for kind, src, _ in items:
            tag = 'ts->mp4   ' if kind == 'ts' else 'faststart '
            print(f'  {tag} {src.relative_to(root)}')
        return

    # 真正执行
    stats = {'done': 0, 'fail': 0, 'skip': 0}
    lock = threading.Lock()

    def run_one(item):
        kind, src, dst = item
        status, msg = process(kind, src, dst)
        with lock:
            stats[status] += 1
            print(f'  [{status}] {msg}')

    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            list(ex.map(run_one, items))     # map 保序触发,内部各自提交
    else:
        for item in items:
            run_one(item)

    print(f'\n完成: 成功 {stats["done"]} | 失败 {stats["fail"]} | 跳过 {stats["skip"]}')
    if stats['fail']:
        sys.exit(1)


if __name__ == '__main__':
    main()
