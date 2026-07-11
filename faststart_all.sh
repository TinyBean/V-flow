#!/usr/bin/env bash
# 批量维护脚本:把 .ts 转成 faststart MP4,并把所有 MP4 系文件的 moov atom 前置。
# 额外:检测浏览器无法播放的视频编码(mpeg4/hevc 等),转码为 H.264。
# (faststart_all.py 的 bash 版,递归处理文件夹。)
#
# - .ts            -> 同目录同名 .mp4(-c copy 无损 + faststart),校验通过后删除原 .ts
#                    若视频编码非 H.264,则转码为 H.264 再封装 mp4
# - .mp4/.m4v/.mov -> 非浏览器可播编码 -> 转码为 H.264(原地替换)
#                    否则若 moov 在 mdat 之后 -> 原地重封装为 faststart(已前置则跳过)
# - .mkv/.webm/.avi 等无 moov atom 的容器,跳过
#
# 浏览器可播判定:视频流编码为 h264 视为可播(hevc/mpeg4/vp9 等一律转码,保证通用)。
#
# 默认 dry-run 只打印计划,加 --apply 才真正执行。失败永远不删原文件。
#
# 用法:
#   ./faststart_all.sh -d "D:/Videos"              # 预览
#   ./faststart_all.sh -d "D:/Videos" --apply      # 执行
#   ./faststart_all.sh -d "D:/Videos" --apply -j 4 # 4 进程并发
#   ./faststart_all.sh --selftest                  # 校验 moov 判定逻辑
set -u

FFMPEG_TIMEOUT=1800   # 单文件最长 30 分钟
TS_EXTS="ts"
FS_EXTS="mp4 m4v mov"

usage() {
    cat <<EOF
用法: $0 -d <dir> [--apply] [-j N] [--selftest]
  -d, --dir <dir>   视频文件夹(递归)
      --apply       真正执行(默认仅 dry-run 预览)
  -j, --jobs N      并发 ffmpeg 进程数(默认 1)
      --selftest    生成两个临时 mp4 校验 moov 判定逻辑后退出
  -h, --help        显示帮助
EOF
    exit "${1:-0}"
}

# 扩展名小写(不含点)
lower_ext() { local n="${1##*.}"; echo "${n,,}"; }

# 输出容器格式名,供 ffmpeg -f 显式指定(.part 临时文件无法从扩展名推断)
container_fmt() { [ "$(lower_ext "$1")" = mov ] && echo mov || echo mp4; }

# MP4 的 moov atom 是否在 mdat 之后(需 faststart)。
# 读顶级 atom 序列:先遇 mdat -> 需前置(返回 0);先遇 moov -> 已前置(返回 1);
# EOF / 异常 -> 返回 1(保守不动)。
# 用 od 取字节十进制值,规避 bash 字符串遇 NUL 截断的问题。
needs_faststart() {
    local file="$1" off=0
    while :; do
        local b
        b=$(od -An -tu1 -j "$off" -N 8 -- "$file" 2>/dev/null) || return 1
        set -- $b
        [ $# -ge 8 ] || return 1
        # type 在第 5-8 字节;零填充成 12 位数字串便于比较
        #   moov = 109 111 111 118 ; mdat = 109 100 97 116
        local tp
        printf -v tp '%03d%03d%03d%03d' "$5" "$6" "$7" "$8"
        [ "$tp" = "109111111118" ] && return 1   # moov 在前 -> 已前置
        [ "$tp" = "109100097116" ] && return 0   # mdat 在前 -> 需前置
        # 非 moov/mdat:按 size 跳到下一个 box
        local size=$(( ($1<<24) + ($2<<16) + ($3<<8) + $4 ))
        local hdrlen=8
        if [ "$size" -eq 1 ]; then                  # 64-bit largesize
            local g
            g=$(od -An -tu1 -j $((off+8)) -N 8 -- "$file" 2>/dev/null) || return 1
            set -- $g
            [ $# -ge 8 ] || return 1
            # 高 32 位非 0 -> box >4GB 且非 moov/mdat,保守不动
            { [ "$1" -ne 0 ] || [ "$2" -ne 0 ] || [ "$3" -ne 0 ] || [ "$4" -ne 0 ]; } && return 1
            size=$(( ($5<<24) + ($6<<16) + ($7<<8) + $8 ))
            hdrlen=16
        fi
        [ "$size" -eq 0 ] && return 1               # box 延伸到 EOF
        [ "$size" -lt "$hdrlen" ] && return 1       # 异常
        off=$(( off + size ))
    done
}

# 视频流是否浏览器不可播(需转码为 H.264)。需转码返回 0,否则返回 1。
# 仅 h264 视为通用可播;hevc/mpeg4/vp9 等一律返回需转码。ffprobe 失败/无视频流 -> 保守不转码。
needs_transcode() {
    local codec
    codec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name \
            -of csv=p=0 -- "$1" 2>/dev/null) || return 1
    [ -z "$codec" ] && return 1          # 无视频流
    [ "$codec" = "h264" ] && return 1     # 浏览器可播
    return 0                              # 其余编码 -> 转码
}

# 返回 'ts' | 'ts-transcode' | 'transcode' | 'faststart' | 'ok' | 'none'
classify() {
    local ext; ext=$(lower_ext "$1")
    case " $FS_EXTS " in *" $ext "*)
        needs_transcode "$1" && echo transcode && return
        needs_faststart "$1" && echo faststart || echo ok
        return ;;
    esac
    case " $TS_EXTS " in *" $ext "*)
        needs_transcode "$1" && echo ts-transcode && return
        echo ts; return ;;
    esac
    echo none
}

