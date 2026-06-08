FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖（markitdown 转换 PDF/DOCX 等需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制项目文件
COPY . .

# 创建上传目录
RUN mkdir -p uploads

# 暴露 API 端口
EXPOSE 5000

# 启动 API 服务
CMD ["python", "api_server.py"]