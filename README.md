# V-flow · 本地视频浏览器

一个轻量的本地视频浏览网页应用,用浏览器即可浏览和播放电脑上的视频文件。

## 快速开始

```bash
# 启动(指定你的视频文件夹)
python app.py --dir "D:\Videos"

# 然后浏览器打开
# http://127.0.0.1:5000
```

## Docker 部署(推荐)

外部视频文件夹映射进容器的 `/app/video`,无需在宿主机安装 Python / FFmpeg。

1. 编辑 `docker-compose.yml`,把 `D:/Videos` 改成你的视频文件夹:

   ```yaml
   volumes:
     - type: bind
       source: D:/Videos      # ← 改成你的视频文件夹
       target: /app/video
   ```

2. 构建并后台启动:

   ```bash
   docker compose up -d --build
   ```

3. 浏览器打开 `http://localhost:5000`。

- 缩略图 / 转封装缓存 / 标签库持久化到命名卷,容器重建不丢失。
- 只读保护视频库(禁用改名/移动):在上面的 bind 段加 `read_only: true`。
- 换端口:改 `ports` 左侧,如 `"8080:5000"`。
- 停止:`docker compose down`(加 `-v` 一并清掉缓存卷)。

不用 compose 也可以:

```bash
docker build -t vflow .
docker run -d -p 5000:5000 -v D:/Videos:/app/video vflow
```

## 命令参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--dir, -d` | 视频文件夹路径 | 用户主目录 |
| `--port, -p` | 端口号 | 5000 |
| `--host` | 监听地址 | 127.0.0.1 |
| `--open, -o` | 启动时自动打开浏览器 | 关闭 |

## 功能

- 文件夹浏览:支持多级目录导航,面包屑路径
- 视频缩略图:自动用 ffmpeg 提取画面生成缩略图(缓存到 .thumbs/)
- 流式播放:支持 HTTP Range,可拖动进度条
- 搜索:当前文件夹内按文件名搜索
- 支持格式:mp4, mkv, webm, avi, mov, m4v, flv, wmv, mpg, ts 等

## 环境要求

- Python 3.8+
- Flask (`pip install flask`)
- FFmpeg (用于生成缩略图,可选)

## 示例

```bash
# 浏览 D 盘 Movies 文件夹,自动打开浏览器
python app.py -d "D:\Movies" -o

# 换个端口
python app.py -d "C:\Users\Videos" -p 8080

# 局域网共享(手机也可访问,用你电脑的IP)
python app.py -d "D:\Videos" --host 0.0.0.0 -p 8080
```
