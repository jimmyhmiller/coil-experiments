#!/usr/bin/env python3
"""Test fixture only: a local HTTP server for the probe demo's `http` scenario.

Usage: http_fixture.py PORT     (serves until killed)
"""
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="text/plain"):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Fixture", "probe-demo")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/hello":
            self._send(200, "hello, probe\n")
        elif self.path == "/boom":
            self._send(500, "it broke\n")
        else:
            self._send(404, "no such thing\n")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode()
        self._send(200, '{"echo": "%s"}\n' % body, "application/json")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
