FROM python:3.11-slim

# 安装 ping 命令和运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r flask && useradd -r -g flask flask

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建运行时目录并设置权限
RUN mkdir -p data logs uploads && \
    chown -R flask:flask /app

# 切换到非 root 用户
USER flask

# 暴露端口
EXPOSE 5000

# 使用 gunicorn 生产运行
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
