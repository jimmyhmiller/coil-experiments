#!/usr/bin/env python3
"""End-to-end checks for the experimental HTTP library."""

import socket
import subprocess
import sys
import urllib.error
import urllib.request


def response_for(request, expected_status, expected_body):
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read()
    if status != expected_status or body != expected_body:
        raise AssertionError(
            f"got {status} {body!r}, wanted {expected_status} {expected_body!r}"
        )


def main():
    server = subprocess.Popen(
        ["coil", "run", "src/experiments/httpd/selfcheck.coil"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        line = server.stderr.readline()
        if not line.startswith("PORT="):
            raise RuntimeError(f"unexpected startup output: {line!r}")
        port = int(server.stderr.readline())
        base = f"http://127.0.0.1:{port}"

        with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
            request = (
                b"POST /echo?copied=1 HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Type: text/plain\r\n"
                b"Content-Length: 10000\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            )
            connection.sendall(request)
            connection.sendall(b"x" * 10000)
            chunks = []
            while True:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks)
            if not raw.startswith(b"HTTP/1.1 200 OK\r\n"):
                raise AssertionError(f"large request got: {raw!r}")
            if not raw.endswith(b"/echo"):
                raise AssertionError(f"large request did not route correctly: {raw!r}")

        response_for(
            urllib.request.Request(base + "/health"),
            200,
            b'{"status":"ok"}',
        )
        response_for(urllib.request.Request(base + "/echo"), 405, b"method not allowed\n")
        response_for(urllib.request.Request(base + "/missing"), 404, b"not found\n")
    finally:
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=1)
    print("http end-to-end passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"http end-to-end failed: {error}", file=sys.stderr)
        raise
