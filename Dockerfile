# V-flow 应用镜像:在 vflow-base 之上只叠加应用代码,无 apt、无 pip,构建秒级。
# 前置(只需一次): docker build -t vflow-base -f Dockerfile.base .
FROM vflow-base:latest

WORKDIR /app

# 仅应用代码(视频与缓存目录由 compose 挂载,不进镜像)
COPY app.py ./
COPY vflow/ ./vflow/
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 5000

# 默认:外部视频文件夹挂载到 /app/video,监听 0.0.0.0:5000
CMD ["python", "app.py", "--dir", "/app/video", "--host", "0.0.0.0", "--port", "5000"]
