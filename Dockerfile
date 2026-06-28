# V-flow 容器镜像
FROM python:3.12-slim

# ffmpeg / ffprobe:缩略图 + .ts 无损转封装所需
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖(命中层缓存,代码改动不重装)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码(视频与缓存目录由 compose 挂载,不进镜像)
COPY app.py ./
COPY vflow/ ./vflow/
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 5000

# 默认:外部视频文件夹挂载到 /app/video,监听 0.0.0.0:5000
CMD ["python", "app.py", "--dir", "/app/video", "--host", "0.0.0.0", "--port", "5000"]