# 通用执行:src -> dst + faststart,额外 ffmpeg 输出参数由调用方传入。成功返回 0。
ffmpeg_run() {
    local src="$1" dst="$2"; shift 2
    local tmp="${dst}.part"
    rm -f -- "$tmp"
    local cmd=(ffmpeg -y -i "$src" "$@" -movflags +faststart -f "$(container_fmt "$dst")" "$tmp")
    local rc=0
    if command -v timeout >/dev/null 2>&1; then
        timeout "$FFMPEG_TIMEOUT" "${cmd[@]}" >/dev/null 2>&1 || rc=$?
    else
        "${cmd[@]}" >/dev/null 2>&1 || rc=$?
    fi
    if [ "$rc" -eq 0 ] && [ -s "$tmp" ]; then mv -f -- "$tmp" "$dst" && return 0; fi
    rm -f -- "$tmp"; return 1
}

# 无损 -c copy 重封装
remux()     { ffmpeg_run "$1" "$2" -c copy; }

# 有损转码为 H.264 + AAC(浏览器通用可播)
transcode() { ffmpeg_run "$1" "$2" -c:v libx264 -crf 20 -preset medium -c:a aac; }

# 处理单个文件,打印恰好一行 '[status] 消息'(status ∈ done/fail/skip)。失败绝不删原文件。
process_file() {
    local file="$1" kind dst
    kind=$(classify "$file")
    case "$kind" in
        ok|none) return 0 ;;
        transcode)
            if transcode "$file" "$file"; then echo "[done] 转码 H.264: $(basename "$file")"
            else echo "[fail] 转码失败: $(basename "$file")"; fi ;;
        ts)
            dst="${file%.*}.mp4"
            if [ -e "$dst" ]; then echo "[skip] 目标已存在,跳过: $(basename "$dst")"; return; fi
            if ! remux "$file" "$dst"; then
                echo "[fail] 转封装失败: $(basename "$file")"; return; fi
            if needs_faststart "$dst"; then
                echo "[fail] 产物校验失败(moov 未前置),保留原文件: $(basename "$file")"; return; fi
            rm -f -- "$file"
            echo "[done] ts -> mp4: $(basename "$file")" ;;
        ts-transcode)
            dst="${file%.*}.mp4"
            if [ -e "$dst" ]; then echo "[skip] 目标已存在,跳过: $(basename "$dst")"; return; fi
            if ! transcode "$file" "$dst"; then
                echo "[fail] 转码失败: $(basename "$file")"; return; fi
            if needs_faststart "$dst"; then
                echo "[fail] 产物校验失败(moov 未前置),保留原文件: $(basename "$file")"; return; fi
            rm -f -- "$file"
            echo "[done] ts -> mp4(转码 H.264): $(basename "$file")" ;;
        faststart)
            if remux "$file" "$file"; then echo "[done] moov 前置: $(basename "$file")"
            else echo "[fail] faststart 失败: $(basename "$file")"; fi ;;
    esac
}

# 最小自检:造一个非 faststart、一个 faststart 的小 mp4,验证 needs_faststart 判定。
selftest() {
    command -v ffmpeg  >/dev/null 2>&1 || { echo "[selftest] 需要 ffmpeg";  exit 1; }
    command -v ffprobe >/dev/null 2>&1 || { echo "[selftest] 需要 ffprobe"; exit 1; }
    local d a b c ok=1
    d=$(mktemp -d); a="$d/a.mp4"; b="$d/b.mp4"; c="$d/c.mp4"
    ffmpeg -y -f lavfi -i color=black:s=16x16:d=0.04 -frames:v 1                 "$a" >/dev/null 2>&1
    ffmpeg -y -f lavfi -i color=black:s=16x16:d=0.04 -frames:v 1 -movflags +faststart "$b" >/dev/null 2>&1
    ffmpeg -y -f lavfi -i color=black:s=16x16:d=0.04 -frames:v 1 -c:v mpeg4      "$c" >/dev/null 2>&1
    [ -s "$a" ] && [ -s "$b" ] && [ -s "$c" ] || { echo "[selftest] 生成测试 mp4 失败"; rm -rf -- "$d"; exit 1; }
    if needs_faststart  "$a"; then echo "[ok] 非 faststart -> 判为需前置"; else echo "[FAIL] a 应判为需前置"; ok=0; fi
    if needs_faststart  "$b"; then echo "[FAIL] b 应判为已前置"; ok=0; else echo "[ok] faststart -> 判为已前置"; fi
    if needs_transcode  "$b"; then echo "[FAIL] h264 应判为可播"; ok=0; else echo "[ok] h264 -> 判为可播"; fi
    if needs_transcode  "$c"; then echo "[ok] mpeg4 -> 判为需转码"; else echo "[FAIL] mpeg4 应判为需转码"; ok=0; fi
    rm -rf -- "$d"
    [ "$ok" -eq 1 ] && { echo "[selftest] 通过"; exit 0; } || exit 1
}

