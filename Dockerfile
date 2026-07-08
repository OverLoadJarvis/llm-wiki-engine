# ============================================================
# Stage 1: 构建前端 (ui-apple)
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# 构建 ui-apple 前端
COPY ui-apple/package.json ui-apple/package-lock.json ./ui-apple/
RUN cd ui-apple && npm ci

COPY ui-apple/ ./ui-apple/
RUN cd ui-apple && npm run build

# ============================================================
# Stage 2: 后端 + 托管前端静态文件
# ============================================================
FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖（markitdown 转换 PDF/DOCX 等需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 复制后端依赖文件并安装
COPY server/requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制后端代码
COPY server/ ./server/

# 从前端构建阶段复制构建产物
COPY --from=frontend-builder /app/ui-apple/dist ./ui-dist/

# 创建上传目录
RUN mkdir -p server/uploads

# 暴露 API 与 MCP 端口
EXPOSE 5000 8081

# 启动 API 服务（同时托管前端）
CMD ["python", "server/api_server.py"]