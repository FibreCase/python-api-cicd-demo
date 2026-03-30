# Simple HTTP Backend

一个基于 Python 标准库实现的简单 HTTP 后端，无需安装第三方依赖。

## Edit to Trigger

Let's Rock!

## 运行

```bash
python main.py
```

默认监听地址：`http://0.0.0.0:8000`

可通过环境变量指定端口：

```bash
PORT=9000 python main.py
```

日志输出为单行 JSON，默认级别为 `INFO`，可通过环境变量调整：

```bash
LOG_LEVEL=DEBUG PORT=9000 python main.py
```

## API

### GET /

返回欢迎信息。

### GET /health

返回服务健康状态和当前 UTC 时间。

### POST /echo

请求体需为 JSON 对象，服务会原样返回。

示例：

```bash
curl -X POST http://127.0.0.1:8000/echo \
  -H "Content-Type: application/json" \
  -d '{"name":"copilot"}'
```

## 日志字段

服务访问日志会输出以下常见字段（按场景动态出现）：

- `timestamp`: UTC 时间
- `level`: 日志级别
- `logger`: 日志器名称
- `message`: 日志消息
- `remote_addr`: 客户端 IP
- `method`: HTTP 方法
- `path`: 请求路径
- `status_code`: 响应状态码
- `response_size`: 响应体大小
- `request_id`: 请求头中的 `X-Request-ID`
- `user_agent`: 请求头中的 `User-Agent`
