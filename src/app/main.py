import json
import logging
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in (
            "remote_addr",
            "method",
            "path",
            "query",
            "status_code",
            "response_size",
            "request_id",
            "user_agent",
            "host",
            "port",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        return json.dumps(payload, ensure_ascii=True)


def setup_logging() -> logging.Logger:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return logging.getLogger("app.http")

    raw_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, raw_level, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())

    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    return logging.getLogger("app.http")


LOGGER = logging.getLogger("app.http")


class ApiHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> tuple[dict | None, str | None]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return None, "Missing Content-Length header"

        try:
            content_length = int(raw_length)
        except ValueError:
            return None, "Invalid Content-Length header"

        if content_length <= 0:
            return None, "Request body is empty"

        raw_body = self.rfile.read(content_length)
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            return None, "Request body must be valid JSON"

        if not isinstance(data, dict):
            return None, "JSON body must be an object"

        return data, None

    def do_GET(self) -> None:
        if self.path == "/":
            self._send_json(200, {"message": "Hello from simple Python HTTP backend"})
            return

        if self.path == "/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "time": datetime.now(timezone.utc).isoformat(),
                },
            )
            return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self) -> None:
        if self.path != "/echo":
            self._send_json(404, {"error": "Not Found"})
            return

        body, error = self._read_json_body()
        if error is not None:
            self._send_json(400, {"error": error})
            return

        self._send_json(200, {"received": body})

    def do_PUT(self) -> None:
        self._send_json(405, {"error": "Method Not Allowed"})

    def do_PATCH(self) -> None:
        self._send_json(405, {"error": "Method Not Allowed"})

    def do_DELETE(self) -> None:
        self._send_json(405, {"error": "Method Not Allowed"})

    def log_message(self, format: str, *args) -> None:
        status_code = None
        response_size = None
        if len(args) >= 1:
            try:
                status_code = int(args[0])
            except (TypeError, ValueError):
                status_code = None
        if len(args) >= 2 and args[1] != "-":
            try:
                response_size = int(args[1])
            except (TypeError, ValueError):
                response_size = None

        request_id = self.headers.get("X-Request-ID") if self.headers else None
        user_agent = self.headers.get("User-Agent") if self.headers else None

        LOGGER.info(
            "http_access",
            extra={
                "remote_addr": self.client_address[0] if self.client_address else None,
                "method": self.command,
                "path": self.path,
                "status_code": status_code,
                "response_size": response_size,
                "request_id": request_id,
                "user_agent": user_agent,
            },
        )

    def log_error(self, format: str, *args) -> None:
        LOGGER.error(
            "http_error",
            extra={
                "remote_addr": self.client_address[0] if self.client_address else None,
                "method": self.command,
                "path": self.path,
                "request_id": self.headers.get("X-Request-ID") if self.headers else None,
                "user_agent": self.headers.get("User-Agent") if self.headers else None,
            },
        )


def main() -> None:
    global LOGGER
    LOGGER = setup_logging()

    host = "0.0.0.0"
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ApiHandler)
    LOGGER.info("server_started", extra={"host": host, "port": port})
    server.serve_forever()


if __name__ == "__main__":
    main()
