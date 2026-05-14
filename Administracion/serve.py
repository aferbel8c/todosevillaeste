#!/usr/bin/env python3
"""
serve.py — Servidor HTTP para el dashboard de monitoreo
Uso: python3 serve.py [puerto]
Por defecto escucha en el puerto 8080
"""

import http.server
import socketserver
import json
import os
import sys
import errno
from urllib.parse import urlparse
from pathlib import Path

BASE_DIR = Path("/opt/pingmonitor")
LOG_FILE = BASE_DIR / "ping_log.json"
HTML_FILE = BASE_DIR / "dashboard.html"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silenciar logs de acceso

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._serve_file(HTML_FILE, "text/html; charset=utf-8")
        elif path == "/data":
            self._serve_json()
        else:
            self.send_error(404)

    def _serve_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, f"Archivo no encontrado: {path}")

    def _serve_json(self):
        try:
            with open(LOG_FILE, "r") as f:
                data = json.load(f)
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(500, str(e))


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    os.chdir(BASE_DIR)
    try:
        with ReusableTCPServer(("", PORT), Handler) as httpd:
            print(f"Servidor activo en http://0.0.0.0:{PORT}")
            httpd.serve_forever()
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            print(f"Error: el puerto {PORT} ya esta en uso.")
            print(f"Prueba con otro puerto: python3 {Path(__file__).name} 8081")
            sys.exit(1)
        raise
