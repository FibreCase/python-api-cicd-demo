# 构建阶段
FROM python:3.12-slim as builder

# 设置工作目录
WORKDIR /app

# 安装uv
RUN pip install uv

# 复制pyproject.toml和uv.lock
COPY pyproject.toml uv.lock ./

# 使用uv sync安装依赖到.venv
RUN uv sync --frozen


# 最终阶段
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 从builder阶段复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 复制项目源代码
COPY src/ ./src/

# 设置环境变量
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    PORT=8000

# 暴露端口8000
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import http.client; conn = http.client.HTTPConnection('localhost', 8000); conn.request('GET', '/health'); exit(0 if conn.getresponse().status == 200 else 1)" || exit(1)

# 运行应用
CMD ["python", "src/app/main.py"]
