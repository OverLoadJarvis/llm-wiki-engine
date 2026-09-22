FROM python:3.13-slim

WORKDIR /app

# 使用阿里云 Debian 镜像加速 apt（清华源近期 502 / Hash Sum mismatch）
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    fi && \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list; \
    fi && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update -o Acquire::By-Hash=false -o Acquire::Retries=5 && \
    apt-get install -y --no-install-recommends -o Acquire::Retries=5 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# OTLP exporter's declared googleapis pin requires protobuf<7; this image pins protobuf 7,
# so the tracing packages are installed separately without that pin.
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple && \
    pip config set global.trusted-host mirrors.aliyun.com && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir googleapis-common-protos==1.75.3 && \
    pip install --no-cache-dir --no-deps \
      opentelemetry-api==1.44.0 \
      opentelemetry-sdk==1.44.0 \
      opentelemetry-semantic-conventions==0.65b0 \
      opentelemetry-proto==1.44.0 \
      opentelemetry-exporter-otlp-proto-common==1.44.0 \
      opentelemetry-exporter-otlp-proto-http==1.44.0

COPY . ./server/

RUN mkdir -p server/uploads

WORKDIR /app/server

EXPOSE 5000 8081

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT:-5000}"]