# ---- argparse(容忍 --apply/-j 在任意位置)----
DIR=""; JOBS=1; APPLY=0
while [ $# -gt 0 ]; do
    case "$1" in
        -d|--dir)   DIR="${2:-}"; shift 2 ;;
        --apply)    APPLY=1; shift ;;
        -j|--jobs)  JOBS="${2:-1}"; shift 2 ;;
        --selftest) selftest ;;
        -h|--help)  usage 0 ;;
        *) echo "[错误] 未知参数: $1" >&2; usage 1 ;;
    esac
done

[ -n "$DIR" ] || { echo "[错误] 缺少 -d/--dir" >&2; usage 1; }
command -v ffmpeg  >/dev/null 2>&1 || { echo "[错误] 未找到 ffmpeg,请先安装并加入 PATH。" >&2; exit 1; }
command -v ffprobe >/dev/null 2>&1 || { echo "[错误] 未找到 ffprobe,请先安装并加入 PATH。" >&2; exit 1; }
DIR=$(cd -- "$DIR" 2>/dev/null && pwd) || { echo "[错误] 不是文件夹: $1" >&2; exit 1; }

# ---- 收集工作项 ----
items=(); ts_n=0; ts_tc_n=0; fs_n=0; tc_n=0
while IFS= read -r -d '' f; do
    case "$(classify "$f")" in
        ts)            items+=("$f"); ts_n=$((ts_n+1)) ;;
        ts-transcode)  items+=("$f"); ts_tc_n=$((ts_tc_n+1)) ;;
        faststart)     items+=("$f"); fs_n=$((fs_n+1)) ;;
        transcode)     items+=("$f"); tc_n=$((tc_n+1)) ;;
    esac
done < <(find "$DIR" -type f -print0)

printf '目录: %s\n' "$DIR"
printf '待处理: %d 转封装 .ts | %d 转码 .ts->H.264 | %d 转码 MP4->H.264 | %d moov 前置\n' \
    "$ts_n" "$ts_tc_n" "$tc_n" "$fs_n"
if [ "$((ts_n + ts_tc_n + tc_n + fs_n))" -eq 0 ]; then
    echo "没有需要处理的文件(全部已是浏览器可播的 faststart MP4)。"; exit 0
fi

# ---- dry-run:仅打印计划 ----
if [ "$APPLY" -eq 0 ]; then
    echo; echo "[dry-run] 仅预览,加 --apply 才真正执行。计划:"
    for f in "${items[@]}"; do
        case "$(classify "$f")" in
            ts)           printf '  ts->mp4       %s\n' "${f#"$DIR"/}" ;;
            ts-transcode) printf '  ts->mp4(h264) %s\n' "${f#"$DIR"/}" ;;
            transcode)    printf '  转码 H.264    %s\n' "${f#"$DIR"/}" ;;
            faststart)    printf '  faststart     %s\n' "${f#"$DIR"/}" ;;
        esac
    done
    exit 0
fi

# ---- 真正执行(可并发):每文件一行 [status],最后统计 ----
export FFMPEG_TIMEOUT TS_EXTS FS_EXTS
export -f lower_ext container_fmt needs_faststart needs_transcode classify \
            ffmpeg_run remux transcode process_file
tmplog=$(mktemp)
printf '%s\0' "${items[@]}" \
    | xargs -0 -P "$JOBS" -I{} bash -c 'process_file "$1"' _ {} \
    | tee "$tmplog"

done_n=$(grep -c '^\[done\]'  "$tmplog")
fail_n=$(grep -c '^\[fail\]'  "$tmplog")
skip_n=$(grep -c '^\[skip\]'  "$tmplog")
rm -f -- "$tmplog"
printf '\n完成: 成功 %d | 失败 %d | 跳过 %d\n' "$done_n" "$fail_n" "$skip_n"
[ "$fail_n" -eq 0 ] || exit 1
