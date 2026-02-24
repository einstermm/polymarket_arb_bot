FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目所有代码到容器内
COPY . .

# 启动命令
CMD ["python", "main.py"]