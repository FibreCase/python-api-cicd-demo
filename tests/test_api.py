import http.client
import json
import socket
import threading

import pytest

from app import main


@pytest.fixture(scope="module")
def running_server() -> tuple[str, int]:
    server = main.ThreadingHTTPServer(("127.0.0.1", 0), main.ApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _request(
    host: str,
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection(host, port, timeout=2)
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    response_body = response.read()
    response_headers = {k.lower(): v for k, v in response.getheaders()}
    status = response.status
    conn.close()
    return status, response_headers, response_body


def _request_json(
    host: str,
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], dict]:
    status, response_headers, response_body = _request(
        host, port, method, path, body=body, headers=headers
    )
    return status, response_headers, json.loads(response_body.decode("utf-8"))


def _raw_request(host: str, port: int, raw_http: str) -> tuple[int, dict]:
    with socket.create_connection((host, port), timeout=2) as sock:
        sock.sendall(raw_http.encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)

        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)

    response_text = b"".join(chunks).decode("utf-8", errors="replace")
    header_text, _, body = response_text.partition("\r\n\r\n")
    status_line = header_text.splitlines()[0]
    status_code = int(status_line.split()[1])
    payload = json.loads(body)
    return status_code, payload


def test_get_root_returns_welcome_message(running_server: tuple[str, int]) -> None:
    host, port = running_server
    status, headers, payload = _request_json(host, port, "GET", "/")

    assert status == 200
    assert headers["content-type"] == "application/json; charset=utf-8"
    assert payload == {"message": "Hello from simple Python HTTP backend"}


def test_get_health_returns_status_and_time(running_server: tuple[str, int]) -> None:
    host, port = running_server
    status, _, payload = _request_json(host, port, "GET", "/health")

    assert status == 200
    assert payload["status"] == "ok"
    assert isinstance(payload["time"], str)
    assert payload["time"].endswith("+00:00")


def test_unknown_get_path_returns_404(running_server: tuple[str, int]) -> None:
    host, port = running_server
    status, _, payload = _request_json(host, port, "GET", "/missing")

    assert status == 404
    assert payload == {"error": "Not Found"}


def test_post_echo_returns_received_payload(running_server: tuple[str, int]) -> None:
    host, port = running_server
    request_payload = {"name": "copilot", "count": 2}
    body = json.dumps(request_payload).encode("utf-8")

    status, _, payload = _request_json(
        host,
        port,
        "POST",
        "/echo",
        body=body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )

    assert status == 200
    assert payload == {"received": request_payload}


def test_post_on_unknown_path_returns_404(running_server: tuple[str, int]) -> None:
    host, port = running_server
    status, _, payload = _request_json(host, port, "POST", "/unknown", body=b"{}")

    assert status == 404
    assert payload == {"error": "Not Found"}


def test_post_echo_with_empty_body_returns_400(running_server: tuple[str, int]) -> None:
    host, port = running_server
    status, _, payload = _request_json(
        host,
        port,
        "POST",
        "/echo",
        body=b"",
        headers={"Content-Type": "application/json", "Content-Length": "0"},
    )

    assert status == 400
    assert payload == {"error": "Request body is empty"}


def test_post_echo_with_invalid_json_returns_400(running_server: tuple[str, int]) -> None:
    host, port = running_server
    body = b"{not-json}"
    status, _, payload = _request_json(
        host,
        port,
        "POST",
        "/echo",
        body=body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )

    assert status == 400
    assert payload == {"error": "Request body must be valid JSON"}


def test_post_echo_with_non_object_json_returns_400(running_server: tuple[str, int]) -> None:
    host, port = running_server
    body = b"[1, 2, 3]"
    status, _, payload = _request_json(
        host,
        port,
        "POST",
        "/echo",
        body=body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )

    assert status == 400
    assert payload == {"error": "JSON body must be an object"}


def test_post_echo_without_content_length_returns_400(
    running_server: tuple[str, int],
) -> None:
    host, port = running_server
    status, payload = _raw_request(
        host,
        port,
        (
            "POST /echo HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Content-Type: application/json\r\n"
            "Connection: close\r\n"
            "\r\n"
            "{}"
        ),
    )

    assert status == 400
    assert payload == {"error": "Missing Content-Length header"}


def test_post_echo_with_invalid_content_length_returns_400(
    running_server: tuple[str, int],
) -> None:
    host, port = running_server
    status, payload = _raw_request(
        host,
        port,
        (
            "POST /echo HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: abc\r\n"
            "Connection: close\r\n"
            "\r\n"
            "{}"
        ),
    )

    assert status == 400
    assert payload == {"error": "Invalid Content-Length header"}


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_unsupported_methods_return_405(
    running_server: tuple[str, int], method: str
) -> None:
    host, port = running_server
    status, _, payload = _request_json(host, port, method, "/")

    assert status == 405
    assert payload == {"error": "Method Not Allowed"}


def test_main_uses_port_env_and_starts_server(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeServer:
        def __init__(self, addr: tuple[str, int], handler_cls: type) -> None:
            captured["addr"] = addr
            captured["handler_cls"] = handler_cls

        def serve_forever(self) -> None:
            captured["serve_forever_called"] = True

    monkeypatch.setenv("PORT", "9010")
    monkeypatch.setattr(main, "ThreadingHTTPServer", FakeServer)

    main.main()

    assert captured["addr"] == ("0.0.0.0", 9010)
    assert captured["handler_cls"] is main.ApiHandler
    assert captured["serve_forever_called"] is True