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

2. 先构建一次基础镜像(环境层:Python + FFmpeg + 依赖),之后改代码不用重跑:

   ```bash
   docker build -t vflow-base -f Dockerfile.base .
   ```

3. 构建应用镜像并后台启动(基于 `vflow-base`,只叠加代码,秒级):

   ```bash
   docker compose up -d --build
   ```

4. 浏览器打开 `http://localhost:5000`。

- 之后改了应用代码,只需重复第 3 步;仅当 `requirements.txt` 或 FFmpeg 等环境变化时才需要重跑第 2 步。
- 缩略图 / 转封装缓存 / 标签库持久化到命名卷,容器重建不丢失。
- 只读保护视频库(禁用改名/移动):在上面的 bind 段加 `read_only: true`。
- 换端口:改 `ports` 左侧,如 `"8080:5000"`。
- 停止:`docker compose down`(加 `-v` 一并清掉缓存卷)。

不用 compose 也可以:

```bash
docker build -t vflow-base -f Dockerfile.base .
docker build -t vflow .
docker run -d -p 5000:5000 -v D:/Videos:/app/video vflow
```

## 网盘接入(可选)

经 [OpenList](https://github.com/OpenListTeam/OpenList)(AList fork)的 WebDAV 桥接,可在 V-flow 里直接浏览 / 播放 115、夸克等网盘视频,并给它们打标签。标签与本地视频共用同一套标签库(网盘路径以 `net/` 前缀和本地路径区分),改名 / 移动 / 删除请到 OpenList 操作。

> 由网盘 / OpenList 决定的限制:网盘视频不生成画面缩略图(字母占位);115 拖动进度条可能因签名 URL 重取略卡。

### 环境变量

默认关闭(`OPENLIST_USER` 留空即禁用)。启用需填:

| 变量 | 说明 | 默认 |
|------|------|------|
| `OPENLIST_DAV` | OpenList 的 WebDAV 根地址,如 `http://192.168.31.223:5244/dav` | 空(禁用) |
| `OPENLIST_USER` | OpenList 账号;**留空则网盘功能关闭** | 空 |
| `OPENLIST_PASS` | OpenList 密码 | 空 |
| `NET_PREFIX` | V-flow 里网盘挂载的虚拟目录名 | `net` |

**Docker**:`cp .env.example .env` 并填入,`docker-compose.yml` 已配 `env_file` 自动读取:

```bash
cp .env.example .env
# 编辑 .env 填 OPENLIST_DAV / OPENLIST_USER / OPENLIST_PASS(.env 已 gitignore,不提交)
```

**本地运行**:

```bash
OPENLIST_DAV=http://192.168.31.223:5244/dav \
OPENLIST_USER=vflow OPENLIST_PASS=xxx \
python app.py -d "D:\Videos"
```

启用后,首页会多出一个「网盘」入口,点进去即是 OpenList 里挂载的网盘。

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
