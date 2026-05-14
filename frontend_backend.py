from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response, Cookie, APIRouter, Depends, Form, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator, EmailStr
from typing import Optional, List, Dict, Tuple, Callable, Any
from pathlib import Path
from PIL import Image
import shutil
import mysql.connector
import json
import base64
import traceback
import secrets
import math
import os
import imaplib
import email as py_email
from passlib.context import CryptContext
from email.mime.text import MIMEText
from email.header import Header
import smtplib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import hmac
import string
import random
import threading
import time
import asyncio
import queue
from collections import deque
import urllib.request
import urllib.error
import urllib.parse
import ssl
from urllib.parse import quote, unquote
import subprocess
import re
import unicodedata
import logging
import ipaddress
import mimetypes
import shlex
from email.utils import parsedate_to_datetime, parseaddr, make_msgid

try:
    import pty
except Exception:
    pty = None

try:
    import fcntl
    import termios
    import struct
except Exception:
    fcntl = None
    termios = None
    struct = None

try:
    from pywebpush import webpush, WebPushException
except Exception:
    webpush = None
    WebPushException = Exception

try:
    import firebase_admin
    from firebase_admin import credentials as firebase_credentials, messaging as firebase_messaging
except Exception:
    firebase_admin = None
    firebase_credentials = None
    firebase_messaging = None

try:
    from py_vapid import Vapid01
except Exception:
    Vapid01 = None

try:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
except Exception:
    Encoding = None
    PublicFormat = None

def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and (value[0] == value[-1]) and value.startswith(("'", '"')):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Falta variable de entorno requerida: {name}")
    return value


_load_env_file(Path(__file__).resolve().parent / ".env")

app = FastAPI(title="Backend de gestión de negocios")
logger = logging.getLogger("frontend_backend")
BACKEND_STARTED_AT = datetime.utcnow().isoformat()
IP_LOG_PATH = Path("web") / "administracion" / "ip_log.txt"
LOG_STREAM_LOCK = threading.Lock()
LOG_STREAM_SUBSCRIBERS: List[queue.Queue] = []
LOG_STREAM_BACKLOG = deque(maxlen=1200)
PVE_BASE_URL = (os.getenv("PVE_BASE_URL") or "https://192.168.0.32:8006").strip().rstrip("/")
PVE_NODE = (os.getenv("PVE_NODE") or "proxmox").strip()
PVE_VMID = int((os.getenv("PVE_VMID") or "102").strip() or "102")
PVE_VMNAME = (os.getenv("PVE_VMNAME") or "ChatbotSERVER").strip() or "ChatbotSERVER"
PVE_USER = (os.getenv("PVE_USER") or "").strip()
PVE_PASSWORD = (os.getenv("PVE_PASSWORD") or "").strip()
PVE_VERIFY_TLS = (os.getenv("PVE_VERIFY_TLS") or "0").strip().lower() in {"1", "true", "yes", "on"}
ADMIN_SSH_HOST = (os.getenv("ADMIN_SSH_HOST") or "192.168.0.40").strip() or "192.168.0.40"
ADMIN_SSH_PORT = int((os.getenv("ADMIN_SSH_PORT") or "22").strip() or "22")
ADMIN_SSH_USER = (os.getenv("ADMIN_SSH_USER") or "").strip()
ADMIN_SSH_STRICT_HOST_KEY = (os.getenv("ADMIN_SSH_STRICT_HOST_KEY") or "accept-new").strip() or "accept-new"
ADMIN_TERMINAL_MODE = (os.getenv("ADMIN_TERMINAL_MODE") or "auto").strip().lower()
TSE_WORKDIR = (os.getenv("TSE_WORKDIR") or str(Path(__file__).resolve().parent)).strip()
TSE_START_CMD = (os.getenv("TSE_START_CMD") or "sudo -n systemctl start todosevillaeste-stack.target").strip()
TSE_STOP_CMD = (os.getenv("TSE_STOP_CMD") or "sudo -n systemctl stop todosevillaeste-stack.target").strip()
TSE_RESTART_CMD = (
    os.getenv("TSE_RESTART_CMD")
    or "sudo -n systemctl restart todosevillaeste-frontend.service"
).strip()
AGENTS_RESTART_CMD = (
    os.getenv("AGENTS_RESTART_CMD")
    or "sudo -n systemctl restart todosevillaeste-agents.service"
).strip()
TSE_SERVICE_CANDIDATES = [
    s.strip() for s in (
        os.getenv("TSE_SERVICE_CANDIDATES")
        or "todosevillaeste-stack.target,todosevillaeste-frontend.service,todosevillaeste-agents.service,todosevillaeste-backend,todosevillaeste"
    ).split(",") if s.strip()
]
TSE_PROCESS_PATTERN = (os.getenv("TSE_PROCESS_PATTERN") or "todosevillaeste|todo_sevilla|iniciar_todo").strip()
IP_COUNTRY_CACHE: Dict[str, Tuple[str, float]] = {}
IP_COUNTRY_CACHE_TTL_SECONDS = 60 * 60 * 12
IP_COUNTRY_LOCK = threading.Lock()
TRUSTED_HIGHLIGHT_IP = "85.219.33.38"
ANTI_BOT_RATE_LOCK = threading.Lock()
ANTI_BOT_RATE_STATE: Dict[str, deque] = {}


def _extract_request_ip(request: Request) -> str:
    forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    return (request.client.host if request.client else "") or ""


def _resolve_country_for_ip(ip_text: str) -> str:
    ip_raw = str(ip_text or "").strip()
    if not ip_raw:
        return "Unknown"
    if ip_raw.startswith("[") and "]" in ip_raw:
        ip_raw = ip_raw[1:ip_raw.index("]")].strip()
    elif ":" in ip_raw and ip_raw.rsplit(":", 1)[1].isdigit() and "." in ip_raw:
        ip_raw = ip_raw.rsplit(":", 1)[0].strip()
    if "%" in ip_raw:
        ip_raw = ip_raw.split("%", 1)[0].strip()
    try:
        ip_obj = ipaddress.ip_address(ip_raw)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            return "Local"
    except Exception:
        return "Unknown"

    now_ts = time.time()
    with IP_COUNTRY_LOCK:
        cached = IP_COUNTRY_CACHE.get(ip_raw)
        if cached and cached[1] > now_ts:
            return cached[0]

    country = "Unknown"
    url = f"https://ipwho.is/{urllib.parse.quote(ip_raw, safe='')}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "frontend-backend/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
        if isinstance(data, dict):
            if bool(data.get("success", True)):
                country = str(data.get("country") or "").strip() or "Unknown"
            else:
                country = str(data.get("message") or "").strip() or "Unknown"
    except Exception:
        country = "Unknown"

    with IP_COUNTRY_LOCK:
        IP_COUNTRY_CACHE[ip_raw] = (country, now_ts + IP_COUNTRY_CACHE_TTL_SECONDS)
    return country


def _format_ip_with_country(ip_text: str) -> str:
    ip_clean = str(ip_text or "").strip() or "unknown"
    if ip_clean.startswith("[") and "]" in ip_clean:
        ip_clean = ip_clean[1:ip_clean.index("]")].strip()
    elif ":" in ip_clean and ip_clean.rsplit(":", 1)[1].isdigit() and "." in ip_clean:
        ip_clean = ip_clean.rsplit(":", 1)[0].strip()
    return f"{ip_clean} ({_resolve_country_for_ip(ip_clean)})"


def _antibot_rate_key(namespace: str, ip_text: str) -> str:
    ip_clean = _normalize_ip_for_compare(ip_text)
    return f"{namespace}:{ip_clean or 'unknown'}"


def check_antibot_rate_limit(namespace: str, ip_text: str, limit: int, window_seconds: int = 300) -> None:
    now_ts = time.time()
    key = _antibot_rate_key(namespace, ip_text)
    cutoff = now_ts - window_seconds
    with ANTI_BOT_RATE_LOCK:
        queue = ANTI_BOT_RATE_STATE.get(key)
        if queue is None:
            queue = deque()
            ANTI_BOT_RATE_STATE[key] = queue
        while queue and queue[0] < cutoff:
            queue.popleft()
        if len(queue) >= limit:
            raise HTTPException(status_code=429, detail="Demasiados intentos, espera unos minutos")
        queue.append(now_ts)


def _normalize_ip_for_compare(ip_text: str) -> str:
    raw = str(ip_text or "").strip()
    if raw.startswith("[") and "]" in raw:
        raw = raw[1:raw.index("]")].strip()
    elif ":" in raw and raw.rsplit(":", 1)[1].isdigit() and "." in raw:
        raw = raw.rsplit(":", 1)[0].strip()
    if "%" in raw:
        raw = raw.split("%", 1)[0].strip()
    return raw


def _colorize_ip_label(ip_text: str, label: str) -> str:
    normalized = _normalize_ip_for_compare(ip_text)
    if normalized == TRUSTED_HIGHLIGHT_IP:
        return label
    return f"\x1b[31m{label}\x1b[0m"


class _UvicornAccessCountryFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = getattr(record, "args", None)
        if not isinstance(args, tuple) or not args:
            return True
        client_addr = str(args[0] or "").strip()
        if not client_addr:
            return True
        if "(" in client_addr and client_addr.endswith(")"):
            return True
        patched = list(args)
        base_label = _format_ip_with_country(client_addr)
        patched[0] = _colorize_ip_label(client_addr, base_label)
        record.args = tuple(patched)
        return True


_uvicorn_access_logger = logging.getLogger("uvicorn.access")
if not any(isinstance(f, _UvicornAccessCountryFilter) for f in _uvicorn_access_logger.filters):
    _uvicorn_access_logger.addFilter(_UvicornAccessCountryFilter())


def _ensure_backend_file_logging() -> None:
    try:
        IP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        file_path = str(IP_LOG_PATH.resolve())
    except Exception:
        file_path = str(IP_LOG_PATH)

    target_loggers = [
        logging.getLogger(),
        logging.getLogger("uvicorn"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("uvicorn.access"),
        logging.getLogger("frontend_backend"),
    ]

    for lg in target_loggers:
        has_same = False
        for h in lg.handlers:
            if isinstance(h, logging.FileHandler):
                try:
                    if str(Path(h.baseFilename).resolve()) == file_path:
                        has_same = True
                        break
                except Exception:
                    if str(h.baseFilename) == file_path:
                        has_same = True
                        break
        if has_same:
            continue

        fh = logging.FileHandler(IP_LOG_PATH, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
        lg.addHandler(fh)


_ensure_backend_file_logging()


class _RealtimeLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            return
        with LOG_STREAM_LOCK:
            LOG_STREAM_BACKLOG.append(line)
            dead_indices: List[int] = []
            for idx, sub in enumerate(LOG_STREAM_SUBSCRIBERS):
                try:
                    sub.put_nowait(line)
                except queue.Full:
                    continue
                except Exception:
                    dead_indices.append(idx)
            if dead_indices:
                for idx in reversed(dead_indices):
                    try:
                        LOG_STREAM_SUBSCRIBERS.pop(idx)
                    except Exception:
                        continue


def _ensure_realtime_log_handler() -> None:
    root_logger = logging.getLogger()
    if any(isinstance(h, _RealtimeLogHandler) for h in root_logger.handlers):
        return
    handler = _RealtimeLogHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root_logger.addHandler(handler)


_ensure_realtime_log_handler()


def _pve_urlopen(request_obj: urllib.request.Request, timeout: float = 6.0):
    if PVE_VERIFY_TLS:
        return urllib.request.urlopen(request_obj, timeout=timeout)
    insecure_ctx = ssl._create_unverified_context()
    return urllib.request.urlopen(request_obj, timeout=timeout, context=insecure_ctx)


def _pve_api_json(path: str, method: str = "GET", form_data: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
    body = None
    req_headers = {"User-Agent": "frontend-backend/1.0"}
    if form_data is not None:
        encoded = urllib.parse.urlencode(form_data).encode("utf-8")
        body = encoded
        req_headers["Content-Type"] = "application/x-www-form-urlencoded"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(f"{PVE_BASE_URL}{path}", data=body, headers=req_headers, method=method.upper())
    try:
        with _pve_urlopen(req, timeout=7.0) as resp:
            raw = resp.read().decode("utf-8", errors="ignore") or "{}"
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = ""
        raise HTTPException(status_code=502, detail=f"Proxmox HTTP {exc.code}: {detail or exc.reason}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar con Proxmox: {exc}")
    try:
        data = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=502, detail="Respuesta inválida de Proxmox")
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Formato inválido de Proxmox")
    return data


def _build_proxmox_console_url(node: str, vmid: int, vmname: str) -> Tuple[str, str]:
    user = PVE_USER
    password = PVE_PASSWORD
    if not user or not password:
        raise HTTPException(status_code=500, detail="Configura PVE_USER y PVE_PASSWORD en el backend")

    login_payload = _pve_api_json(
        "/api2/json/access/ticket",
        method="POST",
        form_data={"username": user, "password": password},
    )
    login_data = login_payload.get("data") if isinstance(login_payload.get("data"), dict) else {}
    pve_ticket = str(login_data.get("ticket") or "").strip()
    csrf = str(login_data.get("CSRFPreventionToken") or "").strip()
    if not pve_ticket:
        raise HTTPException(status_code=502, detail="Proxmox no devolvió ticket de login")

    headers = {"Cookie": f"PVEAuthCookie={pve_ticket}"}
    if csrf:
        headers["CSRFPreventionToken"] = csrf
    vnc_payload = _pve_api_json(
        f"/api2/json/nodes/{urllib.parse.quote(node, safe='')}/qemu/{int(vmid)}/vncproxy",
        method="POST",
        form_data={"websocket": 1},
        headers=headers,
    )
    vnc_data = vnc_payload.get("data") if isinstance(vnc_payload.get("data"), dict) else {}
    vnc_ticket = str(vnc_data.get("ticket") or "").strip()
    port = int(vnc_data.get("port") or 0)
    if not vnc_ticket or not port:
        raise HTTPException(status_code=502, detail="Proxmox no devolvió ticket/puerto VNC")

    ws_path = (
        f"/api2/json/nodes/{urllib.parse.quote(node, safe='')}/qemu/{int(vmid)}"
        f"/vncwebsocket?port={port}&vncticket={urllib.parse.quote(vnc_ticket, safe='')}"
    )
    url = (
        f"{PVE_BASE_URL}/?console=kvm&novnc=1"
        f"&vmid={int(vmid)}&vmname={urllib.parse.quote(vmname, safe='')}"
        f"&node={urllib.parse.quote(node, safe='')}&resize=off&cmd="
        f"&path={urllib.parse.quote(ws_path, safe='')}"
    )
    return url, pve_ticket


def _build_proxmox_direct_url(node: str, vmid: int, vmname: str) -> str:
    return (
        f"{PVE_BASE_URL}/?console=kvm&novnc=1"
        f"&vmid={int(vmid)}&vmname={urllib.parse.quote(vmname, safe='')}"
        f"&node={urllib.parse.quote(node, safe='')}&resize=off&cmd="
    )


def _is_local_client(request: Request) -> bool:

    host = _extract_request_ip(request)
    host = host.strip().lower()

    # localhost
    if host in {"127.0.0.1", "::1", "localhost"}:
        return True

    try:
        ip = ipaddress.ip_address(host)

        return bool(
            ip.is_private or
            ip.is_loopback or
            ip.is_link_local
        )

    except Exception:
        return False


def _require_local_client(request: Request) -> None:
    if not _is_local_client(request):
        raise HTTPException(status_code=403, detail="Acceso solo permitido desde IP local")


def _extract_ws_ip(websocket: WebSocket) -> str:
    forwarded_for = (websocket.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    real_ip = (websocket.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    return (websocket.client.host if websocket.client else "") or ""


def _require_local_ws(websocket: WebSocket) -> None:
    host = _extract_ws_ip(websocket).strip().lower()
    if host in {"127.0.0.1", "::1", "localhost"}:
        return
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Acceso websocket solo permitido desde IP local")


def _require_local_or_admin_request(request: Request) -> None:
    if _is_local_client(request):
        return
    try:
        get_admin_session(request)
        return
    except Exception:
        pass
    referer = (request.headers.get("referer") or "").lower()
    if "/administracion/ip_log.html" in referer or "/web/administracion/ip_log.html" in referer:
        return
    raise HTTPException(status_code=403, detail="Acceso solo permitido desde IP local")


def _require_local_or_admin_ws(websocket: WebSocket) -> None:
    try:
        _require_local_ws(websocket)
        return
    except HTTPException:
        pass
    try:
        _get_admin_session_from_cookie_value(websocket.cookies.get(ADMIN_SESSION_COOKIE))
        return
    except Exception:
        pass
    referer = (websocket.headers.get("referer") or "").lower()
    origin = (websocket.headers.get("origin") or "").lower()
    if ("/administracion/ip_log.html" in referer or "/web/administracion/ip_log.html" in referer) and origin:
        return
    raise HTTPException(status_code=403, detail="Acceso websocket solo permitido desde IP local")


def _redirect_path(base: str, rest: str, query: str) -> RedirectResponse:
    clean_base = (base or "/").strip() or "/"
    if clean_base != "/" and clean_base.endswith("/"):
        clean_base = clean_base.rstrip("/")
    if rest:
        suffix = rest.lstrip("/")
        target = f"/{suffix}" if clean_base == "/" else f"{clean_base}/{suffix}"
    else:
        target = clean_base
    if query:
        target = f"{target}?{query}"
    return RedirectResponse(url=target, status_code=307)


from fastapi.responses import RedirectResponse

@app.middleware("http")
async def request_ip_country_log(request: Request, call_next):

    path = request.url.path or ""

    # Bloquear administración desde fuera de LAN
    if path.startswith("/administracion"):

        if not _is_local_client(request):

            return RedirectResponse(
                url="https://todosevillaeste.es/",
                status_code=302
            )

    started = time.time()

    client_ip = _extract_request_ip(request)
    ip_label = _format_ip_with_country(client_ip)

    response = await call_next(request)

    elapsed_ms = int((time.time() - started) * 1000)

    logger.info(
        '%s "%s %s" %s %dms',
        ip_label,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms
    )

    return response


@app.middleware("http")
async def web_public_guard(request: Request, call_next):
    path = request.url.path or ""
    query = request.url.query or ""

    # Eliminar indexaciones antiguas: devolver 410 a slugs legacy de una sola ruta.
    # Solo afecta a URLs tipo "/peluqueria-belleza-y-estetica" (con guiones) y sin extensión.
    if path and path.startswith("/") and path.count("/") == 1 and "." not in path:
        slug = path.strip("/").lower()
        has_legacy_dash = "-" in slug
        legacy_allowlist = {
            "",
            "app",
            "app/",
            "login",
            "register",
            "cookies",
            "mensajes",
            "negocio",
            "perfil",
            "scan_qr",
            "manuales",
            "planos",
            "checklists",
            "herramientas",
            "rack",
            "rack2",
            "versiones",
            "versiones-cliente",
            "versiones_cliente",
            "support",
        }
        legacy_prefixes = (
            "administracion",
            "icono",
            "img",
            "creador_qr",
            "downloads",
            "user_avatars",
            "account",
            "manuales",
            "planos",
            "checklists",
            "herramientas",
            "frontend",
            "web",
            "rack",
        )
        if has_legacy_dash and slug and slug not in legacy_allowlist and not slug.startswith(legacy_prefixes):
            return Response(status_code=410)
    # URLs legacy antiguas tipo /component/xmap/html/html
    if path.startswith("/component") or "/xmap" in path:
        return Response(status_code=410)

    if path.startswith("/web/frontend/"):
        rest = path[len("/web/frontend/"):]
        if not rest or rest == "/":
            return _redirect_path("/", "frontend.html", query)
        return _redirect_path("/", rest, query)
    if path.startswith("/frontend/"):
        rest = path[len("/frontend/"):]
        if not rest or rest == "/":
            return _redirect_path("/", "frontend.html", query)
        return _redirect_path("/", rest, query)
    if path in {"/frontend", "/frontend/"}:
        return _redirect_path("/", "frontend.html", query)
    if path.startswith("/web/administracion/"):
        rest = path[len("/web/administracion/"):]
        return _redirect_path("/administracion", rest, query)
    if path == "/web/auth/login.html":
        return _redirect_path("/", "login.html", query)
    if path == "/web/auth/register.html":
        return _redirect_path("/", "register.html", query)
    if path.startswith("/web/icono/"):
        rest = path[len("/web/icono/"):]
        return _redirect_path("/icono", rest, query)
    if path.startswith("/web/img/"):
        rest = path[len("/web/img/"):]
        return _redirect_path("/img", rest, query)
    if path.startswith("/web/creador_qr/"):
        rest = path[len("/web/creador_qr/"):]
        return _redirect_path("/creador_qr", rest, query)
    if path.startswith("/web/downloads/"):
        rest = path[len("/web/downloads/"):]
        return _redirect_path("/downloads", rest, query)
    if path.startswith("/web/manuales/"):
        rest = path[len("/web/manuales/"):]
        return _redirect_path("/herramientas/manuales", rest, query)
    if path.startswith("/web/planos/"):
        rest = path[len("/web/planos/"):]
        return _redirect_path("/herramientas/planos", rest, query)
    if path.startswith("/web/herramientas/"):
        rest = path[len("/web/herramientas/"):]
        return _redirect_path("/herramientas", rest, query)
    if path.startswith("/account/"):
        rest = path[len("/account/"):]
        normalized_target = f"/account/{rest.lstrip('/')}" if rest else "/account"
        if normalized_target.rstrip("/") != path.rstrip("/"):
            return _redirect_path("/account", rest, query)

    if path.startswith("/web/versions/public"):
        return await call_next(request)
    if path.startswith("/web/") and not _is_local_client(request):
        return JSONResponse(
            status_code=403,
            content={"detail": "Acceso externo bloqueado fuera de /frontend y /administracion"},
        )

    canonical_html = {
        "/": "/frontend.html",
        "/alta_negocio": "/alta_negocio.html",
        "/alta_negocio/": "/alta_negocio.html",
        "/cookies": "/cookies.html",
        "/cookies/": "/cookies.html",
        "/privacidad": "/privacidad.html",
        "/privacidad/": "/privacidad.html",
        "/aviso-legal": "/aviso_legal.html",
        "/aviso-legal/": "/aviso_legal.html",
        "/aviso_legal": "/aviso_legal.html",
        "/aviso_legal/": "/aviso_legal.html",
        "/manuales": "/herramientas/manuales/index.html",
        "/manuales/": "/herramientas/manuales/index.html",
        "/planos": "/herramientas/planos/index.html",
        "/planos/": "/herramientas/planos/index.html",
        "/checklists": "/checklists/index.html",
        "/checklists/": "/checklists/index.html",
        "/herramientas": "/herramientas/index-herramientas.html",
        "/herramientas/": "/herramientas/index-herramientas.html",
        "/support": "/support.html",
        "/support/": "/support.html",
        "/versiones": "/versiones.html",
        "/versiones/": "/versiones.html",
        "/versiones/cliente": "/versiones_cliente.html",
        "/versiones/cliente/": "/versiones_cliente.html",
        "/versiones-cliente": "/versiones_cliente.html",
    }
    target = canonical_html.get(path)
    if target and target != path:
        if query:
            target = f"{target}?{query}"
        return RedirectResponse(url=target, status_code=307)

    return await call_next(request)


# ------------------------------- CORS -------------------------------
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "http://192.168.0.40:8000",
    "http://192.168.0.40:8001",
    "https://todosevillaeste.es",
    "https://www.todosevillaeste.es",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------- Configuración DB -------------------------------
DB_READ_CONFIG = {
    "host": _require_env("DB_READ_HOST"),
    "port": int(_require_env("DB_READ_PORT")),
    "user": _require_env("DB_READ_USER"),
    "password": _require_env("DB_READ_PASSWORD"),
    "database": _require_env("DB_READ_DATABASE"),
}

DB_WRITE_CONFIG = {
    "host": _require_env("DB_WRITE_HOST"),
    "port": int(_require_env("DB_WRITE_PORT")),
    "user": _require_env("DB_WRITE_USER"),
    "password": _require_env("DB_WRITE_PASSWORD"),
    "database": _require_env("DB_WRITE_DATABASE"),
}

DAYS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
AGENTS_API_BASE = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")
AGENTS_PUBLIC_CHAT_TIMEOUT_SECONDS = float((os.getenv("AGENTS_PUBLIC_CHAT_TIMEOUT_SECONDS") or "185").strip() or "185")
AGENTS_PUBLIC_STREAM_TIMEOUT_SECONDS = float((os.getenv("AGENTS_PUBLIC_STREAM_TIMEOUT_SECONDS") or "190").strip() or "190")

# ------------------------------- Carpetas estáticas -------------------------------
WEB_DIR = Path("web")
VUE_APP_DIR = WEB_DIR / "app"
VUE_DIST_DIR = VUE_APP_DIR / "dist"
VUE_DIST_INDEX = VUE_DIST_DIR / "index.html"
RACK_ROOT_DIR = WEB_DIR / "frontend" / "herramientas" / "rack"
RACK_FRONTEND_DIR = RACK_ROOT_DIR / "frontend"
RACK_FRONTEND_DIST_DIR = RACK_FRONTEND_DIR / "dist"
RACK_BACKEND_DATA_DIR = RACK_ROOT_DIR / "backend" / "data" / "projects"
RACK_BACKEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR = WEB_DIR / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)
BUSINESS_IMG_DIR = IMG_DIR / "businesses"
BUSINESS_IMG_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_IMG_DIR = IMG_DIR / "reviews"
REVIEW_IMG_DIR.mkdir(parents=True, exist_ok=True)
MESSAGE_IMG_DIR = IMG_DIR / "messages"
MESSAGE_IMG_DIR.mkdir(parents=True, exist_ok=True)
SUPPORT_IMG_DIR = IMG_DIR / "support"
SUPPORT_IMG_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------- Auth Config -------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SESSION_COOKIE = "tsev_session"
SESSION_DURATION = 60 * 60 * 24                # 1 día
SESSION_DURATION_REMEMBER = 60 * 60 * 24 * 30  # 30 días
SESSION_COOKIE_DOMAIN_RAW = (os.getenv("SESSION_COOKIE_DOMAIN") or "").strip()
SESSION_COOKIE_DOMAIN = SESSION_COOKIE_DOMAIN_RAW or None
SESSION_COOKIE_SECURE = (os.getenv("SESSION_COOKIE_SECURE", "0").strip().lower() in {"1", "true", "yes", "on"})
CODE_EXPIRY_MINUTES = 10
EMAIL_SENDER = "gestion.todosevillaeste@gmail.com"
EMAIL_PASSWORD = _require_env("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
ADMIN_MAIL_FROM = (os.getenv("ADMIN_MAIL_FROM") or "todosevillaeste@gmail.com").strip()
ADMIN_MAIL_LOGIN = (os.getenv("ADMIN_MAIL_LOGIN") or EMAIL_SENDER).strip()
ADMIN_MAIL_PASSWORD = (os.getenv("ADMIN_MAIL_PASSWORD") or EMAIL_PASSWORD).strip()
ADMIN_IMAP_HOST = (os.getenv("ADMIN_IMAP_HOST") or "imap.gmail.com").strip()
ADMIN_IMAP_PORT = int((os.getenv("ADMIN_IMAP_PORT") or "993").strip() or "993")
ADMIN_IMAP_LOGIN = (os.getenv("ADMIN_IMAP_LOGIN") or ADMIN_MAIL_LOGIN or EMAIL_SENDER).strip()
ADMIN_IMAP_PASSWORD = (os.getenv("ADMIN_IMAP_PASSWORD") or ADMIN_MAIL_PASSWORD or EMAIL_PASSWORD).strip()
GMAIL_API_CLIENT_ID = (os.getenv("GMAIL_API_CLIENT_ID") or "").strip()
GMAIL_API_CLIENT_SECRET = (os.getenv("GMAIL_API_CLIENT_SECRET") or "").strip()
GMAIL_API_REFRESH_TOKEN = (os.getenv("GMAIL_API_REFRESH_TOKEN") or "").strip()
GMAIL_API_USER_EMAIL = (os.getenv("GMAIL_API_USER_EMAIL") or ADMIN_MAIL_LOGIN or EMAIL_SENDER).strip()
GMAIL_API_TIMEOUT = float((os.getenv("GMAIL_API_TIMEOUT_SECONDS") or "20").strip() or "20")
GOOGLE_OAUTH_CLIENT_ID = (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
MICROSOFT_OAUTH_CLIENT_ID = (os.getenv("MICROSOFT_OAUTH_CLIENT_ID") or "").strip()
MICROSOFT_OAUTH_CLIENT_SECRET = (os.getenv("MICROSOFT_OAUTH_CLIENT_SECRET") or "").strip()
MICROSOFT_OAUTH_TENANT = (os.getenv("MICROSOFT_OAUTH_TENANT") or "common").strip() or "common"
OAUTH_STATE_TTL_SECONDS = int((os.getenv("OAUTH_STATE_TTL_SECONDS") or "600").strip() or "600")
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_REVIEW_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MESSAGE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SEVILLA_TZ = ZoneInfo("Europe/Madrid")
WEATHER_URL = "https://api.open-meteo.com/v1/forecastlatitude=37.39&longitude=-5.99&current_weather=true"
ADMIN_SESSION_COOKIE = "tsev_admin_session"
ADMIN_CONFIG_PATH = Path(__file__).resolve().parent / "admin_auth_config.json"
ADMIN_SESSIONS_PATH = Path(__file__).resolve().parent / "admin_sessions.json"
ANDROID_VERSIONS_PATH = Path(__file__).resolve().parent / "android_versions.json"
ANDROID_RELEASES_DIR = WEB_DIR / "downloads" / "android"
ANDROID_RELEASES_DIR.mkdir(parents=True, exist_ok=True)
(ANDROID_RELEASES_DIR / "client").mkdir(parents=True, exist_ok=True)
(ANDROID_RELEASES_DIR / "admin").mkdir(parents=True, exist_ok=True)
WEB_VERSIONS_PATH = Path(__file__).resolve().parent / "web_versions.json"
WEB_VERSIONS_DIR = WEB_DIR / "versions_web"
WEB_VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
VISIBILITY_CONFIG_PATH = Path(__file__).resolve().parent / "visibility_config.json"
ADMIN_DEFAULT_USERNAME = "admin.alberto.tse"
ADMIN_DEFAULT_EMAIL = "gestion.todosevillaeste@gmail.com"
ADMIN_DEFAULT_PASSWORD = _require_env("ADMIN_DEFAULT_PASSWORD")
ADMIN_DEFAULT_RECOVERY_EMAIL = "alberto2008fb@gmail.com"
REALTIME_CACHE = {
    "temperature_c": None,
    "weather_text": "--",
    "updated_at": None,
}
REALTIME_LOCK = threading.Lock()
ADMIN_LOCK = threading.Lock()
ANDROID_VERSIONS_LOCK = threading.Lock()
ANDROID_BUILD_LOCK = threading.Lock()
ANDROID_BUILD_JOBS: Dict[str, dict] = {}
WEB_VERSIONS_LOCK = threading.Lock()
WEB_VERSIONS_STREAM_LOCK = threading.Lock()
WEB_VERSIONS_STREAM_SUBSCRIBERS: List[queue.Queue] = []
WEB_VERSIONS_STREAM_BACKLOG = deque(maxlen=30)
WEB_VERSIONS_STREAM_REV = 0
VISIBILITY_LOCK = threading.Lock()
ADMIN_SESSIONS = {}
ADMIN_RECOVERY_CODES = {}
ADMIN_CONFIG = {}
MANUALES_STORAGE_DIR = WEB_DIR / "frontend" / "herramientas" / "manuales" / "almacenamiento"
MANUALES_STATE_FILE = MANUALES_STORAGE_DIR / "data.json"
MANUALES_STORAGE_LOCK = threading.Lock()
MANUALES_AUTH_COOKIE = "manuales_session"
MANUALES_AUTH_FILE = Path(__file__).resolve().parent / "manuales_sessions.json"
MANUALES_AUTH_USERS = {
    "alberto": "alberto",
    "franklin": "franklin",
}
MANUALES_AUTH_SESSIONS: Dict[str, dict] = {}
MANUALES_AUTH_LOCK = threading.Lock()
OAUTH_STATE_LOCK = threading.Lock()
OAUTH_STATE_STORE: Dict[str, dict] = {}
PLANOS_STORAGE_DIR = WEB_DIR / "frontend" / "herramientas" / "planos" / "almacenamiento"
PLANOS_INFRA_FILE = PLANOS_STORAGE_DIR / "infraestructura.json"
PLANOS_SEDES_FILE = PLANOS_STORAGE_DIR / "sedes.json"
PLANOS_STORAGE_LOCK = threading.Lock()
CHECKLISTS_STORAGE_DIR = WEB_DIR / "frontend" / "herramientas" / "checklists" / "almacenamiento"
CHECKLISTS_DB_FILE = CHECKLISTS_STORAGE_DIR / "db.json"
CHECKLISTS_STORAGE_LOCK = threading.Lock()
CHECKLISTS_STREAM_LOCK = threading.Lock()
CHECKLISTS_STREAM_SUBSCRIBERS: List[queue.Queue] = []
CHECKLISTS_STREAM_BACKLOG = deque(maxlen=80)
VAPID_PUBLIC_KEY = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
VAPID_PRIVATE_KEY = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
VAPID_SUBJECT = (os.getenv("VAPID_SUBJECT") or "mailto:admin@todosevillaeste.es").strip()
VAPID_KEYS_PATH = Path(__file__).resolve().parent / "vapid_keys.json"
FIREBASE_SERVICE_ACCOUNT_FILE = (os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE") or "").strip()
FIREBASE_SERVICE_ACCOUNT_JSON = (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
FIREBASE_PROJECT_ID = (os.getenv("FIREBASE_PROJECT_ID") or "").strip()
FCM_ANDROID_PACKAGE = (os.getenv("FCM_ANDROID_PACKAGE") or "com.todosevillaeste.app").strip() or "com.todosevillaeste.app"
FIREBASE_APP_INSTANCE = None
FIREBASE_INIT_ATTEMPTED = False


def _b64url_no_padding(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _safe_tree_name(raw: Any, fallback: str) -> str:
    text = normalize_space(str(raw or ""))
    if not text:
        return fallback
    # Quitar tildes/diacríticos para nombres estables y portables.
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    # Solo nombres seguros de archivo/carpeta en Windows/Linux.
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")
    return safe or fallback


def _decode_data_url_pdf(value: Any) -> Optional[bytes]:
    raw = str(value or "").strip()
    if not raw:
        return None
    marker = ";base64,"
    idx = raw.find(marker)
    if idx == -1:
        return None
    b64_data = raw[idx + len(marker):]
    try:
        data = base64.b64decode(b64_data, validate=True)
    except Exception:
        return None
    if not data.startswith(b"%PDF"):
        return None
    return data


def _reset_manuales_storage_dir() -> None:
    MANUALES_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    for child in MANUALES_STORAGE_DIR.iterdir():
        if child.name.lower() in {"data.json", "state.json"}:
            continue
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except Exception:
            continue


def _normalize_manuales_payload(payload: Any) -> dict:
    raw = payload if isinstance(payload, dict) else {}
    sections = raw.get("sections") if isinstance(raw.get("sections"), list) else []
    folders = raw.get("folders") if isinstance(raw.get("folders"), list) else []
    manuals = raw.get("manuals") if isinstance(raw.get("manuals"), list) else []
    trash = raw.get("trash") if isinstance(raw.get("trash"), list) else []
    raw_permissions = raw.get("permissions") if isinstance(raw.get("permissions"), dict) else {}
    permissions = {
        "sections": raw_permissions.get("sections") if isinstance(raw_permissions.get("sections"), dict) else {},
        "folders": raw_permissions.get("folders") if isinstance(raw_permissions.get("folders"), dict) else {},
        "manuals": raw_permissions.get("manuals") if isinstance(raw_permissions.get("manuals"), dict) else {},
    }
    return {
        "sections": sections,
        "folders": folders,
        "manuals": manuals,
        "trash": trash,
        "permissions": permissions,
        "selectedSectionId": raw.get("selectedSectionId"),
        "generatedAt": raw.get("generatedAt") or int(time.time() * 1000),
    }


def _set_manuales_session_cookie(response: Response, session_id: str, request: Optional[Request] = None) -> None:
    max_age = int(60 * 60 * 24 * 30)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max_age)
    secure = False
    if request is not None:
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").strip().lower()
        secure = proto == "https"
    response.set_cookie(
        key=MANUALES_AUTH_COOKIE,
        value=session_id,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        expires=expires_at,
        path="/",
    )


def _save_manuales_auth_sessions_locked() -> None:
    data = {"sessions": MANUALES_AUTH_SESSIONS}
    tmp_file = MANUALES_AUTH_FILE.with_suffix(".tmp")
    try:
        tmp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_file.replace(MANUALES_AUTH_FILE)
    except Exception:
        try:
            if tmp_file.exists():
                tmp_file.unlink()
        except Exception:
            pass


def _load_manuales_auth_sessions() -> None:
    now_ts = int(time.time())
    loaded: Dict[str, dict] = {}
    try:
        if MANUALES_AUTH_FILE.exists():
            raw = json.loads(MANUALES_AUTH_FILE.read_text(encoding="utf-8"))
            sessions = raw.get("sessions") if isinstance(raw, dict) else {}
            if isinstance(sessions, dict):
                for sid, row in sessions.items():
                    if not isinstance(row, dict):
                        continue
                    username = normalize_space(str(row.get("username") or "")).lower()
                    expires_at = int(row.get("expires_at") or 0)
                    if username and expires_at > now_ts:
                        loaded[str(sid)] = {"username": username, "expires_at": expires_at}
    except Exception:
        loaded = {}

    with MANUALES_AUTH_LOCK:
        MANUALES_AUTH_SESSIONS.clear()
        MANUALES_AUTH_SESSIONS.update(loaded)
        _save_manuales_auth_sessions_locked()


def _clear_manuales_session_cookie(response: Response, request: Optional[Request] = None) -> None:
    kwargs = {
        "key": MANUALES_AUTH_COOKIE,
        "path": "/",
        "httponly": True,
        "samesite": "lax",
    }
    response.delete_cookie(**kwargs)


_load_manuales_auth_sessions()


def get_manuales_current_user(request: Request) -> dict:
    session_id = (request.cookies.get(MANUALES_AUTH_COOKIE) or "").strip()
    if not session_id:
        raise HTTPException(status_code=401, detail="Login requerido")
    now_ts = int(time.time())
    with MANUALES_AUTH_LOCK:
        row = MANUALES_AUTH_SESSIONS.get(session_id)
        if not row:
            raise HTTPException(status_code=401, detail="Sesion invalida")
        expires_at = int(row.get("expires_at") or 0)
        if expires_at <= now_ts:
            MANUALES_AUTH_SESSIONS.pop(session_id, None)
            _save_manuales_auth_sessions_locked()
            raise HTTPException(status_code=401, detail="Sesion expirada")
        return {"username": str(row.get("username") or "").strip().lower()}


def _normalize_planos_infra(payload: Any) -> dict:
    raw = payload if isinstance(payload, dict) else {}
    cpds = raw.get("cpds") if isinstance(raw.get("cpds"), list) else []
    return {"cpds": cpds}


def _normalize_planos_sedes(payload: Any) -> dict:
    raw = payload if isinstance(payload, dict) else {}
    sedes = raw.get("sedes") if isinstance(raw.get("sedes"), list) else []
    return {"sedes": sedes}


def _materialize_manuales_storage(payload: dict) -> dict:
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    folders = payload.get("folders") if isinstance(payload.get("folders"), list) else []
    manuals = payload.get("manuals") if isinstance(payload.get("manuals"), list) else []

    section_map: Dict[str, dict] = {}
    for idx, sec in enumerate(sections, start=1):
        if not isinstance(sec, dict):
            continue
        sec_id = str(sec.get("id") or "").strip()
        if not sec_id:
            continue
        section_map[sec_id] = {
            "name": _safe_tree_name(sec.get("name"), f"seccion_{idx}"),
        }

    folder_map: Dict[str, dict] = {}
    for idx, folder in enumerate(folders, start=1):
        if not isinstance(folder, dict):
            continue
        folder_id = str(folder.get("id") or "").strip()
        section_id = str(folder.get("sectionId") or "").strip()
        if not folder_id or not section_id or section_id not in section_map:
            continue
        folder_map[folder_id] = {
            "name": _safe_tree_name(folder.get("name"), f"carpeta_{idx}"),
            "sectionId": section_id,
            "parentId": str(folder.get("parentId") or "").strip() or None,
        }

    def folder_chain(folder_id: Optional[str]) -> List[str]:
        chain: List[str] = []
        seen = set()
        cur = folder_id
        while cur:
            node = folder_map.get(cur)
            if not node or cur in seen:
                break
            seen.add(cur)
            chain.insert(0, node["name"])
            cur = node["parentId"]
        return chain

    _reset_manuales_storage_dir()
    written_dirs = 0
    written_pdfs = 0
    name_counters: Dict[str, int] = {}

    for sec in section_map.values():
        sec_dir = MANUALES_STORAGE_DIR / sec["name"]
        sec_dir.mkdir(parents=True, exist_ok=True)
        written_dirs += 1

    for folder_id, folder in folder_map.items():
        section_name = section_map[folder["sectionId"]]["name"]
        rel_chain = folder_chain(folder_id)
        target = MANUALES_STORAGE_DIR / section_name
        for part in rel_chain:
            target = target / part
        target.mkdir(parents=True, exist_ok=True)
        written_dirs += 1

    for idx, manual in enumerate(manuals, start=1):
        if not isinstance(manual, dict):
            continue
        section_id = str(manual.get("sectionId") or "").strip()
        if not section_id or section_id not in section_map:
            continue
        folder_id = str(manual.get("parentId") or "").strip() or None
        section_name = section_map[section_id]["name"]
        parts = [MANUALES_STORAGE_DIR / section_name]
        for piece in folder_chain(folder_id):
            parts.append(parts[-1] / piece)
        target_dir = parts[-1]
        target_dir.mkdir(parents=True, exist_ok=True)

        base_name = _safe_tree_name(manual.get("title"), f"manual_{idx}")
        uniq_key = str(target_dir / base_name).lower()
        next_n = name_counters.get(uniq_key, 0) + 1
        name_counters[uniq_key] = next_n
        final_name = base_name if next_n == 1 else f"{base_name}_{next_n}"

        pdf_bytes = _decode_data_url_pdf(manual.get("pdfData"))
        if not pdf_bytes:
            continue

        pdf_path = target_dir / f"{final_name}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        written_pdfs += 1

    return {
        "sections": len(section_map),
        "folders": len(folder_map),
        "manuals_received": len(manuals),
        "pdfs_written": written_pdfs,
        "directories_written": written_dirs,
    }


def _load_or_generate_vapid_keys() -> None:
    global VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT

    if VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY:
        return
    if not webpush or not Vapid01 or not Encoding or not PublicFormat:
        return

    try:
        if VAPID_KEYS_PATH.exists():
            stored = json.loads(VAPID_KEYS_PATH.read_text(encoding="utf-8"))
            public_key = str((stored or {}).get("public_key") or "").strip()
            private_key = str((stored or {}).get("private_key") or "").strip()
            subject = str((stored or {}).get("subject") or "").strip()
            if public_key and private_key:
                VAPID_PUBLIC_KEY = public_key
                VAPID_PRIVATE_KEY = private_key
                if subject:
                    VAPID_SUBJECT = subject
                return
    except Exception as exc:
        logger.warning("No se pudieron leer claves VAPID persistidas: %s", exc)

    try:
        vapid = Vapid01()
        vapid.generate_keys()
        public_raw = vapid.public_key.public_bytes(
            encoding=Encoding.X962,
            format=PublicFormat.UncompressedPoint,
        )
        private_number = int(vapid.private_key.private_numbers().private_value)
        private_raw = private_number.to_bytes(32, "big")

        VAPID_PUBLIC_KEY = _b64url_no_padding(public_raw)
        VAPID_PRIVATE_KEY = _b64url_no_padding(private_raw)

        payload = {
            "public_key": VAPID_PUBLIC_KEY,
            "private_key": VAPID_PRIVATE_KEY,
            "subject": VAPID_SUBJECT,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        VAPID_KEYS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Claves VAPID generadas en %s", VAPID_KEYS_PATH)
    except Exception as exc:
        logger.warning("No se pudieron generar claves VAPID: %s", exc)


_load_or_generate_vapid_keys()


def _firebase_credentials_from_env():
    if not firebase_credentials:
        return None
    if FIREBASE_SERVICE_ACCOUNT_JSON:
        try:
            payload = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
            if isinstance(payload, dict) and payload:
                return firebase_credentials.Certificate(payload)
        except Exception as exc:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_JSON inválido: %s", exc)
    if FIREBASE_SERVICE_ACCOUNT_FILE:
        path = Path(FIREBASE_SERVICE_ACCOUNT_FILE)
        if path.exists() and path.is_file():
            try:
                return firebase_credentials.Certificate(str(path))
            except Exception as exc:
                logger.warning("No se pudo cargar FIREBASE_SERVICE_ACCOUNT_FILE: %s", exc)
    return None


def get_firebase_app():
    global FIREBASE_APP_INSTANCE, FIREBASE_INIT_ATTEMPTED
    if FIREBASE_APP_INSTANCE is not None:
        return FIREBASE_APP_INSTANCE
    if FIREBASE_INIT_ATTEMPTED:
        return None
    FIREBASE_INIT_ATTEMPTED = True
    if not firebase_admin:
        return None
    cred = _firebase_credentials_from_env()
    if not cred:
        logger.info("FCM deshabilitado: faltan credenciales Firebase.")
        return None
    try:
        options = {}
        if FIREBASE_PROJECT_ID:
            options["projectId"] = FIREBASE_PROJECT_ID
        FIREBASE_APP_INSTANCE = firebase_admin.initialize_app(cred, options=options or None)
        logger.info("Firebase inicializado para FCM.")
        return FIREBASE_APP_INSTANCE
    except Exception as exc:
        logger.warning("No se pudo inicializar Firebase: %s", exc)
        return None

# ------------------------------- Helpers -------------------------------
def _is_ip_literal(value: str) -> bool:
    host = (value or "").strip().strip("[]")
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except Exception:
        return False


def _resolve_cookie_domain_for_request(request: Optional[Request]) -> Optional[str]:
    configured = (SESSION_COOKIE_DOMAIN or "").strip().lstrip(".")
    if not configured:
        return None
    configured = configured.split(":")[0].strip().lower()
    if not configured or _is_ip_literal(configured):
        return None
    if request is None:
        return configured
    host = (request.url.hostname or "").strip().lower()
    if not host or _is_ip_literal(host):
        return None
    if host == configured or host.endswith(f".{configured}"):
        return configured
    return None


def set_user_session_cookie(
    response: Response,
    session_id: str,
    duration: int,
    request: Optional[Request] = None,
) -> None:
    secure_cookie = SESSION_COOKIE_SECURE
    if request is not None and request.url.scheme != "https":
        secure_cookie = False
    kwargs = {
        "key": SESSION_COOKIE,
        "value": session_id,
        "max_age": duration,
        "httponly": True,
        "path": "/",
        "samesite": "lax",
        "secure": secure_cookie,
    }
    cookie_domain = _resolve_cookie_domain_for_request(request)
    if cookie_domain:
        kwargs["domain"] = cookie_domain
    response.set_cookie(**kwargs)


def clear_user_session_cookie(response: Response, request: Optional[Request] = None) -> None:
    kwargs = {"key": SESSION_COOKIE, "path": "/"}
    cookie_domain = _resolve_cookie_domain_for_request(request)
    if cookie_domain:
        kwargs["domain"] = cookie_domain
    response.delete_cookie(**kwargs)


def hash_password(pw: str):
    # bcrypt no admite bytes NUL; usar hexdigest evita ese problema.
    sha_pw_hex = hashlib.sha256(pw.encode("utf-8")).hexdigest()
    return pwd_context.hash(sha_pw_hex)

def verify_password(pw: str, hashed: str):
    sha_pw_hex = hashlib.sha256(pw.encode("utf-8")).hexdigest()
    try:
        if pwd_context.verify(sha_pw_hex, hashed):
            return True
    except Exception:
        pass

    # Compatibilidad con hashes antiguos (digest binario) generados previamente.
    try:
        legacy_sha_pw = hashlib.sha256(pw.encode("utf-8")).digest()
        return pwd_context.verify(legacy_sha_pw, hashed)
    except Exception:
        return False

def generate_code():
    return str(secrets.randbelow(900000) + 100000)

def send_email_code(email: str, code: str):
    msg = MIMEText(f"Tu código de verificación es: {code}")
    msg["Subject"] = f"Código de verificación {code}"
    msg["From"] = EMAIL_SENDER
    msg["To"] = email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


def send_business_credentials_email(email: str, username: str, password: str, place_name: str, public_id: int):
    safe_place = place_name or f"Negocio {public_id}"
    body = (
        f"Buenos dias, para iniciar sesión en tu panel de gestión del negocio {safe_place}, "
        f"tu usuario es: {username} y tu contraseña es: {password} "
        f"la cual tendrás que cambiar en el primer inicio de sesion"
    )
    msg = MIMEText(body, _subtype="plain", _charset="utf-8")
    msg["Subject"] = str(Header("Credenciales de cuenta de negocio", "utf-8"))
    msg["From"] = EMAIL_SENDER
    msg["To"] = email
    msg["X-TSE-Mail-Type"] = "business-credentials"
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        refused = server.send_message(msg)
        if refused:
            raise RuntimeError(f"Destinatarios rechazados por SMTP: {refused}")
    logger.info(
        "Correo negocio aceptado por SMTP | to=%s | user=%s | place_id=%s | place_name=%s",
        email, username, public_id, safe_place
    )


def send_notification_email(email: str, subject: str, body: str):
    msg = MIMEText(body, _subtype="plain", _charset="utf-8")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = EMAIL_SENDER
    msg["To"] = email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


def send_business_status_notification_email(email: str, place_name: str, active: bool):
    clean_email = (email or "").strip()
    if not clean_email:
        raise ValueError("No hay correo de destino para la notificacion")
    clean_place_name = (place_name or "tu negocio").strip() or "tu negocio"
    state_label = "activado" if active else "desactivado"
    subject = f"Actualizacion de tu negocio ({clean_place_name})"
    body = (
        f"Hola,\n\n"
        f"Te informamos de que el negocio \"{clean_place_name}\" ha sido {state_label} desde el panel de administracion.\n\n"
        f"Si necesitas revisar o actualizar la ficha, puedes entrar en tu cuenta de Todo Sevilla Este.\n\n"
        f"Un saludo,\n"
        f"El equipo de Todo Sevilla Este"
    )
    send_notification_email(clean_email, subject, body)


def is_technical_revision_email(email: Optional[str]) -> bool:
    clean_email = (email or "").strip().lower()
    return bool(re.fullmatch(r"revision-\d+-\d+@todosevillaeste\.local", clean_email))


def resolve_visible_business_email(place_row: Dict[str, Any], owner_email: Optional[str] = None) -> str:
    business_email = (place_row.get("business_email") or "").strip().lower()
    contact_email = (place_row.get("contact_email") or "").strip().lower()
    owner_email = (owner_email or "").strip().lower()
    if is_technical_revision_email(business_email) and contact_email:
        return contact_email
    return business_email or contact_email or owner_email or ""


def send_notification_email_html(email: str, subject: str, body_text: str, body_html: str):
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = EMAIL_SENDER
    msg["To"] = email
    msg.attach(MIMEText(body_text or "", _subtype="plain", _charset="utf-8"))
    msg.attach(MIMEText(body_html or "", _subtype="html", _charset="utf-8"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


def send_notification_email_with_attachments(email: str, subject: str, body: str, file_paths: List[Path]):
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart()
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = EMAIL_SENDER
    msg["To"] = email
    msg.attach(MIMEText(body or "", _subtype="plain", _charset="utf-8"))

    for path in file_paths or []:
        if not path or not path.exists() or not path.is_file():
            continue
        part = MIMEBase("application", "octet-stream")
        with path.open("rb") as fh:
            part.set_payload(fh.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
        msg.attach(part)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


def slugify_business_name(name: str):
    raw = (name or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return cleaned or "negocio"


def normalize_business_display_name(name: Optional[str], fallback: str = "") -> str:
    text = (name or "").strip()
    if not text:
        text = (fallback or "").strip()
    if not text:
        return ""
    first = text[0]
    if first.isalpha():
        return first.upper() + text[1:]
    return text


def normalize_space(value: Optional[str]) -> str:
    # Recorta extremos y colapsa espacios internos repetidos.
    return " ".join(str(value or "").split()).strip()


def seems_valid_email(value: str):
    candidate = (value or "").strip()
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", candidate))


def decode_mime_header_value(raw_value: Optional[str]) -> str:
    if not raw_value:
        return ""
    try:
        from email.header import decode_header
        decoded_parts = decode_header(raw_value)
    except Exception:
        return str(raw_value)
    chunks: List[str] = []
    for part, enc in decoded_parts:
        if isinstance(part, bytes):
            try:
                chunks.append(part.decode(enc or "utf-8", errors="replace"))
            except Exception:
                chunks.append(part.decode("utf-8", errors="replace"))
        else:
            chunks.append(str(part))
    return "".join(chunks).strip()


def html_to_text_simple(html: str) -> str:
    if not html:
        return ""
    cleaned = re.sub(r"<\s*br\s*/?\s*>", "\n", html, flags=re.IGNORECASE)
    cleaned = re.sub(r"</\s*p\s*>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_email_text_parts(msg) -> Tuple[str, str]:
    plain_parts: List[str] = []
    html_parts: List[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = (part.get_content_type() or "").lower()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("utf-8", errors="replace")
            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(text)
    else:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            charset = msg.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("utf-8", errors="replace")
            ctype = (msg.get_content_type() or "").lower()
            if ctype == "text/html":
                html_parts.append(text)
            else:
                plain_parts.append(text)
    plain_text = "\n".join([p.strip() for p in plain_parts if p and p.strip()]).strip()
    html_text = "\n".join([h.strip() for h in html_parts if h and h.strip()]).strip()
    if not plain_text and html_text:
        plain_text = html_to_text_simple(html_text)
    return plain_text, html_text


def _decode_imap_mailbox_name(raw_name: str) -> str:
    value = str(raw_name or "").strip().strip('"')
    if not value:
        return ""
    try:
        decoded = imaplib.IMAP4._decode_utf7(value)  # type: ignore[attr-defined]
        return str(decoded or value)
    except Exception:
        return value


def list_admin_imap_mailboxes() -> List[str]:
    if not ADMIN_IMAP_LOGIN or not ADMIN_IMAP_PASSWORD:
        return []
    try:
        mailbox = imaplib.IMAP4_SSL(ADMIN_IMAP_HOST, ADMIN_IMAP_PORT)
        mailbox.login(ADMIN_IMAP_LOGIN, ADMIN_IMAP_PASSWORD)
        status, rows = mailbox.list()
        names: List[str] = []
        if status == "OK":
            for row in rows or []:
                raw = row.decode("utf-8", errors="ignore") if isinstance(row, (bytes, bytearray)) else str(row or "")
                # Typical format: '(\\HasNoChildren) "/" "INBOX"'
                match = re.search(r'"([^"]+)"\s*$', raw.strip())
                if match:
                    names.append(_decode_imap_mailbox_name(match.group(1)))
        try:
            mailbox.logout()
        except Exception:
            pass
        return names
    except Exception:
        return []


def resolve_admin_imap_mailbox(alias: str) -> str:
    key = normalize_space(alias).lower()
    if key in {"", "inbox", "entrada", "recibidos"}:
        return "INBOX"
    if key in {"sent", "enviados"}:
        preferred = [
            "[Gmail]/Sent Mail",
            "[Gmail]/Enviados",
            "Sent",
            "Sent Items",
            "Enviados",
        ]
    elif key in {"trash", "papelera", "deleted"}:
        preferred = [
            "[Gmail]/Trash",
            "[Gmail]/Papelera",
            "Trash",
            "Deleted Items",
            "Papelera",
        ]
    else:
        return alias

    available = {name.lower(): name for name in list_admin_imap_mailboxes()}
    for candidate in preferred:
        exact = available.get(candidate.lower())
        if exact:
            return exact
    for name in available.values():
        low = name.lower()
        if key in {"sent", "enviados"} and ("sent" in low or "envi" in low):
            return name
        if key in {"trash", "papelera", "deleted"} and ("trash" in low or "papelera" in low or "deleted" in low):
            return name
    return preferred[0]


def open_admin_imap_inbox(mailbox_name: str = "INBOX"):
    if not ADMIN_IMAP_LOGIN or not ADMIN_IMAP_PASSWORD:
        raise HTTPException(status_code=500, detail="IMAP no configurado para la cuenta admin")
    try:
        selected_name = resolve_admin_imap_mailbox(mailbox_name)
        mailbox = imaplib.IMAP4_SSL(ADMIN_IMAP_HOST, ADMIN_IMAP_PORT)
        mailbox.login(ADMIN_IMAP_LOGIN, ADMIN_IMAP_PASSWORD)
        status, _ = mailbox.select(selected_name)
        if status != "OK":
            mailbox.logout()
            raise HTTPException(status_code=500, detail=f"No se pudo abrir el buzón IMAP: {selected_name}")
        return mailbox
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo conectar al buzón IMAP")


def parse_inbox_message_payload(uid: str, raw_message: bytes, is_unread: bool, flags_blob: bytes = b"") -> dict:
    msg = py_email.message_from_bytes(raw_message)
    raw_subject = msg.get("Subject", "")
    raw_from = msg.get("From", "")
    raw_to = msg.get("To", "")
    raw_cc = msg.get("Cc", "")
    parsed_name, parsed_email = parseaddr(raw_from)
    from_name = decode_mime_header_value(parsed_name)
    from_email = (parsed_email or "").strip().lower()
    from_display = decode_mime_header_value(raw_from)
    to_display = decode_mime_header_value(raw_to)
    cc_display = decode_mime_header_value(raw_cc)
    subject = decode_mime_header_value(raw_subject)
    plain_body, html_body = extract_email_text_parts(msg)
    snippet_source = plain_body or html_to_text_simple(html_body)
    snippet = normalize_space((snippet_source or "")[:420])
    date_raw = msg.get("Date", "")
    date_iso = None
    if date_raw:
        try:
            date_iso = parsedate_to_datetime(date_raw).astimezone(SEVILLA_TZ).isoformat()
        except Exception:
            date_iso = None
    message_id = (msg.get("Message-ID") or "").strip()
    references = (msg.get("References") or "").strip()
    in_reply_to = (msg.get("In-Reply-To") or "").strip()
    is_starred = b"\\Flagged" in (flags_blob or b"")
    return {
        "uid": str(uid),
        "subject": subject or "(Sin asunto)",
        "from": from_display,
        "from_name": from_name,
        "from_email": from_email,
        "to": to_display,
        "cc": cc_display,
        "snippet": snippet,
        "body_text": plain_body or "",
        "body_html": html_body or "",
        "date": date_iso,
        "is_unread": bool(is_unread),
        "is_starred": bool(is_starred),
        "message_id": message_id,
        "references": references,
        "in_reply_to": in_reply_to,
    }


GMAIL_API_TOKEN_CACHE = {
    "token": "",
    "expires_at": 0.0,
}


def gmail_api_enabled() -> bool:
    return bool(GMAIL_API_CLIENT_ID and GMAIL_API_CLIENT_SECRET and GMAIL_API_REFRESH_TOKEN)


def _gmail_folder_label(folder: str) -> str:
    key = normalize_space(folder).lower()
    if key in {"sent", "enviados"}:
        return "SENT"
    if key in {"trash", "papelera", "deleted"}:
        return "TRASH"
    return "INBOX"


def _gmail_folder_alias(folder: str) -> str:
    key = normalize_space(folder).lower()
    if key in {"sent", "enviados"}:
        return "sent"
    if key in {"trash", "papelera", "deleted"}:
        return "trash"
    if key in {"unread", "no_leidos", "no-leidos"}:
        return "unread"
    if key in {"starred", "destacados"}:
        return "starred"
    return "inbox"


def _gmail_decode_b64url(raw_value: str) -> str:
    raw = str(raw_value or "").strip()
    if not raw:
        return ""
    pad = "=" * ((4 - len(raw) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(raw + pad).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _gmail_headers_to_dict(headers: List[dict]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in headers or []:
        name = str((item or {}).get("name") or "").strip().lower()
        if not name:
            continue
        out[name] = str((item or {}).get("value") or "")
    return out


def _gmail_extract_text_parts(payload: dict) -> Tuple[str, str]:
    if not isinstance(payload, dict):
        return "", ""
    plain_parts: List[str] = []
    html_parts: List[str] = []

    def walk(part: dict):
        mime_type = str((part or {}).get("mimeType") or "").lower()
        body_data = str(((part or {}).get("body") or {}).get("data") or "")
        if mime_type == "text/plain" and body_data:
            plain_parts.append(_gmail_decode_b64url(body_data))
        elif mime_type == "text/html" and body_data:
            html_parts.append(_gmail_decode_b64url(body_data))
        for child in ((part or {}).get("parts") or []):
            if isinstance(child, dict):
                walk(child)

    walk(payload)
    plain = "\n".join([p.strip() for p in plain_parts if p and p.strip()]).strip()
    html = "\n".join([h.strip() for h in html_parts if h and h.strip()]).strip()
    if not plain and html:
        plain = html_to_text_simple(html)
    return plain, html


def _gmail_fetch_access_token() -> Tuple[str, float]:
    if not gmail_api_enabled():
        raise HTTPException(status_code=500, detail="Gmail API no configurada")
    body = urllib.parse.urlencode({
        "client_id": GMAIL_API_CLIENT_ID,
        "client_secret": GMAIL_API_CLIENT_SECRET,
        "refresh_token": GMAIL_API_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=GMAIL_API_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise HTTPException(status_code=500, detail=f"No se pudo obtener token OAuth de Gmail: {detail or exc.reason}")
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo conectar con OAuth de Gmail")

    token = str(data.get("access_token") or "").strip()
    expires_in = float(data.get("expires_in") or 3600)
    if not token:
        raise HTTPException(status_code=500, detail="OAuth de Gmail no devolvió access_token")
    return token, (time.time() + max(60.0, expires_in - 60.0))


def _gmail_access_token() -> str:
    now = time.time()
    token = str(GMAIL_API_TOKEN_CACHE.get("token") or "")
    expires_at = float(GMAIL_API_TOKEN_CACHE.get("expires_at") or 0.0)
    if token and now < expires_at:
        return token
    new_token, new_exp = _gmail_fetch_access_token()
    GMAIL_API_TOKEN_CACHE["token"] = new_token
    GMAIL_API_TOKEN_CACHE["expires_at"] = new_exp
    return new_token


def _gmail_api_request(method: str, path: str, query: Optional[dict] = None, payload: Optional[dict] = None) -> dict:
    token = _gmail_access_token()
    url = f"https://gmail.googleapis.com/gmail/v1/users/me{path}"
    if query:
        qs = urllib.parse.urlencode(query, doseq=True)
        if qs:
            url = f"{url}?{qs}"
    body = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=GMAIL_API_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        status = int(exc.code or 500)
        raise HTTPException(status_code=500 if status >= 500 else status, detail=f"Gmail API error: {detail or exc.reason}")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo conectar con Gmail API")


def _gmail_message_to_payload(message: dict, include_body: bool = False) -> dict:
    payload = message.get("payload") or {}
    headers = _gmail_headers_to_dict(payload.get("headers") or [])
    raw_from = headers.get("from", "")
    from_name, from_email = parseaddr(raw_from)
    raw_to = headers.get("to", "")
    raw_cc = headers.get("cc", "")
    subject = decode_mime_header_value(headers.get("subject", "")) or "(Sin asunto)"
    date_raw = headers.get("date", "")
    date_iso = None
    if date_raw:
        try:
            date_iso = parsedate_to_datetime(date_raw).astimezone(SEVILLA_TZ).isoformat()
        except Exception:
            date_iso = None
    label_ids = {str(x) for x in (message.get("labelIds") or [])}
    plain_body = ""
    html_body = ""
    if include_body:
        plain_body, html_body = _gmail_extract_text_parts(payload)
    snippet = normalize_space(str(message.get("snippet") or "")[:420])
    if not snippet and plain_body:
        snippet = normalize_space(plain_body[:420])
    return {
        "uid": str(message.get("id") or ""),
        "subject": subject,
        "from": decode_mime_header_value(raw_from),
        "from_name": decode_mime_header_value(from_name),
        "from_email": (from_email or "").strip().lower(),
        "to": decode_mime_header_value(raw_to),
        "cc": decode_mime_header_value(raw_cc),
        "snippet": snippet,
        "body_text": plain_body,
        "body_html": html_body,
        "date": date_iso,
        "is_unread": "UNREAD" in label_ids,
        "is_starred": "STARRED" in label_ids,
        "message_id": headers.get("message-id", ""),
        "references": headers.get("references", ""),
        "in_reply_to": headers.get("in-reply-to", ""),
        "thread_id": str(message.get("threadId") or ""),
    }


def feedback_thread_tag(feedback_id: int) -> str:
    return f"[MEJORA #{int(feedback_id)}]"


def fetch_feedback_email_replies(feedback_id: int, target_email: str, limit: int = 80) -> List[dict]:
    cleaned_email = (target_email or "").strip().lower()
    if not cleaned_email:
        return []
    tag = feedback_thread_tag(int(feedback_id)).lower()
    mailbox = open_admin_imap_inbox()
    try:
        status, data = mailbox.uid("search", None, "ALL")
        if status != "OK":
            return []
        raw_uids = [x.decode("utf-8", errors="ignore") for x in (data[0].split() if data and data[0] else [])]
        candidate_uids = raw_uids[-320:]
        rows: List[dict] = []
        seen_message_ids = set()
        for uid in reversed(candidate_uids):
            fetch_status, fetched = mailbox.uid("fetch", uid, "(RFC822 FLAGS)")
            if fetch_status != "OK" or not fetched:
                continue
            raw_message = b""
            flag_blob = b""
            for item in fetched:
                if not isinstance(item, tuple) or len(item) < 2:
                    continue
                flag_blob = item[0] if isinstance(item[0], (bytes, bytearray)) else flag_blob
                if isinstance(item[1], (bytes, bytearray)):
                    raw_message = item[1]
            if not raw_message:
                continue
            payload = parse_inbox_message_payload(uid, raw_message, b"\\Seen" not in (flag_blob or b""), flag_blob)
            from_email = (payload.get("from_email") or "").strip().lower()
            if from_email != cleaned_email:
                continue
            subject = (payload.get("subject") or "").strip().lower()
            if tag not in subject:
                continue
            msg_id = (payload.get("message_id") or "").strip()
            if msg_id and msg_id in seen_message_ids:
                continue
            if msg_id:
                seen_message_ids.add(msg_id)
            rows.append({
                "sender_type": "user_email",
                "body": payload.get("body_text") or payload.get("snippet") or "",
                "email_message_id": msg_id or None,
                "created_at": payload.get("date"),
            })
            if len(rows) >= int(limit):
                break
        rows.reverse()
        return rows
    finally:
        try:
            mailbox.close()
        except Exception:
            pass
        try:
            mailbox.logout()
        except Exception:
            pass

def create_session(cursor, user_id: int, remember: bool):
    session_id = secrets.token_hex(32)
    duration = SESSION_DURATION_REMEMBER if remember else SESSION_DURATION
    expires = datetime.utcnow() + timedelta(seconds=duration)
    cursor.execute(
        "INSERT INTO sessions (id, user_id, expires_at) VALUES (%s,%s,%s)",
        (session_id, user_id, expires)
    )
    return session_id, duration

def get_next_public_id(cursor):
    cursor.execute("SELECT COALESCE(MAX(public_id),0)+1 AS next_id FROM places")
    row = cursor.fetchone()
    if isinstance(row, dict):
        return int(row.get("next_id") or 1)
    if isinstance(row, (tuple, list)):
        return int(row[0] or 1)
    return 1

def parse_db_bool(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8")
        except Exception:
            return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off", ""}:
            return False
    return bool(value)


def normalize_user_roles_payload(
    role_client: Optional[bool],
    role_business: Optional[bool],
    role_admin: Optional[bool],
) -> dict:
    return {
        "client": True if role_client is None else bool(role_client),
        "business": bool(role_business),
        "admin": bool(role_admin),
    }


def get_managed_place_public_id_for_user(conn, user_id: int) -> Optional[int]:
    try:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT place_public_id
                FROM place_user_assignments
                WHERE user_id=%s
                ORDER BY assigned_at DESC, place_public_id DESC
                LIMIT 1
                """,
                (int(user_id),)
            )
            row = cursor.fetchone() or {}
        finally:
            cursor.close()
        mapped_value = row.get("place_public_id")
        if mapped_value is not None:
            try:
                return int(mapped_value)
            except Exception:
                pass
    except Exception:
        pass

    place_columns = get_places_table_columns(conn)
    if "owner_user_id" not in place_columns:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT public_id FROM places WHERE owner_user_id=%s ORDER BY id DESC LIMIT 1",
            (int(user_id),)
        )
        row = cursor.fetchone() or {}
    finally:
        cursor.close()
    value = row.get("public_id")
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def get_user_roles_for_id(conn, user_id: int) -> dict:
    user_columns = get_users_table_columns(conn)
    select_parts = []
    if "role_client" in user_columns:
        select_parts.append("role_client")
    if "role_business" in user_columns:
        select_parts.append("role_business")
    if "role_admin" in user_columns:
        select_parts.append("role_admin")

    row = {}
    if select_parts:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {', '.join(select_parts)} FROM users WHERE id=%s LIMIT 1",
                (int(user_id),)
            )
            row = cursor.fetchone() or {}
        finally:
            cursor.close()

    roles = normalize_user_roles_payload(
        parse_db_bool(row.get("role_client")) if "role_client" in row else None,
        parse_db_bool(row.get("role_business")) if "role_business" in row else None,
        parse_db_bool(row.get("role_admin")) if "role_admin" in row else None,
    )
    managed_place_public_id = get_managed_place_public_id_for_user(conn, int(user_id))
    return {
        "roles": roles,
        "managed_place_public_id": managed_place_public_id,
    }


def ensure_user_has_business_role(conn, user_id: int):
    role_info = get_user_roles_for_id(conn, int(user_id))
    if not bool((role_info.get("roles") or {}).get("business")):
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene rol de negocio")
    return role_info


def get_place_name_for_public_id(conn, public_id: Optional[int]) -> str:
    pid = int(public_id or 0)
    if pid <= 0:
        return ""
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT name FROM places WHERE public_id=%s LIMIT 1", (pid,))
        row = cursor.fetchone() or {}
    finally:
        cursor.close()
    return normalize_business_display_name(row.get("name"), f"Negocio {pid}")


def save_admin_config():
    ADMIN_CONFIG_PATH.write_text(
        json.dumps(ADMIN_CONFIG, ensure_ascii=True, indent=2),
        encoding="utf-8"
    )


def _normalize_qr_allow_rules(values: Optional[List[str]]) -> List[str]:
    out: List[str] = []
    for raw in values or []:
        rule = str(raw or "").strip()
        if not rule:
            continue
        if rule not in out:
            out.append(rule)
    return out


def save_admin_sessions():
    serializable = {}
    for sid, item in ADMIN_SESSIONS.items():
        serializable[sid] = {
            "created_at": item.get("created_at").isoformat() if item.get("created_at") else None,
            "expires_at": item.get("expires_at").isoformat() if item.get("expires_at") else None
        }
    ADMIN_SESSIONS_PATH.write_text(
        json.dumps(serializable, ensure_ascii=True, indent=2),
        encoding="utf-8"
    )


def _default_android_versions_payload() -> dict:
    return {
        "client": {"active_id": None, "items": []},
        "admin": {"active_id": None, "items": []},
    }


def _default_web_versions_payload() -> dict:
    return {
        "public": {"active_id": None, "test_active_id": None, "items": []},
        "admin": {"active_id": None, "test_active_id": None, "items": []},
    }


def load_android_versions_payload() -> dict:
    if not ANDROID_VERSIONS_PATH.exists():
        payload = _default_android_versions_payload()
        ANDROID_VERSIONS_PATH.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8"
        )
        return payload
    try:
        payload = json.loads(ANDROID_VERSIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        payload = _default_android_versions_payload()
    for target in ("client", "admin"):
        payload.setdefault(target, {})
        payload[target].setdefault("active_id", None)
        payload[target].setdefault("items", [])
    return payload


def save_android_versions_payload(payload: dict):
    ANDROID_VERSIONS_PATH.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2),
        encoding="utf-8"
    )


def load_web_versions_payload() -> dict:
    if not WEB_VERSIONS_PATH.exists():
        payload = _default_web_versions_payload()
        WEB_VERSIONS_PATH.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8"
        )
        return payload
    try:
        payload = json.loads(WEB_VERSIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        payload = _default_web_versions_payload()
    for target in ("public", "admin"):
        payload.setdefault(target, {})
        payload[target].setdefault("active_id", None)
        payload[target].setdefault("test_active_id", None)
        payload[target].setdefault("items", [])
    return payload


def _build_web_versions_public_output(payload: dict) -> dict:
    out = {"public": None, "admin": None, "public_test": None, "admin_test": None}
    for target in ("public", "admin"):
        target_payload = payload.get(target) if isinstance(payload.get(target), dict) else {}
        active_id = str(target_payload.get("active_id") or "")
        test_active_id = str(target_payload.get("test_active_id") or "")
        active_entry = None
        test_entry = None
        for item in target_payload.get("items") or []:
            if str(item.get("id")) == active_id:
                active_entry = dict(item)
            if str(item.get("id")) == test_active_id:
                test_entry = dict(item)
        if target == "public":
            out["public_test"] = test_entry
        else:
            out["admin_test"] = test_entry
        out[target] = active_entry
    return out


def _broadcast_web_versions_update(payload: dict) -> None:
    global WEB_VERSIONS_STREAM_REV
    try:
        public_payload = _build_web_versions_public_output(payload)
    except Exception:
        return
    with WEB_VERSIONS_STREAM_LOCK:
        WEB_VERSIONS_STREAM_REV += 1
        message_payload = dict(public_payload)
        message_payload["rev"] = WEB_VERSIONS_STREAM_REV
        message_payload["updated_at"] = datetime.now(SEVILLA_TZ).isoformat()
        try:
            message = json.dumps(message_payload, ensure_ascii=False)
        except Exception:
            return
        WEB_VERSIONS_STREAM_BACKLOG.append(message)
        for sub_q in list(WEB_VERSIONS_STREAM_SUBSCRIBERS):
            try:
                sub_q.put_nowait(message)
            except queue.Full:
                pass


def save_web_versions_payload(payload: dict):
    WEB_VERSIONS_PATH.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2),
        encoding="utf-8"
    )
    _broadcast_web_versions_update(payload)


def get_active_web_version_entry(target: str, mode: str = "live") -> Optional[dict]:
    safe_target = (target or "").strip().lower()
    if safe_target not in {"public", "admin"}:
        return None
    mode_key = "test_active_id" if (mode or "").strip().lower() == "test" else "active_id"
    payload = load_web_versions_payload()
    active_id = str(payload.get(safe_target, {}).get(mode_key) or "")
    if not active_id:
        return None
    for item in payload.get(safe_target, {}).get("items") or []:
        if str(item.get("id")) == active_id:
            return dict(item)
    return None


def get_web_snapshot_dir(target: str, mode: str = "live") -> Optional[Path]:
    entry = get_active_web_version_entry(target, mode=mode)
    if not entry:
        return None
    if entry.get("snapshot_ready") is False:
        return None
    rel = str(entry.get("snapshot_dir") or "").strip()
    if not rel:
        return None
    candidate = (WEB_VERSIONS_DIR / rel).resolve()
    try:
        candidate.relative_to(WEB_VERSIONS_DIR.resolve())
    except ValueError:
        return None
    if candidate.exists():
        return candidate
    entry_id = str(entry.get("id") or "").strip()
    if entry_id:
        with WEB_VERSIONS_LOCK:
            payload = load_web_versions_payload()
            items = payload.get((target or "").strip().lower(), {}).get("items") or []
            for item in items:
                if str(item.get("id")) == entry_id:
                    item["snapshot_ready"] = False
                    item["snapshot_error"] = "Snapshot no encontrado"
                    break
            save_web_versions_payload(payload)
    return None


def resolve_web_public_file(rel_path: str) -> Path:
    return resolve_web_public_file_with_mode(rel_path, mode="live")


def resolve_web_public_file_with_mode(rel_path: str, mode: str = "live") -> Path:
    cleaned = str(rel_path or "").lstrip("/").replace("\\", "/")
    snapshot_root = get_web_snapshot_dir("public", mode=mode)
    if snapshot_root:
        candidate = (snapshot_root / cleaned).resolve()
        try:
            candidate.relative_to(snapshot_root.resolve())
        except ValueError:
            candidate = None
        if candidate and candidate.exists():
            return candidate
    return (WEB_DIR / "frontend" / cleaned)


def resolve_web_public_file_for_request(request: Request, rel_path: str) -> Path:
    mode = "live"
    try:
        path = str(getattr(request, "url", "") or "")
        referer = str(request.headers.get("referer") or "")
        if "/pruebas" in path or "/pruebas" in referer:
            mode = "test"
    except Exception:
        mode = "live"
    return resolve_web_public_file_with_mode(rel_path, mode=mode)


def resolve_web_admin_file(rel_path: str) -> Path:
    return resolve_web_admin_file_with_mode(rel_path, mode="live")


def resolve_web_admin_file_with_mode(rel_path: str, mode: str = "live") -> Path:
    cleaned = str(rel_path or "").lstrip("/").replace("\\", "/")
    snapshot_root = get_web_snapshot_dir("admin", mode=mode)
    if snapshot_root:
        candidate = (snapshot_root / cleaned).resolve()
        try:
            candidate.relative_to(snapshot_root.resolve())
        except ValueError:
            candidate = None
        if candidate and candidate.exists():
            return candidate
    return (WEB_DIR / "administracion" / cleaned)


def _default_visibility_config() -> dict:
    return {
        "public_visible": True,
        "ai_visible": True,
        "updated_at": datetime.now(SEVILLA_TZ).isoformat(),
    }


def load_visibility_config() -> dict:
    if not VISIBILITY_CONFIG_PATH.exists():
        payload = _default_visibility_config()
        VISIBILITY_CONFIG_PATH.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return payload
    try:
        payload = json.loads(VISIBILITY_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        payload = _default_visibility_config()
    payload.setdefault("public_visible", True)
    payload.setdefault("ai_visible", True)
    payload.setdefault("updated_at", datetime.now(SEVILLA_TZ).isoformat())
    return payload


def save_visibility_config(payload: dict):
    payload["updated_at"] = datetime.now(SEVILLA_TZ).isoformat()
    VISIBILITY_CONFIG_PATH.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def frontend_hidden_response() -> HTMLResponse:
    html = (
        "<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        "<title>Todo Sevilla Este</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:0;display:flex;"
        "align-items:center;justify-content:center;min-height:100vh;background:#f4f6f9;"
        "color:#1f2937}main{background:#fff;border:1px solid #dde2ea;border-radius:12px;"
        "padding:24px;max-width:520px;text-align:center}</style></head>"
        "<body><main><h1 style=\"margin:0 0 8px 0\">Contenido no disponible</h1>"
        "<p style=\"margin:0\">La web pública está oculta temporalmente.</p></main></body></html>"
    )
    return HTMLResponse(content=html, status_code=200, headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    })


def is_public_frontend_visible() -> bool:
    with VISIBILITY_LOCK:
        payload = load_visibility_config()
    return bool(payload.get("public_visible", True))


def is_ai_visible() -> bool:
    with VISIBILITY_LOCK:
        payload = load_visibility_config()
    return bool(payload.get("ai_visible", True))


def verify_turnstile_token(token: str, remote_ip: Optional[str] = None) -> bool:
    secret = (os.getenv("CF_TURNSTILE_SECRET") or "").strip()
    if not secret:
        return True
    if not token:
        return False
    try:
        form = {
            "secret": secret,
            "response": token,
        }
        if remote_ip:
            form["remoteip"] = remote_ip
        data = urllib.parse.urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
        return bool(payload.get("success"))
    except Exception:
        return False


def verify_hcaptcha_token(token: str, remote_ip: Optional[str] = None) -> bool:
    secret = (os.getenv("HCAPTCHA_SECRET") or "").strip()
    if not secret:
        return True
    if not token:
        return False
    try:
        form = {
            "secret": secret,
            "response": token,
        }
        if remote_ip:
            form["remoteip"] = remote_ip
        data = urllib.parse.urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            "https://hcaptcha.com/siteverify",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
        return bool(payload.get("success"))
    except Exception:
        return False


def verify_recaptcha_token(token: str, remote_ip: Optional[str] = None) -> bool:
    secret = (os.getenv("RECAPTCHA_SECRET") or "").strip()
    if not secret:
        return True
    if not token:
        return False
    try:
        form = {
            "secret": secret,
            "response": token,
        }
        if remote_ip:
            form["remoteip"] = remote_ip
        data = urllib.parse.urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            "https://www.google.com/recaptcha/api/siteverify",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
        return bool(payload.get("success"))
    except Exception:
        return False


def _antibot_secret() -> str:
    return (os.getenv("ANTI_BOT_SECRET") or "").strip()


def _captcha_secret() -> str:
    return (os.getenv("FIRST_PARTY_CAPTCHA_SECRET") or "").strip() or _antibot_secret()


def _antibot_hmac(message: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def _captcha_numbers_from_nonce(nonce: str, secret: str) -> tuple[int, int, str]:
    digest = hmac.new(secret.encode("utf-8"), nonce.encode("utf-8"), hashlib.sha256).digest()
    a = (digest[0] % 9) + 1
    b = (digest[1] % 9) + 1
    op = "-" if (digest[2] % 2) else "+"
    if op == "-" and a < b:
        a, b = b, a
    return a, b, op


def _captcha_numbers_from_nonce_public(nonce: str) -> tuple[int, int, str]:
    digest = hashlib.sha256(nonce.encode("utf-8")).digest()
    a = (digest[0] % 9) + 1
    b = (digest[1] % 9) + 1
    op = "-" if (digest[2] % 2) else "+"
    if op == "-" and a < b:
        a, b = b, a
    return a, b, op


def create_first_party_captcha() -> dict:
    secret = _captcha_secret()
    alt_secret = _antibot_secret()
    nonce = secrets.token_urlsafe(12)
    issued_at = int(time.time())
    if not (secret or alt_secret):
        return {"token": "", "question": "1 + 1 = ?", "issued_at": issued_at}

    a, b, op = _captcha_numbers_from_nonce_public(nonce)
    message = f"{nonce}|{issued_at}|{a}|{op}|{b}"
    signature_alt = _antibot_hmac(message, alt_secret) if alt_secret else ""
    signature_primary = _antibot_hmac(message, secret) if secret else ""
    return {
        "token": base64.urlsafe_b64encode(
            f"{nonce}|{issued_at}|{a}|{op}|{b}|{signature_alt}|{signature_primary}".encode("utf-8")
        ).decode("utf-8"),
        "question": f"{a} {op} {b} = ?",
        "issued_at": issued_at
    }


def verify_first_party_captcha(token: Optional[str], answer: Optional[str]) -> bool:
    secret = _captcha_secret()
    alt_secret = _antibot_secret()
    if not (secret or alt_secret):
        return True
    if not token or answer is None:
        return False
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = raw.split("|")
        # Legacy format: nonce|issued_at|signature (firmado con _captcha_secret y números derivados del secreto)
        if len(parts) == 3:
            nonce, issued_at_str, signature = parts
            message = f"{nonce}|{issued_at_str}"
            expected = _antibot_hmac(message, secret) if secret else ""
            if not (expected and hmac.compare_digest(signature, expected)):
                return False
            issued_at = int(issued_at_str)
            now = int(time.time())
            if issued_at > now or now - issued_at > 600:
                return False
            a, b, op = _captcha_numbers_from_nonce(nonce, secret)
            expected_answer = str(a + b if op == "+" else a - b)
            return str(answer).strip() == expected_answer

        # New format: nonce|issued_at|a|op|b|sig_alt|sig_primary
        if len(parts) != 7:
            return False
        nonce, issued_at_str, a_text, op, b_text, sig_alt, sig_primary = parts
        issued_at = int(issued_at_str)
        now = int(time.time())
        if issued_at > now or now - issued_at > 600:
            return False
        a = int(a_text)
        b = int(b_text)
        if op not in {"+", "-"}:
            return False
        message = f"{nonce}|{issued_at_str}|{a}|{op}|{b}"
        ok_sig = False
        if alt_secret and sig_alt:
            ok_sig = ok_sig or hmac.compare_digest(sig_alt, _antibot_hmac(message, alt_secret))
        if secret and sig_primary:
            ok_sig = ok_sig or hmac.compare_digest(sig_primary, _antibot_hmac(message, secret))
        if not ok_sig:
            return False
        expected_answer = str(a + b if op == "+" else a - b)
        return str(answer).strip() == expected_answer
    except Exception:
        return False


def create_antibot_challenge() -> dict:
    secret = _antibot_secret()
    issued_at = int(time.time())
    nonce = secrets.token_urlsafe(16)
    if not secret:
        return {"token": "", "issued_at": issued_at, "min_elapsed_ms": 2500}
    message = f"{nonce}|{issued_at}"
    signature = _antibot_hmac(message, secret)
    token = base64.urlsafe_b64encode(f"{nonce}|{issued_at}|{signature}".encode("utf-8")).decode("utf-8")
    return {"token": token, "issued_at": issued_at, "min_elapsed_ms": 2500}


def verify_local_antibot(
    token: Optional[str],
    elapsed_ms: Optional[int],
    honey: Optional[str],
    remote_ip: Optional[str] = None
) -> bool:
    secret = _antibot_secret()
    if not secret:
        return True
    if honey and str(honey).strip():
        return False
    if not token:
        return False
    try:
        raw = base64.urlsafe_b64decode(str(token).encode("utf-8")).decode("utf-8")
        parts = raw.split("|")
        if len(parts) != 3:
            return False
        nonce, issued_at_text, signature = parts
        if not nonce or not issued_at_text or not signature:
            return False
        issued_at = int(issued_at_text)
        now = int(time.time())
        if issued_at > now or now - issued_at > 600:
            return False
        message = f"{nonce}|{issued_at}"
        expected = _antibot_hmac(message, secret)
        if not hmac.compare_digest(signature, expected):
            return False
        try:
            elapsed = int(elapsed_ms or 0)
        except Exception:
            elapsed = 0
        if elapsed < 2500:
            return False
        if elapsed > 30 * 60 * 1000:
            return False
        return True
    except Exception:
        return False


def verify_antibot_token(
    antibot_token: Optional[str],
    antibot_elapsed_ms: Optional[int],
    antibot_honey: Optional[str],
    hcaptcha_token: Optional[str],
    recaptcha_token: Optional[str],
    remote_ip: Optional[str] = None
) -> bool:
    h_secret = (os.getenv("HCAPTCHA_SECRET") or "").strip()
    r_secret = (os.getenv("RECAPTCHA_SECRET") or "").strip()
    if h_secret and hcaptcha_token:
        if verify_hcaptcha_token(hcaptcha_token, remote_ip):
            return True
    if r_secret and recaptcha_token:
        if verify_recaptcha_token(recaptcha_token, remote_ip):
            return True
    if h_secret or r_secret:
        return False
    local_secret = _antibot_secret()
    if local_secret:
        return verify_local_antibot(antibot_token, antibot_elapsed_ms, antibot_honey, remote_ip)
    return True


def verify_public_bot_protection(
    antibot_token: Optional[str],
    antibot_elapsed_ms: Optional[int],
    antibot_honey: Optional[str],
    captcha_token: Optional[str],
    captcha_answer: Optional[str],
    hcaptcha_token: Optional[str],
    recaptcha_token: Optional[str],
    remote_ip: Optional[str] = None
) -> bool:
    if not verify_first_party_captcha(captcha_token, captcha_answer):
        return False
    local_secret = _antibot_secret()
    if local_secret:
        return verify_local_antibot(antibot_token, antibot_elapsed_ms, antibot_honey, remote_ip)
    h_secret = (os.getenv("HCAPTCHA_SECRET") or "").strip()
    r_secret = (os.getenv("RECAPTCHA_SECRET") or "").strip()
    if h_secret:
        if hcaptcha_token:
            return verify_hcaptcha_token(hcaptcha_token, remote_ip)
        return False
    if r_secret:
        if recaptcha_token:
            return verify_recaptcha_token(recaptcha_token, remote_ip)
        return False
    return True


def update_android_build_job(job_id: str, **changes):
    now_iso = datetime.now(SEVILLA_TZ).isoformat()
    with ANDROID_BUILD_LOCK:
        job = ANDROID_BUILD_JOBS.get(job_id)
        if not job:
            return
        job.update(changes)
        job["updated_at"] = now_iso


def resolve_android_sdk_for_server() -> str:
    candidates: List[Path] = []

    env_sdk_root = (os.getenv("ANDROID_SDK_ROOT") or "").strip()
    if env_sdk_root:
        candidates.append(Path(env_sdk_root))
    env_android_home = (os.getenv("ANDROID_HOME") or "").strip()
    if env_android_home:
        candidates.append(Path(env_android_home))

    candidates.extend([
        Path.home() / "Android" / "Sdk",
        Path("/opt/android-sdk"),
        Path("/usr/lib/android-sdk"),
        Path("/opt/android-sdk-linux"),
    ])

    seen = set()
    for c in candidates:
        key = str(c)
        if key in seen:
            continue
        seen.add(key)
        if (c / "platforms").exists() and (c / "build-tools").exists():
            return str(c)

    raise HTTPException(
        status_code=500,
        detail=(
            "No se encontró Android SDK en el servidor. Define ANDROID_SDK_ROOT/ANDROID_HOME "
            "o instala el SDK (debe contener platforms y build-tools)."
        )
    )


def get_next_android_version_label(items: List[dict]) -> str:
    major = 1
    minor = 0
    for item in items or []:
        raw = str(item.get("version") or "").strip()
        match = re.fullmatch(r"(\d+)\.(\d+)", raw)
        if not match:
            continue
        m = int(match.group(1))
        n = int(match.group(2))
        if (m, n) > (major, minor):
            major, minor = m, n
    if minor <= 0:
        return "1.1"
    if minor < 9:
        return f"{major}.{minor + 1}"
    return f"{major + 1}.1"


def android_version_code_from_label(version_label: str) -> int:
    raw = str(version_label or "").strip()
    match = re.fullmatch(r"(\d+)\.(\d+)", raw)
    if not match:
        raise HTTPException(
            status_code=400,
            detail=f"Versión Android inválida: {raw!r}. Formato esperado: N.M",
        )
    major = int(match.group(1))
    minor = int(match.group(2))
    if major < 0 or minor < 0:
        raise HTTPException(status_code=400, detail="Versiones negativas no permitidas")
    code = (major * 100) + minor
    if code <= 0:
        raise HTTPException(status_code=400, detail="versionCode calculado inválido")
    return code


def resolve_java_home_for_server() -> str:
    # 1) Respect explicit JAVA_HOME if it is valid.
    env_home = (os.getenv("JAVA_HOME") or "").strip()
    if env_home:
        candidate = Path(env_home)
        if (candidate / "bin" / "java").exists():
            return str(candidate)

    # 2) Infer from java in PATH.
    java_bin = shutil.which("java")
    if java_bin:
        java_path = Path(java_bin).resolve()
        inferred_home = java_path.parent.parent
        if (inferred_home / "bin" / "java").exists():
            return str(inferred_home)

    # 3) Common Ubuntu/Debian JDK paths (preferred versions first).
    common = [
        Path("/usr/lib/jvm/java-21-openjdk-amd64"),
        Path("/usr/lib/jvm/java-17-openjdk-amd64"),
        Path("/usr/lib/jvm/default-java"),
    ]
    for c in common:
        if (c / "bin" / "java").exists():
            return str(c)

    # 4) Fallback: scan /usr/lib/jvm/* for any JDK/JRE with java binary.
    jvm_root = Path("/usr/lib/jvm")
    if jvm_root.exists():
        for c in sorted(jvm_root.iterdir()):
            if (c / "bin" / "java").exists():
                return str(c)

    raise HTTPException(
        status_code=500,
        detail=(
            "No se encontró Java en el servidor. Instala OpenJDK 17/21 y define JAVA_HOME. "
            "Ejemplo Ubuntu: sudo apt update && sudo apt install -y openjdk-17-jdk"
        )
    )


def run_android_build_on_server(
    target: str,
    version_label: str,
    progress_cb: Optional[Callable[[int, str], None]] = None
) -> dict:
    def report(pct: int, msg: str):
        if progress_cb:
            progress_cb(max(0, min(100, int(pct))), msg)

    report(2, "Preparando entorno de compilación")
    base_dir = Path(__file__).resolve().parent
    if target == "client":
        src_dir = base_dir / "android"
        work_dir = Path("/tmp/agents-android")
    else:
        src_dir = base_dir / "android_admin"
        work_dir = Path("/tmp/agents-android-admin")
    if not src_dir.exists():
        raise HTTPException(status_code=500, detail=f"No existe el proyecto fuente: {src_dir}")

    report(8, "Copiando proyecto a /tmp")
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    shutil.copytree(src_dir, work_dir, ignore=shutil.ignore_patterns("build", ".gradle"))

    gradlew = work_dir / "gradlew"
    if gradlew.exists():
        try:
            gradlew.chmod(0o755)
        except Exception:
            pass

    build_env = os.environ.copy()
    report(12, "Detectando Java y Android SDK")
    java_home = resolve_java_home_for_server()
    android_sdk = resolve_android_sdk_for_server()
    build_env["JAVA_HOME"] = java_home
    build_env["PATH"] = f"{java_home}/bin:{build_env.get('PATH', '')}"
    build_env["ANDROID_HOME"] = android_sdk
    build_env["ANDROID_SDK_ROOT"] = android_sdk
    version_code = android_version_code_from_label(version_label)

    local_properties = work_dir / "local.properties"
    sdk_escaped = android_sdk.replace("\\", "\\\\")
    local_properties.write_text(f"sdk.dir={sdk_escaped}\n", encoding="utf-8")

    build_steps = [
        ["./gradlew", "--stop"],
        [
            "./gradlew",
            "clean",
            "assembleDebug",
            "--no-daemon",
            "--rerun-tasks",
            "--max-workers=1",
            f"-PVERSION_NAME={version_label}",
            f"-PVERSION_CODE={version_code}",
        ],
    ]
    for idx, cmd in enumerate(build_steps):
        if idx == 0:
            report(20, "Deteniendo daemons de Gradle")
        else:
            report(35, "Compilando APK (puede tardar varios minutos)")
        proc = subprocess.run(
            cmd,
            cwd=str(work_dir),
            env=build_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60 * 60,
            check=False,
        )
        if proc.returncode != 0:
            output = (proc.stdout or "").strip()
            short_output = output[-3500:] if len(output) > 3500 else output
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Error compilando APK ({target}) con JAVA_HOME={java_home} y ANDROID_SDK={android_sdk}: "
                    f"{short_output or 'sin salida'}"
                )
            )

    report(90, "Copiando APK generado")
    apk_src = work_dir / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    if not apk_src.exists():
        raise HTTPException(status_code=500, detail=f"No se encontró APK generado: {apk_src}")

    target_dir = ANDROID_RELEASES_DIR / target
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{target}_v{version_label}.apk"
    apk_dst = target_dir / filename
    shutil.copy2(apk_src, apk_dst)
    report(100, "Versión generada correctamente")

    return {
        "filename": filename,
        "download_url": f"/web/downloads/android/{target}/{filename}",
        "size_bytes": int(apk_dst.stat().st_size),
    }


def load_admin_sessions():
    global ADMIN_SESSIONS
    if not ADMIN_SESSIONS_PATH.exists():
        ADMIN_SESSIONS = {}
        return
    raw = json.loads(ADMIN_SESSIONS_PATH.read_text(encoding="utf-8"))
    parsed = {}
    for sid, item in raw.items():
        created = item.get("created_at")
        expires = item.get("expires_at")
        parsed[sid] = {
            "created_at": datetime.fromisoformat(created) if created else None,
            "expires_at": datetime.fromisoformat(expires) if expires else None
        }
    ADMIN_SESSIONS = parsed


def load_admin_config():
    global ADMIN_CONFIG
    if ADMIN_CONFIG_PATH.exists():
        ADMIN_CONFIG = json.loads(ADMIN_CONFIG_PATH.read_text(encoding="utf-8"))
        ADMIN_CONFIG["username"] = ADMIN_DEFAULT_USERNAME
        ADMIN_CONFIG["email"] = ADMIN_DEFAULT_EMAIL
        ADMIN_CONFIG["recovery_email"] = ADMIN_DEFAULT_RECOVERY_EMAIL
        ADMIN_CONFIG.setdefault("session_default_mode", "limited")
        ADMIN_CONFIG.setdefault("session_default_duration_minutes", 1440)
        ADMIN_CONFIG.setdefault("qr_allow_client", [
            "https://todosevillaeste.es/negocio.html?id=",
            "/negocio.html?id=",
        ])
        ADMIN_CONFIG.setdefault("qr_allow_admin", [
            "https://todosevillaeste.es/versiones.html",
            "/versiones.html",
            "https://todosevillaeste.es/versiones",
            "/versiones",
        ])
        ADMIN_CONFIG["qr_allow_client"] = _normalize_qr_allow_rules(ADMIN_CONFIG.get("qr_allow_client"))
        ADMIN_CONFIG["qr_allow_admin"] = _normalize_qr_allow_rules(ADMIN_CONFIG.get("qr_allow_admin"))
        current_hash = ADMIN_CONFIG.get("password_hash", "")
        try:
            if current_hash and verify_password("%alber-adaminAUT", current_hash):
                ADMIN_CONFIG["password_hash"] = hash_password(ADMIN_DEFAULT_PASSWORD)
        except Exception:
            pass
        save_admin_config()
        return

    ADMIN_CONFIG = {
        "username": ADMIN_DEFAULT_USERNAME,
        "email": ADMIN_DEFAULT_EMAIL,
        "password_hash": hash_password(ADMIN_DEFAULT_PASSWORD),
        "recovery_email": ADMIN_DEFAULT_RECOVERY_EMAIL,
        "session_default_mode": "limited",
        "session_default_duration_minutes": 1440,
        "qr_allow_client": [
            "https://todosevillaeste.es/negocio.html?id=",
            "/negocio.html?id=",
        ],
        "qr_allow_admin": [
            "https://todosevillaeste.es/versiones.html",
            "/versiones.html",
            "https://todosevillaeste.es/versiones",
            "/versiones",
        ]
    }
    save_admin_config()


def create_admin_session(mode: str, duration_minutes: Optional[int] = None):
    session_id = secrets.token_hex(32)
    expires_at = None
    max_age = None

    if mode == "limited":
        minutes = int(duration_minutes or 60)
        minutes = max(1, min(minutes, 60 * 24 * 30))
        expires_at = datetime.utcnow() + timedelta(minutes=minutes)
        max_age = minutes * 60
    else:
        max_age = 60 * 60 * 24 * 365 * 10

    with ADMIN_LOCK:
        ADMIN_SESSIONS[session_id] = {
            "created_at": datetime.utcnow(),
            "expires_at": expires_at
        }
        save_admin_sessions()
    return session_id, max_age


def set_admin_session_cookie(
    response: Response,
    request: Optional[Request],
    session_id: str,
    max_age: int,
) -> None:
    secure_cookie = SESSION_COOKIE_SECURE
    if request is not None and request.url.scheme != "https":
        secure_cookie = False
    kwargs = dict(
        key=ADMIN_SESSION_COOKIE,
        value=session_id,
        max_age=int(max_age),
        expires=datetime.now(timezone.utc) + timedelta(seconds=int(max_age)),
        httponly=True,
        samesite="lax",
        path="/",
        secure=secure_cookie,
    )
    cookie_domain = _resolve_cookie_domain_for_request(request)
    if not cookie_domain and request is not None:
        host = (request.url.hostname or "").strip().lower()
        if host in {"todosevillaeste.es", "www.todosevillaeste.es"}:
            cookie_domain = "todosevillaeste.es"
    if cookie_domain:
        kwargs["domain"] = cookie_domain
    response.set_cookie(**kwargs)


def clear_admin_session_cookie(response: Response, request: Optional[Request] = None) -> None:
    kwargs = {"key": ADMIN_SESSION_COOKIE, "path": "/"}
    cookie_domain = _resolve_cookie_domain_for_request(request)
    if not cookie_domain and request is not None:
        host = (request.url.hostname or "").strip().lower()
        if host in {"todosevillaeste.es", "www.todosevillaeste.es"}:
            cookie_domain = "todosevillaeste.es"
    if cookie_domain:
        kwargs["domain"] = cookie_domain
    response.delete_cookie(**kwargs)


def get_admin_session(request: Request):
    session_id = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not session_id:
        raise HTTPException(status_code=401, detail="Sesión de administración requerida")

    with ADMIN_LOCK:
        load_admin_sessions()
        session = ADMIN_SESSIONS.get(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="Sesión de administración inválida")

        expires_at = session.get("expires_at")
        if expires_at is not None and expires_at < datetime.utcnow():
            ADMIN_SESSIONS.pop(session_id, None)
            save_admin_sessions()
            raise HTTPException(status_code=401, detail="Sesión de administración expirada")

    return {"session_id": session_id}


def _get_admin_session_from_cookie_value(session_id: Optional[str]) -> dict:
    sid = str(session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=401, detail="Sesion de administracion requerida")

    with ADMIN_LOCK:
        load_admin_sessions()
        session = ADMIN_SESSIONS.get(sid)
        if not session:
            raise HTTPException(status_code=401, detail="Sesion de administracion invalida")
        expires_at = session.get("expires_at")
        if expires_at is not None and expires_at < datetime.utcnow():
            ADMIN_SESSIONS.pop(sid, None)
            save_admin_sessions()
            raise HTTPException(status_code=401, detail="Sesion de administracion expirada")
    return {"session_id": sid}


def _is_local_admin_terminal_target(host: str) -> bool:
    host_clean = str(host or "").strip().lower()
    if host_clean in {"localhost", "127.0.0.1", "::1", "192.168.0.40"}:
        return True
    return False


def _pty_set_winsize(fd: int, rows: int, cols: int) -> None:
    if fcntl is None or termios is None or struct is None:
        return
    try:
        r = max(10, min(int(rows), 400))
        c = max(20, min(int(cols), 800))
        winsize = struct.pack("HHHH", r, c, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except Exception:
        return


class _AdminTerminalSession:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pid: Optional[int] = None
        self.master_fd: Optional[int] = None
        self.cmd: List[str] = []
        self.backlog = deque(maxlen=6000)
        self.subscribers: List[queue.Queue] = []
        self.reader_thread: Optional[threading.Thread] = None

    def _publish(self, text: str) -> None:
        with self.lock:
            self.backlog.append(text)
            dead: List[int] = []
            for idx, sub in enumerate(self.subscribers):
                try:
                    sub.put_nowait(text)
                except queue.Full:
                    continue
                except Exception:
                    dead.append(idx)
            for idx in reversed(dead):
                try:
                    self.subscribers.pop(idx)
                except Exception:
                    pass

    def _is_alive_locked(self) -> bool:
        if not self.pid:
            return False
        try:
            done_pid, _ = os.waitpid(self.pid, os.WNOHANG)
            if done_pid == 0:
                return True
            self.pid = None
            self.master_fd = None
            return False
        except ChildProcessError:
            self.pid = None
            self.master_fd = None
            return False
        except Exception:
            return True

    def _reader_loop(self) -> None:
        while True:
            with self.lock:
                fd = self.master_fd
            if fd is None:
                break
            try:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                self._publish(chunk.decode("utf-8", errors="ignore"))
            except OSError:
                break
            except Exception:
                break
        with self.lock:
            self.pid = None
            try:
                if self.master_fd is not None:
                    os.close(self.master_fd)
            except Exception:
                pass
            self.master_fd = None
        self._publish("\r\n[Terminal finalizada]\r\n")

    def ensure_started(self, cmd: List[str], intro: str) -> None:
        with self.lock:
            if self._is_alive_locked():
                return
        if pty is None:
            raise HTTPException(status_code=500, detail="El servidor no soporta PTY")
        try:
            child_pid, master_fd = pty.fork()
            if child_pid == 0:
                os.environ["TERM"] = os.environ.get("TERM", "xterm-256color")
                os.execvp(cmd[0], cmd)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"No se pudo iniciar la terminal: {exc}")
        with self.lock:
            self.pid = child_pid
            self.master_fd = master_fd
            self.cmd = list(cmd)
            self.backlog.clear()
            self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.reader_thread.start()
        self._publish(intro)

    def subscribe(self) -> Tuple[queue.Queue, List[str]]:
        sub_q: queue.Queue = queue.Queue(maxsize=1500)
        with self.lock:
            self.subscribers.append(sub_q)
            snapshot = list(self.backlog)[-1200:]
        return sub_q, snapshot

    def unsubscribe(self, sub_q: queue.Queue) -> None:
        with self.lock:
            try:
                self.subscribers.remove(sub_q)
            except ValueError:
                pass

    def write(self, data: str) -> None:
        if not data:
            return
        with self.lock:
            fd = self.master_fd
        if fd is None:
            raise RuntimeError("Terminal no activa")
        os.write(fd, data.encode("utf-8", errors="ignore"))

    def resize(self, rows: int, cols: int) -> None:
        with self.lock:
            fd = self.master_fd
        if fd is None:
            return
        _pty_set_winsize(fd, rows, cols)


ADMIN_TERMINAL_SESSION = _AdminTerminalSession()


def _run_bash(cmd: str, cwd: Optional[str] = None, timeout: int = 8) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/bash", "-lc", cmd],
        cwd=cwd or TSE_WORKDIR,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _tse_active_state() -> dict:
    for service_name in TSE_SERVICE_CANDIDATES:
        res = _run_bash(f"systemctl is-active --quiet {shlex.quote(service_name)}; echo $?", timeout=4)
        if res.returncode == 0 and str(res.stdout or "").strip().endswith("0"):
            return {"active": True, "source": "systemd", "service": service_name}
    if TSE_PROCESS_PATTERN:
        res = _run_bash(f"pgrep -af {shlex.quote(TSE_PROCESS_PATTERN)}", timeout=4)
        if res.returncode == 0 and str(res.stdout or "").strip():
            first = str(res.stdout).splitlines()[0].strip()
            return {"active": True, "source": "process", "service": None, "process": first}
    return {"active": False, "source": "none", "service": None}


def _tse_start() -> dict:
    if not TSE_START_CMD:
        raise HTTPException(status_code=500, detail="TSE_START_CMD no configurado")
    run_cmd = (
        f"nohup /bin/bash -lc {shlex.quote('cd ' + shlex.quote(TSE_WORKDIR) + ' && ' + TSE_START_CMD)} "
        "> /tmp/todosevillaeste-start.log 2>&1 & echo $!"
    )
    res = _run_bash(run_cmd, cwd=TSE_WORKDIR, timeout=6)
    if res.returncode != 0:
        stderr = (res.stderr or "").strip()
        raise HTTPException(status_code=500, detail=f"No se pudo iniciar TodoSevillaEste: {stderr or 'error'}")
    return {"launched": True, "pid": (res.stdout or "").strip()}


def _tse_stop() -> dict:
    if TSE_STOP_CMD:
        res = _run_bash(TSE_STOP_CMD, cwd=TSE_WORKDIR, timeout=12)
        if res.returncode != 0:
            stderr = (res.stderr or "").strip()
            raise HTTPException(status_code=500, detail=f"No se pudo cerrar TodoSevillaEste: {stderr or 'error'}")
        return {"stopped": True, "mode": "custom"}

    for service_name in TSE_SERVICE_CANDIDATES:
        res = _run_bash(f"sudo -n systemctl stop {shlex.quote(service_name)}", timeout=8)
        if res.returncode == 0:
            return {"stopped": True, "mode": "systemd", "service": service_name}

    if TSE_PROCESS_PATTERN:
        res = _run_bash(f"sudo -n pkill -f {shlex.quote(TSE_PROCESS_PATTERN)}", timeout=8)
        if res.returncode == 0:
            return {"stopped": True, "mode": "pkill"}

    raise HTTPException(status_code=500, detail="No se pudo parar TodoSevillaEste (configura TSE_STOP_CMD)")


def _tse_next_terminal_action() -> dict:
    state = _tse_active_state()
    active = bool(state.get("active"))
    if active:
        cmd = TSE_RESTART_CMD or "sudo -n systemctl restart todosevillaeste-stack.target"
        return {"action": "restart", "command": cmd, "state": state}

    # Must be executed in the interactive terminal session.
    return {"action": "start", "command": TSE_START_CMD, "state": state}


def _refresh_realtime_cache_once():
    now_madrid = datetime.now(SEVILLA_TZ)
    temperature = None
    weather_text = "--"
    try:
        with urllib.request.urlopen(WEATHER_URL, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
            current = payload.get("current_weather", {})
            raw_temp = current.get("temperature")
            if raw_temp is not None:
                temperature = float(raw_temp)
                weather_text = f"{round(temperature)} C"
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        pass

    with REALTIME_LOCK:
        if temperature is not None:
            REALTIME_CACHE["temperature_c"] = temperature
            REALTIME_CACHE["weather_text"] = weather_text
        REALTIME_CACHE["updated_at"] = now_madrid.isoformat()


def _realtime_cache_worker():
    while True:
        _refresh_realtime_cache_once()
        time.sleep(60)


@app.on_event("startup")
def start_realtime_cache_worker():
    boot_conn = None
    try:
        boot_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        ensure_place_user_assignments_schema(boot_conn)
        user_columns = get_users_table_columns(boot_conn)
        ensure_users_optional_columns(
            boot_conn,
            need_is_default_account="is_default_account" not in user_columns,
            need_role_flags=any(c not in user_columns for c in ("role_client", "role_business", "role_admin")),
        )
        place_columns = get_places_table_columns(boot_conn)
        ensure_places_optional_columns(boot_conn, need_owner_user="owner_user_id" not in place_columns)
        ensure_reviews_schema(boot_conn)
        ensure_messages_schema(boot_conn)
        ensure_feedback_schema(boot_conn)
    finally:
        try:
            boot_conn.close()
        except Exception:
            pass
    load_admin_config()
    load_admin_sessions()
    try:
        load_android_versions_payload()
    except Exception:
        traceback.print_exc()
    _refresh_realtime_cache_once()
    worker = threading.Thread(target=_realtime_cache_worker, daemon=True)
    worker.start()

# ------------------------------- Modelos Pydantic -------------------------------
class TimeRange(BaseModel):
    inicio: str
    fin: str

class PlaceCreate(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    website: Optional[str] = None
    business_email: Optional[str] = None
    contact_email: Optional[str] = None
    public_contact_email: Optional[str] = None
    notification_email: Optional[str] = None
    opening_hours: Optional[Dict[str, List[TimeRange]]] = None
    category: str
    description: Optional[str] = None
    initial_phrase: Optional[str] = None
    photos: Optional[List[str]] = None
    active: Optional[bool] = True
    map_latitude: Optional[float] = None
    map_longitude: Optional[float] = None
    suppress_business_email: Optional[bool] = False

    @validator("opening_hours", pre=True, always=True)
    def validate_opening_hours(cls, v):
        result = {}
        if not v:
            return {day: [] for day in DAYS}
        for day in DAYS:
            trays = v.get(day, [])
            validated_trays = []
            for t in trays:
                if isinstance(t, dict) and "inicio" in t and "fin" in t:
                    validated_trays.append({"inicio": t["inicio"], "fin": t["fin"]})
            result[day] = validated_trays
        return result

    @validator("map_latitude")
    def validate_map_latitude(cls, value):
        if value is None:
            return None
        if not (-90 <= float(value) <= 90):
            raise ValueError("Latitud fuera de rango")
        return float(value)

    @validator("map_longitude")
    def validate_map_longitude(cls, value):
        if value is None:
            return None
        if not (-180 <= float(value) <= 180):
            raise ValueError("Longitud fuera de rango")
        return float(value)
    
class UpdateUserBody(BaseModel):
    username: str
    email: EmailStr


class AdminUserRolesBody(BaseModel):
    role_client: bool = True
    role_business: bool = False
    role_admin: bool = False
    business_place_public_id: Optional[int] = None


class AdminUserMessageBody(BaseModel):
    message: str


class AdminMailFlagsBody(BaseModel):
    seen: Optional[bool] = None
    starred: Optional[bool] = None


def get_or_create_admin_user_chat(cursor, recipient_id: int, create_if_missing: bool = True) -> Optional[int]:
    admin_sender_id = 0
    user_a, user_b = get_chat_pair_ids(admin_sender_id, int(recipient_id))
    cursor.execute(
        """
        SELECT id FROM chat_threads
        WHERE place_public_id=0 AND user_a_id=%s AND user_b_id=%s
        LIMIT 1
        """,
        (user_a, user_b)
    )
    row = cursor.fetchone()
    if row:
        return int(row.get("id") or 0)
    if not create_if_missing:
        return None
    cursor.execute(
        """
        INSERT INTO chat_threads (
            place_public_id, user_a_id, user_b_id, custom_name_a, custom_name_b, initiated_by_user_id
        ) VALUES (0, %s, %s, 'Administración', 'Administración', %s)
        """,
        (user_a, user_b, int(recipient_id))
    )
    return int(cursor.lastrowid)

@app.delete("/users/{user_id:int}")
def delete_user(user_id: int, admin=Depends(get_admin_session)):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Comprobar si el usuario existe
        cursor.execute("SELECT id, email FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(404, "Usuario no encontrado")

        # Limpiar dependencias del usuario para evitar errores por relaciones
        cursor.execute("DELETE FROM sessions WHERE user_id=%s", (user_id,))
        cursor.execute("DELETE FROM auth_codes WHERE email=%s", (user["email"],))
        ensure_place_user_assignments_schema(conn)
        cursor.execute("DELETE FROM place_user_assignments WHERE user_id=%s", (user_id,))

        place_columns = get_places_table_columns(conn)
        if "owner_user_id" in place_columns:
            cursor.execute(
                "UPDATE places SET owner_user_id=NULL WHERE owner_user_id=%s",
                (user_id,)
            )
        if "business_email" in place_columns:
            cursor.execute(
                "UPDATE places SET business_email=NULL WHERE business_email=%s",
                (user["email"],)
            )

        # Borrar usuario
        cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()

        remove_user_avatar_files(user_id)

        return {"detail": f"Usuario {user['email']} eliminado correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error al eliminar usuario: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
class ResetPasswordRequest(BaseModel):
    email: EmailStr

@app.post("/auth/reset_password")
def reset_password_request(data: ResetPasswordRequest):
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Buscar usuario
        cursor.execute("SELECT id FROM users WHERE email=%s", (data.email,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(404, "Correo no registrado")

        # Generar contraseña temporal y código
        temp_password = generate_random_password()
        code = generate_code()
        hashed_pw = hash_password(temp_password)

        # Actualizar usuario: contraseña temporal y must_change_password
        cursor.execute("""
            UPDATE users SET password_hash=%s, must_change_password=1, temp_code=%s
            WHERE id=%s
        """, (hashed_pw, code, user["id"]))
        conn.commit()
        cursor.close()
        conn.close()

        # Enviar correo con contraseña temporal y código
        msg = MIMEText(f"Tu contraseña temporal es: {temp_password}\nCódigo de seguridad: {code}")
        msg["Subject"] = "Reseteo de contraseña"
        msg["From"] = EMAIL_SENDER
        msg["To"] = data.email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)

        return {"detail": "Se ha enviado la contraseña temporal y código de seguridad a tu correo"}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error al procesar reseteo de contraseña: {e}")


@app.put("/users/{user_id:int}")
def update_user(user_id: int, data: UpdateUserBody, admin=Depends(get_admin_session)):
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        user_columns = get_users_table_columns(conn)
        if "is_default_account" not in user_columns:
            ensure_users_optional_columns(conn, need_is_default_account=True)
            user_columns = get_users_table_columns(conn)
        cursor = conn.cursor(dictionary=True)

        # Comprobar si el usuario existe
        cursor.execute("SELECT id FROM users WHERE id=%s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "Usuario no encontrado")

        # Actualizar username y email
        update_parts = ["username=%s", "email=%s"]
        update_values = [data.username, data.email]
        if "is_default_account" in user_columns:
            update_parts.append("is_default_account=0")
        update_values.append(user_id)
        cursor.execute(
            f"UPDATE users SET {', '.join(update_parts)} WHERE id=%s",
            tuple(update_values)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return {"detail": "Usuario actualizado correctamente"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error al actualizar usuario: {e}")


@app.post("/admin/users/{user_id:int}/message")
def admin_send_message_to_user(user_id: int, data: AdminUserMessageBody, admin=Depends(get_admin_session)):
    cleaned_body = normalize_chat_body((data.message or ""), max_length=4000)
    if not cleaned_body:
        raise HTTPException(status_code=400, detail="Debes escribir un mensaje")

    recipient_id = int(user_id)
    if recipient_id <= 0:
        raise HTTPException(status_code=400, detail="Usuario inválido")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        cursor.execute("SELECT id FROM users WHERE id=%s LIMIT 1", (recipient_id,))
        recipient = cursor.fetchone()
        if not recipient:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        chat_id = get_or_create_admin_user_chat(cursor, recipient_id, create_if_missing=True)
        admin_sender_id = 0

        cursor.execute(
            """
            INSERT INTO chat_messages (chat_id, sender_user_id, receiver_user_id, body, media_url, status)
            VALUES (%s, %s, %s, %s, NULL, 'delivered')
            """,
            (chat_id, admin_sender_id, recipient_id, cleaned_body)
        )
        message_id = int(cursor.lastrowid)
        cursor.execute("UPDATE chat_threads SET updated_at=NOW() WHERE id=%s", (chat_id,))
        conn.commit()

        push_body = "Administración te ha enviado un mensaje. Clica para ver."
        push_url = f"/mensajes.html?chat={int(chat_id)}"
        try:
            send_push_to_user(
                recipient_id,
                title="Nuevo mensaje",
                body=push_body,
                url=push_url,
            )
        except Exception:
            pass
        try:
            send_fcm_to_user(
                recipient_id,
                title="Nuevo mensaje",
                body=push_body,
                url=push_url,
            )
        except Exception:
            pass

        return {
            "detail": "Mensaje enviado",
            "chat_id": chat_id,
            "message_id": message_id,
            "sender_name": "Administración",
            "target_user_id": recipient_id,
        }
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/users/{user_id:int}/chat")
def admin_get_user_chat(user_id: int, admin=Depends(get_admin_session)):
    target_user_id = int(user_id)
    if target_user_id <= 0:
        raise HTTPException(status_code=400, detail="Usuario inválido")
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        cursor.execute("SELECT id, username, email FROM users WHERE id=%s LIMIT 1", (target_user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        chat_id = get_or_create_admin_user_chat(cursor, target_user_id, create_if_missing=True)
        conn.commit()

        cursor.execute(
            """
            SELECT id, chat_id, sender_user_id, receiver_user_id, body, media_url, status, edited, is_deleted, created_at, updated_at, read_at
            FROM chat_messages
            WHERE chat_id=%s
            ORDER BY created_at ASC, id ASC
            LIMIT 400
            """,
            (int(chat_id),)
        )
        rows = cursor.fetchall() or []
        messages = []
        for row in rows:
            sender_user_id = int(row.get("sender_user_id") or 0)
            created_at = row.get("created_at")
            is_deleted = bool(row.get("is_deleted"))
            messages.append({
                "id": int(row.get("id") or 0),
                "sender_user_id": sender_user_id,
                "sender_label": "Administración" if sender_user_id <= 0 else (user_row.get("username") or f"u{target_user_id}"),
                "is_admin_sender": sender_user_id <= 0,
                "body": "Mensaje eliminado" if is_deleted else (row.get("body") or ""),
                "media_url": row.get("media_url"),
                "status": row.get("status") or "delivered",
                "edited": bool(row.get("edited")),
                "is_deleted": is_deleted,
                "created_at": created_at.isoformat() if created_at else None
            })
        return {
            "chat_id": int(chat_id),
            "user": {
                "id": int(user_row.get("id") or target_user_id),
                "username": user_row.get("username") or "",
                "email": user_row.get("email") or "",
            },
            "messages": messages,
        }
    finally:
        cursor.close()
        conn.close()


@app.post("/admin/users/{user_id:int}/chat/messages")
def admin_send_user_chat_message(user_id: int, data: AdminUserMessageBody, admin=Depends(get_admin_session)):
    return admin_send_message_to_user(user_id=user_id, data=data, admin=admin)


@app.patch("/admin/users/{user_id:int}/chat/messages/{message_id:int}")
def admin_edit_user_chat_message(user_id: int, message_id: int, data: AdminUserMessageBody, admin=Depends(get_admin_session)):
    target_user_id = int(user_id)
    mid = int(message_id)
    if target_user_id <= 0 or mid <= 0:
        raise HTTPException(status_code=400, detail="Parámetros inválidos")
    cleaned_body = normalize_chat_body((data.message or ""), max_length=4000)
    if not cleaned_body:
        raise HTTPException(status_code=400, detail="Debes escribir un mensaje")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        chat_id = get_or_create_admin_user_chat(cursor, target_user_id, create_if_missing=False)
        if not chat_id:
            raise HTTPException(status_code=404, detail="Chat no encontrado")
        cursor.execute(
            """
            SELECT id, sender_user_id, is_deleted
            FROM chat_messages
            WHERE id=%s AND chat_id=%s
            LIMIT 1
            """,
            (mid, int(chat_id))
        )
        msg = cursor.fetchone()
        if not msg:
            raise HTTPException(status_code=404, detail="Mensaje no encontrado")
        if int(msg.get("sender_user_id") or 1) > 0:
            raise HTTPException(status_code=403, detail="Solo puedes editar mensajes de Administración")
        if bool(msg.get("is_deleted")):
            raise HTTPException(status_code=400, detail="No puedes editar un mensaje eliminado")

        cursor.execute(
            """
            UPDATE chat_messages
            SET body=%s, edited=1, updated_at=NOW()
            WHERE id=%s
            """,
            (cleaned_body, mid)
        )
        cursor.execute("UPDATE chat_threads SET updated_at=NOW() WHERE id=%s", (int(chat_id),))
        conn.commit()
        return {"detail": "Mensaje editado"}
    finally:
        cursor.close()
        conn.close()


@app.delete("/admin/users/{user_id:int}/chat/messages/{message_id:int}")
def admin_delete_user_chat_message(user_id: int, message_id: int, admin=Depends(get_admin_session)):
    target_user_id = int(user_id)
    mid = int(message_id)
    if target_user_id <= 0 or mid <= 0:
        raise HTTPException(status_code=400, detail="Parámetros inválidos")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        chat_id = get_or_create_admin_user_chat(cursor, target_user_id, create_if_missing=False)
        if not chat_id:
            raise HTTPException(status_code=404, detail="Chat no encontrado")
        cursor.execute(
            """
            SELECT id, sender_user_id, is_deleted
            FROM chat_messages
            WHERE id=%s AND chat_id=%s
            LIMIT 1
            """,
            (mid, int(chat_id))
        )
        msg = cursor.fetchone()
        if not msg:
            raise HTTPException(status_code=404, detail="Mensaje no encontrado")
        if int(msg.get("sender_user_id") or 1) > 0:
            raise HTTPException(status_code=403, detail="Solo puedes eliminar mensajes de Administración")
        if bool(msg.get("is_deleted")):
            return {"detail": "Mensaje ya eliminado"}

        cursor.execute(
            """
            UPDATE chat_messages
            SET is_deleted=1, deleted_at=NOW(), body=NULL, media_url=NULL, edited=0, updated_at=NOW()
            WHERE id=%s
            """,
            (mid,)
        )
        cursor.execute("UPDATE chat_threads SET updated_at=NOW() WHERE id=%s", (int(chat_id),))
        conn.commit()
        remove_message_media_files(int(chat_id), mid)
        return {"detail": "Mensaje eliminado"}
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/users/{user_id:int}/roles")
def admin_get_user_roles(user_id: int, admin=Depends(get_admin_session)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, username, email FROM users WHERE id=%s LIMIT 1", (int(user_id),))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        role_info = get_user_roles_for_id(conn, int(user_id))
        return {
            "user": {
                "id": int(user_row["id"]),
                "username": user_row.get("username") or "",
                "email": user_row.get("email") or "",
            },
            "roles": role_info["roles"],
            "business_place_public_id": role_info["managed_place_public_id"],
        }
    finally:
        cursor.close()
        conn.close()


@app.put("/admin/users/{user_id:int}/roles")
def admin_update_user_roles(user_id: int, data: AdminUserRolesBody, admin=Depends(get_admin_session)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        assignments_ready = True
        try:
            ensure_place_user_assignments_schema(conn)
        except Exception:
            assignments_ready = False
            logger.exception("No se pudo preparar place_user_assignments; usando fallback owner_user_id")
        user_columns = get_users_table_columns(conn)
        if any(col not in user_columns for col in ("role_client", "role_business", "role_admin")):
            ensure_users_optional_columns(conn, need_role_flags=True)
            user_columns = get_users_table_columns(conn)

        place_columns = get_places_table_columns(conn)
        if "owner_user_id" not in place_columns:
            ensure_places_optional_columns(conn, need_owner_user=True)

        cursor.execute("SELECT id, email FROM users WHERE id=%s LIMIT 1", (int(user_id),))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        target_email = (user_row.get("email") or "").strip().lower()
        before_info = get_user_roles_for_id(conn, int(user_id))
        previous_business_role = bool((before_info.get("roles") or {}).get("business"))
        previous_place_public_id = before_info.get("managed_place_public_id")

        role_client = bool(data.role_client)
        role_business = bool(data.role_business)
        role_admin = bool(data.role_admin)
        if not (role_client or role_business or role_admin):
            raise HTTPException(status_code=400, detail="Debes mantener al menos un rol activo")

        selected_place_public_id = int(data.business_place_public_id or 0) if role_business else 0
        if role_business and selected_place_public_id <= 0:
            raise HTTPException(status_code=400, detail="Debes asignar un negocio para el rol negocio")

        if role_business:
            cursor.execute(
                "SELECT public_id FROM places WHERE public_id=%s LIMIT 1",
                (selected_place_public_id,)
            )
            place_row = cursor.fetchone()
            if not place_row:
                raise HTTPException(status_code=404, detail="Negocio no encontrado")

        user_role_update_parts = []
        user_role_update_values = []
        if "role_client" in user_columns:
            user_role_update_parts.append("role_client=%s")
            user_role_update_values.append(1 if role_client else 0)
        if "role_business" in user_columns:
            user_role_update_parts.append("role_business=%s")
            user_role_update_values.append(1 if role_business else 0)
        if "role_admin" in user_columns:
            user_role_update_parts.append("role_admin=%s")
            user_role_update_values.append(1 if role_admin else 0)
        if user_role_update_parts:
            user_role_update_values.append(int(user_id))
            cursor.execute(
                f"UPDATE users SET {', '.join(user_role_update_parts)} WHERE id=%s",
                tuple(user_role_update_values)
            )

        if assignments_ready:
            try:
                cursor.execute("DELETE FROM place_user_assignments WHERE user_id=%s", (int(user_id),))
                if role_business:
                    cursor.execute(
                        """
                        INSERT INTO place_user_assignments (user_id, place_public_id, assigned_at)
                        VALUES (%s, %s, NOW())
                        """,
                        (int(user_id), int(selected_place_public_id))
                    )
            except Exception:
                assignments_ready = False
                logger.exception("Fallo al persistir en place_user_assignments; usando fallback owner_user_id")

        if not assignments_ready:
            if role_business:
                cursor.execute(
                    "UPDATE places SET owner_user_id=NULL WHERE owner_user_id=%s AND public_id<>%s",
                    (int(user_id), int(selected_place_public_id))
                )
                cursor.execute(
                    "UPDATE places SET owner_user_id=%s WHERE public_id=%s",
                    (int(user_id), int(selected_place_public_id))
                )
            else:
                cursor.execute("UPDATE places SET owner_user_id=NULL WHERE owner_user_id=%s", (int(user_id),))

        conn.commit()

        if target_email and seems_valid_email(target_email):
            next_place_public_id = int(selected_place_public_id) if role_business else None
            added_place_name = get_place_name_for_public_id(conn, next_place_public_id)
            removed_place_name = get_place_name_for_public_id(conn, previous_place_public_id)

            try:
                if (not previous_business_role) and role_business:
                    send_notification_email(
                        target_email,
                        "Rol de negocio asignado",
                        f"Ha sido añadido al rol de negocios para gestionar el negocio: {added_place_name or f'Negocio {next_place_public_id}'}",
                    )
                elif previous_business_role and (not role_business):
                    send_notification_email(
                        target_email,
                        "Rol de negocio retirado",
                        f"Ya no puedes gestionar el negocio: {removed_place_name or f'Negocio {previous_place_public_id}'}",
                    )
                elif previous_business_role and role_business and (previous_place_public_id != next_place_public_id):
                    send_notification_email(
                        target_email,
                        "Cambio de negocio gestionado",
                        (
                            f"Ya no puedes gestionar el negocio: {removed_place_name or f'Negocio {previous_place_public_id}'}\n"
                            f"Ha sido añadido al rol de negocios para gestionar el negocio: {added_place_name or f'Negocio {next_place_public_id}'}"
                        ),
                    )
            except Exception:
                logger.exception(
                    "No se pudo enviar correo de cambio de rol negocio | user_id=%s | email=%s",
                    int(user_id),
                    target_email,
                )

        return {
            "detail": "Roles actualizados",
            "roles": {
                "client": role_client,
                "business": role_business,
                "admin": role_admin,
            },
            "business_place_public_id": int(selected_place_public_id) if role_business else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error al actualizar roles de usuario | user_id=%s", int(user_id))
        raise HTTPException(status_code=500, detail=f"Error al actualizar roles: {e}")
    finally:
        cursor.close()
        conn.close()

# ------------------------------- CRUD de Negocios -------------------------------
@app.get("/places")
def get_places():
    last_error = None
    for attempt in range(3):
        conn = None
        cursor = None
        try:
            conn = mysql.connector.connect(**DB_READ_CONFIG)
            cursor = conn.cursor(dictionary=True)
            place_columns = get_places_table_columns(conn)
            select_parts = [
                "id", "public_id", "name", "address", "phone", "website",
                "opening_hours", "category", "description", "initial_phrase",
                "main_photo", "photos", "active"
            ]
            if "owner_user_id" in place_columns:
                select_parts.append("owner_user_id")
            if "business_email" in place_columns:
                select_parts.append("business_email")
            if "contact_email" in place_columns:
                select_parts.append("contact_email")
            if "special_days" in place_columns:
                select_parts.append("special_days")
            if "map_latitude" in place_columns:
                select_parts.append("map_latitude")
            if "map_longitude" in place_columns:
                select_parts.append("map_longitude")
            cursor.execute(f"SELECT {', '.join(select_parts)} FROM places ORDER BY id DESC")
            rows = cursor.fetchall()
            cursor.execute(
                """
                SELECT place_public_id, COUNT(*) AS total_reviews, AVG(rating) AS avg_rating
                FROM reviews
                WHERE is_hidden=0
                GROUP BY place_public_id
                """
            )
            review_rows = cursor.fetchall() or []
            review_map = {
                int(row.get("place_public_id") or 0): {
                    "rating_count": int(row.get("total_reviews") or 0),
                    "rating_avg": round(float(row.get("avg_rating") or 0), 2) if row.get("avg_rating") is not None else 0.0,
                }
                for row in review_rows
                if int(row.get("place_public_id") or 0) > 0
            }
            for r in rows:
                r["name"] = normalize_business_display_name(
                    r.get("name"),
                    f"Negocio {r.get('public_id') or ''}".strip()
                )
                business_email = (r.get("business_email") or "").strip().lower()
                contact_email = (r.get("contact_email") or "").strip().lower()
                if is_technical_revision_email(business_email) and contact_email:
                    r["business_email"] = contact_email
                else:
                    r["business_email"] = business_email or None
                r["contact_email_effective"] = contact_email or r.get("business_email") or None
                try: r["photos"] = json.loads(r["photos"]) if r.get("photos") else []
                except: r["photos"] = []
                try:
                    oh_raw = r.get("opening_hours") or "{}"
                    oh_parsed = json.loads(oh_raw)
                    r["opening_hours"] = {day: oh_parsed.get(day, []) for day in DAYS}
                except:
                    r["opening_hours"] = {day: [] for day in DAYS}
                try:
                    sd_raw = r.get("special_days") or "{}"
                    r["special_days"] = json.loads(sd_raw)
                except:
                    r["special_days"] = {}
                ensure_place_media_urls(r)
                r["active"] = bool(r.get("active", True))
                rating_summary = review_map.get(int(r.get("public_id") or 0)) or {"rating_count": 0, "rating_avg": 0.0}
                r["rating_count"] = int(rating_summary["rating_count"])
                r["rating_avg"] = float(rating_summary["rating_avg"])
            return rows
        except mysql.connector.Error as e:
            last_error = e
            if getattr(e, "errno", None) in (1213, 1205) and attempt < 2:
                time.sleep(0.15 * (attempt + 1))
                continue
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="Error interno al obtener lugares")
        except Exception as e:
            last_error = e
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="Error interno al obtener lugares")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    if last_error:
        traceback.print_exc()
    raise HTTPException(status_code=500, detail="Error interno al obtener lugares")


@app.get("/places/{place_id:int}")
def get_place_by_id(place_id: int):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_READ_CONFIG)
        cursor = conn.cursor(dictionary=True)
        place_columns = get_places_table_columns(conn)
        select_parts = [
            "id", "public_id", "name", "address", "phone", "website",
            "opening_hours", "category", "description", "initial_phrase",
            "main_photo", "photos", "active"
        ]
        if "owner_user_id" in place_columns:
            select_parts.append("owner_user_id")
        if "business_email" in place_columns:
            select_parts.append("business_email")
        if "contact_email" in place_columns:
            select_parts.append("contact_email")
        if "special_days" in place_columns:
            select_parts.append("special_days")
        if "map_latitude" in place_columns:
            select_parts.append("map_latitude")
        if "map_longitude" in place_columns:
            select_parts.append("map_longitude")

        cursor.execute(
            f"SELECT {', '.join(select_parts)} FROM places WHERE public_id=%s LIMIT 1",
            (place_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        if not bool(row.get("active", True)):
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        row["name"] = normalize_business_display_name(row.get("name"), f"Negocio {place_id}")
        business_email = (row.get("business_email") or "").strip().lower()
        contact_email = (row.get("contact_email") or "").strip().lower()
        if is_technical_revision_email(business_email) and contact_email:
            row["business_email"] = contact_email
        else:
            row["business_email"] = business_email or None
        row["contact_email_effective"] = contact_email or row.get("business_email") or None
        try:
            row["photos"] = json.loads(row.get("photos") or "[]")
        except Exception:
            row["photos"] = []
        try:
            oh_raw = row.get("opening_hours") or "{}"
            oh_parsed = json.loads(oh_raw)
            row["opening_hours"] = {day: oh_parsed.get(day, []) for day in DAYS}
        except Exception:
            row["opening_hours"] = {day: [] for day in DAYS}
        try:
            row["special_days"] = json.loads(row.get("special_days") or "{}")
        except Exception:
            row["special_days"] = {}
        ensure_place_media_urls(row)
        row["active"] = bool(row.get("active", True))
        return row
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno al obtener negocio")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ... (los demás endpoints de CRUD se mantienen igual, sin cambios) ...

# ------------------------------- MODELOS AUTH -------------------------------
class RegisterBody(BaseModel):
    username: str
    email: str
    password: str
    birthdate: Optional[str] = None
    recaptcha_token: Optional[str] = None
    hcaptcha_token: Optional[str] = None
    captcha_token: Optional[str] = None
    captcha_answer: Optional[str] = None
    antibot_token: Optional[str] = None
    antibot_elapsed_ms: Optional[int] = None
    antibot_honey: Optional[str] = None
    email_verification_token: Optional[str] = None

class VerifyRegisterBody(BaseModel):
    username: str
    email: str
    password: str
    code: str
    remember: bool = False
    birthdate: Optional[str] = None

class LoginBody(BaseModel):
    login: str
    password: str
    remember: bool = False
    recaptcha_token: Optional[str] = None
    hcaptcha_token: Optional[str] = None
    captcha_token: Optional[str] = None
    captcha_answer: Optional[str] = None
    antibot_token: Optional[str] = None
    antibot_elapsed_ms: Optional[int] = None
    antibot_honey: Optional[str] = None

class VerifyLoginBody(BaseModel):
    login: str
    code: str
    remember: bool = False


class AdminLoginBody(BaseModel):
    username: str
    email: str
    password: str
    mode: Optional[str] = None
    duration_minutes: Optional[int] = None
    turnstile_token: Optional[str] = None
    recaptcha_token: Optional[str] = None
    hcaptcha_token: Optional[str] = None
    antibot_token: Optional[str] = None
    antibot_elapsed_ms: Optional[int] = None
    antibot_honey: Optional[str] = None


class AdminForgotRequestBody(BaseModel):
    username: str
    email: str


class AdminForgotVerifyBody(BaseModel):
    username: str
    email: str
    code: str
    new_password: str


class AdminSessionSettingsBody(BaseModel):
    default_mode: str
    default_duration_minutes: Optional[int] = None
    qr_allow_client: Optional[List[str]] = None
    qr_allow_admin: Optional[List[str]] = None


class AdminRestoreSessionBody(BaseModel):
    session_id: str


class AndroidVersionBuildBody(BaseModel):
    target: str
    notes: str


class AndroidVersionUseBody(BaseModel):
    target: str
    entry_id: str


class WebVersionCreateBody(BaseModel):
    target: str
    notes: str


class WebVersionUseBody(BaseModel):
    target: str
    entry_id: str


class WebVersionUpdateBody(BaseModel):
    target: str
    entry_id: str
    notes: str


class WebVersionDeleteBody(BaseModel):
    target: str
    entry_id: str


class WebVersionSyncBody(BaseModel):
    target: str
    entry_id: str


def _android_build_worker(job_id: str, target: str, notes: str, version_label: str):
    try:
        def on_progress(pct: int, message: str):
            update_android_build_job(job_id, progress=pct, message=message, status="running")

        build_info = run_android_build_on_server(target, version_label, progress_cb=on_progress)
        entry = {
            "id": secrets.token_hex(8),
            "target": target,
            "version": version_label,
            "notes": notes,
            "download_url": build_info["download_url"],
            "filename": build_info["filename"],
            "size_bytes": build_info["size_bytes"],
            "created_at": datetime.now(SEVILLA_TZ).isoformat(),
        }
        with ANDROID_VERSIONS_LOCK:
            payload = load_android_versions_payload()
            payload[target].setdefault("items", [])
            payload[target]["items"].append(entry)
            if payload[target].get("active_id") is None:
                payload[target]["active_id"] = entry["id"]
            save_android_versions_payload(payload)
        update_android_build_job(
            job_id,
            status="done",
            progress=100,
            message="Versión generada y guardada",
            entry=entry
        )
    except HTTPException as e:
        update_android_build_job(
            job_id,
            status="error",
            message="Error durante la compilación",
            error=e.detail if isinstance(e.detail, str) else str(e.detail)
        )
    except Exception as e:
        update_android_build_job(
            job_id,
            status="error",
            message="Error durante la compilación",
            error=str(e)
        )


def _web_snapshot_copy_worker(target: str, entry_id: str, source_dir: Path, snapshot_dir: Path):
    try:
        def _ignore_version_dirs(_dir, names):
            if target != "public":
                return set()
            blocked = {"herramientas", "rack"}
            return set(n for n in names if n in blocked)

        snapshot_dir.mkdir(parents=True, exist_ok=True)
        if snapshot_dir.exists():
            for child in snapshot_dir.iterdir():
                if child.name == ".pending":
                    continue
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    try:
                        child.unlink()
                    except Exception:
                        pass
        pending_marker = snapshot_dir / ".pending"
        pending_marker.write_text("copying", encoding="utf-8")
        shutil.copytree(source_dir, snapshot_dir, dirs_exist_ok=True, ignore=_ignore_version_dirs)
        has_payload = any(child.name != ".pending" for child in snapshot_dir.iterdir())
        if pending_marker.exists():
            pending_marker.unlink()
        if not has_payload:
            raise RuntimeError("Snapshot vacío tras copiar")

        with WEB_VERSIONS_LOCK:
            payload = load_web_versions_payload()
            items = payload.get(target, {}).get("items") or []
            for item in items:
                if str(item.get("id")) == str(entry_id):
                    item["snapshot_ready"] = True
                    item.pop("snapshot_error", None)
                    break
            save_web_versions_payload(payload)
    except Exception as exc:
        with WEB_VERSIONS_LOCK:
            payload = load_web_versions_payload()
            items = payload.get(target, {}).get("items") or []
            for item in items:
                if str(item.get("id")) == str(entry_id):
                    item["snapshot_ready"] = False
                    item["snapshot_error"] = str(exc)
                    break
            save_web_versions_payload(payload)


@app.post("/admin/auth/login")
def admin_login(data: AdminLoginBody, request: Request):
    username = (data.username or "").strip()
    email = (data.email or "").strip().lower()
    password = data.password or ""
    if not username or not email or not password:
        raise HTTPException(status_code=400, detail="Usuario, correo y contraseña son obligatorios")

    check_antibot_rate_limit("admin_login", request.client.host if request.client else "", limit=10, window_seconds=300)

    if not verify_antibot_token(
        data.antibot_token,
        data.antibot_elapsed_ms,
        data.antibot_honey,
        data.hcaptcha_token,
        data.recaptcha_token,
        request.client.host if request.client else None
    ):
        raise HTTPException(status_code=403, detail="Verificación anti-bot fallida")

    cfg = ADMIN_CONFIG
    if username != cfg.get("username") or email != cfg.get("email"):
        raise HTTPException(status_code=401, detail="Credenciales de administración inválidas")
    if not verify_password(password, cfg.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Credenciales de administración inválidas")

    mode = (data.mode or cfg.get("session_default_mode", "limited")).strip().lower()
    if mode not in {"limited", "unlimited"}:
        raise HTTPException(status_code=400, detail="Modo de sesión inválido")
    duration = data.duration_minutes if mode == "limited" else None
    if mode == "limited" and duration is None:
        duration = int(cfg.get("session_default_duration_minutes") or 60)

    session_id, max_age = create_admin_session(mode=mode, duration_minutes=duration)
    response = JSONResponse(content={"detail": "Login admin correcto", "mode": mode, "session_id": session_id})
    set_admin_session_cookie(response=response, request=request, session_id=session_id, max_age=max_age)
    return response


@app.get("/admin/auth/me")
def admin_me(admin=Depends(get_admin_session)):
    return {
        "authenticated": True,
        "username": ADMIN_CONFIG.get("username"),
        "email": ADMIN_CONFIG.get("email"),
        "session_default_mode": ADMIN_CONFIG.get("session_default_mode", "limited"),
        "session_default_duration_minutes": ADMIN_CONFIG.get("session_default_duration_minutes", 60)
    }


class AdminVerifyPasswordBody(BaseModel):
    password: str


@app.post("/admin/auth/verify_password")
def admin_verify_password(data: AdminVerifyPasswordBody, admin=Depends(get_admin_session)):
    password = data.password or ""
    if not password:
        raise HTTPException(status_code=400, detail="Contraseña requerida")
    if not verify_password(password, ADMIN_CONFIG.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Contraseña inválida")
    return {"valid": True}


@app.get("/admin/auth/status")
def admin_status(request: Request):
    try:
        get_admin_session(request)
        authenticated = True
    except HTTPException:
        authenticated = False
    return {"authenticated": authenticated}


@app.post("/admin/auth/logout")
def admin_logout(request: Request, response: Response, admin_session: Optional[str] = Cookie(None, alias=ADMIN_SESSION_COOKIE)):
    if admin_session:
        with ADMIN_LOCK:
            load_admin_sessions()
            ADMIN_SESSIONS.pop(admin_session, None)
            save_admin_sessions()
    clear_admin_session_cookie(response, request=request)
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/")
    return {"detail": "Sesión admin cerrada"}


@app.post("/admin/auth/restore")
def admin_restore_session(data: AdminRestoreSessionBody, request: Request):
    sid = str(data.session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id requerido")
    _get_admin_session_from_cookie_value(sid)
    with ADMIN_LOCK:
        load_admin_sessions()
        sess = ADMIN_SESSIONS.get(sid) or {}
        expires_at = sess.get("expires_at")
    if expires_at is None:
        max_age = 60 * 60 * 24 * 365 * 10
    else:
        remaining = int((expires_at - datetime.utcnow()).total_seconds())
        if remaining <= 0:
            raise HTTPException(status_code=401, detail="Sesion de administracion expirada")
        max_age = remaining
    response = JSONResponse(content={"detail": "Sesion restaurada"})
    set_admin_session_cookie(response=response, request=request, session_id=sid, max_age=max_age)
    return response


@app.post("/admin/ia/cache/refresh")
def admin_refresh_ia_cache(admin=Depends(get_admin_session)):
    target = f"{AGENTS_API_BASE}/agents/public/cache/refresh"
    req = urllib.request.Request(target, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            if not isinstance(payload, dict):
                payload = {}
            return {
                "detail": "Cache IA actualizada",
                "ok": bool(payload.get("ok", True)),
                "places_cached": payload.get("places_cached"),
                "places_cache_last_update": payload.get("places_cache_last_update"),
            }
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"La IA devolvió error: {body or e.reason}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar con la IA: {e}")


@app.post("/agents/public/chat")
async def proxy_agents_public_chat(payload: dict):
    target = f"{AGENTS_API_BASE}/agents/public/chat"
    raw_body = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        target,
        data=raw_body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=AGENTS_PUBLIC_CHAT_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(body) if body else {}
            if not isinstance(data, dict):
                data = {"answer": body}
            return data
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"La IA devolvió error: {body or e.reason}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar con la IA: {e}")


@app.post("/agents/public/chat/stream")
async def proxy_agents_public_chat_stream(payload: dict):
    target = f"{AGENTS_API_BASE}/agents/public/chat/stream"
    raw_body = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        target,
        data=raw_body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    def stream_chunks():
        try:
            with urllib.request.urlopen(req, timeout=AGENTS_PUBLIC_STREAM_TIMEOUT_SECONDS) as resp:
                read_chunk = getattr(resp, "read1", None)
                while True:
                    if callable(read_chunk):
                        chunk = read_chunk(32)
                    else:
                        chunk = resp.read(32)
                    if not chunk:
                        break
                    yield chunk
        except urllib.error.HTTPError as e:
            msg = ""
            try:
                msg = e.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            yield f"Error: {msg or e.reason}".encode("utf-8")
        except Exception as e:
            yield f"Error: No se pudo contactar con la IA ({e})".encode("utf-8")

    return StreamingResponse(
        stream_chunks(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/admin/auth/forgot/request")
def admin_forgot_request(data: AdminForgotRequestBody):
    username = (data.username or "").strip()
    email = (data.email or "").strip().lower()
    if username != ADMIN_CONFIG.get("username") or email != ADMIN_CONFIG.get("email"):
        raise HTTPException(status_code=401, detail="Datos de administración inválidos")

    code = generate_code()
    expires_at = datetime.utcnow() + timedelta(minutes=CODE_EXPIRY_MINUTES)
    with ADMIN_LOCK:
        ADMIN_RECOVERY_CODES[username] = {"code": code, "expires_at": expires_at, "email": email}

    send_email_code(ADMIN_CONFIG.get("recovery_email"), code)
    return {"detail": "Código de recuperación enviado al correo de recuperación"}


@app.post("/admin/auth/forgot/verify")
def admin_forgot_verify(data: AdminForgotVerifyBody):
    username = (data.username or "").strip()
    email = (data.email or "").strip().lower()
    if username != ADMIN_CONFIG.get("username") or email != ADMIN_CONFIG.get("email"):
        raise HTTPException(status_code=401, detail="Datos de administración inválidos")
    if not data.new_password:
        raise HTTPException(status_code=400, detail="Nueva contraseña obligatoria")

    with ADMIN_LOCK:
        recovery = ADMIN_RECOVERY_CODES.get(username)
        if not recovery:
            raise HTTPException(status_code=400, detail="No hay código de recuperación activo")
        if recovery.get("email") != email:
            raise HTTPException(status_code=400, detail="Datos no válidos para recuperación")
        if recovery.get("expires_at") < datetime.utcnow():
            ADMIN_RECOVERY_CODES.pop(username, None)
            raise HTTPException(status_code=400, detail="Código expirado")
        if (recovery.get("code") or "").strip() != (data.code or "").strip():
            raise HTTPException(status_code=400, detail="Código incorrecto")
        ADMIN_RECOVERY_CODES.pop(username, None)

    ADMIN_CONFIG["password_hash"] = hash_password(data.new_password)
    save_admin_config()
    return {"detail": "Contraseña de administración actualizada"}


@app.get("/admin/settings/session")
def admin_session_settings(admin=Depends(get_admin_session)):
    return {
        "default_mode": ADMIN_CONFIG.get("session_default_mode", "limited"),
        "default_duration_minutes": int(ADMIN_CONFIG.get("session_default_duration_minutes", 60)),
        "qr_allow_client": _normalize_qr_allow_rules(ADMIN_CONFIG.get("qr_allow_client")),
        "qr_allow_admin": _normalize_qr_allow_rules(ADMIN_CONFIG.get("qr_allow_admin")),
    }


@app.put("/admin/settings/session")
def admin_update_session_settings(data: AdminSessionSettingsBody, admin=Depends(get_admin_session)):
    mode = (data.default_mode or "").strip().lower()
    if mode not in {"limited", "unlimited"}:
        raise HTTPException(status_code=400, detail="Modo inválido")

    ADMIN_CONFIG["session_default_mode"] = mode
    if mode == "limited":
        minutes = int(data.default_duration_minutes or ADMIN_CONFIG.get("session_default_duration_minutes", 60))
        ADMIN_CONFIG["session_default_duration_minutes"] = max(1, min(minutes, 60 * 24 * 30))
    if data.qr_allow_client is not None:
        ADMIN_CONFIG["qr_allow_client"] = _normalize_qr_allow_rules(data.qr_allow_client)
    else:
        ADMIN_CONFIG["qr_allow_client"] = _normalize_qr_allow_rules(ADMIN_CONFIG.get("qr_allow_client"))
    if data.qr_allow_admin is not None:
        ADMIN_CONFIG["qr_allow_admin"] = _normalize_qr_allow_rules(data.qr_allow_admin)
    else:
        ADMIN_CONFIG["qr_allow_admin"] = _normalize_qr_allow_rules(ADMIN_CONFIG.get("qr_allow_admin"))
    save_admin_config()
    return {"detail": "Configuración de sesión guardada"}


@app.get("/admin/settings/visibility")
def admin_visibility_settings(admin=Depends(get_admin_session)):
    with VISIBILITY_LOCK:
        payload = load_visibility_config()
    return {
        "public_visible": bool(payload.get("public_visible", True)),
        "ai_visible": bool(payload.get("ai_visible", True)),
        "updated_at": payload.get("updated_at"),
    }


@app.put("/admin/settings/visibility")
def admin_update_visibility_settings(data: dict, admin=Depends(get_admin_session)):
    public_visible = bool(data.get("public_visible", True))
    ai_visible = bool(data.get("ai_visible", True))
    with VISIBILITY_LOCK:
        payload = load_visibility_config()
        payload["public_visible"] = public_visible
        payload["ai_visible"] = ai_visible
        save_visibility_config(payload)
    return {"detail": "Configuración de visibilidad guardada"}


@app.get("/public/visibility")
def public_visibility_settings():
    with VISIBILITY_LOCK:
        payload = load_visibility_config()
    return {
        "public_visible": bool(payload.get("public_visible", True)),
        "ai_visible": bool(payload.get("ai_visible", True)),
        "updated_at": payload.get("updated_at"),
    }


@app.get("/public/recaptcha/site-key")
def public_recaptcha_site_key():
    site_key = (os.getenv("RECAPTCHA_SITE_KEY") or "").strip()
    return JSONResponse(
        content={"site_key": site_key},
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/public/hcaptcha/site-key")
def public_hcaptcha_site_key():
    site_key = (os.getenv("HCAPTCHA_SITE_KEY") or "").strip()
    return JSONResponse(
        content={"site_key": site_key},
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/public/antibot/challenge")
def public_antibot_challenge():
    payload = create_antibot_challenge()
    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/public/captcha/challenge")
def public_captcha_challenge():
    payload = create_first_party_captcha()
    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.post("/public/captcha/verify")
def public_captcha_verify(payload: dict):
    token = str(payload.get("token") or "").strip()
    answer = payload.get("answer")
    ok = verify_first_party_captcha(token, answer)
    return {"ok": bool(ok)}


@app.get("/qr/settings/public")
def qr_settings_public(app_mode: Optional[str] = Query(None)):
    mode = (app_mode or "").strip().lower()
    if mode == "admin":
        allow_list = _normalize_qr_allow_rules(ADMIN_CONFIG.get("qr_allow_admin"))
    else:
        allow_list = _normalize_qr_allow_rules(ADMIN_CONFIG.get("qr_allow_client"))
    payload = {
        "app_mode": "admin" if mode == "admin" else "client",
        "allow_list": allow_list,
    }
    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/admin/android_versions")
def admin_android_versions(admin=Depends(get_admin_session)):
    with ANDROID_VERSIONS_LOCK:
        payload = load_android_versions_payload()
    result = {
        "client": {"active_id": payload["client"]["active_id"], "items": []},
        "admin": {"active_id": payload["admin"]["active_id"], "items": []},
    }
    for target in ("client", "admin"):
        active_id = payload[target].get("active_id")
        items = list(payload[target].get("items") or [])
        items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
        for item in items:
            row = dict(item)
            row["is_active"] = str(item.get("id")) == str(active_id)
            result[target]["items"].append(row)
    return result


@app.post("/admin/android_versions/build")
def admin_android_versions_build(data: AndroidVersionBuildBody, admin=Depends(get_admin_session)):
    target = (data.target or "").strip().lower()
    if target not in {"client", "admin"}:
        raise HTTPException(status_code=400, detail="target inválido (client/admin)")
    notes = (data.notes or "").strip()
    if len(notes) < 3:
        raise HTTPException(status_code=400, detail="Describe las novedades (mínimo 3 caracteres)")

    with ANDROID_BUILD_LOCK:
        for job in ANDROID_BUILD_JOBS.values():
            if job.get("target") == target and job.get("status") in {"queued", "running"}:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya hay una compilación en curso para {target}"
                )

    with ANDROID_VERSIONS_LOCK:
        payload = load_android_versions_payload()
        items = payload[target].get("items") or []
        version_label = get_next_android_version_label(items)

    job_id = secrets.token_hex(12)
    now_iso = datetime.now(SEVILLA_TZ).isoformat()
    job = {
        "id": job_id,
        "target": target,
        "version": version_label,
        "notes": notes,
        "status": "queued",
        "progress": 0,
        "message": "Compilación en cola",
        "error": None,
        "entry": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    with ANDROID_BUILD_LOCK:
        ANDROID_BUILD_JOBS[job_id] = job

    worker = threading.Thread(
        target=_android_build_worker,
        args=(job_id, target, notes, version_label),
        daemon=True
    )
    worker.start()
    return {"detail": "Compilación iniciada", "job": job}


@app.get("/admin/android_versions/build_status")
def admin_android_versions_build_status(job_id: str, admin=Depends(get_admin_session)):
    key = (job_id or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="job_id requerido")
    with ANDROID_BUILD_LOCK:
        job = ANDROID_BUILD_JOBS.get(key)
        if not job:
            raise HTTPException(status_code=404, detail="Compilación no encontrada")
        return dict(job)


@app.post("/admin/android_versions/use")
def admin_android_versions_use(data: AndroidVersionUseBody, admin=Depends(get_admin_session)):
    target = (data.target or "").strip().lower()
    entry_id = (data.entry_id or "").strip()
    if target not in {"client", "admin"}:
        raise HTTPException(status_code=400, detail="target inválido (client/admin)")
    if not entry_id:
        raise HTTPException(status_code=400, detail="entry_id requerido")

    with ANDROID_VERSIONS_LOCK:
        payload = load_android_versions_payload()
        items = payload[target].get("items") or []
        found = any(str(item.get("id")) == entry_id for item in items)
        if not found:
            raise HTTPException(status_code=404, detail="Versión no encontrada")
        payload[target]["active_id"] = entry_id
        save_android_versions_payload(payload)
    return {"detail": "Versión marcada en uso"}


@app.get("/admin/web_versions")
def admin_web_versions(admin=Depends(get_admin_session)):
    with WEB_VERSIONS_LOCK:
        payload = load_web_versions_payload()
    result = {
        "public": {
            "active_id": payload["public"]["active_id"],
            "test_active_id": payload["public"].get("test_active_id"),
            "items": [],
        },
        "admin": {
            "active_id": payload["admin"]["active_id"],
            "test_active_id": payload["admin"].get("test_active_id"),
            "items": [],
        },
    }
    for target in ("public", "admin"):
        active_id = payload[target].get("active_id")
        items = list(payload[target].get("items") or [])
        items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
        for item in items:
            row = dict(item)
            row["is_active"] = str(item.get("id")) == str(active_id)
            result[target]["items"].append(row)
    return result


@app.post("/admin/web_versions/create")
def admin_web_versions_create(data: WebVersionCreateBody, admin=Depends(get_admin_session)):
    target = (data.target or "").strip().lower()
    if target not in {"public", "admin"}:
        raise HTTPException(status_code=400, detail="target inválido (public/admin)")
    notes = (data.notes or "").strip()
    if len(notes) < 3:
        raise HTTPException(status_code=400, detail="Describe las novedades (mínimo 3 caracteres)")

    with WEB_VERSIONS_LOCK:
        payload = load_web_versions_payload()
        items = payload[target].get("items") or []
        version_label = get_next_android_version_label(items)
        entry = {
            "id": secrets.token_hex(8),
            "target": target,
            "version": version_label,
            "notes": notes,
            "created_at": datetime.now(SEVILLA_TZ).isoformat(),
        }
        source_dir = WEB_DIR / ("frontend" if target == "public" else "administracion")
        snapshot_rel = f"{target}/{version_label}"
        snapshot_dir = WEB_VERSIONS_DIR / snapshot_rel
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        pending_marker = snapshot_dir / ".pending"
        try:
            pending_marker.write_text("copying", encoding="utf-8")
        except Exception:
            pass
        entry["snapshot_ready"] = False
        entry["snapshot_error"] = None
        entry["snapshot_dir"] = snapshot_rel
        items.append(entry)
        payload[target]["items"] = items
        if payload[target].get("active_id") is None:
            payload[target]["active_id"] = entry["id"]
        save_web_versions_payload(payload)
        worker = threading.Thread(
            target=_web_snapshot_copy_worker,
            args=(target, entry["id"], source_dir, snapshot_dir),
            daemon=True
        )
        worker.start()
    return {"detail": "ok", "entry": entry}


@app.post("/admin/web_versions/update")
def admin_web_versions_update(data: WebVersionUpdateBody, admin=Depends(get_admin_session)):
    target = (data.target or "").strip().lower()
    entry_id = (data.entry_id or "").strip()
    if target not in {"public", "admin"}:
        raise HTTPException(status_code=400, detail="target inválido (public/admin)")
    if not entry_id:
        raise HTTPException(status_code=400, detail="entry_id requerido")
    notes = (data.notes or "").strip()
    if len(notes) < 3:
        raise HTTPException(status_code=400, detail="Describe las novedades (mínimo 3 caracteres)")

    with WEB_VERSIONS_LOCK:
        payload = load_web_versions_payload()
        items = payload[target].get("items") or []
        entry = next((item for item in items if str(item.get("id")) == entry_id), None)
        if not entry:
            raise HTTPException(status_code=404, detail="Versión no encontrada")
        entry["notes"] = notes
        entry["updated_at"] = datetime.now(SEVILLA_TZ).isoformat()
        save_web_versions_payload(payload)
    return {"detail": "ok", "entry": entry}


@app.post("/admin/web_versions/use")
def admin_web_versions_use(data: WebVersionUseBody, admin=Depends(get_admin_session)):
    target = (data.target or "").strip().lower()
    entry_id = (data.entry_id or "").strip()
    if target not in {"public", "admin"}:
        raise HTTPException(status_code=400, detail="target inválido (public/admin)")
    if not entry_id:
        raise HTTPException(status_code=400, detail="entry_id requerido")

    with WEB_VERSIONS_LOCK:
        payload = load_web_versions_payload()
        items = payload[target].get("items") or []
        found = any(str(item.get("id")) == entry_id for item in items)
        if not found:
            raise HTTPException(status_code=404, detail="Versión no encontrada")
        payload[target]["active_id"] = entry_id
        save_web_versions_payload(payload)
    return {"detail": "ok"}


@app.post("/admin/web_versions/use_test")
def admin_web_versions_use_test(data: WebVersionUseBody, admin=Depends(get_admin_session)):
    target = (data.target or "").strip().lower()
    entry_id = (data.entry_id or "").strip()
    if target not in {"public", "admin"}:
        raise HTTPException(status_code=400, detail="target inválido (public/admin)")
    if not entry_id:
        raise HTTPException(status_code=400, detail="entry_id requerido")

    with WEB_VERSIONS_LOCK:
        payload = load_web_versions_payload()
        items = payload[target].get("items") or []
        found = any(str(item.get("id")) == entry_id for item in items)
        if not found:
            raise HTTPException(status_code=404, detail="Versión no encontrada")
        payload[target]["test_active_id"] = entry_id
        save_web_versions_payload(payload)
    return {"detail": "ok"}


def _pick_latest_web_entry_id(items: List[dict]) -> Optional[str]:
    if not items:
        return None
    sorted_items = sorted(
        items,
        key=lambda item: str(item.get("created_at") or ""),
        reverse=True,
    )
    return str(sorted_items[0].get("id") or "") or None


def _clear_dir_preserving(root: Path, preserve_names: Optional[set] = None) -> None:
    preserve = preserve_names or set()
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return
    for child in root.iterdir():
        if child.name in preserve:
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except Exception:
                pass


@app.post("/admin/web_versions/delete")
def admin_web_versions_delete(data: WebVersionDeleteBody, admin=Depends(get_admin_session)):
    target = (data.target or "").strip().lower()
    entry_id = (data.entry_id or "").strip()
    if target not in {"public", "admin"}:
        raise HTTPException(status_code=400, detail="target inválido (public/admin)")
    if not entry_id:
        raise HTTPException(status_code=400, detail="entry_id requerido")

    snapshot_rel = None
    with WEB_VERSIONS_LOCK:
        payload = load_web_versions_payload()
        items = list(payload[target].get("items") or [])
        entry = next((item for item in items if str(item.get("id")) == entry_id), None)
        if not entry:
            raise HTTPException(status_code=404, detail="Versión no encontrada")
        snapshot_rel = str(entry.get("snapshot_dir") or "").strip() or None
        items = [item for item in items if str(item.get("id")) != entry_id]
        payload[target]["items"] = items
        if str(payload[target].get("active_id") or "") == entry_id:
            payload[target]["active_id"] = _pick_latest_web_entry_id(items)
        if str(payload[target].get("test_active_id") or "") == entry_id:
            payload[target]["test_active_id"] = _pick_latest_web_entry_id(items)
        save_web_versions_payload(payload)

    if snapshot_rel:
        candidate = (WEB_VERSIONS_DIR / snapshot_rel).resolve()
        try:
            candidate.relative_to(WEB_VERSIONS_DIR.resolve())
        except ValueError:
            candidate = None
    if candidate and candidate.exists():
        shutil.rmtree(candidate, ignore_errors=True)
    return {"detail": "ok"}


@app.post("/admin/web_versions/sync")
def admin_web_versions_sync(data: WebVersionSyncBody, admin=Depends(get_admin_session)):
    target = (data.target or "").strip().lower()
    entry_id = (data.entry_id or "").strip()
    if target not in {"public", "admin"}:
        raise HTTPException(status_code=400, detail="target inválido (public/admin)")
    if not entry_id:
        raise HTTPException(status_code=400, detail="entry_id requerido")

    with WEB_VERSIONS_LOCK:
        payload = load_web_versions_payload()
        items = payload.get(target, {}).get("items") or []
        entry = next((item for item in items if str(item.get("id")) == entry_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Versión no encontrada")
    if entry.get("snapshot_ready") is False:
        raise HTTPException(status_code=409, detail="La versión todavía se está copiando")
    snapshot_rel = str(entry.get("snapshot_dir") or "").strip()
    if not snapshot_rel:
        raise HTTPException(status_code=400, detail="Snapshot inválido")
    snapshot_dir = (WEB_VERSIONS_DIR / snapshot_rel).resolve()
    try:
        snapshot_dir.relative_to(WEB_VERSIONS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Snapshot inválido")
    if not snapshot_dir.exists():
        raise HTTPException(status_code=404, detail="No se encontró el snapshot")

    dest_dir = WEB_DIR / ("frontend" if target == "public" else "administracion")
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(snapshot_dir, dest_dir, dirs_exist_ok=True)
    return {"detail": "ok"}


@app.get("/web/versions/public")
def web_versions_public():
    with WEB_VERSIONS_LOCK:
        payload = load_web_versions_payload()
    return _build_web_versions_public_output(payload)


@app.get("/web/versions/stream")
async def web_versions_stream(request: Request, target: Optional[str] = None):
    safe_target = (target or "").strip().lower()
    if safe_target and safe_target not in {"public", "admin"}:
        raise HTTPException(status_code=400, detail="target inválido (public/admin)")

    sub_q: queue.Queue = queue.Queue(maxsize=120)
    with WEB_VERSIONS_STREAM_LOCK:
        WEB_VERSIONS_STREAM_SUBSCRIBERS.append(sub_q)
        snapshot = list(WEB_VERSIONS_STREAM_BACKLOG)[-10:]

    if not snapshot:
        with WEB_VERSIONS_LOCK:
            payload = load_web_versions_payload()
        baseline = _build_web_versions_public_output(payload)
        with WEB_VERSIONS_STREAM_LOCK:
            global WEB_VERSIONS_STREAM_REV
            WEB_VERSIONS_STREAM_REV += 1
            baseline_payload = dict(baseline)
            baseline_payload["rev"] = WEB_VERSIONS_STREAM_REV
            baseline_payload["updated_at"] = datetime.now(SEVILLA_TZ).isoformat()
            try:
                baseline_message = json.dumps(baseline_payload, ensure_ascii=False)
            except Exception:
                baseline_message = None
            if baseline_message:
                WEB_VERSIONS_STREAM_BACKLOG.append(baseline_message)
                snapshot = [baseline_message]

    def _filter_message(raw: str) -> str:
        if not safe_target:
            return raw
        try:
            data = json.loads(raw)
        except Exception:
            return raw
        if safe_target == "public":
            filtered = {
                "public": data.get("public"),
                "public_test": data.get("public_test"),
                "rev": data.get("rev"),
                "updated_at": data.get("updated_at"),
            }
        else:
            filtered = {
                "admin": data.get("admin"),
                "admin_test": data.get("admin_test"),
                "rev": data.get("rev"),
                "updated_at": data.get("updated_at"),
            }
        try:
            return json.dumps(filtered, ensure_ascii=False)
        except Exception:
            return raw

    async def event_stream():
        try:
            yield "retry: 1500\n\n"
            for item in snapshot:
                yield f"event: versions\ndata: {_filter_message(item)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.to_thread(sub_q.get, True, 1.0)
                    yield f"event: versions\ndata: {_filter_message(item)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with WEB_VERSIONS_STREAM_LOCK:
                try:
                    WEB_VERSIONS_STREAM_SUBSCRIBERS.remove(sub_q)
                except ValueError:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/android/versions/public")
def android_versions_public():
    with ANDROID_VERSIONS_LOCK:
        payload = load_android_versions_payload()
    out = {"client": None, "admin": None}
    for target in ("client", "admin"):
        active_id = str(payload[target].get("active_id") or "")
        active_entry = None
        for item in payload[target].get("items") or []:
            if str(item.get("id")) == active_id:
                active_entry = dict(item)
                break
        out[target] = active_entry
    return out

# ------------------------------- ENDPOINTS AUTH -------------------------------
@app.get("/auth/oauth/providers")
def auth_oauth_providers():
    return {
        "google": oauth_provider_enabled("google"),
        "microsoft": oauth_provider_enabled("microsoft"),
    }


def _oauth_callback_url(provider: str, request: Request) -> str:
    key = (provider or "").strip().lower()
    if key == "google":
        return str(request.url_for("oauth_google_callback"))
    if key == "microsoft":
        return str(request.url_for("oauth_microsoft_callback"))
    raise HTTPException(status_code=404, detail="Proveedor OAuth no soportado")


@app.get("/auth/oauth/{provider}/start")
def auth_oauth_start(provider: str, request: Request, redirect: Optional[str] = "/"):
    key = (provider or "").strip().lower()
    if key not in {"google", "microsoft"}:
        raise HTTPException(status_code=404, detail="Proveedor OAuth no soportado")
    if not oauth_provider_enabled(key):
        raise HTTPException(status_code=503, detail="Proveedor OAuth no configurado")

    cfg = _oauth_provider_config(key)
    redirect_uri = _oauth_callback_url(key, request)
    remember = str(request.query_params.get("remember") or "1").strip().lower() in {"1", "true", "yes", "on"}
    safe_redirect = _oauth_resolve_safe_redirect(unquote(redirect or ""), request)
    state = secrets.token_urlsafe(24)
    _oauth_state_store(state, {
        "provider": key,
        "redirect": safe_redirect,
        "remember": remember,
        "created_at": time.time(),
    })

    params = {
        "client_id": cfg.get("client_id"),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": cfg.get("scope"),
        "state": state,
        "prompt": "select_account",
    }
    if key == "microsoft":
        params["response_mode"] = "query"

    url = f"{cfg.get('authorize_url')}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


def _oauth_handle_callback(provider: str, request: Request, code: Optional[str], state: Optional[str], error: Optional[str]) -> Response:
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth {provider}: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="OAuth incompleto")

    payload = _oauth_state_pop(state, provider)
    if not payload:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido")

    cfg = _oauth_provider_config(provider)
    redirect_uri = _oauth_callback_url(provider, request)
    token_data = _oauth_exchange_code(cfg, code, redirect_uri)
    userinfo = _oauth_fetch_userinfo(provider, cfg, token_data)

    email = str(userinfo.get("email") or userinfo.get("mail") or userinfo.get("userPrincipalName") or "").strip()
    display_name = str(userinfo.get("name") or userinfo.get("displayName") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="No se pudo obtener el correo del proveedor")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        user_id = _oauth_get_or_create_user(conn, cursor, email, display_name)
        session_id, duration = create_session(cursor, user_id, bool(payload.get("remember")))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    target = _oauth_add_auth_param(str(payload.get("redirect") or "/frontend.html"))
    response = RedirectResponse(url=target, status_code=302)
    set_user_session_cookie(response, session_id, duration, request=request)
    return response


@app.get("/auth/oauth/google/callback", name="oauth_google_callback")
def oauth_google_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    return _oauth_handle_callback("google", request, code, state, error)


@app.get("/auth/oauth/microsoft/callback", name="oauth_microsoft_callback")
def oauth_microsoft_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    return _oauth_handle_callback("microsoft", request, code, state, error)


@app.post("/auth/register")
def register(data: RegisterBody, request: Request):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        username = (data.username or "").strip()
        email = (data.email or "").strip().lower()
        password = data.password or ""
        email_verification_token = (data.email_verification_token or "").strip()

        if not username or not email or not password:
            raise HTTPException(400, "Debes completar usuario, correo y contraseña")

        check_antibot_rate_limit("register", request.client.host if request.client else "", limit=20, window_seconds=300)

        if not verify_public_bot_protection(
            data.antibot_token,
            data.antibot_elapsed_ms,
            data.antibot_honey,
            data.captcha_token,
            data.captcha_answer,
            data.hcaptcha_token,
            data.recaptcha_token,
            request.client.host if request.client else None
        ):
            raise HTTPException(status_code=403, detail="Verificación anti-bot fallida")

        if not email_verification_token:
            raise HTTPException(status_code=400, detail="Debes verificar tu correo antes de registrarte")

        if not verify_register_email_ok_token(email, email_verification_token):
            raise HTTPException(status_code=400, detail="Debes verificar tu correo antes de registrarte")

        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            raise HTTPException(400, "El nombre de usuario ya está en uso")

        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            raise HTTPException(400, "El correo ya está registrado")

        columns = get_users_table_columns(conn)
        hashed_pw = hash_password(password)

        insert_fields = ["username", "email", "password_hash"]
        insert_values = [username, email, hashed_pw]
        if "role_client" in columns:
            insert_fields.append("role_client")
            insert_values.append(1)
        if "birthdate" in columns and data.birthdate:
            insert_fields.append("birthdate")
            insert_values.append(data.birthdate)
        if "email_verification_enabled" in columns:
            insert_fields.append("email_verification_enabled")
            insert_values.append(0)

        placeholders = ",".join(["%s"] * len(insert_fields))
        cursor.execute(
            f"INSERT INTO users ({','.join(insert_fields)}) VALUES ({placeholders})",
            tuple(insert_values)
        )
        new_user_id = cursor.lastrowid
        get_user_avatar_dir(new_user_id)
        session_id, duration = create_session(cursor, new_user_id, False)
        conn.commit()

        response = JSONResponse(content={"detail": "Usuario registrado y sesión iniciada"})
        set_user_session_cookie(response, session_id, duration, request=request)
        return response
    finally:
        cursor.close()
        conn.close()

class RegisterCheckBody(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None


@app.post("/auth/register/check")
def register_check(data: RegisterCheckBody):
    if not (data.username or data.email):
        raise HTTPException(status_code=400, detail="Debes indicar usuario o correo")
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        response = {"username_available": None, "email_available": None}
        if data.username:
            cursor.execute("SELECT id FROM users WHERE username=%s", ((data.username or "").strip(),))
            response["username_available"] = cursor.fetchone() is None
        if data.email:
            cursor.execute("SELECT id FROM users WHERE email=%s", ((data.email or "").strip().lower(),))
            response["email_available"] = cursor.fetchone() is None
        return JSONResponse(content=response)
    finally:
        cursor.close()
        conn.close()


class RegisterEmailCodeSendBody(BaseModel):
    email: EmailStr


class RegisterEmailCodeVerifyBody(BaseModel):
    email: EmailStr
    code: str


def _register_email_ok_secret() -> str:
    return _antibot_secret() or _captcha_secret()


def create_register_email_ok_token(email: str, ttl_seconds: int = 20 * 60) -> str:
    secret = _register_email_ok_secret()
    issued_at = int(time.time())
    nonce = secrets.token_urlsafe(12)
    message = f"{email}|{issued_at}|{nonce}"
    signature = _antibot_hmac(message, secret) if secret else ""
    payload = f"{email}|{issued_at}|{nonce}|{signature}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def verify_register_email_ok_token(email: str, token: str, ttl_seconds: int = 20 * 60) -> bool:
    secret = _register_email_ok_secret()
    if not secret:
        return True
    if not email or not token:
        return False
    try:
        raw = base64.urlsafe_b64decode(str(token).encode("utf-8")).decode("utf-8")
        parts = raw.split("|")
        if len(parts) != 4:
            return False
        email_in, issued_at_text, nonce, signature = parts
        if (email_in or "").strip().lower() != (email or "").strip().lower():
            return False
        issued_at = int(issued_at_text)
        now = int(time.time())
        if issued_at > now or now - issued_at > int(ttl_seconds):
            return False
        message = f"{email_in}|{issued_at_text}|{nonce}"
        expected = _antibot_hmac(message, secret)
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


@app.post("/auth/register/email_code/send")
def register_email_code_send(data: RegisterEmailCodeSendBody, request: Request):
    email = (str(data.email) or "").strip().lower()
    check_antibot_rate_limit(
        "register_email_code_send",
        request.client.host if request.client else "",
        limit=8,
        window_seconds=600,
    )
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Ese correo ya está registrado")

        cursor.execute(
            "DELETE FROM auth_codes WHERE email=%s AND type IN ('register_email', 'register_email_ok')",
            (email,),
        )
        code = generate_code()
        expires = datetime.utcnow() + timedelta(minutes=CODE_EXPIRY_MINUTES)
        cursor.execute(
            "INSERT INTO auth_codes (email, code, type, expires_at) VALUES (%s,%s,'register_email',%s)",
            (email, code, expires),
        )
        conn.commit()

        send_email_code(email, code)
        return {"detail": "Código enviado al correo"}
    finally:
        cursor.close()
        conn.close()


@app.post("/auth/register/email_code/verify")
def register_email_code_verify(data: RegisterEmailCodeVerifyBody, request: Request):
    email = (str(data.email) or "").strip().lower()
    code = (str(data.code) or "").strip()
    if not code or not code.isdigit() or len(code) != 6:
        raise HTTPException(status_code=400, detail="Código inválido")

    check_antibot_rate_limit(
        "register_email_code_verify",
        request.client.host if request.client else "",
        limit=25,
        window_seconds=300,
    )
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT expires_at FROM auth_codes WHERE email=%s AND code=%s AND type='register_email' ORDER BY expires_at DESC LIMIT 1",
            (email, code),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Código inválido")
        if row["expires_at"].replace(tzinfo=timezone.utc) < datetime.utcnow().replace(tzinfo=timezone.utc):
            raise HTTPException(status_code=400, detail="Código expirado")

        cursor.execute("DELETE FROM auth_codes WHERE email=%s AND type='register_email'", (email,))

        conn.commit()
        token = create_register_email_ok_token(email)
        return {"ok": True, "token": token}
    finally:
        cursor.close()
        conn.close()

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    is_default_account: Optional[bool] = False

@app.post("/users")
def create_user(user: UserCreate, admin=Depends(get_admin_session)):
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        user_columns = get_users_table_columns(conn)
        if ("is_default_account" not in user_columns) or any(
            c not in user_columns for c in ("role_client", "role_business", "role_admin")
        ):
            ensure_users_optional_columns(
                conn,
                need_is_default_account="is_default_account" not in user_columns,
                need_role_flags=any(c not in user_columns for c in ("role_client", "role_business", "role_admin")),
            )
            user_columns = get_users_table_columns(conn)
        cursor = conn.cursor(dictionary=True)

        # Comprobar duplicados
        cursor.execute("SELECT id FROM users WHERE username=%s OR email=%s", (user.username, user.email))
        if cursor.fetchone():
            raise HTTPException(400, "Usuario o email ya existe")

        # Hashear password
        hashed_pw = hash_password(user.password)

        # Insertar en la DB
        columns = get_users_table_columns(conn)
        insert_fields = ["username", "email", "password_hash"]
        insert_values = [user.username, user.email, hashed_pw]
        if "role_client" in columns:
            insert_fields.append("role_client")
            insert_values.append(1)
        if "email_verification_enabled" in columns:
            insert_fields.append("email_verification_enabled")
            insert_values.append(0)
        if "is_default_account" in columns:
            insert_fields.append("is_default_account")
            insert_values.append(1 if user.is_default_account else 0)
        placeholders = ",".join(["%s"] * len(insert_fields))
        cursor.execute(
            f"INSERT INTO users ({','.join(insert_fields)}) VALUES ({placeholders})",
            tuple(insert_values)
        )
        user_id = cursor.lastrowid
        get_user_avatar_dir(user_id)

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "status":"created",
            "user":{
                "id":user_id,
                "username":user.username,
                "email":user.email,
                "is_default_account": bool(user.is_default_account)
            }
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error al crear usuario: {e}")



def generate_random_password(length=12):
    chars = string.ascii_letters + string.digits + ".-+*/!@#&$"
    return "".join(random.choice(chars) for _ in range(length))


def oauth_provider_enabled(provider: str) -> bool:
    key = (provider or "").strip().lower()
    if key == "google":
        return bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)
    if key == "microsoft":
        return bool(MICROSOFT_OAUTH_CLIENT_ID and MICROSOFT_OAUTH_CLIENT_SECRET)
    return False


def _oauth_state_cleanup(now: Optional[float] = None) -> None:
    ts = now or time.time()
    cutoff = ts - max(60, OAUTH_STATE_TTL_SECONDS)
    expired = [k for k, v in OAUTH_STATE_STORE.items() if float(v.get("created_at") or 0) < cutoff]
    for key in expired:
        OAUTH_STATE_STORE.pop(key, None)


def _oauth_state_store(state: str, payload: dict) -> None:
    with OAUTH_STATE_LOCK:
        _oauth_state_cleanup()
        OAUTH_STATE_STORE[state] = payload


def _oauth_state_pop(state: str, provider: str) -> Optional[dict]:
    key = (state or "").strip()
    if not key:
        return None
    with OAUTH_STATE_LOCK:
        _oauth_state_cleanup()
        payload = OAUTH_STATE_STORE.pop(key, None)
    if not payload:
        return None
    if (payload.get("provider") or "").strip().lower() != (provider or "").strip().lower():
        return None
    created_at = float(payload.get("created_at") or 0.0)
    if created_at and (time.time() - created_at) > OAUTH_STATE_TTL_SECONDS:
        return None
    return payload


def _oauth_resolve_safe_redirect(raw: Optional[str], request: Request) -> str:
    target = (raw or "").strip() or "/frontend.html"
    try:
        parsed = urllib.parse.urlparse(target)
        if parsed.scheme or parsed.netloc:
            base = urllib.parse.urlparse(str(request.base_url))
            if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
                return "/frontend.html"
            path = parsed.path or "/frontend.html"
            query = f"?{parsed.query}" if parsed.query else ""
            fragment = f"#{parsed.fragment}" if parsed.fragment else ""
            return f"{path}{query}{fragment}"
        if not target.startswith("/"):
            return "/frontend.html"
        return target
    except Exception:
        return "/frontend.html"


def _oauth_add_auth_param(target: str) -> str:
    try:
        parsed = urllib.parse.urlparse(target)
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        qs["_auth"] = [str(int(time.time() * 1000))]
        new_query = urllib.parse.urlencode(qs, doseq=True)
        return urllib.parse.urlunparse(("", "", parsed.path or "/frontend.html", parsed.params, new_query, parsed.fragment))
    except Exception:
        return "/frontend.html"


def _oauth_provider_config(provider: str) -> dict:
    key = (provider or "").strip().lower()
    if key == "google":
        return {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "scope": "openid email profile",
        }
    if key == "microsoft":
        tenant = MICROSOFT_OAUTH_TENANT or "common"
        return {
            "authorize_url": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
            "token_url": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            "userinfo_url": "https://graph.microsoft.com/v1.0/me",
            "client_id": MICROSOFT_OAUTH_CLIENT_ID,
            "client_secret": MICROSOFT_OAUTH_CLIENT_SECRET,
            "scope": "openid email profile User.Read",
        }
    raise HTTPException(status_code=404, detail="Proveedor OAuth no soportado")


def _oauth_http_request(method: str, url: str, body: Optional[bytes] = None, headers: Optional[dict] = None, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise HTTPException(status_code=400, detail=f"OAuth error: {detail or exc.reason}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OAuth error: {exc}")


def _oauth_exchange_code(cfg: dict, code: str, redirect_uri: str) -> dict:
    body = urllib.parse.urlencode({
        "client_id": cfg.get("client_id"),
        "client_secret": cfg.get("client_secret"),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }).encode("utf-8")
    return _oauth_http_request(
        "POST",
        cfg.get("token_url"),
        body=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20.0,
    )


def _oauth_fetch_userinfo(provider: str, cfg: dict, token_data: dict) -> dict:
    access_token = str(token_data.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="OAuth no devolvió access_token")
    if (provider or "").strip().lower() == "google":
        return _oauth_http_request(
            "GET",
            cfg.get("userinfo_url"),
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20.0,
        )
    if (provider or "").strip().lower() == "microsoft":
        return _oauth_http_request(
            "GET",
            cfg.get("userinfo_url"),
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20.0,
        )
    raise HTTPException(status_code=404, detail="Proveedor OAuth no soportado")


def _oauth_suggest_username(email: str) -> str:
    local = (email.split("@")[0] if email else "") or "usuario"
    base = re.sub(r"[^a-zA-Z0-9._-]", "_", local).strip("._-")
    return base or "usuario"


def _oauth_get_or_create_user(conn, cursor, email: str, display_name: Optional[str] = None) -> int:
    clean_email = (email or "").strip().lower()
    if not seems_valid_email(clean_email):
        raise HTTPException(status_code=400, detail="Correo inválido en OAuth")
    cursor.execute("SELECT id FROM users WHERE email=%s", (clean_email,))
    existing = cursor.fetchone()
    if existing:
        return int(existing["id"])

    columns = get_users_table_columns(conn)
    base_username = _oauth_suggest_username(clean_email)
    username = base_username
    suffix = 1
    while True:
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if not cursor.fetchone():
            break
        suffix += 1
        username = f"{base_username}{suffix}"

    insert_fields = ["username", "email", "password_hash"]
    insert_values = [username, clean_email, hash_password(generate_random_password())]
    if "role_client" in columns:
        insert_fields.append("role_client")
        insert_values.append(1)
    if "email_verification_enabled" in columns:
        insert_fields.append("email_verification_enabled")
        insert_values.append(0)
    if "must_change_password" in columns:
        insert_fields.append("must_change_password")
        insert_values.append(0)

    placeholders = ",".join(["%s"] * len(insert_fields))
    cursor.execute(
        f"INSERT INTO users ({','.join(insert_fields)}) VALUES ({placeholders})",
        tuple(insert_values)
    )
    new_user_id = cursor.lastrowid
    get_user_avatar_dir(new_user_id)
    return int(new_user_id)


def is_legacy_default_account(username: Optional[str], email: Optional[str]) -> bool:
    raw_username = (username or "").strip()
    raw_email = (email or "").strip().lower()
    if not raw_username or not raw_email:
        return False
    if not re.fullmatch(r"user_[a-z0-9]{5}", raw_username):
        return False
    return raw_email == f"{raw_username.lower()}@correo.ess"


def _get_user_from_session_db(session_id: str, db_config: dict):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT u.id, u.username, u.email
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.id=%s AND s.expires_at > UTC_TIMESTAMP()
            """,
            (session_id,)
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


# Simulación de usuario logueado
def get_current_user(request: Request):
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise HTTPException(status_code=401, detail="No hay sesión")

    user = _get_user_from_session_db(session_id, DB_READ_CONFIG)
    if not user:
        # Fallback por posible desfase de réplica/lectura.
        user = _get_user_from_session_db(session_id, DB_WRITE_CONFIG)

    if not user:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")

    return user


BASE_DIR = Path(__file__).resolve().parent

AVATAR_DIR = BASE_DIR / "user_avatars"
AVATAR_DIR.mkdir(exist_ok=True)


def get_user_avatar_dir(user_id: int) -> Path:
    path = AVATAR_DIR / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def remove_user_avatar_files(user_id: int):
    user_dir = AVATAR_DIR / str(user_id)
    if user_dir.exists():
        for path in user_dir.glob("*"):
            if path.is_file():
                path.unlink()
    for legacy in AVATAR_DIR.glob(f"{user_id}.*"):
        if legacy.is_file():
            legacy.unlink()


def get_business_image_dir(public_id: int) -> Path:
    path = BUSINESS_IMG_DIR / str(public_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_business_main_photo_url(public_id: int) -> Optional[str]:
    modern = BUSINESS_IMG_DIR / str(public_id) / "main.webp"
    if modern.exists():
        return f"/web/img/businesses/{public_id}/main.webp"
    legacy = IMG_DIR / f"{public_id}.webp"
    if legacy.exists():
        return f"/web/img/{public_id}.webp"
    return None


def ensure_place_media_urls(place_row: dict):
    public_id = int(place_row.get("public_id") or 0)
    place_row["main_photo"] = place_row.get("main_photo") or (get_business_main_photo_url(public_id) if public_id else None)
    photos = place_row.get("photos")
    if not isinstance(photos, list):
        photos = []
    place_row["photos"] = [p for p in photos if isinstance(p, str) and p.strip()]
    contact_email = (place_row.get("contact_email") or "").strip()
    business_email = (place_row.get("business_email") or "").strip()
    place_row["contact_email"] = contact_email or None
    place_row["contact_email_effective"] = contact_email or business_email or None
    place_row["map_latitude"] = normalize_coordinate(place_row.get("map_latitude"), -90, 90)
    place_row["map_longitude"] = normalize_coordinate(place_row.get("map_longitude"), -180, 180)


def normalize_coordinate(value, min_value: float, max_value: float):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if number < min_value or number > max_value:
        return None
    return round(number, 7)


def reverse_geocode_address_from_coordinates(lat: float, lng: float) -> Optional[str]:
    normalized_lat = normalize_coordinate(lat, -90, 90)
    normalized_lng = normalize_coordinate(lng, -180, 180)
    if normalized_lat is None or normalized_lng is None:
        return None
    try:
        query = urllib.parse.urlencode(
            {
                "format": "jsonv2",
                "lat": f"{normalized_lat:.7f}",
                "lon": f"{normalized_lng:.7f}",
                "addressdetails": 1,
                "zoom": 18,
            }
        )
        req = urllib.request.Request(
            f"https://nominatim.openstreetmap.org/reverse?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": "TodoSevillaEste/4.2 (backend reverse geocoder)"
            }
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads((resp.read() or b"{}").decode("utf-8", errors="ignore"))
        address = data.get("address") if isinstance(data, dict) else None
        if isinstance(address, dict):
            road = (
                address.get("road")
                or address.get("pedestrian")
                or address.get("footway")
                or address.get("path")
                or address.get("residential")
            )
            house_number = address.get("house_number")
            city = address.get("city") or address.get("town") or address.get("village")
            district = address.get("suburb") or address.get("neighbourhood")
            parts: List[str] = []
            if road and house_number:
                parts.append(f"{road}, {house_number}")
            elif road:
                parts.append(str(road))
            if district:
                parts.append(str(district))
            if city:
                parts.append(str(city))
            label = ", ".join([str(p).strip() for p in parts if str(p).strip()]).strip()
            if label:
                return label
        display_name = str(data.get("display_name") or "").strip() if isinstance(data, dict) else ""
        if display_name:
            return display_name
    except Exception:
        return None
    return None


def get_user_avatar_url(user_id: int):
    user_dir = AVATAR_DIR / str(user_id)
    if user_dir.exists():
        for path in user_dir.glob("*"):
            if path.suffix.lower() in ALLOWED_AVATAR_EXTENSIONS:
                return f"/user_avatars/{user_id}/{path.name}"
    for path in AVATAR_DIR.glob(f"{user_id}.*"):
        if path.suffix.lower() in ALLOWED_AVATAR_EXTENSIONS:
            return f"/user_avatars/{path.name}"
    return "/web/img/default-avatar.png"


def get_users_table_columns(conn):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SHOW COLUMNS FROM users")
        return {row["Field"] for row in cursor.fetchall()}
    finally:
        cursor.close()


def get_places_table_columns(conn):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SHOW COLUMNS FROM places")
        return {row["Field"] for row in cursor.fetchall()}
    finally:
        cursor.close()


def ensure_users_optional_columns(
    conn,
    need_birthdate: bool = False,
    need_email_verification: bool = False,
    need_is_default_account: bool = False,
    need_role_flags: bool = False,
):
    if not need_birthdate and not need_email_verification and not need_is_default_account and not need_role_flags:
        return

    cursor = conn.cursor()
    try:
        if need_birthdate:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN birthdate DATE NULL")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    pass
                if "Duplicate column name" not in str(e):
                    raise

        if need_email_verification:
            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN email_verification_enabled TINYINT(1) NOT NULL DEFAULT 0"
                )
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    pass
                if "Duplicate column name" not in str(e):
                    raise
    finally:
        cursor.close()

    conn.commit()


def ensure_places_optional_columns(
    conn,
    need_owner_user: bool = False,
    need_business_email: bool = False,
    need_special_days: bool = False,
    need_contact_email: bool = False,
    need_map_latitude: bool = False,
    need_map_longitude: bool = False
):
    if not (
        need_owner_user
        or need_business_email
        or need_special_days
        or need_contact_email
        or need_map_latitude
        or need_map_longitude
    ):
        return

    cursor = conn.cursor()
    try:
        if need_owner_user:
            try:
                cursor.execute("ALTER TABLE places ADD COLUMN owner_user_id INT NULL")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    pass
                if "Duplicate column name" not in str(e):
                    raise
        if need_business_email:
            try:
                cursor.execute("ALTER TABLE places ADD COLUMN business_email VARCHAR(255) NULL")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    pass
                if "Duplicate column name" not in str(e):
                    raise
        if need_special_days:
            try:
                cursor.execute("ALTER TABLE places ADD COLUMN special_days LONGTEXT NULL")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    pass
                if "Duplicate column name" not in str(e):
                    raise
        if need_contact_email:
            try:
                cursor.execute("ALTER TABLE places ADD COLUMN contact_email VARCHAR(255) NULL")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    pass
                if "Duplicate column name" not in str(e):
                    raise
        if need_map_latitude:
            try:
                cursor.execute("ALTER TABLE places ADD COLUMN map_latitude DOUBLE NULL")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    pass
                if "Duplicate column name" not in str(e):
                    raise
        if need_map_longitude:
            try:
                cursor.execute("ALTER TABLE places ADD COLUMN map_longitude DOUBLE NULL")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    pass
                if "Duplicate column name" not in str(e):
                    raise
        if need_is_default_account:
            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN is_default_account TINYINT(1) NOT NULL DEFAULT 0"
                )
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    pass
                if "Duplicate column name" not in str(e):
                    raise
        if need_role_flags:
            for sql in (
                "ALTER TABLE users ADD COLUMN role_client TINYINT(1) NOT NULL DEFAULT 1",
                "ALTER TABLE users ADD COLUMN role_business TINYINT(1) NOT NULL DEFAULT 0",
                "ALTER TABLE users ADD COLUMN role_admin TINYINT(1) NOT NULL DEFAULT 0",
            ):
                try:
                    cursor.execute(sql)
                except Exception as e:
                    errno = getattr(e, "errno", None)
                    if errno == 1142:
                        continue
                    if "Duplicate column name" in str(e):
                        continue
                    raise
    finally:
        cursor.close()
    conn.commit()


def ensure_place_user_assignments_schema(conn):
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS place_user_assignments (
                user_id INT NOT NULL,
                place_public_id INT NOT NULL,
                assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, place_public_id),
                INDEX idx_place_user_assignments_place (place_public_id),
                INDEX idx_place_user_assignments_user (user_id),
                INDEX idx_place_user_assignments_assigned (assigned_at)
            )
            """
        )
        place_columns = get_places_table_columns(conn)
        if "owner_user_id" in place_columns:
            cursor.execute(
                """
                INSERT IGNORE INTO place_user_assignments (user_id, place_public_id, assigned_at)
                SELECT owner_user_id, public_id, NOW()
                FROM places
                WHERE owner_user_id IS NOT NULL
                """
            )
    finally:
        cursor.close()
    conn.commit()


def ensure_reviews_schema(conn, allow_write_fallback: bool = True):
    cursor = conn.cursor()
    try:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                place_public_id INT NOT NULL,
                user_id INT NOT NULL,
                rating TINYINT NOT NULL,
                description TEXT NOT NULL,
                photos_json LONGTEXT NULL,
                is_hidden TINYINT(1) NOT NULL DEFAULT 0,
                hidden_reason VARCHAR(500) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_reviews_place (place_public_id),
                INDEX idx_reviews_user (user_id),
                INDEX idx_reviews_hidden (is_hidden),
                INDEX idx_reviews_created (created_at)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS review_votes (
                review_id BIGINT NOT NULL,
                user_id INT NOT NULL,
                vote TINYINT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (review_id, user_id),
                INDEX idx_review_votes_review (review_id),
                INDEX idx_review_votes_user (user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS review_reports (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                review_id BIGINT NOT NULL,
                reporter_user_id INT NOT NULL,
                reason TEXT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                admin_action VARCHAR(20) NULL,
                admin_note VARCHAR(500) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME NULL,
                INDEX idx_review_reports_review (review_id),
                INDEX idx_review_reports_reporter (reporter_user_id),
                INDEX idx_review_reports_status (status)
            )
            """
        ]
        for sql in statements:
            try:
                cursor.execute(sql)
            except Exception as e:
                if getattr(e, "errno", None) == 1142:
                    if allow_write_fallback:
                        try:
                            write_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                            try:
                                ensure_reviews_schema(write_conn, allow_write_fallback=False)
                            finally:
                                write_conn.close()
                        except Exception:
                            pass
                    return
                raise

        # Compatibilidad hacia atrás: agregar columnas faltantes en instalaciones antiguas.
        def ensure_column(table: str, column: str, definition_sql: str):
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (column,))
            if cursor.fetchone():
                return
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition_sql}")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    if allow_write_fallback:
                        try:
                            write_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                            try:
                                ensure_reviews_schema(write_conn, allow_write_fallback=False)
                            finally:
                                write_conn.close()
                        except Exception:
                            pass
                    return
                if "Duplicate column name" in str(e):
                    return
                raise

        ensure_column("reviews", "photos_json", "photos_json LONGTEXT NULL")
        ensure_column("reviews", "is_hidden", "is_hidden TINYINT(1) NOT NULL DEFAULT 0")
        ensure_column("reviews", "hidden_reason", "hidden_reason VARCHAR(500) NULL")
        ensure_column("reviews", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("reviews", "updated_at", "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        ensure_column("reviews", "pending_recheck", "pending_recheck TINYINT(1) NOT NULL DEFAULT 0")
        ensure_column("reviews", "previous_rating", "previous_rating TINYINT NULL")
        ensure_column("reviews", "previous_description", "previous_description TEXT NULL")
        ensure_column("reviews", "previous_photos_json", "previous_photos_json LONGTEXT NULL")
        ensure_column("reviews", "last_edit_requested_at", "last_edit_requested_at DATETIME NULL")

        ensure_column("review_votes", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("review_votes", "updated_at", "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        ensure_column("review_reports", "status", "status VARCHAR(20) NOT NULL DEFAULT 'pending'")
        ensure_column("review_reports", "admin_action", "admin_action VARCHAR(20) NULL")
        ensure_column("review_reports", "admin_note", "admin_note VARCHAR(500) NULL")
        ensure_column("review_reports", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("review_reports", "resolved_at", "resolved_at DATETIME NULL")

        # Verifica que las tablas base realmente existen; evita fallar tarde en INSERT/SELECT.
        def table_exists(table: str) -> bool:
            try:
                cursor.execute(f"SELECT 1 FROM {table} LIMIT 1")
                cursor.fetchone()
                return True
            except Exception as e:
                if getattr(e, "errno", None) == 1146:
                    return False
                if getattr(e, "errno", None) == 1142:
                    # Sin permiso SELECT en esta conexión; no bloqueamos aquí.
                    return True
                raise

        required_tables = ("reviews", "review_votes", "review_reports")
        missing_tables = [t for t in required_tables if not table_exists(t)]
        if missing_tables and allow_write_fallback:
            try:
                write_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                try:
                    ensure_reviews_schema(write_conn, allow_write_fallback=False)
                finally:
                    write_conn.close()
            except Exception:
                pass
            missing_tables = [t for t in required_tables if not table_exists(t)]

        if missing_tables:
            raise HTTPException(
                status_code=503,
                detail=(
                    "El sistema de reseñas no está inicializado en la base de datos. "
                    f"Tablas faltantes: {', '.join(missing_tables)}."
                )
            )
    finally:
        cursor.close()
    conn.commit()


def ensure_messages_schema(conn, allow_write_fallback: bool = True):
    cursor = conn.cursor()
    try:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS chat_threads (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                place_public_id INT NOT NULL,
                user_a_id INT NOT NULL,
                user_b_id INT NOT NULL,
                initiated_by_user_id INT NULL,
                custom_name_a VARCHAR(180) NULL,
                custom_name_b VARCHAR(180) NULL,
                is_blocked TINYINT(1) NOT NULL DEFAULT 0,
                blocked_by_user_id INT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_chat_place_pair (place_public_id, user_a_id, user_b_id),
                INDEX idx_chat_place (place_public_id),
                INDEX idx_chat_user_a (user_a_id),
                INDEX idx_chat_user_b (user_b_id),
                INDEX idx_chat_blocked (is_blocked)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS global_chat_messages (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                sender_user_id INT NOT NULL,
                body TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_global_chat_sender (sender_user_id),
                INDEX idx_global_chat_created (created_at)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                sender_user_id INT NOT NULL,
                receiver_user_id INT NOT NULL,
                body TEXT NULL,
                media_url VARCHAR(500) NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'delivered',
                edited TINYINT(1) NOT NULL DEFAULT 0,
                is_deleted TINYINT(1) NOT NULL DEFAULT 0,
                deleted_at DATETIME NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                read_at DATETIME NULL,
                INDEX idx_chat_messages_chat (chat_id),
                INDEX idx_chat_messages_receiver (receiver_user_id),
                INDEX idx_chat_messages_created (created_at),
                INDEX idx_chat_messages_status (status)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                endpoint VARCHAR(700) NOT NULL,
                p256dh VARCHAR(255) NOT NULL,
                auth VARCHAR(255) NOT NULL,
                user_agent VARCHAR(255) NULL,
                fail_count INT NOT NULL DEFAULT 0,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                last_success_at DATETIME NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_push_endpoint (endpoint),
                INDEX idx_push_user_active (user_id, is_active)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS fcm_device_tokens (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token VARCHAR(255) NOT NULL,
                platform VARCHAR(40) NOT NULL DEFAULT 'android',
                app_variant VARCHAR(40) NOT NULL DEFAULT 'client',
                device_id VARCHAR(120) NULL,
                user_agent VARCHAR(255) NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                fail_count INT NOT NULL DEFAULT 0,
                last_success_at DATETIME NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_fcm_token (token),
                INDEX idx_fcm_user_active (user_id, is_active),
                INDEX idx_fcm_platform (platform, app_variant)
            )
            """
        ]
        for sql in statements:
            try:
                cursor.execute(sql)
            except Exception as e:
                if getattr(e, "errno", None) == 1142:
                    if allow_write_fallback:
                        try:
                            write_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                            try:
                                ensure_messages_schema(write_conn, allow_write_fallback=False)
                            finally:
                                write_conn.close()
                        except Exception:
                            pass
                    return
                raise

        def ensure_column(table: str, column: str, definition_sql: str):
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (column,))
            if cursor.fetchone():
                return
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition_sql}")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    if allow_write_fallback:
                        try:
                            write_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                            try:
                                ensure_messages_schema(write_conn, allow_write_fallback=False)
                            finally:
                                write_conn.close()
                        except Exception:
                            pass
                    return
                if "Duplicate column name" in str(e):
                    return
                raise

        ensure_column("chat_threads", "custom_name_a", "custom_name_a VARCHAR(180) NULL")
        ensure_column("chat_threads", "custom_name_b", "custom_name_b VARCHAR(180) NULL")
        ensure_column("chat_threads", "initiated_by_user_id", "initiated_by_user_id INT NULL")
        ensure_column("chat_threads", "is_blocked", "is_blocked TINYINT(1) NOT NULL DEFAULT 0")
        ensure_column("chat_threads", "blocked_by_user_id", "blocked_by_user_id INT NULL")
        ensure_column("chat_threads", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("chat_threads", "updated_at", "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        ensure_column("chat_messages", "body", "body TEXT NULL")
        ensure_column("chat_messages", "media_url", "media_url VARCHAR(500) NULL")
        ensure_column("chat_messages", "status", "status VARCHAR(20) NOT NULL DEFAULT 'delivered'")
        ensure_column("chat_messages", "edited", "edited TINYINT(1) NOT NULL DEFAULT 0")
        ensure_column("chat_messages", "is_deleted", "is_deleted TINYINT(1) NOT NULL DEFAULT 0")
        ensure_column("chat_messages", "deleted_at", "deleted_at DATETIME NULL")
        ensure_column("chat_messages", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("chat_messages", "updated_at", "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        ensure_column("chat_messages", "read_at", "read_at DATETIME NULL")

        ensure_column("global_chat_messages", "sender_user_id", "sender_user_id INT NOT NULL")
        ensure_column("global_chat_messages", "body", "body TEXT NOT NULL")
        ensure_column("global_chat_messages", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("global_chat_messages", "updated_at", "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        ensure_column("push_subscriptions", "user_agent", "user_agent VARCHAR(255) NULL")
        ensure_column("push_subscriptions", "fail_count", "fail_count INT NOT NULL DEFAULT 0")
        ensure_column("push_subscriptions", "is_active", "is_active TINYINT(1) NOT NULL DEFAULT 1")
        ensure_column("push_subscriptions", "last_success_at", "last_success_at DATETIME NULL")
        ensure_column("push_subscriptions", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("push_subscriptions", "updated_at", "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        ensure_column("fcm_device_tokens", "platform", "platform VARCHAR(40) NOT NULL DEFAULT 'android'")
        ensure_column("fcm_device_tokens", "app_variant", "app_variant VARCHAR(40) NOT NULL DEFAULT 'client'")
        ensure_column("fcm_device_tokens", "device_id", "device_id VARCHAR(120) NULL")
        ensure_column("fcm_device_tokens", "user_agent", "user_agent VARCHAR(255) NULL")
        ensure_column("fcm_device_tokens", "is_active", "is_active TINYINT(1) NOT NULL DEFAULT 1")
        ensure_column("fcm_device_tokens", "fail_count", "fail_count INT NOT NULL DEFAULT 0")
        ensure_column("fcm_device_tokens", "last_success_at", "last_success_at DATETIME NULL")
        ensure_column("fcm_device_tokens", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("fcm_device_tokens", "updated_at", "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    finally:
        cursor.close()
    conn.commit()


def ensure_support_schema(conn, allow_write_fallback: bool = True):
    cursor = conn.cursor()
    try:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS support_tickets (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                place_public_id INT NULL,
                subject VARCHAR(200) NOT NULL,
                custom_subject VARCHAR(200) NULL,
                custom_name_user VARCHAR(180) NULL,
                body TEXT NOT NULL,
                email VARCHAR(255) NULL,
                attachments_json LONGTEXT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                user_visible TINYINT(1) NOT NULL DEFAULT 1,
                user_blocked TINYINT(1) NOT NULL DEFAULT 0,
                user_deleted TINYINT(1) NOT NULL DEFAULT 0,
                first_admin_response_at DATETIME NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                closed_at DATETIME NULL,
                closed_by_admin_username VARCHAR(120) NULL,
                INDEX idx_support_tickets_user (user_id),
                INDEX idx_support_tickets_status (status),
                INDEX idx_support_tickets_created (created_at)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS support_ticket_messages (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ticket_id BIGINT NOT NULL,
                sender_type VARCHAR(20) NOT NULL,
                sender_user_id INT NULL,
                body TEXT NULL,
                attachments_json LONGTEXT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_support_ticket_messages_ticket (ticket_id),
                INDEX idx_support_ticket_messages_created (created_at)
            )
            """
        ]
        for sql in statements:
            try:
                cursor.execute(sql)
            except Exception as e:
                if getattr(e, "errno", None) == 1142:
                    if allow_write_fallback:
                        try:
                            write_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                            try:
                                ensure_support_schema(write_conn, allow_write_fallback=False)
                            finally:
                                write_conn.close()
                        except Exception:
                            pass
                    return
                raise

        def ensure_column(table: str, column: str, definition_sql: str):
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (column,))
            if cursor.fetchone():
                return
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition_sql}")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    if allow_write_fallback:
                        try:
                            write_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                            try:
                                ensure_support_schema(write_conn, allow_write_fallback=False)
                            finally:
                                write_conn.close()
                        except Exception:
                            pass
                    return
                if "Duplicate column name" in str(e):
                    return
                raise

        ensure_column("support_tickets", "place_public_id", "place_public_id INT NULL")
        ensure_column("support_tickets", "custom_subject", "custom_subject VARCHAR(200) NULL")
        ensure_column("support_tickets", "custom_name_user", "custom_name_user VARCHAR(180) NULL")
        ensure_column("support_tickets", "attachments_json", "attachments_json LONGTEXT NULL")
        ensure_column("support_tickets", "status", "status VARCHAR(20) NOT NULL DEFAULT 'open'")
        ensure_column("support_tickets", "user_visible", "user_visible TINYINT(1) NOT NULL DEFAULT 1")
        ensure_column("support_tickets", "user_blocked", "user_blocked TINYINT(1) NOT NULL DEFAULT 0")
        ensure_column("support_tickets", "user_deleted", "user_deleted TINYINT(1) NOT NULL DEFAULT 0")
        ensure_column("support_tickets", "first_admin_response_at", "first_admin_response_at DATETIME NULL")
        ensure_column("support_tickets", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("support_tickets", "updated_at", "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        ensure_column("support_tickets", "closed_at", "closed_at DATETIME NULL")
        ensure_column("support_tickets", "closed_by_admin_username", "closed_by_admin_username VARCHAR(120) NULL")
        try:
            cursor.execute("SHOW COLUMNS FROM support_tickets LIKE 'user_id'")
            user_col = cursor.fetchone()
            if user_col and len(user_col) >= 3 and str(user_col[2]).upper() == "NO":
                cursor.execute("ALTER TABLE support_tickets MODIFY COLUMN user_id INT NULL")
        except Exception as e:
            errno = getattr(e, "errno", None)
            if errno != 1142:
                raise

        ensure_column("support_ticket_messages", "sender_type", "sender_type VARCHAR(20) NOT NULL")
        ensure_column("support_ticket_messages", "sender_user_id", "sender_user_id INT NULL")
        ensure_column("support_ticket_messages", "body", "body TEXT NULL")
        ensure_column("support_ticket_messages", "attachments_json", "attachments_json LONGTEXT NULL")
        ensure_column("support_ticket_messages", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
    finally:
        cursor.close()
    conn.commit()


def ensure_feedback_schema(conn, allow_write_fallback: bool = True):
    cursor = conn.cursor()
    try:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS feedback_submissions (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                email VARCHAR(255) NOT NULL,
                rating TINYINT NOT NULL DEFAULT 5,
                subject VARCHAR(200) NOT NULL,
                body TEXT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                last_admin_contact_at DATETIME NULL,
                INDEX idx_feedback_status (status),
                INDEX idx_feedback_created (created_at),
                INDEX idx_feedback_user (user_id),
                INDEX idx_feedback_email (email)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS feedback_messages (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                feedback_id BIGINT NOT NULL,
                sender_type VARCHAR(20) NOT NULL,
                body TEXT NOT NULL,
                email_message_id VARCHAR(255) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_feedback_messages_feedback (feedback_id),
                INDEX idx_feedback_messages_created (created_at)
            )
            """
        ]
        for sql in statements:
            try:
                cursor.execute(sql)
            except Exception as e:
                if getattr(e, "errno", None) == 1142:
                    if allow_write_fallback:
                        try:
                            write_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                            try:
                                ensure_feedback_schema(write_conn, allow_write_fallback=False)
                            finally:
                                write_conn.close()
                        except Exception:
                            pass
                    return
                raise

        def ensure_column(table: str, column: str, definition_sql: str):
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (column,))
            if cursor.fetchone():
                return
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition_sql}")
            except Exception as e:
                errno = getattr(e, "errno", None)
                if errno == 1142:
                    if allow_write_fallback:
                        try:
                            write_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                            try:
                                ensure_feedback_schema(write_conn, allow_write_fallback=False)
                            finally:
                                write_conn.close()
                        except Exception:
                            pass
                    return
                if "Duplicate column name" in str(e):
                    return
                raise

        ensure_column("feedback_submissions", "user_id", "user_id INT NULL")
        ensure_column("feedback_submissions", "email", "email VARCHAR(255) NOT NULL")
        ensure_column("feedback_submissions", "rating", "rating TINYINT NOT NULL DEFAULT 5")
        ensure_column("feedback_submissions", "subject", "subject VARCHAR(200) NOT NULL")
        ensure_column("feedback_submissions", "body", "body TEXT NOT NULL")
        ensure_column("feedback_submissions", "status", "status VARCHAR(20) NOT NULL DEFAULT 'open'")
        ensure_column("feedback_submissions", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("feedback_submissions", "updated_at", "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        ensure_column("feedback_submissions", "last_admin_contact_at", "last_admin_contact_at DATETIME NULL")

        ensure_column("feedback_messages", "feedback_id", "feedback_id BIGINT NOT NULL")
        ensure_column("feedback_messages", "sender_type", "sender_type VARCHAR(20) NOT NULL")
        ensure_column("feedback_messages", "body", "body TEXT NOT NULL")
        ensure_column("feedback_messages", "email_message_id", "email_message_id VARCHAR(255) NULL")
        ensure_column("feedback_messages", "created_at", "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
    finally:
        cursor.close()
    conn.commit()


def push_notifications_available() -> bool:
    return bool(webpush and VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY and VAPID_SUBJECT)


def normalize_push_subscription_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    endpoint = normalize_space(str((payload or {}).get("endpoint") or ""))
    keys = (payload or {}).get("keys") or {}
    if not isinstance(keys, dict):
        keys = {}
    p256dh = normalize_space(str(keys.get("p256dh") or ""))
    auth = normalize_space(str(keys.get("auth") or ""))
    if not endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Suscripción push inválida")
    return {"endpoint": endpoint, "p256dh": p256dh, "auth": auth}


def store_push_subscription_for_user(user_id: int, subscription: Dict[str, Any], user_agent: str = "") -> None:
    sub = normalize_push_subscription_payload(subscription)
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor()
    try:
        ensure_messages_schema(conn)
        cursor.execute(
            """
            INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent, fail_count, is_active)
            VALUES (%s, %s, %s, %s, %s, 0, 1)
            ON DUPLICATE KEY UPDATE
                user_id=VALUES(user_id),
                p256dh=VALUES(p256dh),
                auth=VALUES(auth),
                user_agent=VALUES(user_agent),
                fail_count=0,
                is_active=1,
                updated_at=NOW()
            """,
            (int(user_id), sub["endpoint"], sub["p256dh"], sub["auth"], (user_agent or "")[:255]),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def delete_push_subscription(endpoint: str, user_id: Optional[int] = None) -> None:
    ep = normalize_space(endpoint)
    if not ep:
        return
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor()
    try:
        ensure_messages_schema(conn)
        if user_id is None:
            cursor.execute("DELETE FROM push_subscriptions WHERE endpoint=%s", (ep,))
        else:
            cursor.execute("DELETE FROM push_subscriptions WHERE endpoint=%s AND user_id=%s", (ep, int(user_id)))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def send_push_notification_to_user(user_id: int, title: str, body: str, url: str) -> None:
    if not push_notifications_available():
        return
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        cursor.execute(
            """
            SELECT endpoint, p256dh, auth, fail_count
            FROM push_subscriptions
            WHERE user_id=%s AND is_active=1
            """,
            (int(user_id),),
        )
        subs = cursor.fetchall() or []
        if not subs:
            return

        payload = json.dumps({"title": title, "body": body, "url": url}, ensure_ascii=False)
        vapid_claims = {"sub": VAPID_SUBJECT}

        for sub in subs:
            endpoint = str(sub.get("endpoint") or "")
            subscription_info = {
                "endpoint": endpoint,
                "keys": {
                    "p256dh": str(sub.get("p256dh") or ""),
                    "auth": str(sub.get("auth") or ""),
                },
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims,
                    ttl=120,
                )
                cursor.execute(
                    "UPDATE push_subscriptions SET fail_count=0, is_active=1, last_success_at=NOW(), updated_at=NOW() WHERE endpoint=%s",
                    (endpoint,),
                )
            except WebPushException as exc:
                status_code = None
                try:
                    status_code = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
                except Exception:
                    status_code = None
                if status_code in {404, 410}:
                    cursor.execute("DELETE FROM push_subscriptions WHERE endpoint=%s", (endpoint,))
                else:
                    cursor.execute(
                        """
                        UPDATE push_subscriptions
                        SET fail_count=COALESCE(fail_count,0)+1,
                            is_active=CASE WHEN COALESCE(fail_count,0)+1 >= 6 THEN 0 ELSE 1 END,
                            updated_at=NOW()
                        WHERE endpoint=%s
                        """,
                        (endpoint,),
                    )
            except Exception:
                cursor.execute(
                    """
                    UPDATE push_subscriptions
                    SET fail_count=COALESCE(fail_count,0)+1,
                        is_active=CASE WHEN COALESCE(fail_count,0)+1 >= 6 THEN 0 ELSE 1 END,
                        updated_at=NOW()
                    WHERE endpoint=%s
                    """,
                    (endpoint,),
                )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def fcm_notifications_available() -> bool:
    return bool(firebase_messaging and get_firebase_app() is not None)


def normalize_fcm_token(token: str) -> str:
    cleaned = normalize_space(str(token or ""))
    if len(cleaned) < 20:
        raise HTTPException(status_code=400, detail="Token FCM inválido")
    if len(cleaned) > 255:
        raise HTTPException(status_code=400, detail="Token FCM demasiado largo")
    return cleaned


def store_fcm_token_for_user(
    user_id: int,
    token: str,
    platform: str = "android",
    app_variant: str = "client",
    device_id: str = "",
    user_agent: str = "",
) -> None:
    normalized_token = normalize_fcm_token(token)
    normalized_platform = normalize_space(platform or "android")[:40] or "android"
    normalized_variant = normalize_space(app_variant or "client")[:40] or "client"
    normalized_device_id = normalize_space(device_id or "")[:120]
    normalized_ua = normalize_space(user_agent or "")[:255]
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor()
    try:
        ensure_messages_schema(conn)
        cursor.execute(
            """
            INSERT INTO fcm_device_tokens (
                user_id, token, platform, app_variant, device_id, user_agent,
                is_active, fail_count, last_success_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 1, 0, NULL)
            ON DUPLICATE KEY UPDATE
                user_id=VALUES(user_id),
                platform=VALUES(platform),
                app_variant=VALUES(app_variant),
                device_id=VALUES(device_id),
                user_agent=VALUES(user_agent),
                is_active=1,
                fail_count=0,
                updated_at=NOW()
            """,
            (
                int(user_id),
                normalized_token,
                normalized_platform,
                normalized_variant,
                normalized_device_id or None,
                normalized_ua or None,
            ),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def deactivate_fcm_token(token: str, user_id: Optional[int] = None) -> None:
    cleaned = normalize_space(token or "")
    if not cleaned:
        return
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor()
    try:
        ensure_messages_schema(conn)
        if user_id is None:
            cursor.execute(
                "UPDATE fcm_device_tokens SET is_active=0, updated_at=NOW() WHERE token=%s",
                (cleaned,),
            )
        else:
            cursor.execute(
                """
                UPDATE fcm_device_tokens
                SET is_active=0, updated_at=NOW()
                WHERE token=%s AND user_id=%s
                """,
                (cleaned, int(user_id)),
            )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def send_fcm_notification_to_user(
    user_id: int,
    title: str,
    body: str,
    url: str,
    sender_name: str = "",
) -> None:
    if not fcm_notifications_available():
        return
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        cursor.execute(
            """
            SELECT token
            FROM fcm_device_tokens
            WHERE user_id=%s AND is_active=1
            ORDER BY updated_at DESC
            LIMIT 50
            """,
            (int(user_id),),
        )
        rows = cursor.fetchall() or []
        tokens = [normalize_space(str(row.get("token") or "")) for row in rows]
        tokens = [token for token in tokens if token]
        if not tokens:
            return

        message_data = {
            "title": str(title or "Nuevo mensaje"),
            "body": str(body or "Tienes un mensaje nuevo."),
            "url": str(url or "/mensajes.html"),
            "sender_name": str(sender_name or ""),
        }

        for token in tokens:
            message = firebase_messaging.Message(
                token=token,
                data=message_data,
                notification=firebase_messaging.Notification(
                    title=str(title or "Nuevo mensaje"),
                    body=str(body or "Tienes un mensaje nuevo."),
                ),
                android=firebase_messaging.AndroidConfig(
                    priority="high",
                    ttl=timedelta(minutes=5),
                    collapse_key="chat_message",
                    notification=firebase_messaging.AndroidNotification(
                        channel_id="tse_messages",
                        click_action="OPEN_MESSAGES",
                        tag="chat_message",
                    ),
                ),
            )
            try:
                firebase_messaging.send(message, app=get_firebase_app())
                cursor.execute(
                    """
                    UPDATE fcm_device_tokens
                    SET fail_count=0, is_active=1, last_success_at=NOW(), updated_at=NOW()
                    WHERE token=%s
                    """,
                    (token,),
                )
            except Exception as exc:
                err_text = str(exc).lower()
                should_disable = any(
                    marker in err_text
                    for marker in (
                        "registration-token-not-registered",
                        "unregistered",
                        "invalid-argument",
                        "mismatched-credential",
                    )
                )
                if should_disable:
                    cursor.execute(
                        """
                        UPDATE fcm_device_tokens
                        SET is_active=0, updated_at=NOW()
                        WHERE token=%s
                        """,
                        (token,),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE fcm_device_tokens
                        SET fail_count=COALESCE(fail_count,0)+1,
                            is_active=CASE WHEN COALESCE(fail_count,0)+1 >= 10 THEN 0 ELSE 1 END,
                            updated_at=NOW()
                        WHERE token=%s
                        """,
                        (token,),
                    )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def make_support_ticket_code(ticket_id: int) -> str:
    return str(int(ticket_id)).zfill(6)


def decode_json_list(raw_value) -> List[str]:
    if raw_value is None:
        return []
    try:
        parsed = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except Exception:
        parsed = []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str) and item.strip()]


def save_support_media(ticket_id: int, prefix: str, up_file: Optional[UploadFile]) -> Optional[str]:
    if not up_file:
        return None
    ext = Path(up_file.filename or "").suffix.lower()
    if ext not in ALLOWED_MESSAGE_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato de imagen no permitido")
    try:
        image = Image.open(up_file.file).convert("RGB")
        ticket_dir = SUPPORT_IMG_DIR / str(ticket_id)
        ticket_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{prefix}_{secrets.token_hex(4)}.webp"
        output = ticket_dir / filename
        image.save(output, "WEBP", quality=86)
        return f"/web/img/support/{ticket_id}/{filename}"
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo procesar una imagen adjunta")


def support_media_url_to_path(ticket_id: int, media_url: str) -> Optional[Path]:
    prefix = f"/web/img/support/{int(ticket_id)}/"
    if not str(media_url or "").startswith(prefix):
        return None
    name = str(media_url)[len(prefix):]
    if not name or "/" in name or "\\" in name:
        return None
    file_path = SUPPORT_IMG_DIR / str(ticket_id) / name
    return file_path if file_path.exists() and file_path.is_file() else None


def serialize_support_message_row(row: dict, current_user_id: int, is_admin: bool = False) -> dict:
    sender_type = (row.get("sender_type") or "").strip().lower()
    sender_user_id = int(row.get("sender_user_id") or 0)
    created_at = row.get("created_at")
    return {
        "id": int(row.get("id") or 0),
        "ticket_id": int(row.get("ticket_id") or 0),
        "sender_type": sender_type or "user",
        "sender_user_id": sender_user_id if sender_user_id > 0 else None,
        "body": row.get("body") or "",
        "attachments": decode_json_list(row.get("attachments_json")),
        "created_at": created_at.isoformat() if created_at else None,
        "is_mine": (sender_type == "admin") if is_admin else (sender_user_id == int(current_user_id)),
    }

def get_chat_pair_ids(user_id_1: int, user_id_2: int) -> Tuple[int, int]:
    first = int(user_id_1)
    second = int(user_id_2)
    return (first, second) if first < second else (second, first)


def normalize_chat_body(body: Optional[str], max_length: int = 4000) -> str:
    text = (body or "").strip()
    if len(text) > max_length:
        raise HTTPException(status_code=400, detail=f"El mensaje no puede superar {max_length} caracteres")
    return text


def save_message_media(chat_id: int, message_id: int, up_file: Optional[UploadFile]) -> Optional[str]:
    if not up_file:
        return None
    ext = Path(up_file.filename or "").suffix.lower()
    if ext not in ALLOWED_MESSAGE_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato de imagen no permitido")
    try:
        image = Image.open(up_file.file).convert("RGB")
        chat_dir = MESSAGE_IMG_DIR / str(chat_id)
        chat_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{message_id}_{secrets.token_hex(4)}.webp"
        output = chat_dir / filename
        image.save(output, "WEBP", quality=86)
        return f"/web/img/messages/{chat_id}/{filename}"
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo procesar la imagen del mensaje")


def remove_message_media_files(chat_id: int, message_id: int):
    chat_dir = MESSAGE_IMG_DIR / str(chat_id)
    if not chat_dir.exists():
        return
    for file_path in chat_dir.glob(f"{message_id}_*"):
        if file_path.is_file():
            file_path.unlink()


def remove_chat_media_files(chat_id: int):
    chat_dir = MESSAGE_IMG_DIR / str(chat_id)
    if chat_dir.exists():
        shutil.rmtree(chat_dir, ignore_errors=True)


def serialize_chat_message_row(row: dict, current_user_id: int) -> dict:
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")
    read_at = row.get("read_at")
    is_deleted = bool(row.get("is_deleted"))
    body = row.get("body") or ""
    media_url = row.get("media_url")
    if is_deleted:
        body = "Mensaje eliminado"
        media_url = None
    return {
        "id": int(row.get("id") or 0),
        "chat_id": int(row.get("chat_id") or 0),
        "sender_user_id": int(row.get("sender_user_id") or 0),
        "receiver_user_id": int(row.get("receiver_user_id") or 0),
        "is_mine": int(row.get("sender_user_id") or 0) == int(current_user_id),
        "body": body,
        "media_url": media_url,
        "status": row.get("status") or "delivered",
        "edited": bool(row.get("edited")),
        "is_deleted": is_deleted,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "read_at": read_at.isoformat() if read_at else None
    }


def get_chat_thread_or_404(cursor, chat_id: int, current_user_id: int) -> dict:
    cursor.execute(
        """
        SELECT id, place_public_id, user_a_id, user_b_id, custom_name_a, custom_name_b,
               is_blocked, blocked_by_user_id, created_at, updated_at
        FROM chat_threads
        WHERE id=%s
        LIMIT 1
        """,
        (chat_id,)
    )
    chat = cursor.fetchone()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    user_a = int(chat.get("user_a_id") or 0)
    user_b = int(chat.get("user_b_id") or 0)
    if int(current_user_id) not in {user_a, user_b}:
        raise HTTPException(status_code=403, detail="No tienes acceso a este chat")
    return chat


def get_other_user_id_for_chat(chat: dict, current_user_id: int) -> int:
    user_a = int(chat.get("user_a_id") or 0)
    user_b = int(chat.get("user_b_id") or 0)
    return user_b if int(current_user_id) == user_a else user_a


def serialize_chat_thread_for_user(cursor, chat: dict, current_user_id: int, include_last_message: bool = False) -> dict:
    other_user_id = get_other_user_id_for_chat(chat, current_user_id)
    other_user = {}
    if other_user_id > 0:
        cursor.execute("SELECT id, username FROM users WHERE id=%s LIMIT 1", (other_user_id,))
        other_user = cursor.fetchone() or {}
    place_public_id = int(chat.get("place_public_id") or 0)
    place = {}
    if place_public_id > 0:
        cursor.execute("SELECT public_id, name FROM places WHERE public_id=%s LIMIT 1", (place_public_id,))
        place = cursor.fetchone() or {}
    custom_name = chat.get("custom_name_a") if int(current_user_id) == int(chat.get("user_a_id") or 0) else chat.get("custom_name_b")
    payload = {
        "id": int(chat.get("id") or 0),
        "place_public_id": place_public_id,
        "place_name": (
            normalize_business_display_name(place.get("name"), f"Negocio {place_public_id}")
            if place_public_id > 0 else "Chat privado"
        ),
        "place_photo": get_business_main_photo_url(place_public_id) if place_public_id > 0 else "/web/img/default-avatar.png",
        "other_user": {
            "id": int(other_user.get("id") or other_user_id),
            "username": (
                "Administración"
                if int(other_user_id) <= 0
                else (other_user.get("username") or f"Usuario {other_user_id}")
            ),
            "avatar": (
                "/icono/admin/configuracion.png"
                if int(other_user_id) <= 0
                else get_user_avatar_url(int(other_user.get("id") or other_user_id))
            )
        },
        "custom_name": custom_name,
        "is_blocked": bool(chat.get("is_blocked")),
        "blocked_by_user_id": int(chat.get("blocked_by_user_id")) if chat.get("blocked_by_user_id") is not None else None,
        "updated_at": chat.get("updated_at").isoformat() if chat.get("updated_at") else None,
        "created_at": chat.get("created_at").isoformat() if chat.get("created_at") else None
    }
    if include_last_message:
        cursor.execute(
            """
            SELECT id, chat_id, sender_user_id, receiver_user_id, body, media_url, status, edited, is_deleted, created_at, updated_at, read_at
            FROM chat_messages
            WHERE chat_id=%s
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (int(chat.get("id") or 0),)
        )
        last_message = cursor.fetchone()
        payload["last_message"] = (
            serialize_chat_message_row(last_message, current_user_id)
            if last_message else None
        )
        cursor.execute(
            """
            SELECT COUNT(*) AS unread
            FROM chat_messages
            WHERE chat_id=%s AND receiver_user_id=%s AND status<>'read'
            """,
            (int(chat.get("id") or 0), int(current_user_id))
        )
        unread_row = cursor.fetchone() or {}
        payload["unread_count"] = int(unread_row.get("unread") or 0)
    return payload


def get_optional_current_user(request: Request):
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    user = _get_user_from_session_db(session_id, DB_READ_CONFIG)
    if user:
        return user
    return _get_user_from_session_db(session_id, DB_WRITE_CONFIG)


def serialize_review_media(review_id: int, files: List[UploadFile]) -> List[str]:
    review_dir = REVIEW_IMG_DIR / str(review_id)
    review_dir.mkdir(parents=True, exist_ok=True)
    urls = []
    for index, up_file in enumerate(files, start=1):
        ext = Path(up_file.filename or "").suffix.lower()
        if ext not in ALLOWED_REVIEW_IMAGE_EXTENSIONS:
            continue
        try:
            image = Image.open(up_file.file).convert("RGB")
            filename = f"{index}_{secrets.token_hex(4)}.webp"
            output = review_dir / filename
            image.save(output, "WEBP", quality=86)
            urls.append(f"/web/img/reviews/{review_id}/{filename}")
        except Exception:
            continue
    return urls


def get_place_name_by_public_id(cursor, place_public_id: int) -> str:
    cursor.execute("SELECT name FROM places WHERE public_id=%s LIMIT 1", (place_public_id,))
    row = cursor.fetchone() or {}
    return normalize_business_display_name(row.get("name"), f"Negocio {place_public_id}")


def enrich_review_rows(rows: List[dict], current_user_id: Optional[int]) -> List[dict]:
    prepared = []
    for row in rows:
        try:
            photos = json.loads(row.get("photos_json") or "[]")
        except Exception:
            photos = []
        try:
            previous_photos = json.loads(row.get("previous_photos_json") or "[]")
        except Exception:
            previous_photos = []
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")
        was_edited = bool(created_at and updated_at and updated_at > created_at)
        review = {
            "id": int(row["id"]),
            "place_public_id": int(row["place_public_id"]),
            "place_name": normalize_business_display_name(
                row.get("place_name"),
                f"Negocio {row.get('place_public_id') or ''}".strip()
            ),
            "rating": int(row.get("rating") or 0),
            "description": row.get("description") or "",
            "photos": [p for p in photos if isinstance(p, str) and p.strip()],
            "is_hidden": bool(row.get("is_hidden")),
            "hidden_reason": row.get("hidden_reason"),
            "created_at": created_at.isoformat() if created_at else None,
            "updated_at": updated_at.isoformat() if updated_at else None,
            "was_edited": was_edited,
            "pending_recheck": bool(row.get("pending_recheck")),
            "last_edit_requested_at": row.get("last_edit_requested_at").isoformat() if row.get("last_edit_requested_at") else None,
            "previous_rating": int(row.get("previous_rating")) if row.get("previous_rating") is not None else None,
            "previous_description": row.get("previous_description"),
            "previous_photos": [p for p in previous_photos if isinstance(p, str) and p.strip()],
            "like_count": int(row.get("like_count") or 0),
            "dislike_count": int(row.get("dislike_count") or 0),
            "report_count": int(row.get("report_count") or 0),
            "user": {
                "id": int(row.get("user_id") or 0),
                "username": row.get("username") or "Usuario",
                "birthdate": str(row["birthdate"]) if row.get("birthdate") else None,
                "description": row.get("user_description") or "",
                "avatar": get_user_avatar_url(int(row.get("user_id") or 0))
            },
            "my_vote": (
                "like" if int(row.get("my_vote") or 0) == 1
                else "dislike" if int(row.get("my_vote") or 0) == -1
                else None
            ),
            "is_owner": current_user_id is not None and int(row.get("user_id") or -1) == int(current_user_id)
        }
        prepared.append(review)
    return prepared


def get_review_order_sql(sort: str) -> str:
    normalized = (sort or "").strip().lower()
    if normalized == "rating_desc":
        return "r.rating DESC, r.created_at DESC"
    if normalized == "rating_asc":
        return "r.rating ASC, r.created_at DESC"
    if normalized == "oldest":
        return "r.created_at ASC"
    return "r.created_at DESC"


def get_reviews_summary(cursor, place_public_id: int, include_hidden: bool = False) -> dict:
    if include_hidden:
        cursor.execute(
            """
            SELECT COUNT(*) AS total_reviews, AVG(rating) AS avg_rating
            FROM reviews
            WHERE place_public_id=%s
            """,
            (place_public_id,)
        )
    else:
        cursor.execute(
            """
            SELECT COUNT(*) AS total_reviews, AVG(rating) AS avg_rating
            FROM reviews
            WHERE place_public_id=%s AND is_hidden=0
            """,
            (place_public_id,)
        )
    row = cursor.fetchone() or {}
    return {
        "total_reviews": int(row.get("total_reviews") or 0),
        "avg_rating": round(float(row.get("avg_rating") or 0), 2) if row.get("avg_rating") is not None else 0.0
    }


def remove_review_media_files(review_id: int):
    review_dir = REVIEW_IMG_DIR / str(review_id)
    if review_dir.exists():
        shutil.rmtree(review_dir, ignore_errors=True)


def moderate_review_action(conn, review_id: int, action: str, reason: Optional[str], actor_is_admin: bool = True, notify_user: bool = True):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT r.id, r.place_public_id, r.user_id, r.rating, r.description, r.photos_json, r.is_hidden,
                   u.email, u.username
            FROM reviews r
            JOIN users u ON u.id = r.user_id
            WHERE r.id=%s
            LIMIT 1
            """,
            (review_id,)
        )
        review = cursor.fetchone()
        if not review:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")

        normalized_action = (action or "").strip().lower()
        note = (reason or "").strip()

        if normalized_action == "hide":
            cursor.execute(
                """
                UPDATE reviews
                SET is_hidden=1,
                    hidden_reason=%s,
                    pending_recheck=0,
                    previous_rating=NULL,
                    previous_description=NULL,
                    previous_photos_json=NULL,
                    last_edit_requested_at=NULL
                WHERE id=%s
                """,
                (note or "Reseña oculta por moderación", review_id)
            )
            conn.commit()
            if notify_user:
                try:
                    send_notification_email(
                        review["email"],
                        "Tu reseña ha sido ocultada",
                        (
                            f"Hola {review['username']},\n\n"
                            f"Tu reseña del negocio {review['place_public_id']} ha sido ocultada por moderación.\n"
                            f"Motivo: {note or 'No especificado'}\n\n"
                            "Puedes revisarla desde tu panel de reseñas."
                        )
                    )
                except Exception:
                    traceback.print_exc()
            return {"detail": "Reseña ocultada"}

        if normalized_action == "unhide":
            cursor.execute(
                """
                UPDATE reviews
                SET is_hidden=0,
                    hidden_reason=NULL,
                    pending_recheck=0,
                    previous_rating=NULL,
                    previous_description=NULL,
                    previous_photos_json=NULL,
                    last_edit_requested_at=NULL
                WHERE id=%s
                """,
                (review_id,)
            )
            conn.commit()
            return {"detail": "Reseña visible de nuevo"}

        if normalized_action == "delete":
            cursor.execute("DELETE FROM review_votes WHERE review_id=%s", (review_id,))
            cursor.execute("DELETE FROM review_reports WHERE review_id=%s", (review_id,))
            cursor.execute("DELETE FROM reviews WHERE id=%s", (review_id,))
            conn.commit()
            remove_review_media_files(review_id)
            if notify_user:
                try:
                    send_notification_email(
                        review["email"],
                        "Tu reseña ha sido eliminada",
                        (
                            f"Hola {review['username']},\n\n"
                            f"Tu reseña del negocio {review['place_public_id']} ha sido eliminada por moderación.\n"
                            f"Motivo: {note or 'No especificado'}."
                        )
                    )
                except Exception:
                    traceback.print_exc()
            return {"detail": "Reseña eliminada"}

        raise HTTPException(status_code=400, detail="Acción de moderación no válida")
    finally:
        cursor.close()

# Subir foto de perfil
@app.post("/users/me/avatar")
async def upload_avatar(file: UploadFile = File(...), user=Depends(get_current_user)):
    ext = Path(file.filename).suffix
    ext = ext.lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato no permitido")
    remove_user_avatar_files(user["id"])
    avatar_dir = get_user_avatar_dir(user["id"])
    avatar_path = avatar_dir / f"avatar{ext}"
    with avatar_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {
        "message": "Avatar subido correctamente",
        "avatar": f"{user['id']}/{avatar_path.name}",
        "avatar_url": f"/user_avatars/{user['id']}/{avatar_path.name}"
    }


# Eliminar foto de perfil
@app.delete("/users/me/avatar")
async def delete_avatar(user=Depends(get_current_user)):
    remove_user_avatar_files(user["id"])
    return {"message": "Avatar eliminado, se ha puesto el predeterminado"}


class UpdateMyUserBody(BaseModel):
    username: Optional[str] = None
    description: Optional[str] = None
    birthdate: Optional[str] = None
    email_verification_enabled: Optional[bool] = None


@app.put("/users/me")
def update_me(data: UpdateMyUserBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    try:
        columns = get_users_table_columns(conn)
        need_birthdate = data.birthdate is not None and "birthdate" not in columns
        need_email_verification = (
            data.email_verification_enabled is not None and
            "email_verification_enabled" not in columns
        )
        if need_birthdate or need_email_verification:
            ensure_users_optional_columns(
                conn,
                need_birthdate=need_birthdate,
                need_email_verification=need_email_verification
            )
            columns = get_users_table_columns(conn)
        if "is_default_account" not in columns:
            ensure_users_optional_columns(conn, need_is_default_account=True)
            columns = get_users_table_columns(conn)
        updates = []
        values = []

        if data.username is not None and "username" in columns:
            username = data.username.strip()
            if username:
                updates.append("username=%s")
                values.append(username)
                if "is_default_account" in columns:
                    updates.append("is_default_account=0")
        if data.description is not None and "description" in columns:
            updates.append("description=%s")
            values.append(data.description)
        if data.birthdate is not None and "birthdate" in columns:
            updates.append("birthdate=%s")
            values.append(data.birthdate)
        if data.email_verification_enabled is not None and "email_verification_enabled" in columns:
            updates.append("email_verification_enabled=%s")
            values.append(1 if data.email_verification_enabled else 0)

        if not updates:
            return {"detail": "Sin cambios"}

        cursor = conn.cursor()
        try:
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id=%s",
                (*values, user["id"])
            )
        finally:
            cursor.close()
        conn.commit()
    finally:
        conn.close()

    return {"detail": "Usuario actualizado correctamente"}


class ChangeMyPasswordBody(BaseModel):
    old_password: str
    new_password: str


@app.post("/users/me/password")
def change_my_password(data: ChangeMyPasswordBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id=%s", (user["id"],))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if not verify_password(data.old_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

        hashed_pw = hash_password(data.new_password)
        cursor.execute(
            "UPDATE users SET password_hash=%s, must_change_password=0, temp_code=NULL WHERE id=%s",
            (hashed_pw, user["id"])
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return {"detail": "Contraseña actualizada correctamente"}


class ChangeMyEmailBody(BaseModel):
    email: EmailStr
    password: str


class PushSubscribeBody(BaseModel):
    subscription: Dict[str, Any]


class PushUnsubscribeBody(BaseModel):
    endpoint: str


class FcmRegisterBody(BaseModel):
    token: str
    platform: Optional[str] = "android"
    app_variant: Optional[str] = "client"
    device_id: Optional[str] = None


class FcmUnregisterBody(BaseModel):
    token: str


@app.post("/users/me/email")
def change_my_email(data: ChangeMyEmailBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id=%s", (user["id"],))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if not verify_password(data.password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Contraseña incorrecta")

        cursor.execute(
            "SELECT id FROM users WHERE email=%s AND id<>%s",
            (data.email, user["id"])
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El correo ya está en uso")

        user_columns = get_users_table_columns(conn)
        if "is_default_account" not in user_columns:
            ensure_users_optional_columns(conn, need_is_default_account=True)
            user_columns = get_users_table_columns(conn)
        if "is_default_account" in user_columns:
            cursor.execute(
                "UPDATE users SET email=%s, is_default_account=0 WHERE id=%s",
                (data.email, user["id"])
            )
        else:
            cursor.execute("UPDATE users SET email=%s WHERE id=%s", (data.email, user["id"]))

        place_columns = get_places_table_columns(conn)
        if "owner_user_id" in place_columns and "business_email" in place_columns:
            cursor.execute(
                "UPDATE places SET business_email=%s WHERE owner_user_id=%s",
                (data.email, user["id"])
            )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return {"detail": "Correo actualizado correctamente"}


@app.post("/users/me/delete/request_code")
def request_delete_my_account_code(user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT email FROM users WHERE id=%s", (user["id"],))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        email = row["email"]
        code = generate_code()
        expires = datetime.utcnow() + timedelta(minutes=CODE_EXPIRY_MINUTES)
        cursor.execute(
            "INSERT INTO auth_codes (email, code, type, expires_at) VALUES (%s,%s,'delete_account',%s)",
            (email, code, expires)
        )
        conn.commit()
        send_email_code(email, code)
        return {"detail": "Código enviado al correo de tu cuenta"}
    finally:
        cursor.close()
        conn.close()


class DeleteMyAccountBody(BaseModel):
    password: Optional[str] = None
    code: Optional[str] = None


@app.delete("/users/me")
def delete_my_account(data: DeleteMyAccountBody, response: Response, user=Depends(get_current_user)):
    if not (data.password or data.code):
        raise HTTPException(status_code=400, detail="Debes indicar contraseña o código")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT email, password_hash FROM users WHERE id=%s", (user["id"],))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        email = row["email"]

        valid = False
        if data.password:
            valid = verify_password(data.password, row["password_hash"])
            if not valid:
                raise HTTPException(status_code=400, detail="Contraseña incorrecta")
        elif data.code:
            cursor.execute(
                """
                SELECT code, expires_at FROM auth_codes
                WHERE email=%s AND type='delete_account'
                ORDER BY expires_at DESC LIMIT 1
                """,
                (email,)
            )
            code_row = cursor.fetchone()
            if not code_row:
                raise HTTPException(status_code=400, detail="No hay código activo")
            if code_row["expires_at"].replace(tzinfo=timezone.utc) < datetime.utcnow().replace(tzinfo=timezone.utc):
                raise HTTPException(status_code=400, detail="Código expirado")
            if (code_row["code"] or "").strip() != (data.code or "").strip():
                raise HTTPException(status_code=400, detail="Código incorrecto")
            valid = True

        if not valid:
            raise HTTPException(status_code=400, detail="No autorizado para borrar la cuenta")

        cursor.execute("DELETE FROM sessions WHERE user_id=%s", (user["id"],))
        cursor.execute("DELETE FROM auth_codes WHERE email=%s", (email,))
        cursor.execute("DELETE FROM users WHERE id=%s", (user["id"],))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    remove_user_avatar_files(user["id"])

    clear_user_session_cookie(response)
    return {"detail": "Cuenta eliminada correctamente"}


@app.post("/users/{user_id:int}/reset_password")
def reset_password(user_id: int, admin=Depends(get_admin_session)):
    conn = None
    cursor = None
    try:
        # Conectar a la base de datos
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # Buscar el usuario
        cursor.execute("SELECT id, email FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Generar nueva contraseña aleatoria
        new_pw = generate_random_password()
        hashed_pw = hash_password(new_pw)
        
        # Actualizar la contraseña y marcar must_change_password
        cursor.execute(
            "UPDATE users SET password_hash=%s, must_change_password=1, temp_code=NULL WHERE id=%s",
            (hashed_pw, user_id)
        )
        conn.commit()
        
        # Enviar correo con la nueva contraseña
        msg = MIMEText(f"Tu nueva contraseña es: {new_pw}")
        msg["Subject"] = "Contraseña reseteada"
        msg["From"] = EMAIL_SENDER
        msg["To"] = user["email"]

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        return {"detail": "Contraseña reseteada y enviada por correo"}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al resetear la contraseña: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


class ChangePasswordBody(BaseModel):
    user_id: int
    new_password: str

@app.post("/users/change_password")
def change_password(data: ChangePasswordBody):
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        cursor = conn.cursor()
        hashed_pw = hash_password(data.new_password)
        cursor.execute(
            "UPDATE users SET password_hash=%s, must_change_password=0, temp_code=NULL WHERE id=%s",
            (hashed_pw, data.user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"detail": "Contraseña actualizada correctamente"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error al cambiar contraseña: {e}")


@app.get("/users")
def list_users(admin=Depends(get_admin_session)):
    try:
        conn = mysql.connector.connect(**DB_READ_CONFIG)
        user_columns = get_users_table_columns(conn)
        place_columns = get_places_table_columns(conn)
        cursor = conn.cursor(dictionary=True)
        select_parts = ["u.id", "u.username", "u.email"]
        if "is_default_account" in user_columns:
            select_parts.append("u.is_default_account")
        if "role_client" in user_columns:
            select_parts.append("u.role_client")
        if "role_business" in user_columns:
            select_parts.append("u.role_business")
        if "role_admin" in user_columns:
            select_parts.append("u.role_admin")
        cursor.execute(f"SELECT {', '.join(select_parts)} FROM users u ORDER BY u.id DESC")
        rows = cursor.fetchall()
        cursor.close()
        for r in rows:
            r["visible_id"] = f"u{r['id']}"
            db_mark = bool(r.get("is_default_account", False))
            r["is_default_account"] = db_mark or is_legacy_default_account(r.get("username"), r.get("email"))
            roles = normalize_user_roles_payload(
                parse_db_bool(r.get("role_client")) if "role_client" in r else None,
                parse_db_bool(r.get("role_business")) if "role_business" in r else None,
                parse_db_bool(r.get("role_admin")) if "role_admin" in r else None,
            )
            managed_place = get_managed_place_public_id_for_user(conn, int(r.get("id") or 0))
            r["roles"] = roles
            r["managed_place_public_id"] = managed_place
        conn.close()
        return rows
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al obtener usuarios")


# ------------------------------- ENDPOINT LOGIN -------------------------------
from datetime import timezone




@app.post("/auth/register/verify")
def verify_register(data: VerifyRegisterBody, request: Request):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    # Revisar si el código existe y no ha expirado
    cursor.execute(
        "SELECT * FROM auth_codes WHERE email=%s AND code=%s AND type='register'",
        (data.email, data.code)
    )
    code_row = cursor.fetchone()
    if not code_row:
        raise HTTPException(400, "Código inválido")
    
    if code_row['expires_at'].replace(tzinfo=timezone.utc) < datetime.utcnow().replace(tzinfo=timezone.utc):
        raise HTTPException(400, "Código expirado")
    
    # Crear el usuario
    hashed_pw = hash_password(data.password)
    columns = get_users_table_columns(conn)
    insert_fields = ["username", "email", "password_hash"]
    insert_values = [data.username, data.email, hashed_pw]
    if "role_client" in columns:
        insert_fields.append("role_client")
        insert_values.append(1)
    if "birthdate" in columns and data.birthdate:
        insert_fields.append("birthdate")
        insert_values.append(data.birthdate)
    if "email_verification_enabled" in columns:
        insert_fields.append("email_verification_enabled")
        insert_values.append(0)
    placeholders = ",".join(["%s"] * len(insert_fields))
    cursor.execute(
        f"INSERT INTO users ({','.join(insert_fields)}) VALUES ({placeholders})",
        tuple(insert_values)
    )
    created_user_id = cursor.lastrowid
    get_user_avatar_dir(created_user_id)
    
    # Opcional: crear sesión directamente
    session_id, duration = create_session(cursor, created_user_id, data.remember)
    
    conn.commit()
    cursor.close()
    conn.close()
    
    response = JSONResponse(content={"detail": "Usuario registrado y sesión iniciada"})
    set_user_session_cookie(response, session_id, duration, request=request)
    return response


@app.post("/auth/logout")
def logout(request: Request, response: Response, tsev_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE)):
    if not tsev_session:
        clear_user_session_cookie(response, request=request)
        return {"detail": "Sesión cerrada"}

    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        cursor = conn.cursor()
        # Borrar la sesión de la tabla sessions
        cursor.execute("DELETE FROM sessions WHERE id=%s", (tsev_session,))
        conn.commit()
        cursor.close()
        conn.close()

        # Borrar la cookie en el navegador
        clear_user_session_cookie(response, request=request)
        return {"detail": "Sesión cerrada"}
    except Exception as e:
        raise HTTPException(500, f"Error al cerrar sesión: {e}")


# login verify
@app.post("/auth/login/verify")
def verify_login(data: VerifyLoginBody, request: Request):
    """
    Verifica el código enviado al email tras login.
    """
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        # Buscar usuario
        cursor.execute(
            "SELECT id, email, must_change_password, temp_code FROM users WHERE username=%s OR email=%s",
            (data.login, data.login)
        )
        user = cursor.fetchone()
        if not user:
            raise HTTPException(400, "Usuario no encontrado")

        # Obtener último código activo de login
        cursor.execute(
            "SELECT * FROM auth_codes WHERE email=%s AND type='login' ORDER BY expires_at DESC LIMIT 1",
            (user["email"],)
        )
        code_row = cursor.fetchone()
        if not code_row:
            raise HTTPException(400, "No se encontró un código activo")

        # Revisar expiración UTC
        if code_row['expires_at'].replace(tzinfo=timezone.utc) < datetime.utcnow().replace(tzinfo=timezone.utc):
            raise HTTPException(400, "Código expirado")

        # Comparar códigos limpiando espacios
        if (code_row['code'] or "").strip() != (data.code or "").strip():
            raise HTTPException(400, "Código incorrecto")

        # Si debe cambiar contraseña, no creamos sesión todavía.
        if user["must_change_password"]:
            cursor.execute("DELETE FROM auth_codes WHERE email=%s AND type='login'", (user["email"],))
            conn.commit()
            cursor.close()
            conn.close()
            return JSONResponse(content={"must_change_password": True, "user_id": user["id"]})

        # Código correcto: crear sesión
        session_id, duration = create_session(cursor, user["id"], data.remember)

        # Borrar código usado
        cursor.execute("DELETE FROM auth_codes WHERE email=%s AND type='login'", (user["email"],))
        conn.commit()

        # Cerrar conexión
        cursor.close()
        conn.close()

        # Devolver cookie de sesión
        response = JSONResponse(content={"detail": "Login exitoso"})
        set_user_session_cookie(response, session_id, duration, request=request)
        return response

    except HTTPException:
        cursor.close()
        conn.close()
        raise
    except Exception as e:
        cursor.close()
        conn.close()
        traceback.print_exc()
        raise HTTPException(500, f"Error interno: {e}")

    
@app.post("/auth/login")
def login(data: LoginBody, request: Request):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        columns = get_users_table_columns(conn)
        select_parts = ["id", "email", "must_change_password"]
        has_email_verification = "email_verification_enabled" in columns
        if has_email_verification:
            select_parts.append("email_verification_enabled")

        check_antibot_rate_limit("login", request.client.host if request.client else "", limit=25, window_seconds=300)

        if not verify_public_bot_protection(
            data.antibot_token,
            data.antibot_elapsed_ms,
            data.antibot_honey,
            data.captcha_token,
            data.captcha_answer,
            data.hcaptcha_token,
            data.recaptcha_token,
            request.client.host if request.client else None
        ):
            raise HTTPException(status_code=403, detail="Verificación anti-bot fallida")

        # Buscar usuario por username o email
        cursor.execute(
            f"SELECT {', '.join(select_parts)} FROM users WHERE username=%s OR email=%s",
            (data.login, data.login)
        )
        user = cursor.fetchone()
        if not user:
            raise HTTPException(400, "Usuario no encontrado")
        
        # Verificar contraseña
        cursor.execute("SELECT password_hash FROM users WHERE id=%s", (user["id"],))
        pw_row = cursor.fetchone()
        if not verify_password(data.password, pw_row["password_hash"]):
            raise HTTPException(400, "Contraseña incorrecta")

        email_verification_enabled = (
            parse_db_bool(user.get("email_verification_enabled"))
            if has_email_verification else False
        )

        # Si no requiere verificación por correo, iniciar sesión directa
        if not email_verification_enabled:
            if user["must_change_password"]:
                cursor.close()
                conn.close()
                return JSONResponse(content={"must_change_password": True, "user_id": user["id"]})

            session_id, duration = create_session(cursor, user["id"], data.remember)
            conn.commit()
            response = JSONResponse(content={"detail": "Login exitoso", "requires_email_verification": False})
            set_user_session_cookie(response, session_id, duration, request=request)
            cursor.close()
            conn.close()
            return response

        # Generar código de login temporal si verificación por correo activa
        code = generate_code()
        expires = datetime.utcnow() + timedelta(minutes=CODE_EXPIRY_MINUTES)
        cursor.execute(
            "INSERT INTO auth_codes (email, code, type, expires_at) VALUES (%s,%s,'login',%s)",
            (user["email"], code, expires)
        )
        conn.commit()
        send_email_code(user["email"], code)
        cursor.close()
        conn.close()
        return {"detail": "Código de verificación enviado al correo", "requires_email_verification": True}

    except HTTPException:
        cursor.close()
        conn.close()
        raise
    except Exception as e:
        cursor.close()
        conn.close()
        traceback.print_exc()
        raise HTTPException(500, f"Error en login: {e}")



class ForgotPasswordRequest(BaseModel):
    email: EmailStr

@app.post("/auth/forgot_password")
def forgot_password(data: ForgotPasswordRequest):
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM users WHERE email=%s", (data.email,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(404, "Correo no registrado")

        code = generate_code()
        expires = datetime.utcnow() + timedelta(minutes=CODE_EXPIRY_MINUTES)

        # Guardamos el código para reseteo de contraseña
        cursor.execute("""
            INSERT INTO auth_codes (email, code, type, expires_at)
            VALUES (%s, %s, 'reset', %s)
        """, (data.email, code, expires))
        conn.commit()
        cursor.close()
        conn.close()

        # Enviar correo
        send_email_code(data.email, code)

        return {"detail": "Código de verificación enviado a tu correo"}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error al generar código de reseteo: {e}")

class ResetPasswordVerify(BaseModel):
    email: EmailStr
    code: str
    new_password: str

@app.post("/auth/reset_password/verify")
def reset_password_verify(data: ResetPasswordVerify):
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Verificar que el código existe y no ha expirado
        cursor.execute("""
            SELECT * FROM auth_codes 
            WHERE email=%s AND code=%s AND type='reset'
        """, (data.email, data.code))
        code_row = cursor.fetchone()
        if not code_row:
            raise HTTPException(400, "Código inválido")
        if code_row['expires_at'].replace(tzinfo=timezone.utc) < datetime.utcnow().replace(tzinfo=timezone.utc):
            raise HTTPException(400, "Código expirado")

        # Actualizar contraseña
        hashed_pw = hash_password(data.new_password)
        cursor.execute("""
            UPDATE users SET password_hash=%s, must_change_password=0, temp_code=NULL WHERE email=%s
        """, (hashed_pw, data.email))

        # Borrar el código usado
        cursor.execute("""
            DELETE FROM auth_codes WHERE email=%s AND code=%s AND type='reset'
        """, (data.email, data.code))

        conn.commit()
        cursor.close()
        conn.close()

        return {"detail": "Contraseña actualizada correctamente"}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error al cambiar contraseña: {e}")

    


@app.get("/auth/me")
@app.get("/users/me")
def me(request: Request):
    user = get_current_user(request)
    birthdate = None
    description = ""
    role_info = {"roles": {"client": True, "business": False, "admin": False}, "managed_place_public_id": None}

    conn = mysql.connector.connect(**DB_READ_CONFIG)
    try:
        columns = get_users_table_columns(conn)
        select_parts = ["username", "email"]
        if "birthdate" in columns:
            select_parts.append("birthdate")
        if "description" in columns:
            select_parts.append("description")
        if "email_verification_enabled" in columns:
            select_parts.append("email_verification_enabled")
        if "role_client" in columns:
            select_parts.append("role_client")
        if "role_business" in columns:
            select_parts.append("role_business")
        if "role_admin" in columns:
            select_parts.append("role_admin")

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {', '.join(select_parts)} FROM users WHERE id=%s",
                (user["id"],)
            )
            row = cursor.fetchone() or {}
        finally:
            cursor.close()

        if "birthdate" in row and row["birthdate"] is not None:
            birthdate = str(row["birthdate"])
        if "description" in row and row["description"] is not None:
            description = row["description"]
        role_info = get_user_roles_for_id(conn, int(user["id"]))
    finally:
        conn.close()

    payload = {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "birthdate": birthdate,
        "description": description,
        "email_verification_enabled": (
            parse_db_bool(row.get("email_verification_enabled", 0))
            if "row" in locals() else False
        ),
        "avatar": get_user_avatar_url(user["id"]),
        "roles": role_info["roles"],
        "managed_place_public_id": role_info["managed_place_public_id"],
    }
    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/notifications/vapid_public_key")
def notifications_vapid_public_key():
    enabled = push_notifications_available()
    return {
        "enabled": enabled,
        "public_key": VAPID_PUBLIC_KEY if enabled else "",
    }


@app.post("/notifications/subscribe")
def notifications_subscribe(payload: PushSubscribeBody, request: Request, user=Depends(get_current_user)):
    if not push_notifications_available():
        raise HTTPException(status_code=503, detail="Notificaciones push no disponibles en el servidor")
    user_agent = (request.headers.get("user-agent") or "").strip()[:255]
    store_push_subscription_for_user(
        user_id=int(user["id"]),
        subscription=payload.subscription or {},
        user_agent=user_agent,
    )
    return {"detail": "Suscripción push guardada"}


@app.post("/notifications/unsubscribe")
def notifications_unsubscribe(payload: PushUnsubscribeBody, user=Depends(get_current_user)):
    delete_push_subscription(endpoint=payload.endpoint, user_id=int(user["id"]))
    return {"detail": "Suscripción push eliminada"}


@app.get("/notifications/fcm/status")
def notifications_fcm_status():
    return {"enabled": fcm_notifications_available()}


@app.post("/notifications/fcm/register")
def notifications_fcm_register(payload: FcmRegisterBody, request: Request, user=Depends(get_current_user)):
    user_agent = (request.headers.get("user-agent") or "").strip()[:255]
    store_fcm_token_for_user(
        user_id=int(user["id"]),
        token=payload.token,
        platform=payload.platform or "android",
        app_variant=payload.app_variant or "client",
        device_id=payload.device_id or "",
        user_agent=user_agent,
    )
    return {
        "detail": "Token FCM registrado",
        "fcm_enabled": fcm_notifications_available(),
    }


@app.post("/notifications/fcm/unregister")
def notifications_fcm_unregister(payload: FcmUnregisterBody, user=Depends(get_current_user)):
    deactivate_fcm_token(token=payload.token, user_id=int(user["id"]))
    return {"detail": "Token FCM desactivado"}


@app.get("/notifications/fcm/me")
def notifications_fcm_me(user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        cursor.execute(
            """
            SELECT id, platform, app_variant, device_id, is_active, fail_count, last_success_at, updated_at
            FROM fcm_device_tokens
            WHERE user_id=%s
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (int(user["id"]),),
        )
        rows = cursor.fetchall() or []
        payload = []
        for row in rows:
            payload.append(
                {
                    "id": int(row.get("id") or 0),
                    "platform": row.get("platform") or "android",
                    "app_variant": row.get("app_variant") or "client",
                    "device_id": row.get("device_id"),
                    "is_active": bool(row.get("is_active")),
                    "fail_count": int(row.get("fail_count") or 0),
                    "last_success_at": row.get("last_success_at").isoformat() if row.get("last_success_at") else None,
                    "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
                }
            )
        return {"enabled": fcm_notifications_available(), "tokens": payload}
    finally:
        cursor.close()
        conn.close()


class ReviewVoteBody(BaseModel):
    vote: str


class ReviewReportBody(BaseModel):
    reason: str


class ReviewEditBody(BaseModel):
    rating: Optional[int] = None
    description: Optional[str] = None


class ReviewModerationBody(BaseModel):
    action: str
    reason: Optional[str] = None
    notify_user: Optional[bool] = True


class ReviewReportModerationBody(BaseModel):
    action: str
    reason: Optional[str] = None
    notify_user: Optional[bool] = True


class ReviewRevisionModerationBody(BaseModel):
    action: str
    reason: Optional[str] = None


class ChatRenameBody(BaseModel):
    name: Optional[str] = None


class ChatBlockBody(BaseModel):
    blocked: bool


class ChatMessageEditBody(BaseModel):
    body: str


class GlobalChatMessageBody(BaseModel):
    body: str


class SupportTicketCloseBody(BaseModel):
    close: bool = True


class SupportTicketEmailBody(BaseModel):
    subject: str
    body: str


class AdminMailSendBody(BaseModel):
    to_email: Optional[str] = None
    to_username: Optional[str] = None
    subject: str
    body: str


@app.post("/messages/chats/from_place/{place_id:int}")
def open_chat_for_place(place_id: int, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        place_columns = get_places_table_columns(conn)
        if "owner_user_id" not in place_columns:
            raise HTTPException(status_code=400, detail="El negocio no tiene propietario de cuenta configurado")
        cursor.execute(
            "SELECT public_id, name, owner_user_id FROM places WHERE public_id=%s LIMIT 1",
            (place_id,)
        )
        place = cursor.fetchone()
        if not place:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        owner_user_id = int(place.get("owner_user_id") or 0)
        if owner_user_id <= 0:
            raise HTTPException(status_code=400, detail="Este negocio no tiene cuenta vinculada")
        if owner_user_id == int(user["id"]):
            raise HTTPException(status_code=400, detail="No puedes iniciar un chat contigo mismo")
        user_a, user_b = get_chat_pair_ids(int(user["id"]), owner_user_id)
        cursor.execute(
            """
            SELECT id FROM chat_threads
            WHERE place_public_id=%s AND user_a_id=%s AND user_b_id=%s
            LIMIT 1
            """,
            (place_id, user_a, user_b)
        )
        existing = cursor.fetchone()
        if existing:
            chat_id = int(existing["id"])
            cursor.execute(
                """
                UPDATE chat_threads
                SET updated_at=NOW(),
                    initiated_by_user_id=COALESCE(initiated_by_user_id, %s)
                WHERE id=%s
                """,
                (int(user["id"]), chat_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO chat_threads (place_public_id, user_a_id, user_b_id, initiated_by_user_id)
                VALUES (%s, %s, %s, %s)
                """,
                (place_id, user_a, user_b, int(user["id"]))
            )
            chat_id = int(cursor.lastrowid)
        conn.commit()
        return {"detail": "Chat listo", "chat_id": chat_id}
    finally:
        cursor.close()
        conn.close()


@app.post("/messages/chats/with_user/{target_user_id:int}")
def open_chat_with_user(target_user_id: int, place_public_id: Optional[int] = Query(None), user=Depends(get_current_user)):
    if int(target_user_id) == int(user["id"]):
        raise HTTPException(status_code=400, detail="No puedes iniciar un chat contigo mismo")
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        cursor.execute("SELECT id FROM users WHERE id=%s LIMIT 1", (int(target_user_id),))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario objetivo no encontrado")

        final_place_public_id = int(place_public_id or 0)
        if final_place_public_id > 0:
            cursor.execute(
                "SELECT public_id FROM places WHERE public_id=%s LIMIT 1",
                (final_place_public_id,)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Negocio no encontrado")
        else:
            cursor.execute(
                """
                SELECT public_id
                FROM places
                WHERE owner_user_id=%s
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(target_user_id),)
            )
            place_row = cursor.fetchone()
            final_place_public_id = int(place_row.get("public_id") or 0) if place_row else 0

        user_a, user_b = get_chat_pair_ids(int(user["id"]), int(target_user_id))
        cursor.execute(
            """
            SELECT id FROM chat_threads
            WHERE place_public_id=%s AND user_a_id=%s AND user_b_id=%s
            LIMIT 1
            """,
            (final_place_public_id, user_a, user_b)
        )
        row = cursor.fetchone()
        if row:
            chat_id = int(row["id"])
            cursor.execute(
                """
                UPDATE chat_threads
                SET updated_at=NOW(),
                    initiated_by_user_id=COALESCE(initiated_by_user_id, %s)
                WHERE id=%s
                """,
                (int(user["id"]), chat_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO chat_threads (place_public_id, user_a_id, user_b_id, initiated_by_user_id)
                VALUES (%s, %s, %s, %s)
                """,
                (final_place_public_id, user_a, user_b, int(user["id"]))
            )
            chat_id = int(cursor.lastrowid)
        conn.commit()
        return {
            "detail": "Chat listo con usuario objetivo",
            "chat_id": chat_id,
            "target_user_id": int(target_user_id),
            "place_public_id": final_place_public_id
        }
    finally:
        cursor.close()
        conn.close()


@app.get("/messages/chats")
def list_my_chats(with_user_id: Optional[int] = Query(None), user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        if with_user_id is not None:
            me = int(user["id"])
            other = int(with_user_id)
            user_a, user_b = get_chat_pair_ids(me, other)
            cursor.execute(
                """
                SELECT id, place_public_id, user_a_id, user_b_id, custom_name_a, custom_name_b,
                       initiated_by_user_id, is_blocked, blocked_by_user_id, created_at, updated_at
                FROM chat_threads
                WHERE user_a_id=%s AND user_b_id=%s
                ORDER BY updated_at DESC, id DESC
                """,
                (user_a, user_b)
            )
        else:
            cursor.execute(
                """
                SELECT id, place_public_id, user_a_id, user_b_id, custom_name_a, custom_name_b,
                       initiated_by_user_id, is_blocked, blocked_by_user_id, created_at, updated_at
                FROM chat_threads
                WHERE (user_a_id=%s OR user_b_id=%s)
                  AND (
                        EXISTS (SELECT 1 FROM chat_messages cm WHERE cm.chat_id=chat_threads.id LIMIT 1)
                        OR initiated_by_user_id=%s
                  )
                ORDER BY updated_at DESC, id DESC
                """,
                (int(user["id"]), int(user["id"]), int(user["id"]))
            )
        chats = cursor.fetchall() or []
        payload = [
            serialize_chat_thread_for_user(cursor, chat, int(user["id"]), include_last_message=True)
            for chat in chats
        ]
        return {"chats": payload}
    finally:
        cursor.close()
        conn.close()


@app.get("/messages/global")
def list_global_messages(request: Request, limit: int = Query(80, ge=1, le=300)):
    current_user = get_optional_current_user(request)
    current_user_id = int(current_user["id"]) if current_user else 0
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        cursor.execute(
            """
            SELECT gm.id, gm.sender_user_id, gm.body, gm.created_at, gm.updated_at,
                   u.username
            FROM global_chat_messages gm
            JOIN users u ON u.id = gm.sender_user_id
            ORDER BY gm.created_at DESC, gm.id DESC
            LIMIT %s
            """,
            (int(limit),)
        )
        rows = cursor.fetchall() or []
        rows.reverse()
        messages = []
        for row in rows:
            created_at = row.get("created_at")
            updated_at = row.get("updated_at")
            sender_user_id = int(row.get("sender_user_id") or 0)
            messages.append({
                "id": int(row.get("id") or 0),
                "sender_user_id": sender_user_id,
                "username": row.get("username") or f"Usuario {sender_user_id}",
                "avatar": get_user_avatar_url(sender_user_id),
                "body": row.get("body") or "",
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": updated_at.isoformat() if updated_at else None,
                "is_mine": sender_user_id == current_user_id
            })
        return {"messages": messages}
    finally:
        cursor.close()
        conn.close()


@app.post("/messages/global")
def create_global_message(data: GlobalChatMessageBody, user=Depends(get_current_user)):
    text = normalize_chat_body(data.body, max_length=1200)
    if not text:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacio")
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        cursor.execute(
            """
            INSERT INTO global_chat_messages (sender_user_id, body)
            VALUES (%s, %s)
            """,
            (int(user["id"]), text)
        )
        message_id = int(cursor.lastrowid)
        conn.commit()
        cursor.execute(
            """
            SELECT gm.id, gm.sender_user_id, gm.body, gm.created_at, gm.updated_at,
                   u.username
            FROM global_chat_messages gm
            JOIN users u ON u.id = gm.sender_user_id
            WHERE gm.id=%s
            LIMIT 1
            """,
            (message_id,)
        )
        row = cursor.fetchone() or {}
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")
        return {
            "detail": "Mensaje enviado",
            "message": {
                "id": int(row.get("id") or message_id),
                "sender_user_id": int(row.get("sender_user_id") or user["id"]),
                "username": row.get("username") or user.get("username") or "Usuario",
                "avatar": get_user_avatar_url(int(user["id"])),
                "body": row.get("body") or text,
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": updated_at.isoformat() if updated_at else None,
                "is_mine": True
            }
        }
    finally:
        cursor.close()
        conn.close()


@app.get("/messages/chats/{chat_id:int}")
def get_chat(chat_id: int, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        chat = get_chat_thread_or_404(cursor, chat_id, int(user["id"]))
        return {"chat": serialize_chat_thread_for_user(cursor, chat, int(user["id"]), include_last_message=True)}
    finally:
        cursor.close()
        conn.close()


@app.patch("/messages/chats/{chat_id:int}/rename")
def rename_chat(chat_id: int, data: ChatRenameBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        chat = get_chat_thread_or_404(cursor, chat_id, int(user["id"]))
        cleaned_name = (data.name or "").strip()
        if len(cleaned_name) > 180:
            raise HTTPException(status_code=400, detail="El nombre no puede superar 180 caracteres")
        own_name_column = "custom_name_a" if int(user["id"]) == int(chat.get("user_a_id") or 0) else "custom_name_b"
        cursor.execute(
            f"UPDATE chat_threads SET {own_name_column}=%s, updated_at=NOW() WHERE id=%s",
            (cleaned_name or None, chat_id)
        )
        conn.commit()
        return {"detail": "Nombre del chat actualizado"}
    finally:
        cursor.close()
        conn.close()


@app.patch("/messages/chats/{chat_id:int}/block")
def block_or_unblock_chat(chat_id: int, data: ChatBlockBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        _ = get_chat_thread_or_404(cursor, chat_id, int(user["id"]))
        if bool(data.blocked):
            cursor.execute(
                """
                UPDATE chat_threads
                SET is_blocked=1, blocked_by_user_id=%s, updated_at=NOW()
                WHERE id=%s
                """,
                (int(user["id"]), chat_id)
            )
            detail = "Chat bloqueado"
        else:
            cursor.execute(
                """
                UPDATE chat_threads
                SET is_blocked=0, blocked_by_user_id=NULL, updated_at=NOW()
                WHERE id=%s
                """,
                (chat_id,)
            )
            detail = "Chat desbloqueado"
        conn.commit()
        return {"detail": detail}
    finally:
        cursor.close()
        conn.close()


@app.delete("/messages/chats/{chat_id:int}")
def delete_chat_conversation(chat_id: int, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        _ = get_chat_thread_or_404(cursor, chat_id, int(user["id"]))
        cursor.execute("DELETE FROM chat_messages WHERE chat_id=%s", (chat_id,))
        cursor.execute("DELETE FROM chat_threads WHERE id=%s", (chat_id,))
        conn.commit()
        remove_chat_media_files(chat_id)
        return {"detail": "Conversación eliminada permanentemente"}
    finally:
        cursor.close()
        conn.close()


@app.get("/messages/chats/{chat_id:int}/messages")
def list_chat_messages(chat_id: int, mark_read: bool = Query(True), user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        chat = get_chat_thread_or_404(cursor, chat_id, int(user["id"]))
        if mark_read:
            cursor.execute(
                """
                UPDATE chat_messages
                SET status='read', read_at=NOW()
                WHERE chat_id=%s AND receiver_user_id=%s AND status<>'read'
                """,
                (chat_id, int(user["id"]))
            )
            conn.commit()
        cursor.execute(
            """
            SELECT id, chat_id, sender_user_id, receiver_user_id, body, media_url, status, edited, is_deleted, created_at, updated_at, read_at
            FROM chat_messages
            WHERE chat_id=%s
            ORDER BY created_at ASC, id ASC
            """,
            (chat_id,)
        )
        rows = cursor.fetchall() or []
        messages = [serialize_chat_message_row(row, int(user["id"])) for row in rows]
        return {
            "chat": serialize_chat_thread_for_user(cursor, chat, int(user["id"]), include_last_message=True),
            "messages": messages
        }
    finally:
        cursor.close()
        conn.close()


@app.post("/messages/chats/{chat_id:int}/messages")
def send_chat_message(
    chat_id: int,
    body: str = Form(""),
    file: Optional[UploadFile] = File(None),
    user=Depends(get_current_user)
):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        chat = get_chat_thread_or_404(cursor, chat_id, int(user["id"]))
        if bool(chat.get("is_blocked")):
            raise HTTPException(status_code=403, detail="Este chat está bloqueado. No puedes enviar mensajes.")
        cleaned_body = normalize_chat_body(body)
        if not cleaned_body and not file:
            raise HTTPException(status_code=400, detail="Debes escribir un mensaje o adjuntar una imagen")
        receiver_user_id = get_other_user_id_for_chat(chat, int(user["id"]))
        cursor.execute("SELECT id FROM users WHERE id=%s LIMIT 1", (receiver_user_id,))
        receiver_exists = bool(cursor.fetchone())
        message_status = "delivered" if receiver_exists else "failed"
        cursor.execute(
            """
            INSERT INTO chat_messages (chat_id, sender_user_id, receiver_user_id, body, media_url, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (chat_id, int(user["id"]), receiver_user_id, cleaned_body or None, None, message_status)
        )
        message_id = int(cursor.lastrowid)
        media_url = save_message_media(chat_id, message_id, file)
        if media_url:
            cursor.execute(
                "UPDATE chat_messages SET media_url=%s WHERE id=%s",
                (media_url, message_id)
            )
        cursor.execute("UPDATE chat_threads SET updated_at=NOW() WHERE id=%s", (chat_id,))
        conn.commit()
        cursor.execute(
            """
            SELECT id, chat_id, sender_user_id, receiver_user_id, body, media_url, status, edited, is_deleted, created_at, updated_at, read_at
            FROM chat_messages
            WHERE id=%s
            LIMIT 1
            """,
            (message_id,)
        )
        row = cursor.fetchone() or {}

        sender_name = str(user.get("username") or "Usuario")
        push_body = f"{sender_name} te ha enviado un mensaje. Clica para ver."
        push_url = f"/mensajes.html?chat={int(chat_id)}"
        try:
            send_push_notification_to_user(
                user_id=int(receiver_user_id),
                title="Nuevo mensaje",
                body=push_body,
                url=push_url,
            )
        except Exception:
            pass
        try:
            send_fcm_notification_to_user(
                user_id=int(receiver_user_id),
                title="Nuevo mensaje",
                body=push_body,
                url=push_url,
                sender_name=sender_name,
            )
        except Exception:
            pass

        return {"detail": "Mensaje enviado", "message": serialize_chat_message_row(row, int(user["id"]))}
    finally:
        cursor.close()
        conn.close()


@app.patch("/messages/chats/{chat_id:int}/messages/{message_id:int}")
def edit_chat_message(chat_id: int, message_id: int, data: ChatMessageEditBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        _ = get_chat_thread_or_404(cursor, chat_id, int(user["id"]))
        cleaned_body = normalize_chat_body(data.body)
        if not cleaned_body:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
        cursor.execute(
            """
            SELECT id, sender_user_id, is_deleted
            FROM chat_messages
            WHERE id=%s AND chat_id=%s
            LIMIT 1
            """,
            (message_id, chat_id)
        )
        msg = cursor.fetchone()
        if not msg:
            raise HTTPException(status_code=404, detail="Mensaje no encontrado")
        if int(msg.get("sender_user_id") or 0) != int(user["id"]):
            raise HTTPException(status_code=403, detail="Solo puedes editar tus mensajes")
        if bool(msg.get("is_deleted")):
            raise HTTPException(status_code=400, detail="No puedes editar un mensaje eliminado")
        cursor.execute(
            """
            UPDATE chat_messages
            SET body=%s, edited=1, updated_at=NOW()
            WHERE id=%s
            """,
            (cleaned_body, message_id)
        )
        cursor.execute("UPDATE chat_threads SET updated_at=NOW() WHERE id=%s", (chat_id,))
        conn.commit()
        return {"detail": "Mensaje editado"}
    finally:
        cursor.close()
        conn.close()


@app.delete("/messages/chats/{chat_id:int}/messages/{message_id:int}")
def delete_chat_message(chat_id: int, message_id: int, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_messages_schema(conn)
        _ = get_chat_thread_or_404(cursor, chat_id, int(user["id"]))
        cursor.execute(
            """
            SELECT id, sender_user_id, is_deleted
            FROM chat_messages
            WHERE id=%s AND chat_id=%s
            LIMIT 1
            """,
            (message_id, chat_id)
        )
        msg = cursor.fetchone()
        if not msg:
            raise HTTPException(status_code=404, detail="Mensaje no encontrado")
        if int(msg.get("sender_user_id") or 0) != int(user["id"]):
            raise HTTPException(status_code=403, detail="Solo puedes eliminar tus mensajes")
        if bool(msg.get("is_deleted")):
            return {"detail": "Mensaje ya eliminado"}
        cursor.execute(
            """
            UPDATE chat_messages
            SET is_deleted=1, deleted_at=NOW(), body=NULL, media_url=NULL, edited=0, updated_at=NOW()
            WHERE id=%s
            """,
            (message_id,)
        )
        cursor.execute("UPDATE chat_threads SET updated_at=NOW() WHERE id=%s", (chat_id,))
        conn.commit()
        remove_message_media_files(chat_id, message_id)
        return {"detail": "Mensaje eliminado"}
    finally:
        cursor.close()
        conn.close()


@app.post("/support/tickets")
async def create_support_ticket(
    request: Request,
    subject: str = Form(""),
    custom_subject: str = Form(""),
    body: str = Form(""),
    email: str = Form(""),
    place_public_id: Optional[int] = Form(None),
    files: List[UploadFile] = File([])
):
    user = get_current_user(request)
    cleaned_subject = (subject or "").strip()
    cleaned_custom_subject = (custom_subject or "").strip()
    cleaned_body = normalize_chat_body(body, max_length=6000)
    if not cleaned_subject:
        raise HTTPException(status_code=400, detail="Debes indicar un asunto")
    if cleaned_subject.lower() == "otros" and len(cleaned_custom_subject) < 3:
        raise HTTPException(status_code=400, detail="Debes explicar el asunto personalizado")
    if not cleaned_body:
        raise HTTPException(status_code=400, detail="Debes escribir el cuerpo del ticket")
    cleaned_email = (email or "").strip().lower()
    if cleaned_email and not seems_valid_email(cleaned_email):
        raise HTTPException(status_code=400, detail="El correo indicado no es válido")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        ticket_email = cleaned_email
        if not ticket_email:
            cursor.execute("SELECT email FROM users WHERE id=%s LIMIT 1", (int(user["id"]),))
            row = cursor.fetchone() or {}
            ticket_email = (row.get("email") or "").strip().lower()
        subject_is_feedback = cleaned_subject.lower() == "feedback/mejoras"
        user_visible = 0 if subject_is_feedback else 1

        cursor.execute(
            """
            INSERT INTO support_tickets (user_id, place_public_id, subject, custom_subject, body, email, attachments_json, status, user_visible)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'open', %s)
            """,
            (
                int(user["id"]),
                int(place_public_id) if place_public_id else None,
                cleaned_subject,
                cleaned_custom_subject or None,
                cleaned_body,
                ticket_email or None,
                "[]",
                user_visible
            )
        )
        ticket_id = int(cursor.lastrowid)
        attachments = []
        for idx, up_file in enumerate(files or []):
            if idx >= 8:
                break
            media_url = save_support_media(ticket_id, f"ticket{ticket_id}_a{idx+1}", up_file)
            if media_url:
                attachments.append(media_url)
        cursor.execute(
            "UPDATE support_tickets SET attachments_json=%s WHERE id=%s",
            (json.dumps(attachments), ticket_id)
        )
        conn.commit()
        return {
            "detail": "Ticket creado",
            "ticket_id": ticket_id,
            "ticket_code": make_support_ticket_code(ticket_id),
            "user_visible": bool(user_visible)
        }
    finally:
        cursor.close()
        conn.close()


@app.post("/feedback/submissions")
@app.post("/support/feedback")
async def create_feedback_submission(
    request: Request,
    subject: str = Form(""),
    body: str = Form(""),
    rating: int = Form(5)
):
    user = get_current_user(request)
    _ = normalize_space(subject)
    cleaned_body = normalize_chat_body(body, max_length=6000) or ""
    try:
        cleaned_rating = int(rating)
    except (TypeError, ValueError):
        cleaned_rating = 0
    if cleaned_rating < 1 or cleaned_rating > 5:
        raise HTTPException(status_code=400, detail="Debes indicar una valoración entre 1 y 5")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_feedback_schema(conn)
        submission_user_id = int(user["id"])
        cursor.execute("SELECT email FROM users WHERE id=%s LIMIT 1", (submission_user_id,))
        row = cursor.fetchone() or {}
        cleaned_email = (row.get("email") or "").strip().lower()
        if not cleaned_email or not seems_valid_email(cleaned_email):
            raise HTTPException(status_code=400, detail="Tu cuenta no tiene un correo válido para enviar valoraciones")

        cursor.execute(
            """
            INSERT INTO feedback_submissions (user_id, email, rating, subject, body, status)
            VALUES (%s, %s, %s, %s, %s, 'open')
            """,
            (
                submission_user_id,
                cleaned_email,
                cleaned_rating,
                "",
                cleaned_body,
            )
        )
        feedback_id = int(cursor.lastrowid)
        conn.commit()
        return {
            "detail": "Mejora enviada",
            "feedback_id": feedback_id
        }
    finally:
        cursor.close()
        conn.close()


@app.get("/support/tickets/my")
def list_my_support_tickets(user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            """
            SELECT id, user_id, place_public_id, subject, custom_subject, body, email, attachments_json, status,
                   user_visible, user_blocked, user_deleted, custom_name_user, first_admin_response_at, created_at, updated_at, closed_at
            FROM support_tickets
            WHERE user_id=%s AND user_visible=1 AND user_deleted=0
            ORDER BY updated_at DESC, id DESC
            """,
            (int(user["id"]),)
        )
        rows = cursor.fetchall() or []
        tickets = []
        for row in rows:
            ticket_id = int(row.get("id") or 0)
            cursor.execute(
                """
                SELECT id, ticket_id, sender_type, sender_user_id, body, attachments_json, created_at
                FROM support_ticket_messages
                WHERE ticket_id=%s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (ticket_id,)
            )
            last_row = cursor.fetchone()
            tickets.append({
                "id": ticket_id,
                "ticket_code": make_support_ticket_code(ticket_id),
                "subject": row.get("subject") or "",
                "custom_subject": row.get("custom_subject") or "",
                "custom_name": row.get("custom_name_user") or "",
                "body": row.get("body") or "",
                "email": row.get("email") or "",
                "status": row.get("status") or "open",
                "attachments": decode_json_list(row.get("attachments_json")),
                "user_visible": bool(row.get("user_visible")),
                "user_blocked": bool(row.get("user_blocked")),
                "place_public_id": int(row.get("place_public_id")) if row.get("place_public_id") is not None else None,
                "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
                "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
                "closed_at": row.get("closed_at").isoformat() if row.get("closed_at") else None,
                "first_admin_response_at": row.get("first_admin_response_at").isoformat() if row.get("first_admin_response_at") else None,
                "last_message": serialize_support_message_row(last_row, int(user["id"])) if last_row else None
            })
        return {"tickets": tickets}
    finally:
        cursor.close()
        conn.close()


@app.get("/support/tickets/{ticket_id:int}")
def get_my_support_ticket(ticket_id: int, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            """
            SELECT id, user_id, place_public_id, subject, custom_subject, body, email, attachments_json, status,
                   user_visible, user_blocked, user_deleted, custom_name_user, first_admin_response_at, created_at, updated_at, closed_at
            FROM support_tickets
            WHERE id=%s AND user_id=%s
            LIMIT 1
            """,
            (int(ticket_id), int(user["id"]))
        )
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        if not bool(ticket.get("user_visible")) or bool(ticket.get("user_deleted")):
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        cursor.execute(
            """
            SELECT id, ticket_id, sender_type, sender_user_id, body, attachments_json, created_at
            FROM support_ticket_messages
            WHERE ticket_id=%s
            ORDER BY created_at ASC, id ASC
            """,
            (int(ticket_id),)
        )
        rows = cursor.fetchall() or []
        return {
            "ticket": {
                "id": int(ticket["id"]),
                "ticket_code": make_support_ticket_code(int(ticket["id"])),
                "subject": ticket.get("subject") or "",
                "custom_subject": ticket.get("custom_subject") or "",
                "custom_name": ticket.get("custom_name_user") or "",
                "body": ticket.get("body") or "",
                "email": ticket.get("email") or "",
                "status": ticket.get("status") or "open",
                "attachments": decode_json_list(ticket.get("attachments_json")),
                "user_visible": bool(ticket.get("user_visible")),
                "user_blocked": bool(ticket.get("user_blocked")),
                "place_public_id": int(ticket.get("place_public_id")) if ticket.get("place_public_id") is not None else None,
                "created_at": ticket.get("created_at").isoformat() if ticket.get("created_at") else None,
                "updated_at": ticket.get("updated_at").isoformat() if ticket.get("updated_at") else None,
                "closed_at": ticket.get("closed_at").isoformat() if ticket.get("closed_at") else None,
                "first_admin_response_at": ticket.get("first_admin_response_at").isoformat() if ticket.get("first_admin_response_at") else None
            },
            "messages": [serialize_support_message_row(row, int(user["id"])) for row in rows]
        }
    finally:
        cursor.close()
        conn.close()


@app.post("/support/tickets/{ticket_id:int}/messages")
async def post_my_support_ticket_message(
    ticket_id: int,
    request: Request,
    body: str = Form(""),
    files: List[UploadFile] = File([])
):
    user = get_current_user(request)
    cleaned_body = normalize_chat_body(body, max_length=4000)
    if not cleaned_body and not files:
        raise HTTPException(status_code=400, detail="Debes escribir un mensaje o adjuntar una imagen")
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            "SELECT id, user_id, status, user_visible, user_blocked, user_deleted FROM support_tickets WHERE id=%s LIMIT 1",
            (int(ticket_id),)
        )
        ticket = cursor.fetchone()
        if not ticket or int(ticket.get("user_id") or 0) != int(user["id"]):
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        if not bool(ticket.get("user_visible")) or bool(ticket.get("user_deleted")):
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        if bool(ticket.get("user_blocked")):
            raise HTTPException(status_code=403, detail="Este ticket está bloqueado. No puedes enviar mensajes.")
        if (ticket.get("status") or "open") != "open":
            raise HTTPException(status_code=400, detail="El ticket está cerrado")

        attachments = []
        for idx, up_file in enumerate(files or []):
            if idx >= 8:
                break
            media_url = save_support_media(ticket_id, f"msg_u_{secrets.token_hex(3)}_{idx+1}", up_file)
            if media_url:
                attachments.append(media_url)

        cursor.execute(
            """
            INSERT INTO support_ticket_messages (ticket_id, sender_type, sender_user_id, body, attachments_json)
            VALUES (%s, 'user', %s, %s, %s)
            """,
            (int(ticket_id), int(user["id"]), cleaned_body or None, json.dumps(attachments))
        )
        message_id = int(cursor.lastrowid)
        cursor.execute("UPDATE support_tickets SET updated_at=NOW() WHERE id=%s", (int(ticket_id),))
        conn.commit()

        cursor.execute(
            """
            SELECT id, ticket_id, sender_type, sender_user_id, body, attachments_json, created_at
            FROM support_ticket_messages
            WHERE id=%s
            LIMIT 1
            """,
            (message_id,)
        )
        row = cursor.fetchone() or {}
        return {"detail": "Mensaje enviado", "message": serialize_support_message_row(row, int(user["id"]))}
    finally:
        cursor.close()
        conn.close()


@app.patch("/support/tickets/{ticket_id:int}/rename")
def rename_support_ticket(ticket_id: int, data: ChatRenameBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            "SELECT id, user_id, user_visible, user_deleted FROM support_tickets WHERE id=%s LIMIT 1",
            (int(ticket_id),)
        )
        ticket = cursor.fetchone()
        if not ticket or int(ticket.get("user_id") or 0) != int(user["id"]):
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        if not bool(ticket.get("user_visible")) or bool(ticket.get("user_deleted")):
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        cleaned_name = (data.name or "").strip()
        if len(cleaned_name) > 180:
            raise HTTPException(status_code=400, detail="El nombre no puede superar 180 caracteres")
        cursor.execute(
            "UPDATE support_tickets SET custom_name_user=%s, updated_at=NOW() WHERE id=%s",
            (cleaned_name or None, int(ticket_id))
        )
        conn.commit()
        return {"detail": "Nombre del ticket actualizado"}
    finally:
        cursor.close()
        conn.close()


@app.patch("/support/tickets/{ticket_id:int}/block")
def block_or_unblock_support_ticket(ticket_id: int, data: ChatBlockBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            "SELECT id, user_id, user_visible, user_deleted FROM support_tickets WHERE id=%s LIMIT 1",
            (int(ticket_id),)
        )
        ticket = cursor.fetchone()
        if not ticket or int(ticket.get("user_id") or 0) != int(user["id"]):
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        if not bool(ticket.get("user_visible")) or bool(ticket.get("user_deleted")):
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        cursor.execute(
            "UPDATE support_tickets SET user_blocked=%s, updated_at=NOW() WHERE id=%s",
            (1 if bool(data.blocked) else 0, int(ticket_id))
        )
        conn.commit()
        return {"detail": "Ticket bloqueado" if bool(data.blocked) else "Ticket desbloqueado"}
    finally:
        cursor.close()
        conn.close()


@app.delete("/support/tickets/{ticket_id:int}")
def delete_support_ticket_for_user(ticket_id: int, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            "SELECT id, user_id, user_visible, user_deleted FROM support_tickets WHERE id=%s LIMIT 1",
            (int(ticket_id),)
        )
        ticket = cursor.fetchone()
        if not ticket or int(ticket.get("user_id") or 0) != int(user["id"]):
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        if not bool(ticket.get("user_visible")) or bool(ticket.get("user_deleted")):
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        cursor.execute(
            "UPDATE support_tickets SET user_deleted=1, updated_at=NOW() WHERE id=%s",
            (int(ticket_id),)
        )
        conn.commit()
        return {"detail": "Ticket eliminado de tu bandeja"}
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/support/tickets")
def admin_list_support_tickets(
    status: str = Query("open"),
    subject: Optional[str] = Query(None),
    admin=Depends(get_admin_session)
):
    normalized_status = (status or "open").strip().lower()
    subject_filter = (subject or "").strip()
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        where_parts = []
        params: List = []
        if normalized_status in {"open", "closed"}:
            where_parts.append("t.status=%s")
            params.append(normalized_status)
        if subject_filter:
            where_parts.append("(t.subject LIKE %s OR COALESCE(t.custom_subject, '') LIKE %s)")
            like = f"%{subject_filter}%"
            params.extend([like, like])
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        cursor.execute(
            f"""
            SELECT t.id, t.user_id, t.place_public_id, t.subject, t.custom_subject, t.body, t.email, t.attachments_json,
                   t.status, t.user_visible, t.first_admin_response_at, t.created_at, t.updated_at, t.closed_at,
                   u.username, u.email AS account_email
            FROM support_tickets t
            LEFT JOIN users u ON u.id=t.user_id
            {where_sql}
            ORDER BY t.updated_at DESC, t.id DESC
            """,
            tuple(params)
        )
        rows = cursor.fetchall() or []
        payload = []
        for row in rows:
            ticket_id = int(row.get("id") or 0)
            cursor.execute(
                """
                SELECT id, ticket_id, sender_type, sender_user_id, body, attachments_json, created_at
                FROM support_ticket_messages
                WHERE ticket_id=%s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (ticket_id,)
            )
            last_row = cursor.fetchone()
            payload.append({
                "id": ticket_id,
                "ticket_code": make_support_ticket_code(ticket_id),
                "user_id": int(row["user_id"]) if row.get("user_id") is not None else None,
                "username": row.get("username") or "Visitante",
                "subject": row.get("subject") or "",
                "custom_subject": row.get("custom_subject") or "",
                "body": row.get("body") or "",
                "email": row.get("email") or "",
                "destination_email": (row.get("email") or row.get("account_email") or ""),
                "status": row.get("status") or "open",
                "attachments": decode_json_list(row.get("attachments_json")),
                "user_visible": bool(row.get("user_visible")),
                "place_public_id": int(row.get("place_public_id")) if row.get("place_public_id") is not None else None,
                "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
                "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
                "closed_at": row.get("closed_at").isoformat() if row.get("closed_at") else None,
                "first_admin_response_at": row.get("first_admin_response_at").isoformat() if row.get("first_admin_response_at") else None,
                "open_duration_seconds": (
                    max(0, int((row.get("closed_at") - row.get("created_at")).total_seconds()))
                    if row.get("closed_at") and row.get("created_at") else None
                ),
                "last_message": serialize_support_message_row(last_row, 0, is_admin=True) if last_row else None
            })
        return {"tickets": payload}
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/feedback")
def admin_list_feedback(
    status: str = Query("open"),
    q: str = Query(""),
    admin=Depends(get_admin_session)
):
    normalized_status = (status or "open").strip().lower()
    search_query = normalize_space(q).lower()
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_feedback_schema(conn)
        where_parts = []
        params: List[Any] = []
        if normalized_status in {"open", "closed"}:
            where_parts.append("f.status=%s")
            params.append(normalized_status)
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        cursor.execute(
            f"""
            SELECT f.id, f.user_id, f.email, f.rating, f.subject, f.body, f.status, f.created_at, f.updated_at, f.last_admin_contact_at,
                   u.username, u.email AS account_email
            FROM feedback_submissions f
            LEFT JOIN users u ON u.id=f.user_id
            {where_sql}
            ORDER BY f.updated_at DESC, f.id DESC
            LIMIT 600
            """,
            tuple(params)
        )
        rows = cursor.fetchall() or []
        payload = []
        for row in rows:
            item = {
                "id": int(row.get("id") or 0),
                "user_id": int(row["user_id"]) if row.get("user_id") is not None else None,
                "username": row.get("username") or "Visitante",
                "email": row.get("email") or "",
                "destination_email": (row.get("email") or row.get("account_email") or ""),
                "rating": int(row.get("rating") or 0),
                "subject": row.get("subject") or "",
                "body": row.get("body") or "",
                "status": row.get("status") or "open",
                "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
                "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
                "last_admin_contact_at": row.get("last_admin_contact_at").isoformat() if row.get("last_admin_contact_at") else None,
            }
            if search_query:
                haystack = " ".join([
                    str(item.get("username") or "").lower(),
                    str(item.get("destination_email") or "").lower(),
                    str(item.get("subject") or "").lower(),
                    str(item.get("body") or "").lower(),
                ])
                if search_query not in haystack:
                    continue
            payload.append(item)
        return JSONResponse(
            content={"feedback": payload},
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    finally:
        cursor.close()
        conn.close()


@app.patch("/admin/feedback/{feedback_id:int}/status")
def admin_update_feedback_status(feedback_id: int, data: SupportTicketCloseBody, admin=Depends(get_admin_session)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_feedback_schema(conn)
        cursor.execute("SELECT id FROM feedback_submissions WHERE id=%s LIMIT 1", (int(feedback_id),))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Mejora no encontrada")
        next_status = "closed" if bool(data.close) else "open"
        cursor.execute(
            "UPDATE feedback_submissions SET status=%s, updated_at=NOW() WHERE id=%s",
            (next_status, int(feedback_id))
        )
        conn.commit()
        return {"detail": "Estado actualizado", "status": next_status}
    finally:
        cursor.close()
        conn.close()


@app.post("/admin/feedback/{feedback_id:int}/report-change")
def admin_report_feedback_change(feedback_id: int, admin=Depends(get_admin_session)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_feedback_schema(conn)
        cursor.execute(
            """
            SELECT f.id, f.email, u.email AS account_email
            FROM feedback_submissions f
            LEFT JOIN users u ON u.id=f.user_id
            WHERE f.id=%s
            LIMIT 1
            """,
            (int(feedback_id),)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Mejora no encontrada")
        dest_email = (row.get("email") or row.get("account_email") or "").strip().lower()
        if not dest_email or not seems_valid_email(dest_email):
            raise HTTPException(status_code=400, detail="Esta mejora no tiene un correo válido para notificar")

        mail_subject = "Actualización de tu valoración"
        mail_body = "Hemos aplicado cambios gracias a tu valoración. Gracias."
        send_notification_email(dest_email, mail_subject, mail_body)

        cursor.execute(
            """
            UPDATE feedback_submissions
            SET last_admin_contact_at=NOW(), updated_at=NOW()
            WHERE id=%s
            """,
            (int(feedback_id),)
        )
        conn.commit()
        return {"detail": "Correo de notificación enviado", "email": dest_email}
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/feedback/{feedback_id:int}/conversation")
def admin_feedback_conversation(feedback_id: int, admin=Depends(get_admin_session)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_feedback_schema(conn)
        cursor.execute(
            """
            SELECT f.id, f.user_id, f.email, f.subject, f.body, f.status, f.created_at, f.updated_at, f.last_admin_contact_at,
                   u.username
            FROM feedback_submissions f
            LEFT JOIN users u ON u.id=f.user_id
            WHERE f.id=%s
            LIMIT 1
            """,
            (int(feedback_id),)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Mejora no encontrada")

        created_at = row.get("created_at")
        messages = [{
            "id": f"seed-{int(feedback_id)}",
            "sender_type": "user",
            "sender_label": (row.get("username") or "Usuario"),
            "body": row.get("body") or "",
            "created_at": created_at.isoformat() if created_at else None,
            "is_mine": False,
            "source": "submission",
        }]

        cursor.execute(
            """
            SELECT id, sender_type, body, email_message_id, created_at
            FROM feedback_messages
            WHERE feedback_id=%s
            ORDER BY created_at ASC, id ASC
            LIMIT 600
            """,
            (int(feedback_id),)
        )
        local_rows = cursor.fetchall() or []
        local_email_ids = set()
        for item in local_rows:
            email_message_id = (item.get("email_message_id") or "").strip()
            if email_message_id:
                local_email_ids.add(email_message_id)
            sender_type = item.get("sender_type") or "admin"
            is_admin = sender_type == "admin"
            dt = item.get("created_at")
            messages.append({
                "id": int(item.get("id") or 0),
                "sender_type": sender_type,
                "sender_label": "Administración" if is_admin else (row.get("username") or "Usuario"),
                "body": item.get("body") or "",
                "created_at": dt.isoformat() if dt else None,
                "is_mine": bool(is_admin),
                "source": "db",
            })

        email = (row.get("email") or "").strip().lower()
        email_rows = fetch_feedback_email_replies(int(feedback_id), email, limit=120)
        for item in email_rows:
            msg_id = (item.get("email_message_id") or "").strip()
            if msg_id and msg_id in local_email_ids:
                continue
            messages.append({
                "id": f"mail-{msg_id or secrets.token_hex(4)}",
                "sender_type": "user_email",
                "sender_label": row.get("username") or "Usuario",
                "body": item.get("body") or "",
                "created_at": item.get("created_at"),
                "is_mine": False,
                "source": "email",
            })

        def sort_key(m: dict):
            raw = m.get("created_at")
            if not raw:
                return datetime.min.replace(tzinfo=timezone.utc)
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except Exception:
                return datetime.min.replace(tzinfo=timezone.utc)

        messages.sort(key=sort_key)
        return {
            "feedback": {
                "id": int(row.get("id") or 0),
                "user_id": int(row["user_id"]) if row.get("user_id") is not None else None,
                "username": row.get("username") or "Visitante",
                "email": row.get("email") or "",
                "subject": row.get("subject") or "",
                "status": row.get("status") or "open",
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
                "last_admin_contact_at": row.get("last_admin_contact_at").isoformat() if row.get("last_admin_contact_at") else None,
            },
            "messages": messages
        }
    finally:
        cursor.close()
        conn.close()


@app.post("/admin/feedback/{feedback_id:int}/conversation/messages")
def admin_feedback_send_message(feedback_id: int, data: AdminUserMessageBody, admin=Depends(get_admin_session)):
    cleaned_body = normalize_chat_body((data.message or ""), max_length=6000)
    if not cleaned_body:
        raise HTTPException(status_code=400, detail="Debes escribir un mensaje")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_feedback_schema(conn)
        cursor.execute(
            "SELECT id, email, subject FROM feedback_submissions WHERE id=%s LIMIT 1",
            (int(feedback_id),)
        )
        feedback = cursor.fetchone()
        if not feedback:
            raise HTTPException(status_code=404, detail="Mejora no encontrada")
        dest_email = (feedback.get("email") or "").strip().lower()
        if not dest_email or not seems_valid_email(dest_email):
            raise HTTPException(status_code=400, detail="La mejora no tiene un correo válido para responder")

        tagged_subject = f"{feedback_thread_tag(int(feedback_id))} {feedback.get('subject') or 'Mejora'}".strip()
        msg = MIMEText(cleaned_body, _subtype="plain", _charset="utf-8")
        msg["Subject"] = str(Header(tagged_subject, "utf-8"))
        msg["From"] = ADMIN_MAIL_FROM or EMAIL_SENDER
        msg["To"] = dest_email
        out_message_id = make_msgid(domain="todosevillaeste.es")
        msg["Message-ID"] = out_message_id

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=25) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(ADMIN_MAIL_LOGIN or EMAIL_SENDER, ADMIN_MAIL_PASSWORD or EMAIL_PASSWORD)
            server.send_message(msg)

        cursor.execute(
            """
            INSERT INTO feedback_messages (feedback_id, sender_type, body, email_message_id)
            VALUES (%s, 'admin', %s, %s)
            """,
            (int(feedback_id), cleaned_body, out_message_id)
        )
        cursor.execute(
            """
            UPDATE feedback_submissions
            SET last_admin_contact_at=NOW(), updated_at=NOW(), status='open'
            WHERE id=%s
            """,
            (int(feedback_id),)
        )
        conn.commit()
        return {"detail": "Mensaje enviado", "email": dest_email}
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/support/tickets/{ticket_id:int}")
def admin_get_support_ticket(ticket_id: int, admin=Depends(get_admin_session)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            """
            SELECT t.id, t.user_id, t.place_public_id, t.subject, t.custom_subject, t.body, t.email, t.attachments_json,
                   t.status, t.user_visible, t.first_admin_response_at, t.created_at, t.updated_at, t.closed_at,
                   u.username, u.email AS account_email
            FROM support_tickets t
            LEFT JOIN users u ON u.id=t.user_id
            WHERE t.id=%s
            LIMIT 1
            """,
            (int(ticket_id),)
        )
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        cursor.execute(
            """
            SELECT id, ticket_id, sender_type, sender_user_id, body, attachments_json, created_at
            FROM support_ticket_messages
            WHERE ticket_id=%s
            ORDER BY created_at ASC, id ASC
            """,
            (int(ticket_id),)
        )
        rows = cursor.fetchall() or []
        return {
            "ticket": {
                "id": int(ticket["id"]),
                "ticket_code": make_support_ticket_code(int(ticket["id"])),
                "user_id": int(ticket["user_id"]) if ticket.get("user_id") is not None else None,
                "username": ticket.get("username") or "Visitante",
                "subject": ticket.get("subject") or "",
                "custom_subject": ticket.get("custom_subject") or "",
                "body": ticket.get("body") or "",
                "email": ticket.get("email") or "",
                "destination_email": (ticket.get("email") or ticket.get("account_email") or ""),
                "status": ticket.get("status") or "open",
                "attachments": decode_json_list(ticket.get("attachments_json")),
                "user_visible": bool(ticket.get("user_visible")),
                "place_public_id": int(ticket.get("place_public_id")) if ticket.get("place_public_id") is not None else None,
                "created_at": ticket.get("created_at").isoformat() if ticket.get("created_at") else None,
                "updated_at": ticket.get("updated_at").isoformat() if ticket.get("updated_at") else None,
                "closed_at": ticket.get("closed_at").isoformat() if ticket.get("closed_at") else None,
                "first_admin_response_at": ticket.get("first_admin_response_at").isoformat() if ticket.get("first_admin_response_at") else None,
                "open_duration_seconds": (
                    max(0, int((ticket.get("closed_at") - ticket.get("created_at")).total_seconds()))
                    if ticket.get("closed_at") and ticket.get("created_at") else None
                )
            },
            "messages": [serialize_support_message_row(row, 0, is_admin=True) for row in rows]
        }
    finally:
        cursor.close()
        conn.close()


@app.post("/admin/support/tickets/{ticket_id:int}/messages")
async def admin_send_support_ticket_message(
    ticket_id: int,
    body: str = Form(""),
    files: List[UploadFile] = File([]),
    admin=Depends(get_admin_session)
):
    cleaned_body = normalize_chat_body(body, max_length=4000)
    if not cleaned_body and not files:
        raise HTTPException(status_code=400, detail="Debes escribir un mensaje o adjuntar una imagen")
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute("SELECT id, status FROM support_tickets WHERE id=%s LIMIT 1", (int(ticket_id),))
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        if (ticket.get("status") or "open") != "open":
            raise HTTPException(status_code=400, detail="El ticket está cerrado")

        attachments = []
        for idx, up_file in enumerate(files or []):
            if idx >= 8:
                break
            media_url = save_support_media(ticket_id, f"msg_a_{secrets.token_hex(3)}_{idx+1}", up_file)
            if media_url:
                attachments.append(media_url)

        cursor.execute(
            """
            INSERT INTO support_ticket_messages (ticket_id, sender_type, sender_user_id, body, attachments_json)
            VALUES (%s, 'admin', NULL, %s, %s)
            """,
            (int(ticket_id), cleaned_body or None, json.dumps(attachments))
        )
        message_id = int(cursor.lastrowid)
        cursor.execute(
            """
            UPDATE support_tickets
            SET updated_at=NOW(),
                user_visible=1,
                first_admin_response_at=COALESCE(first_admin_response_at, NOW())
            WHERE id=%s
            """,
            (int(ticket_id),)
        )
        conn.commit()
        cursor.execute(
            """
            SELECT id, ticket_id, sender_type, sender_user_id, body, attachments_json, created_at
            FROM support_ticket_messages
            WHERE id=%s
            LIMIT 1
            """,
            (message_id,)
        )
        row = cursor.fetchone() or {}
        return {"detail": "Mensaje enviado", "message": serialize_support_message_row(row, 0, is_admin=True)}
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/support/metrics")
def admin_support_metrics(admin=Depends(get_admin_session)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_tickets,
                SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS open_tickets,
                SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) AS closed_tickets,
                AVG(CASE WHEN closed_at IS NOT NULL THEN TIMESTAMPDIFF(SECOND, created_at, closed_at) END) AS avg_open_seconds,
                AVG(CASE WHEN first_admin_response_at IS NOT NULL THEN TIMESTAMPDIFF(SECOND, created_at, first_admin_response_at) END) AS avg_wait_seconds
            FROM support_tickets
            """
        )
        row = cursor.fetchone() or {}
        return {
            "total_tickets": int(row.get("total_tickets") or 0),
            "open_tickets": int(row.get("open_tickets") or 0),
            "closed_tickets": int(row.get("closed_tickets") or 0),
            "avg_open_seconds": int(float(row.get("avg_open_seconds") or 0)),
            "avg_wait_seconds": int(float(row.get("avg_wait_seconds") or 0))
        }
    finally:
        cursor.close()
        conn.close()


@app.post("/admin/support/tickets/{ticket_id:int}/close")
def admin_close_or_open_support_ticket(ticket_id: int, data: SupportTicketCloseBody, request: Request, admin=Depends(get_admin_session)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            """
            SELECT t.id, t.user_id, t.subject, t.custom_subject, t.email, u.email AS account_email, t.created_at
            FROM support_tickets t
            LEFT JOIN users u ON u.id=t.user_id
            WHERE t.id=%s
            LIMIT 1
            """,
            (int(ticket_id),)
        )
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        if bool(data.close):
            cursor.execute(
                """
                UPDATE support_tickets
                SET status='closed', closed_at=NOW(), closed_by_admin_username=%s, updated_at=NOW()
                WHERE id=%s
                """,
                ((admin or {}).get("username") or "admin", int(ticket_id))
            )
            detail = "Ticket cerrado"
            closed_dt = datetime.now(SEVILLA_TZ)
            final_subject = (ticket.get("subject") or "").strip()
            final_custom = (ticket.get("custom_subject") or "").strip()
            if final_custom:
                final_subject = f"{final_subject} - {final_custom}"
            dest_email = (ticket.get("email") or ticket.get("account_email") or "").strip().lower()
            if dest_email and seems_valid_email(dest_email):
                ticket_code = make_support_ticket_code(int(ticket_id))
                closed_hm = closed_dt.strftime("%H:%M")
                messages_url = f"{str(request.base_url).rstrip('/')}/mensajes.html?support_ticket={int(ticket_id)}"
                mail_subject = f"Ticket#{ticket_code} cerrado"
                plain = (
                    f"Ticket#{ticket_code} sobre {final_subject}, ha sido cerrado a las {closed_hm}. "
                    f"Puede ver el registro del ticket aquí: {messages_url}"
                )
                html = (
                    f"<p>Ticket#{ticket_code} sobre {final_subject}, ha sido cerrado a las {closed_hm}.</p>"
                    f"<p>Puede ver el registro del ticket <a href=\"{messages_url}\">aquí</a>.</p>"
                    f"<p><small>Para acceder al chat debes iniciar sesión con tu cuenta.</small></p>"
                )
                try:
                    send_notification_email_html(dest_email, mail_subject, plain, html)
                except Exception:
                    logger.exception("No se pudo enviar correo de cierre de ticket %s", ticket_id)
        else:
            cursor.execute(
                """
                UPDATE support_tickets
                SET status='open', closed_at=NULL, closed_by_admin_username=NULL, updated_at=NOW()
                WHERE id=%s
                """,
                (int(ticket_id),)
            )
            detail = "Ticket reabierto"
        conn.commit()
        return {"detail": detail}
    finally:
        cursor.close()
        conn.close()


@app.post("/admin/support/tickets/{ticket_id:int}/email")
async def admin_send_support_ticket_email(
    ticket_id: int,
    subject: str = Form(""),
    body: str = Form(""),
    files: List[UploadFile] = File([]),
    admin=Depends(get_admin_session)
):
    cleaned_subject = (subject or "").strip()
    cleaned_body = (body or "").strip()
    if not cleaned_subject:
        raise HTTPException(status_code=400, detail="Asunto obligatorio")
    if not cleaned_body:
        raise HTTPException(status_code=400, detail="Cuerpo obligatorio")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_support_schema(conn)
        cursor.execute(
            """
            SELECT t.id, t.email, u.email AS account_email
            FROM support_tickets t
            LEFT JOIN users u ON u.id=t.user_id
            WHERE t.id=%s
            LIMIT 1
            """,
            (int(ticket_id),)
        )
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        target_email = (ticket.get("email") or ticket.get("account_email") or "").strip().lower()
        if not target_email or not seems_valid_email(target_email):
            raise HTTPException(status_code=400, detail="El ticket no tiene un correo válido para enviar")

        temp_files: List[Path] = []
        for idx, up_file in enumerate(files or []):
            if idx >= 8:
                break
            media_url = save_support_media(ticket_id, f"email_{secrets.token_hex(3)}_{idx+1}", up_file)
            if not media_url:
                continue
            maybe_path = support_media_url_to_path(ticket_id, media_url)
            if maybe_path:
                temp_files.append(maybe_path)

        send_notification_email_with_attachments(target_email, cleaned_subject, cleaned_body, temp_files)

        cursor.execute(
            """
            INSERT INTO support_ticket_messages (ticket_id, sender_type, sender_user_id, body, attachments_json)
            VALUES (%s, 'admin', NULL, %s, %s)
            """,
            (
                int(ticket_id),
                f"[Correo enviado a {target_email}] {cleaned_subject}\n\n{cleaned_body}",
                json.dumps([f"/web/img/support/{ticket_id}/{p.name}" for p in temp_files])
            )
        )
        cursor.execute("UPDATE support_tickets SET updated_at=NOW() WHERE id=%s", (int(ticket_id),))
        conn.commit()
        return {"detail": f"Correo enviado a {target_email}"}
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/mail/resolve")
def admin_mail_resolve_recipient(
    query: str = Query(""),
    limit: int = Query(8, ge=1, le=25),
    admin=Depends(get_admin_session)
):
    cleaned = normalize_space(query).strip()
    if len(cleaned) < 2:
        return {"matches": []}
    normalized_email = cleaned.lower()

    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        rows: List[Dict[str, Any]] = []
        cursor.execute(
            """
            SELECT id, username, email
            FROM users
            WHERE email=%s OR username=%s
            ORDER BY id DESC
            LIMIT %s
            """,
            (normalized_email, cleaned, int(limit))
        )
        exact_rows = cursor.fetchall() or []
        rows.extend(exact_rows)

        if len(rows) < int(limit):
            remaining = int(limit) - len(rows)
            like_term = f"%{cleaned}%"
            existing_ids = {int(r.get("id") or 0) for r in rows}
            cursor.execute(
                """
                SELECT id, username, email
                FROM users
                WHERE username LIKE %s OR email LIKE %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (like_term, like_term, remaining * 2)
            )
            for row in cursor.fetchall() or []:
                row_id = int(row.get("id") or 0)
                if row_id in existing_ids:
                    continue
                rows.append(row)
                existing_ids.add(row_id)
                if len(rows) >= int(limit):
                    break

        payload = []
        for row in rows:
            payload.append({
                "user_id": int(row.get("id") or 0),
                "username": row.get("username") or "",
                "email": row.get("email") or ""
            })
        return {"matches": payload}
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/mail/folders")
def admin_mail_folders(admin=Depends(get_admin_session)):
    if gmail_api_enabled():
        return {
            "folders": ["INBOX", "SENT", "TRASH"],
            "aliases": {
                "inbox": "INBOX",
                "sent": "SENT",
                "trash": "TRASH",
            },
            "provider": "gmail_api",
        }
    available = list_admin_imap_mailboxes()
    return {
        "folders": available,
        "aliases": {
            "inbox": resolve_admin_imap_mailbox("inbox"),
            "sent": resolve_admin_imap_mailbox("sent"),
            "trash": resolve_admin_imap_mailbox("trash"),
        },
        "provider": "imap",
    }


@app.get("/admin/mail/inbox")
def admin_mail_inbox(
    limit: int = Query(35, ge=1, le=100),
    query: str = Query(""),
    folder: str = Query("inbox"),
    unread_only: bool = Query(False),
    starred_only: bool = Query(False),
    admin=Depends(get_admin_session)
):
    if gmail_api_enabled():
        mailbox_label = _gmail_folder_label(folder)
        query_clean = normalize_space(query)
        q_parts: List[str] = []
        if query_clean:
            q_parts.append(query_clean)
        if bool(unread_only):
            q_parts.append("is:unread")
        if bool(starred_only):
            q_parts.append("is:starred")
        gmail_query = " ".join(q_parts).strip()
        list_params: Dict[str, Any] = {
            "maxResults": int(limit),
            "labelIds": [mailbox_label],
        }
        if gmail_query:
            list_params["q"] = gmail_query
        listed = _gmail_api_request("GET", "/messages", query=list_params)
        message_refs = listed.get("messages") or []
        picks: List[dict] = []
        for ref in message_refs:
            msg_id = str((ref or {}).get("id") or "").strip()
            if not msg_id:
                continue
            msg = _gmail_api_request(
                "GET",
                f"/messages/{msg_id}",
                query={
                    "format": "metadata",
                    "metadataHeaders": ["Subject", "From", "To", "Cc", "Date", "Message-ID", "References", "In-Reply-To"],
                },
            )
            row = _gmail_message_to_payload(msg, include_body=False)
            picks.append({
                "uid": row["uid"],
                "subject": row["subject"],
                "from": row["from"],
                "from_name": row["from_name"],
                "from_email": row["from_email"],
                "to": row.get("to") or "",
                "cc": row.get("cc") or "",
                "snippet": row["snippet"],
                "date": row["date"],
                "is_unread": bool(row["is_unread"]),
                "is_starred": bool(row.get("is_starred")),
                "message_id": row["message_id"],
                "references": row["references"],
                "in_reply_to": row["in_reply_to"],
            })
        unread_count_resp = _gmail_api_request(
            "GET",
            "/messages",
            query={"maxResults": 1, "labelIds": [mailbox_label], "q": "is:unread"},
        )
        unread_count = int(unread_count_resp.get("resultSizeEstimate") or 0)
        return {
            "messages": picks,
            "unread_count": unread_count,
            "folder": mailbox_label,
            "requested_folder": _gmail_folder_alias(folder),
            "provider": "gmail_api",
        }

    mailbox = open_admin_imap_inbox(folder)
    try:
        status_unseen, unseen_data = mailbox.uid("search", None, "UNSEEN")
        unread_count = 0
        if status_unseen == "OK" and unseen_data and unseen_data[0]:
            unread_count = len([x for x in unseen_data[0].split() if x])

        status, data = mailbox.uid("search", None, "ALL")
        if status != "OK":
            raise HTTPException(status_code=500, detail="No se pudo leer la bandeja de entrada")
        raw_uids = [x.decode("utf-8", errors="ignore") for x in (data[0].split() if data and data[0] else [])]
        query_clean = normalize_space(query).lower()
        picks = []
        scan_limit = min(max(int(limit) * 4, 40), 350)
        candidate_uids = raw_uids[-scan_limit:]
        for uid in reversed(candidate_uids):
            fetch_status, fetched = mailbox.uid("fetch", uid, "(RFC822 FLAGS)")
            if fetch_status != "OK" or not fetched:
                continue
            raw_message = b""
            flag_blob = b""
            for item in fetched:
                if not isinstance(item, tuple) or len(item) < 2:
                    continue
                flag_blob = item[0] if isinstance(item[0], (bytes, bytearray)) else flag_blob
                if isinstance(item[1], (bytes, bytearray)):
                    raw_message = item[1]
            if not raw_message:
                continue
            is_unread = b"\\Seen" not in (flag_blob or b"")
            row = parse_inbox_message_payload(uid, raw_message, is_unread, flag_blob)
            if unread_only and not bool(row.get("is_unread")):
                continue
            if starred_only and not bool(row.get("is_starred")):
                continue
            if query_clean:
                haystack = " ".join([
                    str(row.get("subject") or "").lower(),
                    str(row.get("from") or "").lower(),
                    str(row.get("from_email") or "").lower(),
                    str(row.get("to") or "").lower(),
                    str(row.get("snippet") or "").lower(),
                ])
                if query_clean not in haystack:
                    continue
            picks.append({
                "uid": row["uid"],
                "subject": row["subject"],
                "from": row["from"],
                "from_name": row["from_name"],
                "from_email": row["from_email"],
                "to": row.get("to") or "",
                "cc": row.get("cc") or "",
                "snippet": row["snippet"],
                "date": row["date"],
                "is_unread": bool(row["is_unread"]),
                "is_starred": bool(row.get("is_starred")),
                "message_id": row["message_id"],
                "references": row["references"],
                "in_reply_to": row["in_reply_to"],
            })
            if len(picks) >= int(limit):
                break
        return {
            "messages": picks,
            "unread_count": int(unread_count),
            "folder": resolve_admin_imap_mailbox(folder),
            "requested_folder": normalize_space(folder) or "inbox",
            "provider": "imap",
        }
    finally:
        try:
            mailbox.close()
        except Exception:
            pass
        try:
            mailbox.logout()
        except Exception:
            pass


@app.get("/admin/mail/inbox/{uid}")
def admin_mail_inbox_message(
    uid: str,
    mark_read: bool = Query(True),
    folder: str = Query("inbox"),
    admin=Depends(get_admin_session)
):
    raw_uid = str(uid or "").strip()
    if gmail_api_enabled():
        cleaned_uid = re.sub(r"[^A-Za-z0-9_-]", "", raw_uid)
    else:
        cleaned_uid = re.sub(r"[^0-9]", "", raw_uid)
    if not cleaned_uid:
        raise HTTPException(status_code=400, detail="ID de correo no válido")

    if gmail_api_enabled():
        msg = _gmail_api_request("GET", f"/messages/{cleaned_uid}", query={"format": "full"})
        payload = _gmail_message_to_payload(msg, include_body=True)
        if bool(mark_read) and bool(payload.get("is_unread")):
            _gmail_api_request(
                "POST",
                f"/messages/{cleaned_uid}/modify",
                payload={"removeLabelIds": ["UNREAD"]},
            )
            payload["is_unread"] = False
        return {"message": payload, "provider": "gmail_api"}

    mailbox = open_admin_imap_inbox(folder)
    try:
        fetch_status, fetched = mailbox.uid("fetch", cleaned_uid, "(RFC822 FLAGS)")
        if fetch_status != "OK" or not fetched:
            raise HTTPException(status_code=404, detail="Correo no encontrado")
        raw_message = b""
        flag_blob = b""
        for item in fetched:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            flag_blob = item[0] if isinstance(item[0], (bytes, bytearray)) else flag_blob
            if isinstance(item[1], (bytes, bytearray)):
                raw_message = item[1]
        if not raw_message:
            raise HTTPException(status_code=404, detail="Correo no encontrado")
        is_unread = b"\\Seen" not in (flag_blob or b"")
        payload = parse_inbox_message_payload(cleaned_uid, raw_message, is_unread, flag_blob)
        if bool(mark_read):
            try:
                mailbox.uid("store", cleaned_uid, "+FLAGS", "(\\Seen)")
                payload["is_unread"] = False
            except Exception:
                pass
        return {"message": payload, "provider": "imap"}
    finally:
        try:
            mailbox.close()
        except Exception:
            pass
        try:
            mailbox.logout()
        except Exception:
            pass


@app.patch("/admin/mail/inbox/{uid}/flags")
def admin_mail_update_flags(
    uid: str,
    data: AdminMailFlagsBody,
    folder: str = Query("inbox"),
    admin=Depends(get_admin_session)
):
    raw_uid = str(uid or "").strip()
    if gmail_api_enabled():
        cleaned_uid = re.sub(r"[^A-Za-z0-9_-]", "", raw_uid)
    else:
        cleaned_uid = re.sub(r"[^0-9]", "", raw_uid)
    if not cleaned_uid:
        raise HTTPException(status_code=400, detail="ID de correo no válido")

    if gmail_api_enabled():
        add_labels: List[str] = []
        remove_labels: List[str] = []
        if data.seen is not None:
            if bool(data.seen):
                remove_labels.append("UNREAD")
            else:
                add_labels.append("UNREAD")
        if data.starred is not None:
            if bool(data.starred):
                add_labels.append("STARRED")
            else:
                remove_labels.append("STARRED")
        if add_labels or remove_labels:
            _gmail_api_request(
                "POST",
                f"/messages/{cleaned_uid}/modify",
                payload={
                    "addLabelIds": add_labels,
                    "removeLabelIds": remove_labels,
                },
            )
        return {"detail": "Flags actualizados", "provider": "gmail_api"}

    mailbox = open_admin_imap_inbox(folder)
    try:
        if data.seen is not None:
            if bool(data.seen):
                mailbox.uid("store", cleaned_uid, "+FLAGS", "(\\Seen)")
            else:
                mailbox.uid("store", cleaned_uid, "-FLAGS", "(\\Seen)")
        if data.starred is not None:
            if bool(data.starred):
                mailbox.uid("store", cleaned_uid, "+FLAGS", "(\\Flagged)")
            else:
                mailbox.uid("store", cleaned_uid, "-FLAGS", "(\\Flagged)")
        return {"detail": "Flags actualizados", "provider": "imap"}
    finally:
        try:
            mailbox.close()
        except Exception:
            pass
        try:
            mailbox.logout()
        except Exception:
            pass


@app.post("/admin/mail/inbox/{uid}/trash")
def admin_mail_move_to_trash(
    uid: str,
    folder: str = Query("inbox"),
    admin=Depends(get_admin_session)
):
    raw_uid = str(uid or "").strip()
    if gmail_api_enabled():
        cleaned_uid = re.sub(r"[^A-Za-z0-9_-]", "", raw_uid)
    else:
        cleaned_uid = re.sub(r"[^0-9]", "", raw_uid)
    if not cleaned_uid:
        raise HTTPException(status_code=400, detail="ID de correo no válido")

    if gmail_api_enabled():
        _gmail_api_request("POST", f"/messages/{cleaned_uid}/trash", payload={})
        return {"detail": "Correo movido a papelera", "provider": "gmail_api"}

    mailbox = open_admin_imap_inbox(folder)
    trash_box = resolve_admin_imap_mailbox("trash")
    try:
        status_copy, _ = mailbox.uid("COPY", cleaned_uid, trash_box)
        if status_copy != "OK":
            raise HTTPException(status_code=500, detail="No se pudo mover a papelera")
        mailbox.uid("store", cleaned_uid, "+FLAGS", "(\\Deleted)")
        mailbox.expunge()
        return {"detail": "Correo movido a papelera", "provider": "imap"}
    finally:
        try:
            mailbox.close()
        except Exception:
            pass
        try:
            mailbox.logout()
        except Exception:
            pass


@app.post("/admin/mail/send")
async def admin_send_mail(
    to_email: str = Form(""),
    to_username: str = Form(""),
    subject: str = Form(""),
    body: str = Form(""),
    in_reply_to: str = Form(""),
    references: str = Form(""),
    files: List[UploadFile] = File([]),
    admin=Depends(get_admin_session)
):
    cleaned_subject = normalize_space(subject)
    cleaned_body = (body or "").strip()
    cleaned_to_email = (to_email or "").strip().lower()
    cleaned_to_username = normalize_space(to_username)
    cleaned_reply_to = normalize_space(in_reply_to)
    cleaned_references = normalize_space(references)

    if not cleaned_subject:
        raise HTTPException(status_code=400, detail="Debes indicar un asunto")
    if not cleaned_body:
        raise HTTPException(status_code=400, detail="Debes indicar el cuerpo del correo")

    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        resolved_user = None
        if cleaned_to_username:
            cursor.execute(
                "SELECT id, username, email FROM users WHERE username=%s LIMIT 1",
                (cleaned_to_username,)
            )
            resolved_user = cursor.fetchone()
            if not resolved_user:
                raise HTTPException(status_code=404, detail="No existe un usuario con ese nombre")
            if not cleaned_to_email:
                cleaned_to_email = (resolved_user.get("email") or "").strip().lower()

        if not cleaned_to_email:
            raise HTTPException(status_code=400, detail="Debes indicar correo destinatario o un usuario")
        if not seems_valid_email(cleaned_to_email):
            raise HTTPException(status_code=400, detail="Correo destinatario no válido")

        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email import encoders

        temp_files: List[Path] = []
        try:
            temp_dir = SUPPORT_IMG_DIR / "_admin_mail_tmp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            for idx, up_file in enumerate(files or []):
                if idx >= 10:
                    break
                content_type = (up_file.content_type or "").lower()
                if content_type and not content_type.startswith("image/"):
                    continue
                ext = Path(up_file.filename or "").suffix.lower()
                if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                    ext = mimetypes.guess_extension(content_type or "") or ".bin"
                tmp_name = f"mail_{secrets.token_hex(8)}_{idx+1}{ext}"
                tmp_path = temp_dir / tmp_name
                with tmp_path.open("wb") as fh:
                    shutil.copyfileobj(up_file.file, fh)
                temp_files.append(tmp_path)

            msg = MIMEMultipart()
            msg["Subject"] = str(Header(cleaned_subject, "utf-8"))
            msg["From"] = ADMIN_MAIL_FROM or EMAIL_SENDER
            msg["To"] = cleaned_to_email
            if cleaned_reply_to:
                msg["In-Reply-To"] = cleaned_reply_to
            if cleaned_references:
                msg["References"] = cleaned_references
            elif cleaned_reply_to:
                msg["References"] = cleaned_reply_to
            msg.attach(MIMEText(cleaned_body, _subtype="plain", _charset="utf-8"))

            for path in temp_files:
                if not path.exists() or not path.is_file():
                    continue
                part = MIMEBase("application", "octet-stream")
                with path.open("rb") as fh:
                    part.set_payload(fh.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
                msg.attach(part)

            if gmail_api_enabled():
                raw_b64 = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8").rstrip("=")
                _gmail_api_request("POST", "/messages/send", payload={"raw": raw_b64})
            else:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=25) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(ADMIN_MAIL_LOGIN or EMAIL_SENDER, ADMIN_MAIL_PASSWORD or EMAIL_PASSWORD)
                    server.send_message(msg)
        finally:
            for tmp in temp_files:
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass

        return {
            "detail": f"Correo enviado a {cleaned_to_email}",
            "to_email": cleaned_to_email,
            "to_username": (resolved_user or {}).get("username") if resolved_user else None
        }
    finally:
        cursor.close()
        conn.close()


@app.get("/profiles/{user_id:int}")
def get_public_profile(user_id: int):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        columns = get_users_table_columns(conn)
        select_parts = ["id", "username"]
        if "birthdate" in columns:
            select_parts.append("birthdate")
        if "description" in columns:
            select_parts.append("description")
        cursor.execute(
            f"SELECT {', '.join(select_parts)} FROM users WHERE id=%s LIMIT 1",
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        cursor.execute(
            "SELECT COUNT(*) AS total FROM reviews WHERE user_id=%s AND is_hidden=0",
            (user_id,)
        )
        total_reviews = int((cursor.fetchone() or {}).get("total") or 0)
        return {
            "id": int(row["id"]),
            "username": row.get("username") or "Usuario",
            "birthdate": str(row["birthdate"]) if row.get("birthdate") else None,
            "description": row.get("description") or "",
            "avatar": get_user_avatar_url(int(row["id"])),
            "total_public_reviews": total_reviews
        }
    finally:
        cursor.close()
        conn.close()


@app.get("/profiles/{user_id:int}/reviews")
def get_public_profile_reviews(user_id: int, request: Request, limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)):
    current_user = get_optional_current_user(request)
    current_user_id = int(current_user["id"]) if current_user else None
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute("SELECT id FROM users WHERE id=%s LIMIT 1", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        my_vote_sql = "0 AS my_vote"
        params: List = [user_id]
        if current_user_id is not None:
            my_vote_sql = "(SELECT rv3.vote FROM review_votes rv3 WHERE rv3.review_id=r.id AND rv3.user_id=%s LIMIT 1) AS my_vote"
            params = [current_user_id, user_id]
        query = f"""
            SELECT r.id, r.place_public_id, p.name AS place_name, r.user_id, r.rating, r.description, r.photos_json,
                   r.is_hidden, r.hidden_reason, r.created_at, r.updated_at,
                   r.pending_recheck, r.previous_rating, r.previous_description, r.previous_photos_json, r.last_edit_requested_at,
                   u.username, u.birthdate, u.description AS user_description,
                   (SELECT COUNT(*) FROM review_votes rv1 WHERE rv1.review_id=r.id AND rv1.vote=1) AS like_count,
                   (SELECT COUNT(*) FROM review_votes rv2 WHERE rv2.review_id=r.id AND rv2.vote=-1) AS dislike_count,
                   (SELECT COUNT(*) FROM review_reports rr WHERE rr.review_id=r.id AND rr.status='pending') AS report_count,
                   {my_vote_sql}
            FROM reviews r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN places p ON p.public_id = r.place_public_id
            WHERE r.user_id=%s AND r.is_hidden=0
            ORDER BY r.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall() or []
        reviews = enrich_review_rows(rows, current_user_id)
        return {"reviews": reviews, "count": len(reviews)}
    finally:
        cursor.close()
        conn.close()

@app.middleware("http")
async def admin_local_only_guard(request: Request, call_next):

    path = request.url.path or ""

    if path.startswith("/administracion"):

        try:
            _require_local_client(request)
        except HTTPException:
            return JSONResponse(
                status_code=403,
                content={"detail": "Error"}
            )

    return await call_next(request)


@app.get("/places/{place_id:int}/reviews")
def list_place_reviews(
    place_id: int,
    request: Request,
    sort: str = Query("newest"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sample: bool = Query(False)
):
    current_user = get_optional_current_user(request)
    current_user_id = int(current_user["id"]) if current_user else None
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute("SELECT public_id, name FROM places WHERE public_id=%s LIMIT 1", (place_id,))
        place_row = cursor.fetchone()
        if not place_row:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        summary = get_reviews_summary(cursor, place_id, include_hidden=False)
        my_vote_sql = "0 AS my_vote"
        params: List = [place_id]
        if current_user_id is not None:
            my_vote_sql = "(SELECT rv3.vote FROM review_votes rv3 WHERE rv3.review_id=r.id AND rv3.user_id=%s LIMIT 1) AS my_vote"
            params = [current_user_id, place_id]
        if sample:
            query = f"""
                SELECT r.id, r.place_public_id, p.name AS place_name, r.user_id, r.rating, r.description, r.photos_json,
                       r.is_hidden, r.hidden_reason, r.created_at, r.updated_at,
                       r.pending_recheck, r.previous_rating, r.previous_description, r.previous_photos_json, r.last_edit_requested_at,
                       u.username, u.birthdate, u.description AS user_description,
                       (SELECT COUNT(*) FROM review_votes rv1 WHERE rv1.review_id=r.id AND rv1.vote=1) AS like_count,
                       (SELECT COUNT(*) FROM review_votes rv2 WHERE rv2.review_id=r.id AND rv2.vote=-1) AS dislike_count,
                       (SELECT COUNT(*) FROM review_reports rr WHERE rr.review_id=r.id AND rr.status='pending') AS report_count,
                       {my_vote_sql}
                FROM reviews r
                JOIN users u ON u.id = r.user_id
                LEFT JOIN places p ON p.public_id = r.place_public_id
                WHERE r.place_public_id=%s AND r.is_hidden=0
                ORDER BY r.created_at DESC, r.id DESC
                LIMIT %s
            """
            params.append(limit)
        else:
            query = f"""
                SELECT r.id, r.place_public_id, p.name AS place_name, r.user_id, r.rating, r.description, r.photos_json,
                       r.is_hidden, r.hidden_reason, r.created_at, r.updated_at,
                       r.pending_recheck, r.previous_rating, r.previous_description, r.previous_photos_json, r.last_edit_requested_at,
                       u.username, u.birthdate, u.description AS user_description,
                       (SELECT COUNT(*) FROM review_votes rv1 WHERE rv1.review_id=r.id AND rv1.vote=1) AS like_count,
                       (SELECT COUNT(*) FROM review_votes rv2 WHERE rv2.review_id=r.id AND rv2.vote=-1) AS dislike_count,
                       (SELECT COUNT(*) FROM review_reports rr WHERE rr.review_id=r.id AND rr.status='pending') AS report_count,
                       {my_vote_sql}
                FROM reviews r
                JOIN users u ON u.id = r.user_id
                LEFT JOIN places p ON p.public_id = r.place_public_id
                WHERE r.place_public_id=%s AND r.is_hidden=0
                ORDER BY {get_review_order_sql(sort)}
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall() or []
        reviews = enrich_review_rows(rows, current_user_id)
        return {
            "place_public_id": int(place_id),
            "summary": summary,
            "reviews": reviews
        }
    finally:
        cursor.close()
        conn.close()


@app.post("/places/{place_id:int}/reviews")
async def create_place_review(
    place_id: int,
    request: Request,
    rating: int = Form(...),
    description: str = Form(""),
    files: List[UploadFile] = File([])
):
    user = get_current_user(request)
    normalized_rating = int(rating or 0)
    cleaned_description = (description or "").strip()
    if normalized_rating < 1 or normalized_rating > 5:
        raise HTTPException(status_code=400, detail="La puntuación debe estar entre 1 y 5")
    if not cleaned_description:
        raise HTTPException(status_code=400, detail="La descripción es obligatoria")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute("SELECT public_id FROM places WHERE public_id=%s LIMIT 1", (place_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Negocio no encontrado")

        cursor.execute(
            """
            INSERT INTO reviews (place_public_id, user_id, rating, description, photos_json)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (place_id, int(user["id"]), normalized_rating, cleaned_description, "[]")
        )
        review_id = int(cursor.lastrowid)
        media_urls = serialize_review_media(review_id, files or [])
        cursor.execute(
            "UPDATE reviews SET photos_json=%s WHERE id=%s",
            (json.dumps(media_urls), review_id)
        )
        conn.commit()
        return {"detail": "Reseña creada", "review_id": review_id}
    finally:
        cursor.close()
        conn.close()


@app.get("/users/me/reviews")
def list_my_reviews(user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute(
            """
            SELECT r.id, r.place_public_id, p.name AS place_name, r.user_id, r.rating, r.description, r.photos_json,
                   r.is_hidden, r.hidden_reason, r.created_at, r.updated_at,
                   r.pending_recheck, r.previous_rating, r.previous_description, r.previous_photos_json, r.last_edit_requested_at,
                   u.username, u.birthdate, u.description AS user_description,
                   (SELECT COUNT(*) FROM review_votes rv1 WHERE rv1.review_id=r.id AND rv1.vote=1) AS like_count,
                   (SELECT COUNT(*) FROM review_votes rv2 WHERE rv2.review_id=r.id AND rv2.vote=-1) AS dislike_count,
                   (SELECT COUNT(*) FROM review_reports rr WHERE rr.review_id=r.id AND rr.status='pending') AS report_count,
                   (SELECT rv3.vote FROM review_votes rv3 WHERE rv3.review_id=r.id AND rv3.user_id=%s LIMIT 1) AS my_vote
            FROM reviews r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN places p ON p.public_id = r.place_public_id
            WHERE r.user_id=%s
            ORDER BY r.created_at DESC
            """,
            (int(user["id"]), int(user["id"]))
        )
        rows = cursor.fetchall() or []
        return {"reviews": enrich_review_rows(rows, int(user["id"]))}
    finally:
        cursor.close()
        conn.close()


@app.put("/users/me/reviews/{review_id:int}")
def update_my_review(review_id: int, data: ReviewEditBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute(
            """
            SELECT id, rating, description, photos_json, is_hidden, pending_recheck
            FROM reviews
            WHERE id=%s AND user_id=%s
            LIMIT 1
            """,
            (review_id, int(user["id"]))
        )
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        next_rating = int(existing.get("rating") or 0)
        next_description = existing.get("description") or ""
        parts = []
        values: List = []
        if data.rating is not None:
            rating = int(data.rating)
            if rating < 1 or rating > 5:
                raise HTTPException(status_code=400, detail="La puntuación debe estar entre 1 y 5")
            next_rating = rating
            parts.append("rating=%s")
            values.append(rating)
        if data.description is not None:
            cleaned = (data.description or "").strip()
            if not cleaned:
                raise HTTPException(status_code=400, detail="La descripción es obligatoria")
            next_description = cleaned
            parts.append("description=%s")
            values.append(cleaned)
        if not parts:
            return {"detail": "Sin cambios"}
        was_changed = (
            next_rating != int(existing.get("rating") or 0) or
            next_description != (existing.get("description") or "")
        )
        if not was_changed:
            return {"detail": "Sin cambios"}
        if bool(existing.get("is_hidden")):
            parts.extend([
                "pending_recheck=1",
                "previous_rating=%s",
                "previous_description=%s",
                "previous_photos_json=%s",
                "last_edit_requested_at=NOW()"
            ])
            values.extend([
                int(existing.get("rating") or 0),
                existing.get("description") or "",
                existing.get("photos_json") or "[]"
            ])
        values.append(review_id)
        cursor.execute(f"UPDATE reviews SET {', '.join(parts)} WHERE id=%s", tuple(values))
        conn.commit()
        if bool(existing.get("is_hidden")):
            return {
                "detail": (
                    "Reseña modificada y enviada para revisión de administración. "
                    "Se mantendrá oculta hasta su revisión."
                ),
                "pending_recheck": True
            }
        return {"detail": "Reseña actualizada", "pending_recheck": False}
    finally:
        cursor.close()
        conn.close()


@app.delete("/users/me/reviews/{review_id:int}")
def delete_my_review(review_id: int, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute("SELECT id FROM reviews WHERE id=%s AND user_id=%s LIMIT 1", (review_id, int(user["id"])))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        cursor.execute("DELETE FROM review_votes WHERE review_id=%s", (review_id,))
        cursor.execute("DELETE FROM review_reports WHERE review_id=%s", (review_id,))
        cursor.execute("DELETE FROM reviews WHERE id=%s", (review_id,))
        conn.commit()
        remove_review_media_files(review_id)
        return {"detail": "Reseña eliminada"}
    finally:
        cursor.close()
        conn.close()


@app.post("/reviews/{review_id:int}/vote")
def vote_review(review_id: int, data: ReviewVoteBody, user=Depends(get_current_user)):
    normalized_vote = (data.vote or "").strip().lower()
    vote_value = 0
    if normalized_vote == "like":
        vote_value = 1
    elif normalized_vote == "dislike":
        vote_value = -1
    elif normalized_vote in {"none", "", "clear"}:
        vote_value = 0
    else:
        raise HTTPException(status_code=400, detail="Voto no válido")

    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute("SELECT id FROM reviews WHERE id=%s LIMIT 1", (review_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        if vote_value == 0:
            cursor.execute(
                "DELETE FROM review_votes WHERE review_id=%s AND user_id=%s",
                (review_id, int(user["id"]))
            )
        else:
            cursor.execute(
                """
                INSERT INTO review_votes (review_id, user_id, vote)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE vote=VALUES(vote), updated_at=CURRENT_TIMESTAMP
                """,
                (review_id, int(user["id"]), vote_value)
            )
        conn.commit()
        return {"detail": "Voto actualizado"}
    finally:
        cursor.close()
        conn.close()


@app.post("/reviews/{review_id:int}/report")
def report_review(review_id: int, data: ReviewReportBody, user=Depends(get_current_user)):
    reason = (data.reason or "").strip()
    if len(reason) < 4:
        raise HTTPException(status_code=400, detail="Debes indicar un motivo")
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute("SELECT user_id FROM reviews WHERE id=%s LIMIT 1", (review_id,))
        review = cursor.fetchone()
        if not review:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        if int(review["user_id"]) == int(user["id"]):
            raise HTTPException(status_code=400, detail="No puedes reportar tu propia reseña")
        cursor.execute(
            """
            SELECT id FROM review_reports
            WHERE review_id=%s AND reporter_user_id=%s AND status='pending'
            LIMIT 1
            """,
            (review_id, int(user["id"]))
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Ya has reportado esta reseña")
        cursor.execute(
            """
            INSERT INTO review_reports (review_id, reporter_user_id, reason, status)
            VALUES (%s, %s, %s, 'pending')
            """,
            (review_id, int(user["id"]), reason)
        )
        conn.commit()
        return {"detail": "Reporte enviado"}
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/reviews")
def admin_list_reviews(
    place_public_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    rating: Optional[int] = Query(None),
    hidden: Optional[str] = Query("all"),
    limit: int = Query(200, ge=1, le=1000),
    admin=Depends(get_admin_session)
):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        filters = []
        params: List = []
        if place_public_id is not None:
            filters.append("r.place_public_id=%s")
            params.append(int(place_public_id))
        if user_id is not None:
            filters.append("r.user_id=%s")
            params.append(int(user_id))
        if rating is not None:
            filters.append("r.rating=%s")
            params.append(int(rating))
        normalized_hidden = (hidden or "all").strip().lower()
        if normalized_hidden == "visible":
            filters.append("r.is_hidden=0")
        elif normalized_hidden == "hidden":
            filters.append("r.is_hidden=1")
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        query = f"""
            SELECT r.id, r.place_public_id, p.name AS place_name, r.user_id, r.rating, r.description, r.photos_json,
                   r.is_hidden, r.hidden_reason, r.created_at, r.updated_at,
                   r.pending_recheck, r.previous_rating, r.previous_description, r.previous_photos_json, r.last_edit_requested_at,
                   u.username, u.birthdate, u.description AS user_description,
                   (SELECT COUNT(*) FROM review_votes rv1 WHERE rv1.review_id=r.id AND rv1.vote=1) AS like_count,
                   (SELECT COUNT(*) FROM review_votes rv2 WHERE rv2.review_id=r.id AND rv2.vote=-1) AS dislike_count,
                   (SELECT COUNT(*) FROM review_reports rr WHERE rr.review_id=r.id AND rr.status='pending') AS report_count,
                   0 AS my_vote
            FROM reviews r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN places p ON p.public_id = r.place_public_id
            {where_sql}
            ORDER BY r.created_at DESC
            LIMIT %s
        """
        params.append(limit)
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall() or []
        return {"reviews": enrich_review_rows(rows, None)}
    finally:
        cursor.close()
        conn.close()


@app.patch("/admin/reviews/{review_id:int}/moderate")
def admin_moderate_review(review_id: int, data: ReviewModerationBody, admin=Depends(get_admin_session)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    try:
        ensure_reviews_schema(conn)
        return moderate_review_action(conn, review_id, data.action, data.reason, actor_is_admin=True, notify_user=bool(data.notify_user))
    finally:
        conn.close()


@app.patch("/admin/reviews/{review_id:int}/revision")
def admin_review_revision(review_id: int, data: ReviewRevisionModerationBody, admin=Depends(get_admin_session)):
    normalized_action = (data.action or "").strip().lower()
    note = (data.reason or "").strip()
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute(
            """
            SELECT id, is_hidden, pending_recheck, hidden_reason,
                   rating, description, photos_json,
                   previous_rating, previous_description, previous_photos_json
            FROM reviews
            WHERE id=%s
            LIMIT 1
            """,
            (review_id,)
        )
        review = cursor.fetchone()
        if not review:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        if not bool(review.get("pending_recheck")):
            raise HTTPException(status_code=400, detail="La reseña no tiene una modificación pendiente")

        if normalized_action == "approve":
            cursor.execute(
                """
                UPDATE reviews
                SET is_hidden=0,
                    hidden_reason=NULL,
                    pending_recheck=0,
                    previous_rating=NULL,
                    previous_description=NULL,
                    previous_photos_json=NULL,
                    last_edit_requested_at=NULL
                WHERE id=%s
                """,
                (review_id,)
            )
            conn.commit()
            return {"detail": "Modificación aprobada y reseña publicada"}

        if normalized_action == "reject":
            cursor.execute(
                """
                UPDATE reviews
                SET rating=%s,
                    description=%s,
                    photos_json=%s,
                    is_hidden=1,
                    hidden_reason=%s,
                    pending_recheck=0,
                    previous_rating=NULL,
                    previous_description=NULL,
                    previous_photos_json=NULL,
                    last_edit_requested_at=NULL
                WHERE id=%s
                """,
                (
                    int(review.get("previous_rating") or review.get("rating") or 0),
                    review.get("previous_description") or review.get("description") or "",
                    review.get("previous_photos_json") or review.get("photos_json") or "[]",
                    note or review.get("hidden_reason") or "Modificación rechazada por administración",
                    review_id
                )
            )
            conn.commit()
            return {"detail": "Modificación rechazada"}

        raise HTTPException(status_code=400, detail="Acción no válida")
    finally:
        cursor.close()
        conn.close()


@app.get("/admin/review_reports")
def admin_list_review_reports(
    status: str = Query("pending"),
    place_public_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    limit: int = Query(300, ge=1, le=1000),
    admin=Depends(get_admin_session)
):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        filters = []
        params: List = []
        normalized_status = (status or "pending").strip().lower()
        if normalized_status in {"pending", "resolved", "dismissed"}:
            filters.append("rr.status=%s")
            params.append(normalized_status)
        if place_public_id is not None:
            filters.append("r.place_public_id=%s")
            params.append(int(place_public_id))
        if user_id is not None:
            filters.append("r.user_id=%s")
            params.append(int(user_id))
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        cursor.execute(
            f"""
            SELECT rr.id, rr.review_id, rr.reporter_user_id, rr.reason, rr.status, rr.admin_action, rr.admin_note,
                   rr.created_at, rr.resolved_at,
                   r.place_public_id, r.user_id AS review_user_id, r.rating, r.description,
                   p.name AS place_name,
                   reporter.username AS reporter_username,
                   owner.username AS review_username
            FROM review_reports rr
            JOIN reviews r ON r.id = rr.review_id
            LEFT JOIN places p ON p.public_id = r.place_public_id
            LEFT JOIN users reporter ON reporter.id = rr.reporter_user_id
            LEFT JOIN users owner ON owner.id = r.user_id
            {where_sql}
            ORDER BY rr.created_at DESC
            LIMIT %s
            """,
            tuple(params + [limit])
        )
        rows = cursor.fetchall() or []
        payload = []
        for row in rows:
            payload.append({
                "id": int(row["id"]),
                "review_id": int(row["review_id"]),
                "reporter_user_id": int(row["reporter_user_id"]),
                "reporter_username": row.get("reporter_username") or "Usuario",
                "reason": row.get("reason") or "",
                "status": row.get("status") or "pending",
                "admin_action": row.get("admin_action"),
                "admin_note": row.get("admin_note"),
                "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
                "resolved_at": row.get("resolved_at").isoformat() if row.get("resolved_at") else None,
                "review": {
                    "id": int(row["review_id"]),
                    "place_public_id": int(row["place_public_id"]),
                    "place_name": normalize_business_display_name(
                        row.get("place_name"),
                        f"Negocio {row.get('place_public_id') or ''}".strip()
                    ),
                    "user_id": int(row["review_user_id"]),
                    "username": row.get("review_username") or "Usuario",
                    "rating": int(row.get("rating") or 0),
                    "description": row.get("description") or ""
                }
            })
        return {"reports": payload}
    finally:
        cursor.close()
        conn.close()


@app.patch("/admin/review_reports/{report_id:int}")
def admin_moderate_review_report(report_id: int, data: ReviewReportModerationBody, admin=Depends(get_admin_session)):
    normalized_action = (data.action or "").strip().lower()
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_reviews_schema(conn)
        cursor.execute(
            """
            SELECT rr.id, rr.review_id, rr.status
            FROM review_reports rr
            WHERE rr.id=%s
            LIMIT 1
            """,
            (report_id,)
        )
        report_row = cursor.fetchone()
        if not report_row:
            raise HTTPException(status_code=404, detail="Reporte no encontrado")
        if normalized_action in {"hide", "delete"}:
            moderate_review_action(conn, int(report_row["review_id"]), normalized_action, data.reason, actor_is_admin=True, notify_user=bool(data.notify_user))
            cursor.execute(
                """
                UPDATE review_reports
                SET status='resolved', admin_action=%s, admin_note=%s, resolved_at=NOW()
                WHERE id=%s
                """,
                (normalized_action, (data.reason or "").strip() or None, report_id)
            )
            conn.commit()
            return {"detail": "Reporte resuelto"}
        if normalized_action == "dismiss":
            cursor.execute(
                """
                UPDATE review_reports
                SET status='dismissed', admin_action='dismiss', admin_note=%s, resolved_at=NOW()
                WHERE id=%s
                """,
                ((data.reason or "").strip() or None, report_id)
            )
            conn.commit()
            return {"detail": "Reporte descartado"}
        raise HTTPException(status_code=400, detail="Acción no válida")
    finally:
        cursor.close()
        conn.close()


@app.get("/meta/realtime")
def get_realtime_meta():
    now_madrid = datetime.now(SEVILLA_TZ)
    with REALTIME_LOCK:
        cached_temp = REALTIME_CACHE["temperature_c"]
        cached_text = REALTIME_CACHE["weather_text"]
        updated_at = REALTIME_CACHE["updated_at"]

    return {
        "madrid_iso": now_madrid.isoformat(),
        "time_hm": now_madrid.strftime("%H:%M"),
        "temperature_c": cached_temp,
        "weather_text": cached_text,
        "updated_at": updated_at,
    }


@app.get("/meta/public-config")
def get_public_config():
    return {
        "google_maps_api_key": (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
    }


@app.post("/places")
def create_place(place: PlaceCreate, request: Request):
    """
    Crea un nuevo lugar en la base de datos.
    """
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        current_user = None
        try:
            current_user = get_current_user(request)
        except HTTPException:
            current_user = None
        admin_session = None
        try:
            admin_session = _get_admin_session_from_cookie_value(request.cookies.get(ADMIN_SESSION_COOKIE))
        except HTTPException:
            admin_session = None
        if not current_user and not admin_session:
            raise HTTPException(status_code=401, detail="Sesión requerida")
        place_columns = get_places_table_columns(conn)
        ensure_places_optional_columns(
            conn,
            need_owner_user="owner_user_id" not in place_columns,
            need_business_email="business_email" not in place_columns,
            need_special_days="special_days" not in place_columns,
            need_contact_email="contact_email" not in place_columns,
            need_map_latitude="map_latitude" not in place_columns,
            need_map_longitude="map_longitude" not in place_columns
        )
        place_columns = get_places_table_columns(conn)
        user_columns = get_users_table_columns(conn)
        ensure_users_optional_columns(
            conn,
            need_email_verification="email_verification_enabled" not in user_columns,
            need_role_flags=any(c not in user_columns for c in ("role_client", "role_business", "role_admin")),
        )
        user_columns = get_users_table_columns(conn)

        cursor = conn.cursor(dictionary=True)
        public_id = get_next_public_id(cursor)
        normalized_place_name = normalize_business_display_name(place.name, f"Negocio {public_id}")
        public_contact_email = (place.public_contact_email or "").strip().lower()
        business_email = (place.business_email or "").strip().lower()
        contact_email = (place.contact_email or "").strip().lower()
        notification_email = (place.notification_email or "").strip().lower()
        public_flow = bool(
            current_user
            and (
                bool(place.suppress_business_email)
                or bool(notification_email)
                or bool(public_contact_email)
                or is_technical_revision_email(business_email)
            )
        )
        previous_business_role = False
        if current_user:
            cursor.execute("SELECT role_business FROM users WHERE id=%s LIMIT 1", (int(current_user["id"]),))
            user_state = cursor.fetchone() or {}
            previous_business_role = parse_db_bool(user_state.get("role_business"))
        if public_flow:
            owner_user_id = int(current_user["id"])
            owner_email = (current_user.get("email") or "").strip().lower()
            if not owner_email:
                raise HTTPException(status_code=400, detail="No se pudo resolver el correo de la cuenta")
            business_email = owner_email
            contact_email = public_contact_email or contact_email or None
        elif place.suppress_business_email and not contact_email and notification_email:
            contact_email = notification_email
        map_latitude = normalize_coordinate(place.map_latitude, -90, 90)
        map_longitude = normalize_coordinate(place.map_longitude, -180, 180)
        if (map_latitude is None) != (map_longitude is None):
            raise HTTPException(status_code=400, detail="Debes indicar latitud y longitud juntas")
        place_address = place.address
        if map_latitude is not None and map_longitude is not None:
            auto_address = reverse_geocode_address_from_coordinates(map_latitude, map_longitude)
            if auto_address:
                place_address = auto_address
        if not public_flow:
            if not business_email:
                raise HTTPException(status_code=400, detail="El correo del negocio es obligatorio")
            if not seems_valid_email(business_email):
                raise HTTPException(status_code=400, detail="El correo del negocio no es válido")
        if contact_email and not seems_valid_email(contact_email):
            raise HTTPException(status_code=400, detail="El correo de contacto no es válido")
        if public_flow:
            owner_user_id = int(current_user["id"])
            if "role_business" in user_columns:
                cursor.execute("UPDATE users SET role_business=1 WHERE id=%s", (owner_user_id,))
            final_username = current_user.get("username") or f"usuario-{owner_user_id}"
            raw_password = None
        else:
            cursor.execute("SELECT id FROM users WHERE email=%s", (business_email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="El correo del negocio ya está en uso")

            temp_username = f"negocio-temp-{public_id}-{secrets.token_hex(3)}"
            raw_password = generate_random_password()
            hashed_pw = hash_password(raw_password)
            user_insert_fields = ["username", "email", "password_hash"]
            user_insert_values = [temp_username, business_email, hashed_pw]
            if "role_client" in user_columns:
                user_insert_fields.append("role_client")
                user_insert_values.append(1)
            if "role_business" in user_columns:
                user_insert_fields.append("role_business")
                user_insert_values.append(1)
            if "email_verification_enabled" in user_columns:
                user_insert_fields.append("email_verification_enabled")
                user_insert_values.append(0)
            user_placeholders = ",".join(["%s"] * len(user_insert_fields))
            cursor.execute(
                f"INSERT INTO users ({','.join(user_insert_fields)}) VALUES ({user_placeholders})",
                tuple(user_insert_values)
            )
            owner_user_id = cursor.lastrowid
            get_user_avatar_dir(owner_user_id)
            final_username = f"{slugify_business_name(normalized_place_name)}-{owner_user_id}"
            cursor.execute("UPDATE users SET username=%s WHERE id=%s", (final_username, owner_user_id))

        oh_json = json.dumps(jsonable_encoder(place.opening_hours))
        photos_json = json.dumps(jsonable_encoder(place.photos)) if place.photos else None
        insert_fields = [
            "public_id", "name", "address", "phone", "website", "opening_hours",
            "category", "description", "initial_phrase", "main_photo", "photos", "active"
        ]
        insert_values = [
            public_id,
            normalized_place_name,
            place_address,
            place.phone,
            place.website,
            oh_json,
            place.category,
            place.description,
            place.initial_phrase,
            None,
            photos_json,
            1 if place.active else 0
        ]
        if "owner_user_id" in place_columns:
            insert_fields.append("owner_user_id")
            insert_values.append(owner_user_id)
        if "business_email" in place_columns:
            insert_fields.append("business_email")
            insert_values.append(business_email)
        if "contact_email" in place_columns:
            insert_fields.append("contact_email")
            insert_values.append(contact_email or None)
        if "special_days" in place_columns:
            insert_fields.append("special_days")
            insert_values.append(json.dumps({}))
        if "map_latitude" in place_columns:
            insert_fields.append("map_latitude")
            insert_values.append(map_latitude)
        if "map_longitude" in place_columns:
            insert_fields.append("map_longitude")
            insert_values.append(map_longitude)

        placeholders = ",".join(["%s"] * len(insert_fields))
        cursor.execute(
            f"INSERT INTO places ({','.join(insert_fields)}) VALUES ({placeholders})",
            tuple(insert_values)
        )
        ensure_place_user_assignments_schema(conn)
        cursor.execute(
            """
            INSERT INTO place_user_assignments (user_id, place_public_id, assigned_at)
            VALUES (%s, %s, NOW())
            ON DUPLICATE KEY UPDATE assigned_at=VALUES(assigned_at)
            """,
            (int(owner_user_id), int(public_id))
        )
        get_business_image_dir(public_id)
        conn.commit()
        cursor.close()
        conn.close()

        email_delivery = "accepted_by_smtp"
        review_email_delivery = "skipped"
        if public_flow:
            email_delivery = "skipped_by_request"
            review_target = notification_email or public_contact_email or business_email
            if review_target:
                try:
                    send_notification_email(
                        review_target,
                        f"{normalized_place_name} está en revisión",
                        (
                            f"¡Felicidades!,\n\n"
                            f"Tu solicitud para crear el negocio '{normalized_place_name}' ha sido recibida y está en revisión.\n"
                            f"Te avisaremos cuando el equipo la valide.\n\n"
                        )
                    )
                    review_email_delivery = "accepted_by_smtp"
                except Exception as mail_error:
                    traceback.print_exc()
                    try:
                        rb_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                        rb_cursor = rb_conn.cursor()
                        rb_cursor.execute("DELETE FROM place_user_assignments WHERE place_public_id=%s", (int(public_id),))
                        rb_cursor.execute("DELETE FROM places WHERE public_id=%s", (public_id,))
                        if "role_business" in user_columns and not previous_business_role:
                            rb_cursor.execute("UPDATE users SET role_business=0 WHERE id=%s", (int(owner_user_id),))
                        rb_conn.commit()
                        rb_cursor.close()
                        rb_conn.close()
                    except Exception:
                        traceback.print_exc()
                    shutil.rmtree(BUSINESS_IMG_DIR / str(public_id), ignore_errors=True)
                    raise HTTPException(
                        status_code=500,
                        detail=f"No se pudo enviar el correo de revisión: {mail_error}"
                    )
            else:
                review_email_delivery = "missing_target"
        else:
            try:
                send_business_credentials_email(
                    email=business_email,
                    username=final_username,
                    password=raw_password,
                    place_name=normalized_place_name,
                    public_id=public_id
                )
            except Exception as mail_error:
                traceback.print_exc()
                try:
                    rb_conn = mysql.connector.connect(**DB_WRITE_CONFIG)
                    rb_cursor = rb_conn.cursor()
                    rb_cursor.execute("DELETE FROM sessions WHERE user_id=%s", (owner_user_id,))
                    rb_cursor.execute("DELETE FROM users WHERE id=%s", (owner_user_id,))
                    rb_cursor.execute("DELETE FROM place_user_assignments WHERE user_id=%s", (owner_user_id,))
                    rb_cursor.execute("DELETE FROM places WHERE public_id=%s", (public_id,))
                    rb_conn.commit()
                    rb_cursor.close()
                    rb_conn.close()
                except Exception:
                    traceback.print_exc()
                remove_user_avatar_files(owner_user_id)
                shutil.rmtree(BUSINESS_IMG_DIR / str(public_id), ignore_errors=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"No se pudo enviar el correo con credenciales: {mail_error}"
                )

        warning_parts = []
        if "owner_user_id" not in place_columns:
            warning_parts.append("No se pudo vincular usuario-negocio (falta columna owner_user_id)")
        if "business_email" not in place_columns:
            warning_parts.append("No se pudo guardar correo de negocio en places (falta columna business_email)")

        return {
            "detail": "Registro creado correctamente",
            "id": public_id,
            "business_user": {
                "id": owner_user_id,
                "username": final_username,
                "email": business_email,
                "temporary_password": raw_password
            },
            "public_flow": public_flow,
            "email_delivery": email_delivery,
            "review_email_delivery": review_email_delivery,
            "warning": " | ".join(warning_parts) if warning_parts else None
        }
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al crear el negocio")

@app.put("/places/{place_id}")
def update_place(place_id: int, place: PlaceCreate, admin=Depends(get_admin_session)):
    """
    Actualiza todos los campos de un lugar existente.
    """
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        place_columns = get_places_table_columns(conn)
        ensure_places_optional_columns(
            conn,
            need_owner_user="owner_user_id" not in place_columns,
            need_business_email="business_email" not in place_columns,
            need_special_days="special_days" not in place_columns,
            need_contact_email="contact_email" not in place_columns,
            need_map_latitude="map_latitude" not in place_columns,
            need_map_longitude="map_longitude" not in place_columns
        )
        place_columns = get_places_table_columns(conn)

        cursor = conn.cursor(dictionary=True)
        normalized_place_name = normalize_business_display_name(place.name, f"Negocio {place_id}")
        oh_json = json.dumps(jsonable_encoder(place.opening_hours))
        photos_json = json.dumps(jsonable_encoder(place.photos)) if place.photos else None
        map_latitude = normalize_coordinate(place.map_latitude, -90, 90)
        map_longitude = normalize_coordinate(place.map_longitude, -180, 180)
        if (map_latitude is None) != (map_longitude is None):
            raise HTTPException(status_code=400, detail="Debes indicar latitud y longitud juntas")
        place_address = place.address
        if map_latitude is not None and map_longitude is not None:
            auto_address = reverse_geocode_address_from_coordinates(map_latitude, map_longitude)
            if auto_address:
                place_address = auto_address
        update_parts = [
            "name=%s", "address=%s", "phone=%s", "website=%s",
            "opening_hours=%s", "category=%s", "description=%s",
            "initial_phrase=%s", "photos=%s", "active=%s"
        ]
        update_values = [
            normalized_place_name, place_address, place.phone, place.website,
            oh_json, place.category, place.description,
            place.initial_phrase, photos_json, 1 if place.active else 0
        ]
        business_email = (place.business_email or "").strip().lower()
        contact_email = (place.contact_email or "").strip().lower()
        if business_email and not seems_valid_email(business_email):
            raise HTTPException(status_code=400, detail="Correo del negocio no válido")
        if contact_email and not seems_valid_email(contact_email):
            raise HTTPException(status_code=400, detail="Correo de contacto no válido")
        if "business_email" in place_columns:
            update_parts.append("business_email=%s")
            update_values.append(business_email or None)
        if "contact_email" in place_columns:
            update_parts.append("contact_email=%s")
            update_values.append(contact_email or None)
        if "map_latitude" in place_columns:
            update_parts.append("map_latitude=%s")
            update_values.append(map_latitude)
        if "map_longitude" in place_columns:
            update_parts.append("map_longitude=%s")
            update_values.append(map_longitude)

        update_values.append(place_id)
        cursor.execute(
            f"UPDATE places SET {', '.join(update_parts)} WHERE public_id=%s",
            tuple(update_values)
        )

        if "owner_user_id" in place_columns:
            cursor.execute("SELECT owner_user_id FROM places WHERE public_id=%s", (place_id,))
            row = cursor.fetchone() or {}
            owner_user_id = row.get("owner_user_id")
            if owner_user_id:
                owner_updates = []
                owner_values = []
                if business_email:
                    owner_updates.append("email=%s")
                    owner_values.append(business_email)
                if owner_updates:
                    owner_values.append(owner_user_id)
                    cursor.execute(
                        f"UPDATE users SET {', '.join(owner_updates)} WHERE id=%s",
                        tuple(owner_values)
                    )
        conn.commit()
        cursor.close()
        conn.close()

        return {"detail": "Actualizado correctamente"}
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al actualizar el negocio")

@app.put("/places/{place_id}/active")
def toggle_active(place_id: int, payload: dict, admin=Depends(get_admin_session)):
    """
    Cambia el estado activo/inactivo de un lugar.
    Recibe JSON: { "active": true/false, "send_email": true/false }
    """
    if "active" not in payload:
        raise HTTPException(status_code=400, detail="Falta campo 'active'")
    raw_send_email = payload.get("send_email", False)
    if isinstance(raw_send_email, bool):
        send_email = raw_send_email
    else:
        send_email = str(raw_send_email).strip().lower() in {"1", "true", "yes", "si", "sí"}
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        place_columns = get_places_table_columns(conn)
        select_columns = ["public_id", "name"]
        for col in ("owner_user_id", "business_email", "contact_email"):
            if col in place_columns:
                select_columns.append(col)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT {', '.join(select_columns)} FROM places WHERE public_id=%s LIMIT 1",
            (place_id,)
        )
        place_row = cursor.fetchone()
        if not place_row:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")

        cursor.execute("UPDATE places SET active=%s WHERE public_id=%s",
                       (1 if payload["active"] else 0, place_id))
        conn.commit()

        email_sent = False
        email_recipient = ""
        if send_email:
            owner_email = ""
            owner_user_id = place_row.get("owner_user_id")
            if owner_user_id:
                cursor.execute("SELECT email FROM users WHERE id=%s LIMIT 1", (int(owner_user_id),))
                owner_row = cursor.fetchone() or {}
                owner_email = (owner_row.get("email") or "").strip().lower()
            email_recipient = resolve_visible_business_email(place_row, owner_email)
            if email_recipient:
                try:
                    send_business_status_notification_email(
                        email_recipient,
                        place_row.get("name") or f"Negocio {place_id}",
                        bool(payload["active"])
                    )
                    email_sent = True
                except Exception:
                    logger.exception("No se pudo enviar el correo de estado del negocio %s", place_id)

        cursor.close()
        conn.close()

        return {
            "detail": "Estado actualizado",
            "email_sent": email_sent,
            "email_recipient": email_recipient if email_sent else None,
        }
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al cambiar estado")
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass

@app.delete("/places/{place_id}")
def delete_place(place_id: int, admin=Depends(get_admin_session)):
    """
    Elimina un lugar de la base de datos y borra su imagen principal si existe.
    """
    try:
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        ensure_place_user_assignments_schema(conn)
        place_columns = get_places_table_columns(conn)
        cursor = conn.cursor(dictionary=True)
        owner_user_id = None
        if "owner_user_id" in place_columns:
            cursor.execute("SELECT owner_user_id FROM places WHERE public_id=%s", (place_id,))
            row = cursor.fetchone() or {}
            owner_user_id = row.get("owner_user_id")

        cursor.execute("DELETE FROM places WHERE public_id=%s", (place_id,))
        cursor.execute("DELETE FROM place_user_assignments WHERE place_public_id=%s", (int(place_id),))
        if owner_user_id:
            cursor.execute("DELETE FROM sessions WHERE user_id=%s", (owner_user_id,))
            cursor.execute("DELETE FROM users WHERE id=%s", (owner_user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        # Borrar imagen principal y carpeta multimedia si existe
        img_path = IMG_DIR / f"{place_id}.webp"
        if img_path.exists(): 
            img_path.unlink()
        biz_dir = BUSINESS_IMG_DIR / str(place_id)
        if biz_dir.exists():
            shutil.rmtree(biz_dir, ignore_errors=True)
        if owner_user_id:
            remove_user_avatar_files(owner_user_id)

        return {"detail": "Eliminado correctamente"}
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al eliminar")


class BusinessMeUpdateBody(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    business_email: Optional[str] = None
    contact_email: Optional[str] = None
    use_account_email: Optional[bool] = None
    description: Optional[str] = None
    initial_phrase: Optional[str] = None
    opening_hours: Optional[Dict[str, List[TimeRange]]] = None
    special_days: Optional[Dict] = None
    map_latitude: Optional[float] = None
    map_longitude: Optional[float] = None

    @validator("map_latitude")
    def validate_map_latitude(cls, value):
        if value is None:
            return None
        if not (-90 <= float(value) <= 90):
            raise ValueError("Latitud fuera de rango")
        return float(value)

    @validator("map_longitude")
    def validate_map_longitude(cls, value):
        if value is None:
            return None
        if not (-180 <= float(value) <= 180):
            raise ValueError("Longitud fuera de rango")
        return float(value)


class DeleteBusinessPhotoBody(BaseModel):
    photo_url: str


@app.get("/business/me")
def business_me(user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_READ_CONFIG)
    try:
        ensure_user_has_business_role(conn, int(user["id"]))
        managed_place_public_id = get_managed_place_public_id_for_user(conn, int(user["id"]))
        if not managed_place_public_id:
            return {
                "has_business": False,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "avatar": get_user_avatar_url(user["id"])
                }
            }
        place_columns = get_places_table_columns(conn)

        select_parts = [
            "id", "public_id", "name", "address", "phone", "website",
            "opening_hours", "category", "description", "initial_phrase",
            "main_photo", "photos", "active"
        ]
        if "owner_user_id" in place_columns:
            select_parts.append("owner_user_id")
        if "business_email" in place_columns:
            select_parts.append("business_email")
        if "contact_email" in place_columns:
            select_parts.append("contact_email")
        if "special_days" in place_columns:
            select_parts.append("special_days")
        if "map_latitude" in place_columns:
            select_parts.append("map_latitude")
        if "map_longitude" in place_columns:
            select_parts.append("map_longitude")

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {', '.join(select_parts)} FROM places WHERE public_id=%s LIMIT 1",
                (int(managed_place_public_id),)
            )
            place = cursor.fetchone()
        finally:
            cursor.close()

        if not place:
            return {
                "has_business": False,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "avatar": get_user_avatar_url(user["id"])
                }
            }

        place["name"] = normalize_business_display_name(
            place.get("name"),
            f"Negocio {place.get('public_id') or ''}".strip()
        )
        try:
            place["opening_hours"] = json.loads(place.get("opening_hours") or "{}")
        except Exception:
            place["opening_hours"] = {}
        try:
            place["photos"] = json.loads(place.get("photos") or "[]")
        except Exception:
            place["photos"] = []
        try:
            place["special_days"] = json.loads(place.get("special_days") or "{}")
        except Exception:
            place["special_days"] = {}
        ensure_place_media_urls(place)

        place["active"] = bool(place.get("active", True))
        business_email = (place.get("business_email") or "").strip().lower()
        contact_email = (place.get("contact_email") or "").strip().lower()
        if is_technical_revision_email(business_email) and contact_email:
            place["business_email"] = contact_email
        else:
            place["business_email"] = business_email or user["email"]
        place["contact_email_effective"] = contact_email or place["business_email"] or user["email"]

        return {
            "has_business": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "avatar": get_user_avatar_url(user["id"])
            },
            "place": place
        }
    finally:
        conn.close()


@app.put("/business/me")
def business_update_me(payload: BusinessMeUpdateBody, user=Depends(get_current_user)):
    conn = mysql.connector.connect(**DB_WRITE_CONFIG)
    try:
        ensure_user_has_business_role(conn, int(user["id"]))
        managed_place_public_id = get_managed_place_public_id_for_user(conn, int(user["id"]))
        if not managed_place_public_id:
            raise HTTPException(status_code=403, detail="Cuenta sin negocio vinculado")
        place_columns = get_places_table_columns(conn)
        ensure_places_optional_columns(
            conn,
            need_contact_email="contact_email" not in place_columns,
            need_map_latitude="map_latitude" not in place_columns,
            need_map_longitude="map_longitude" not in place_columns
        )
        place_columns = get_places_table_columns(conn)

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT public_id FROM places WHERE public_id=%s LIMIT 1",
                (int(managed_place_public_id),)
            )
            current_place = cursor.fetchone()
            if not current_place:
                raise HTTPException(status_code=403, detail="Cuenta sin negocio vinculado")

            place_parts = []
            place_values = []

            if payload.name is not None:
                if not payload.name.strip():
                    raise HTTPException(status_code=400, detail="El nombre del negocio no puede estar vacío")
                place_parts.append("name=%s")
                place_values.append(
                    normalize_business_display_name(
                        payload.name.strip(),
                        f"Negocio {current_place.get('public_id') or ''}".strip()
                    )
                )
            if payload.category is not None:
                place_parts.append("category=%s")
                place_values.append(payload.category)
            requested_address = payload.address if payload.address is not None else None
            if payload.phone is not None:
                place_parts.append("phone=%s")
                place_values.append(payload.phone)
            if payload.description is not None:
                place_parts.append("description=%s")
                place_values.append(payload.description)
            if payload.initial_phrase is not None:
                place_parts.append("initial_phrase=%s")
                place_values.append(payload.initial_phrase)
            if payload.opening_hours is not None:
                place_parts.append("opening_hours=%s")
                place_values.append(json.dumps(jsonable_encoder(payload.opening_hours)))
            if payload.special_days is not None and "special_days" in place_columns:
                place_parts.append("special_days=%s")
                place_values.append(json.dumps(jsonable_encoder(payload.special_days)))
            if payload.business_email is not None and "business_email" in place_columns:
                normalized_email = (payload.business_email or "").strip().lower()
                if normalized_email and not seems_valid_email(normalized_email):
                    raise HTTPException(status_code=400, detail="Correo del negocio no válido")
                place_parts.append("business_email=%s")
                place_values.append(normalized_email or None)
            if "contact_email" in place_columns:
                use_account_email = bool(payload.use_account_email)
                if use_account_email:
                    place_parts.append("contact_email=%s")
                    place_values.append(None)
                elif payload.contact_email is not None:
                    contact_email = (payload.contact_email or "").strip().lower()
                    if contact_email and not seems_valid_email(contact_email):
                        raise HTTPException(status_code=400, detail="Correo de contacto no válido")
                    place_parts.append("contact_email=%s")
                    place_values.append(contact_email or None)
            map_fields_sent = "map_latitude" in payload.__fields_set__ or "map_longitude" in payload.__fields_set__
            if map_fields_sent and "map_latitude" in place_columns and "map_longitude" in place_columns:
                map_latitude = normalize_coordinate(payload.map_latitude, -90, 90) if payload.map_latitude is not None else None
                map_longitude = normalize_coordinate(payload.map_longitude, -180, 180) if payload.map_longitude is not None else None
                if (map_latitude is None) != (map_longitude is None):
                    raise HTTPException(status_code=400, detail="Debes indicar latitud y longitud juntas")
                place_parts.append("map_latitude=%s")
                place_values.append(map_latitude)
                place_parts.append("map_longitude=%s")
                place_values.append(map_longitude)
                if map_latitude is not None and map_longitude is not None:
                    auto_address = reverse_geocode_address_from_coordinates(map_latitude, map_longitude)
                    if auto_address:
                        requested_address = auto_address

            if requested_address is not None:
                place_parts.append("address=%s")
                place_values.append(requested_address)

            if place_parts:
                place_values.append(current_place["public_id"])
                cursor.execute(
                    f"UPDATE places SET {', '.join(place_parts)} WHERE public_id=%s",
                    tuple(place_values)
                )

            user_parts = []
            user_values = []

            if payload.business_email is not None:
                new_email = (payload.business_email or "").strip().lower()
                if not new_email:
                    raise HTTPException(status_code=400, detail="Debes indicar un correo de negocio")
                cursor.execute("SELECT id FROM users WHERE email=%s AND id<>%s", (new_email, user["id"]))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="El correo ya está en uso por otra cuenta")
                user_parts.append("email=%s")
                user_values.append(new_email)

            if user_parts:
                user_values.append(user["id"])
                cursor.execute(
                    f"UPDATE users SET {', '.join(user_parts)} WHERE id=%s",
                    tuple(user_values)
                )

            conn.commit()
        finally:
            cursor.close()

        return {"detail": "Datos del negocio actualizados"}
    finally:
        conn.close()

@app.get("/account/settings/")
async def redirect_settings():
    return RedirectResponse(url="/account/settings/index.html")


@app.get("/support")
@app.get("/support/")
@app.get("/support.html")
def support_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "support.html"))


@app.get("/frontend.html")
def frontend_html_page(request: Request):
    if not is_ai_visible() and not request.url.path.startswith("/pruebas"):
        html_path = resolve_web_public_file_for_request(request, "frontend.html")
        html = html_path.read_text(encoding="utf-8")
        inject = "<style>.assistant-toggle,.assistant-panel{display:none !important}</style>"
        html = html.replace("</head>", f"{inject}</head>")
        return HTMLResponse(content=html, status_code=200, headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        })
    return no_cache_file_response(resolve_web_public_file_for_request(request, "frontend.html"))


@app.get("/scan_qr.html")
def scan_qr_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "scan_qr.html"))


@app.get("/mensajes.html")
def mensajes_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "mensajes.html"))


@app.get("/negocio.html")
def negocio_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "negocio.html"))


@app.get("/alta_negocio.html")
def alta_negocio_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "alta_negocio.html"))

@app.get("/negocios_gestion.html")
def negocios_gestion_public_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "negocios_gestion.html"))


@app.get("/perfil.html")
def perfil_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "perfil.html"))


@app.get("/ui_public.css")
def ui_public_css(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "ui_public.css"))


@app.get("/ui_public.js")
def ui_public_js(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "ui_public.js"))


@app.get("/west_widget.css")
def west_widget_css(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "west_widget.css"))


@app.get("/west_widget.js")
def west_widget_js(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "west_widget.js"))


@app.get("/manifest.webmanifest")
def frontend_manifest(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "manifest.webmanifest"))


@app.get("/sitemap.xml")
def sitemap_xml():
    path = Path(__file__).resolve().parent / "sitemap.xml"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(path, media_type="application/xml; charset=utf-8")


@app.get("/robots.txt")
def robots_txt():
    path = Path(__file__).resolve().parent / "robots.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(path, media_type="text/plain; charset=utf-8")


@app.get("/sw.js")
def frontend_sw(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "sw.js"))


@app.get("/login.html")
@app.get("/frontend/login.html")
def frontend_login_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "login.html"))


@app.get("/register.html")
@app.get("/frontend/register.html")
def frontend_register_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "register.html"))


@app.get("/cookies.html")
@app.get("/frontend/cookies.html")
def frontend_cookies_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "cookies.html"))


@app.get("/terminos.html")
@app.get("/frontend/terminos.html")
@app.get("/public/terminos.html")
def frontend_terms_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "terminos.html"))


@app.get("/privacidad.html")
@app.get("/frontend/privacidad.html")
@app.get("/public/privacidad.html")
@app.get("/privacidad")
@app.get("/privacidad/")
def frontend_privacy_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "privacidad.html"))


@app.get("/aviso_legal.html")
@app.get("/frontend/aviso_legal.html")
@app.get("/public/aviso_legal.html")
@app.get("/aviso-legal")
@app.get("/aviso-legal/")
def frontend_aviso_legal_page(request: Request):
    return no_cache_file_response(resolve_web_public_file_for_request(request, "aviso_legal.html"))


@app.get("/frontend/{path:path}")
def frontend_legacy_asset(request: Request, path: str):
    return no_cache_file_response(resolve_web_public_file_for_request(request, path))


@app.get("/pruebas")
@app.get("/pruebas/")
def pruebas_frontend(request: Request):
    return no_cache_file_response(resolve_web_public_file_with_mode("frontend.html", mode="test"))


@app.get("/pruebas/{path:path}")
def pruebas_frontend_asset(path: str):
    return no_cache_file_response(resolve_web_public_file_with_mode(path, mode="test"))


@app.get("/versiones")
@app.get("/versiones/")
@app.get("/versiones.html")
def versions_page(admin=Depends(get_admin_session)):
    return FileResponse(WEB_DIR / "frontend" / "versiones.html", media_type="text/html; charset=utf-8")


@app.get("/versiones/cliente")
@app.get("/versiones/cliente/")
@app.get("/versiones-cliente")
@app.get("/versiones_cliente.html")
def versions_client_page():
    return FileResponse(WEB_DIR / "frontend" / "versiones_cliente.html", media_type="text/html; charset=utf-8")


@app.post("/api/manuales/auth/login")
async def manuales_auth_login(payload: dict, request: Request):
    username = normalize_space(str((payload or {}).get("username") or "")).lower()
    password = str((payload or {}).get("password") or "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Usuario y contraseña obligatorios")
    expected = MANUALES_AUTH_USERS.get(username)
    if not expected or expected != password:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    session_id = secrets.token_hex(32)
    with MANUALES_AUTH_LOCK:
        MANUALES_AUTH_SESSIONS[session_id] = {
            "username": username,
            "expires_at": int(time.time()) + (60 * 60 * 24 * 30),
        }
        _save_manuales_auth_sessions_locked()
    response = JSONResponse(content={"ok": True, "username": username})
    _set_manuales_session_cookie(response, session_id, request=request)
    return response


@app.post("/api/manuales/auth/logout")
async def manuales_auth_logout(request: Request, response: Response):
    sid = (request.cookies.get(MANUALES_AUTH_COOKIE) or "").strip()
    if sid:
        with MANUALES_AUTH_LOCK:
            MANUALES_AUTH_SESSIONS.pop(sid, None)
            _save_manuales_auth_sessions_locked()
    _clear_manuales_session_cookie(response, request=request)
    return {"ok": True}


@app.get("/api/manuales/auth/me")
async def manuales_auth_me(request: Request):
    session_id = (request.cookies.get(MANUALES_AUTH_COOKIE) or "").strip()
    if not session_id:
        return {"authenticated": False, "username": ""}

    now_ts = int(time.time())
    with MANUALES_AUTH_LOCK:
        row = MANUALES_AUTH_SESSIONS.get(session_id)
        if not row:
            return {"authenticated": False, "username": ""}
        expires_at = int(row.get("expires_at") or 0)
        if expires_at <= now_ts:
            MANUALES_AUTH_SESSIONS.pop(session_id, None)
            _save_manuales_auth_sessions_locked()
            return {"authenticated": False, "username": ""}
        return {"authenticated": True, "username": str(row.get("username") or "").strip().lower()}


@app.get("/api/state")
async def get_manuales_state(user=Depends(get_manuales_current_user)):
    with MANUALES_STORAGE_LOCK:
        if not MANUALES_STATE_FILE.exists():
            return {
                "sections": [],
                "folders": [],
                "manuals": [],
                "trash": [],
                "permissions": {"sections": {}, "folders": {}, "manuals": {}},
                "selectedSectionId": None,
                "generatedAt": int(time.time() * 1000),
            }
        try:
            raw = json.loads(MANUALES_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        return _normalize_manuales_payload(raw)


@app.post("/api/state")
async def save_manuales_state(payload: dict, user=Depends(get_manuales_current_user)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload invalido")
    normalized = _normalize_manuales_payload(payload)
    with MANUALES_STORAGE_LOCK:
        MANUALES_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        MANUALES_STATE_FILE.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        stats = _materialize_manuales_storage(normalized)
    return {"ok": True, **stats}


@app.put("/manuales/almacenamiento/sync")
@app.put("/manuales/lista_manuales/sync")
async def sync_manuales_tree(payload: dict, user=Depends(get_manuales_current_user)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload invalido")
    normalized = _normalize_manuales_payload(payload)
    with MANUALES_STORAGE_LOCK:
        MANUALES_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        MANUALES_STATE_FILE.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        stats = _materialize_manuales_storage(normalized)
    return {"ok": True, **stats}


@app.get("/api/infraestructura")
async def get_planos_infra():
    with PLANOS_STORAGE_LOCK:
        PLANOS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if not PLANOS_INFRA_FILE.exists():
            PLANOS_INFRA_FILE.write_text(
                json.dumps({"cpds": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return {"cpds": []}
        try:
            raw = json.loads(PLANOS_INFRA_FILE.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        return _normalize_planos_infra(raw)


@app.post("/api/infraestructura")
async def save_planos_infra(payload: dict):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload invalido")
    normalized = _normalize_planos_infra(payload)
    with PLANOS_STORAGE_LOCK:
        PLANOS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        PLANOS_INFRA_FILE.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {"ok": True}


@app.get("/api/sedes")
async def get_planos_sedes():
    with PLANOS_STORAGE_LOCK:
        PLANOS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if not PLANOS_SEDES_FILE.exists():
            PLANOS_SEDES_FILE.write_text(
                json.dumps({"sedes": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return {"sedes": []}
        try:
            raw = json.loads(PLANOS_SEDES_FILE.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        return _normalize_planos_sedes(raw)


@app.post("/api/sedes")
async def save_planos_sedes(payload: dict):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload invalido")
    normalized = _normalize_planos_sedes(payload)
    with PLANOS_STORAGE_LOCK:
        PLANOS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        PLANOS_SEDES_FILE.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {"ok": True}


def _normalize_checklists_payload(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {"templates": [], "checklists": [], "meta": {}}
    templates = raw.get("templates")
    checklists = raw.get("checklists")
    if not isinstance(templates, list):
        templates = []
    if not isinstance(checklists, list):
        checklists = []
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    return {"templates": templates, "checklists": checklists, "meta": meta}


def _broadcast_checklists_update(payload: dict) -> None:
    try:
        message = json.dumps(payload, ensure_ascii=False)
    except Exception:
        return
    with CHECKLISTS_STREAM_LOCK:
        CHECKLISTS_STREAM_BACKLOG.append(message)
        for sub_q in list(CHECKLISTS_STREAM_SUBSCRIBERS):
            try:
                sub_q.put_nowait(message)
            except queue.Full:
                pass


@app.get("/api/checklists")
async def get_checklists_db():
    with CHECKLISTS_STORAGE_LOCK:
        CHECKLISTS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if not CHECKLISTS_DB_FILE.exists():
            payload = {"templates": [], "checklists": [], "meta": {"updatedAt": datetime.utcnow().isoformat()}}
            CHECKLISTS_DB_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return payload
        try:
            raw = json.loads(CHECKLISTS_DB_FILE.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        normalized = _normalize_checklists_payload(raw)
        if not normalized.get("meta") or not normalized["meta"].get("updatedAt"):
            normalized["meta"] = {"updatedAt": datetime.utcnow().isoformat()}
        return normalized


@app.post("/api/checklists")
async def save_checklists_db(payload: dict):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload invalido")
    normalized = _normalize_checklists_payload(payload)
    with CHECKLISTS_STORAGE_LOCK:
        CHECKLISTS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        updated_at = datetime.utcnow().isoformat()
        normalized["meta"] = {**(normalized.get("meta") or {}), "updatedAt": updated_at}
        CHECKLISTS_DB_FILE.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    _broadcast_checklists_update({"updatedAt": updated_at})
    return {"ok": True, "updatedAt": updated_at}


@app.get("/api/checklists/stream")
async def checklists_stream(request: Request):
    sub_q: queue.Queue = queue.Queue(maxsize=200)
    with CHECKLISTS_STREAM_LOCK:
        CHECKLISTS_STREAM_SUBSCRIBERS.append(sub_q)
        snapshot = list(CHECKLISTS_STREAM_BACKLOG)[-20:]

    async def event_stream():
        try:
            yield "retry: 1500\n\n"
            for item in snapshot:
                yield f"event: update\ndata: {item}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.to_thread(sub_q.get, True, 1.0)
                    yield f"event: update\ndata: {item}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with CHECKLISTS_STREAM_LOCK:
                try:
                    CHECKLISTS_STREAM_SUBSCRIBERS.remove(sub_q)
                except ValueError:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/administracion")
async def redirect_admin():
    return RedirectResponse(url="/administracion/index-panel.html")


@app.get("/administracion/")
async def redirect_admin_slash():
    return RedirectResponse(url="/administracion/index-panel.html")


def no_cache_file_response(path: Path, media_type: Optional[str] = None) -> FileResponse:
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return FileResponse(path, media_type=media_type, headers=headers)


@app.get("/administracion/index-panel.html")
def admin_index_panel_page():
    return no_cache_file_response(resolve_web_admin_file("index-panel.html"))


@app.get("/administracion/negocios_gestion.html")
def admin_negocios_gestion_page():
    return no_cache_file_response(resolve_web_admin_file("negocios_gestion.html"))


@app.get("/administracion/ip_log.html")
@app.get("/web/administracion/ip_log.html")
def admin_ip_log_page(request: Request, admin=Depends(get_admin_session)):
    referer = (request.headers.get("referer") or "").lower()
    fetch_dest = (request.headers.get("sec-fetch-dest") or "").lower()
    allowed_ref = (
        "/administracion/index-panel.html" in referer or
        "/web/administracion/index-panel.html" in referer or
        referer.rstrip("/").endswith("/administracion")
    )
    if not allowed_ref and fetch_dest != "iframe":
        raise HTTPException(status_code=403, detail="Acceso solo permitido desde el panel global")
    return no_cache_file_response(resolve_web_admin_file("ip_log.html"))


@app.get("/administracion/api/pve-console-url")
def admin_pve_console_url(
    admin=Depends(get_admin_session),
    node: Optional[str] = None,
    vmid: Optional[int] = None,
    vmname: Optional[str] = None,
):
    final_node = (node or PVE_NODE or "proxmox").strip()
    final_vmid = int(vmid or PVE_VMID or 102)
    final_vmname = (vmname or PVE_VMNAME or "ChatbotSERVER").strip() or "ChatbotSERVER"
    fallback_url = _build_proxmox_direct_url(final_node, final_vmid, final_vmname)
    try:
        url, pve_ticket = _build_proxmox_console_url(final_node, final_vmid, final_vmname)
        payload = {
            "url": url,
            "node": final_node,
            "vmid": final_vmid,
            "vmname": final_vmname,
            "mode": "ticket",
        }
        resp = JSONResponse(content=payload)
        # Cookie shared by host (no port scoping), so it can be sent to :8006 too.
        resp.set_cookie(
            key="PVEAuthCookie",
            value=pve_ticket,
            max_age=120,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
        )
        return resp
    except HTTPException as exc:
        logger.warning(
            "No se pudo generar ticket Proxmox (node=%s vmid=%s): %s",
            final_node,
            final_vmid,
            getattr(exc, "detail", str(exc)),
        )
        return {
            "url": fallback_url,
            "node": final_node,
            "vmid": final_vmid,
            "vmname": final_vmname,
            "mode": "direct",
            "warning": str(getattr(exc, "detail", "Error de ticket Proxmox")),
        }
    except Exception as exc:
        logger.exception("Error inesperado generando URL de consola Proxmox")
        return {
            "url": fallback_url,
            "node": final_node,
            "vmid": final_vmid,
            "vmname": final_vmname,
            "mode": "direct",
            "warning": f"Error inesperado: {exc}",
        }


@app.get("/administracion/api/ip-log/stream")
async def admin_ip_log_stream(request: Request, admin=Depends(get_admin_session)):
    sub_q: queue.Queue = queue.Queue(maxsize=800)
    with LOG_STREAM_LOCK:
        LOG_STREAM_SUBSCRIBERS.append(sub_q)
        snapshot = list(LOG_STREAM_BACKLOG)[-350:]

    async def event_stream():
        try:
            yield "retry: 1500\n\n"
            for line in snapshot:
                safe = str(line).replace("\r", "")
                yield f"data: {safe}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    line = await asyncio.to_thread(sub_q.get, True, 1.0)
                    safe = str(line).replace("\r", "")
                    yield f"data: {safe}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with LOG_STREAM_LOCK:
                try:
                    LOG_STREAM_SUBSCRIBERS.remove(sub_q)
                except ValueError:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/administracion/api/ssh/info")
def admin_ssh_info(request: Request):
    _require_local_or_admin_request(request)
    target = f"{ADMIN_SSH_USER}@{ADMIN_SSH_HOST}" if ADMIN_SSH_USER else ADMIN_SSH_HOST
    mode = ADMIN_TERMINAL_MODE
    if mode == "auto":
        mode = "local" if _is_local_admin_terminal_target(ADMIN_SSH_HOST) else "ssh"
    return {"host": ADMIN_SSH_HOST, "port": ADMIN_SSH_PORT, "user": ADMIN_SSH_USER, "target": target, "mode": mode}


@app.post("/administracion/api/backend/restart")
def admin_restart_backend(request: Request):
    _require_local_or_admin_request(request)
    service_name = "chatbot-frontend-backend.service"
    # Ejecutar en segundo plano para que pueda responder antes de reiniciar el propio servicio.
    cmd = (
        "nohup /bin/bash -lc "
        "\"sudo -n systemctl restart chatbot-frontend-backend.service\" "
        "> /tmp/chatbot-backend-restart.log 2>&1 &"
    )
    try:
        subprocess.Popen(
            ["/bin/bash", "-lc", cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo lanzar el reinicio: {exc}")
    return {
        "ok": True,
        "detail": f"Reinicio de {service_name} lanzado",
        "note": "Requiere sudo sin password para systemctl restart",
    }


@app.get("/administracion/api/backend/instance")
def admin_backend_instance(request: Request):
    _require_local_or_admin_request(request)
    return {"pid": os.getpid(), "started_at": BACKEND_STARTED_AT}


@app.get("/administracion/api/tse/state")
def admin_tse_state(request: Request):
    _require_local_or_admin_request(request)
    return _tse_active_state()


@app.get("/administracion/api/tse/terminal-action")
def admin_tse_terminal_action(request: Request):
    _require_local_or_admin_request(request)
    return _tse_next_terminal_action()


@app.post("/administracion/api/tse/toggle")
def admin_tse_toggle(request: Request):
    _require_local_or_admin_request(request)
    current = _tse_active_state()
    was_active = bool(current.get("active"))
    action = "stop" if was_active else "start"

    if action == "start":
        result = _tse_start()
        time.sleep(1.4)
    else:
        result = _tse_stop()
        time.sleep(0.9)

    after = _tse_active_state()
    return {
        "ok": True,
        "action": action,
        "before_active": was_active,
        "after_active": bool(after.get("active")),
        "before": current,
        "after": after,
        "result": result,
    }


@app.post("/administracion/api/tse/restart-services")
def admin_tse_restart_services(request: Request):
    _require_local_or_admin_request(request)
    cmd = str(TSE_RESTART_CMD or "").strip()
    if not cmd:
        raise HTTPException(status_code=500, detail="TSE_RESTART_CMD no configurado")
    res = _run_bash(cmd, cwd=TSE_WORKDIR, timeout=25)
    if res.returncode != 0:
        stderr = (res.stderr or "").strip()
        stdout = (res.stdout or "").strip()
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo reiniciar servicios TodoSevillaEste: {stderr or stdout or 'error'}",
        )
    return {"ok": True, "detail": "Servicios TodoSevillaEste reiniciados"}


@app.post("/administracion/api/agents/restart")
def admin_agents_restart(request: Request):
    _require_local_or_admin_request(request)
    cmd = str(AGENTS_RESTART_CMD or "").strip()
    if not cmd:
        raise HTTPException(status_code=500, detail="AGENTS_RESTART_CMD no configurado")
    res = _run_bash(cmd, cwd=TSE_WORKDIR, timeout=25)
    if res.returncode != 0:
        stderr = (res.stderr or "").strip()
        stdout = (res.stdout or "").strip()
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo reiniciar Backend IA: {stderr or stdout or 'error'}",
        )
    return {"ok": True, "detail": "Backend IA reiniciado"}


@app.websocket("/administracion/api/ssh/ws")
async def admin_ssh_ws(websocket: WebSocket):
    try:
        _require_local_or_admin_ws(websocket)
    except HTTPException:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    target = f"{ADMIN_SSH_USER}@{ADMIN_SSH_HOST}" if ADMIN_SSH_USER else ADMIN_SSH_HOST
    mode = ADMIN_TERMINAL_MODE
    if mode == "auto":
        mode = "local" if _is_local_admin_terminal_target(ADMIN_SSH_HOST) else "ssh"

    if mode == "local":
        cmd = [
            "/bin/bash",
            "-lic",
            "unset NO_COLOR; export TERM=xterm-256color COLORTERM=truecolor FORCE_COLOR_PROMPT=yes CLICOLOR=1; cd ~ && exec /bin/bash -li",
        ]
        intro = "Terminal local de 192.168.0.40 iniciada.\r\n\r\n"
    else:
        cmd = [
            "ssh",
            "-tt",
            "-o",
            f"StrictHostKeyChecking={ADMIN_SSH_STRICT_HOST_KEY}",
            "-o",
            "ServerAliveInterval=30",
            "-p",
            str(ADMIN_SSH_PORT),
            target,
        ]
        intro = (
            f"\r\nConectando a {target}:{ADMIN_SSH_PORT} ...\r\n"
            "Si te pide password o fingerprint, escribelo directamente.\r\n\r\n"
        )

    try:
        ADMIN_TERMINAL_SESSION.ensure_started(cmd, intro)
    except HTTPException as exc:
        await websocket.send_text(json.dumps({"type": "output", "data": f"\r\n[ERROR] {exc.detail}\r\n"}, ensure_ascii=False))
        await websocket.close(code=1011)
        return

    sub_q, snapshot = ADMIN_TERMINAL_SESSION.subscribe()

    async def forward_stdout_pty():
        try:
            for item in snapshot:
                await websocket.send_text(json.dumps({"type": "output", "data": item}, ensure_ascii=False))
            while True:
                try:
                    chunk = await asyncio.to_thread(sub_q.get, True, 1.0)
                except queue.Empty:
                    continue
                await websocket.send_text(json.dumps({"type": "output", "data": str(chunk)}, ensure_ascii=False))
        except Exception:
            pass

    stdout_task = asyncio.create_task(forward_stdout_pty())
    await websocket.send_text(json.dumps({"type": "output", "data": "\r\n[Sesion restaurada]\r\n"}, ensure_ascii=False))
    try:
        while True:
            raw = await websocket.receive_text()
            msg_type = "data"
            data = raw
            if raw and raw[:1] == "{":
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        msg_type = str(parsed.get("type") or "data")
                        if msg_type == "resize":
                            ADMIN_TERMINAL_SESSION.resize(int(parsed.get("rows") or 24), int(parsed.get("cols") or 80))
                            continue
                        if msg_type == "exec":
                            cmd = str(parsed.get("command") or "").strip()
                            if cmd:
                                if len(cmd) > 2000:
                                    cmd = cmd[:2000]
                                ADMIN_TERMINAL_SESSION.write(cmd + "\n")
                            continue
                        data = str(parsed.get("data") or "")
                except Exception:
                    data = raw
            ADMIN_TERMINAL_SESSION.write(data)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if stdout_task:
            stdout_task.cancel()
        ADMIN_TERMINAL_SESSION.unsubscribe(sub_q)


@app.get("/administracion/admin_negocios.html")
@app.get("/web/administracion/admin_negocios.html")
def admin_negocios_page(request: Request, admin=Depends(get_admin_session)):
    referer = (request.headers.get("referer") or "").lower()
    fetch_dest = (request.headers.get("sec-fetch-dest") or "").lower()
    allowed_ref = (
        "/administracion/index-panel.html" in referer or
        "/web/administracion/index-panel.html" in referer or
        referer.rstrip("/").endswith("/administracion")
    )
    if not allowed_ref and fetch_dest != "iframe":
        raise HTTPException(status_code=403, detail="Acceso solo permitido desde el panel global")
    return no_cache_file_response(resolve_web_admin_file("admin_negocios.html"))


@app.get("/administracion/admin_usuarios.html")
@app.get("/web/administracion/admin_usuarios.html")
def admin_usuarios_page(request: Request, admin=Depends(get_admin_session)):
    referer = (request.headers.get("referer") or "").lower()
    fetch_dest = (request.headers.get("sec-fetch-dest") or "").lower()
    allowed_ref = (
        "/administracion/index-panel.html" in referer or
        "/web/administracion/index-panel.html" in referer or
        referer.rstrip("/").endswith("/administracion")
    )
    if not allowed_ref and fetch_dest != "iframe":
        raise HTTPException(status_code=403, detail="Acceso solo permitido desde el panel global")
    return no_cache_file_response(resolve_web_admin_file("admin_usuarios.html"))


@app.get("/administracion/admin_reviews.html")
@app.get("/web/administracion/admin_reviews.html")
def admin_reviews_page(request: Request, admin=Depends(get_admin_session)):
    referer = (request.headers.get("referer") or "").lower()
    fetch_dest = (request.headers.get("sec-fetch-dest") or "").lower()
    allowed_ref = (
        "/administracion/index-panel.html" in referer or
        "/web/administracion/index-panel.html" in referer or
        referer.rstrip("/").endswith("/administracion")
    )
    if not allowed_ref and fetch_dest != "iframe":
        raise HTTPException(status_code=403, detail="Acceso solo permitido desde el panel global")
    return no_cache_file_response(resolve_web_admin_file("admin_reviews.html"))


@app.get("/administracion/admin_support.html")
@app.get("/web/administracion/admin_support.html")
def admin_support_page(request: Request, admin=Depends(get_admin_session)):
    referer = (request.headers.get("referer") or "").lower()
    fetch_dest = (request.headers.get("sec-fetch-dest") or "").lower()
    allowed_ref = (
        "/administracion/index-panel.html" in referer or
        "/web/administracion/index-panel.html" in referer or
        referer.rstrip("/").endswith("/administracion")
    )
    if not allowed_ref and fetch_dest != "iframe":
        raise HTTPException(status_code=403, detail="Acceso solo permitido desde el panel global")
    return no_cache_file_response(resolve_web_admin_file("admin_support.html"))


@app.get("/administracion/admin_versions.html")
@app.get("/web/administracion/admin_versions.html")
def admin_versions_page(request: Request, admin=Depends(get_admin_session)):
    referer = (request.headers.get("referer") or "").lower()
    fetch_dest = (request.headers.get("sec-fetch-dest") or "").lower()
    allowed_ref = (
        "/administracion/index-panel.html" in referer or
        "/web/administracion/index-panel.html" in referer or
        referer.rstrip("/").endswith("/administracion")
    )
    if not allowed_ref and fetch_dest != "iframe":
        raise HTTPException(status_code=403, detail="Acceso solo permitido desde el panel global")
    return no_cache_file_response(resolve_web_admin_file("admin_versions.html"))


@app.get("/administracion/admin_mails.html")
@app.get("/web/administracion/admin_mails.html")
def admin_mails_page(request: Request, admin=Depends(get_admin_session)):
    referer = (request.headers.get("referer") or "").lower()
    fetch_dest = (request.headers.get("sec-fetch-dest") or "").lower()
    allowed_ref = (
        "/administracion/index-panel.html" in referer or
        "/web/administracion/index-panel.html" in referer or
        referer.rstrip("/").endswith("/administracion")
    )
    if not allowed_ref and fetch_dest != "iframe":
        raise HTTPException(status_code=403, detail="Acceso solo permitido desde el panel global")
    return no_cache_file_response(resolve_web_admin_file("admin_mails.html"))


@app.get("/administracion/vendor/{path:path}")
def admin_vendor_asset(path: str, admin=Depends(get_admin_session)):
    return no_cache_file_response(resolve_web_admin_file(f"vendor/{path}"))


@app.get("/administracion/ui_admin.css")
@app.get("/web/administracion/ui_admin.css")
def admin_ui_css(admin=Depends(get_admin_session)):
    return no_cache_file_response(resolve_web_admin_file("ui_admin.css"))


@app.get("/administracion/ui_admin.js")
@app.get("/web/administracion/ui_admin.js")
def admin_ui_js(admin=Depends(get_admin_session)):
    return no_cache_file_response(resolve_web_admin_file("ui_admin.js"))


@app.get("/administracion/versiones/{path:path}")
def admin_versiones_asset(path: str, admin=Depends(get_admin_session)):
    return no_cache_file_response(resolve_web_admin_file(f"versiones/{path}"))


@app.get("/administracion/assets/{path:path}")
def admin_assets_asset(path: str, admin=Depends(get_admin_session)):
    return no_cache_file_response(resolve_web_admin_file(path))


@app.get("/administracion/pruebas")
@app.get("/administracion/pruebas/")
def admin_pruebas_index(admin=Depends(get_admin_session)):
    return no_cache_file_response(resolve_web_admin_file_with_mode("index-panel.html", mode="test"))


@app.get("/administracion/pruebas/{path:path}")
def admin_pruebas_asset(path: str, admin=Depends(get_admin_session)):
    return no_cache_file_response(resolve_web_admin_file_with_mode(path, mode="test"))


@app.post("/places/{place_id}/main_photo")
async def upload_main_photo(place_id: int, file: UploadFile = File(...), admin=Depends(get_admin_session)):
    """
    Sube la foto principal de un lugar y la convierte a WebP.
    """
    try:
        image = Image.open(file.file).convert("RGB")
        biz_dir = get_business_image_dir(place_id)
        output_path = biz_dir / "main.webp"
        image.save(output_path, "WEBP", quality=90)
        legacy_path = IMG_DIR / f"{place_id}.webp"
        image.save(legacy_path, "WEBP", quality=90)

        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        cursor = conn.cursor()
        cursor.execute("UPDATE places SET main_photo=%s WHERE public_id=%s",
                       (f"/web/img/businesses/{place_id}/main.webp", place_id))
        conn.commit()
        cursor.close()
        conn.close()

        return {"detail": "Imagen principal subida"}
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al procesar la imagen")


@app.post("/business/me/main_photo")
async def upload_my_business_main_photo(file: UploadFile = File(...), user=Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        image = Image.open(file.file).convert("RGB")
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        ensure_user_has_business_role(conn, int(user["id"]))
        managed_place_public_id = get_managed_place_public_id_for_user(conn, int(user["id"]))
        if not managed_place_public_id:
            raise HTTPException(status_code=403, detail="Cuenta sin negocio vinculado")
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT public_id FROM places WHERE public_id=%s LIMIT 1",
            (int(managed_place_public_id),)
        )
        place = cursor.fetchone()
        if not place:
            raise HTTPException(status_code=403, detail="Cuenta sin negocio vinculado")
        public_id = int(place["public_id"])
        biz_dir = get_business_image_dir(public_id)
        output_path = biz_dir / "main.webp"
        image.save(output_path, "WEBP", quality=90)
        legacy_path = IMG_DIR / f"{public_id}.webp"
        image.save(legacy_path, "WEBP", quality=90)
        cursor.execute(
            "UPDATE places SET main_photo=%s WHERE public_id=%s",
            (f"/web/img/businesses/{public_id}/main.webp", public_id)
        )
        conn.commit()
        return {"detail": "Foto principal actualizada"}
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="No se pudo actualizar la foto principal")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.post("/business/me/photos")
async def upload_my_business_extra_photo(file: UploadFile = File(...), user=Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        image = Image.open(file.file).convert("RGB")
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        ensure_user_has_business_role(conn, int(user["id"]))
        managed_place_public_id = get_managed_place_public_id_for_user(conn, int(user["id"]))
        if not managed_place_public_id:
            raise HTTPException(status_code=403, detail="Cuenta sin negocio vinculado")
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT public_id, photos FROM places WHERE public_id=%s LIMIT 1",
            (int(managed_place_public_id),)
        )
        place = cursor.fetchone()
        if not place:
            raise HTTPException(status_code=403, detail="Cuenta sin negocio vinculado")
        public_id = int(place["public_id"])
        existing_photos = []
        try:
            existing_photos = json.loads(place.get("photos") or "[]")
        except Exception:
            existing_photos = []
        biz_dir = get_business_image_dir(public_id)
        filename = f"extra_{datetime.now(SEVILLA_TZ).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(3)}.webp"
        output_path = biz_dir / filename
        image.save(output_path, "WEBP", quality=90)
        photo_url = f"/web/img/businesses/{public_id}/{filename}"
        existing_photos = [p for p in existing_photos if isinstance(p, str) and p.strip()]
        existing_photos.append(photo_url)
        cursor.execute(
            "UPDATE places SET photos=%s WHERE public_id=%s",
            (json.dumps(existing_photos), public_id)
        )
        conn.commit()
        return {"detail": "Foto añadida", "photo_url": photo_url}
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="No se pudo subir la foto")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.delete("/business/me/photos")
def delete_my_business_extra_photo(payload: DeleteBusinessPhotoBody, user=Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        target = (payload.photo_url or "").strip()
        if not target:
            raise HTTPException(status_code=400, detail="Falta photo_url")
        conn = mysql.connector.connect(**DB_WRITE_CONFIG)
        ensure_user_has_business_role(conn, int(user["id"]))
        managed_place_public_id = get_managed_place_public_id_for_user(conn, int(user["id"]))
        if not managed_place_public_id:
            raise HTTPException(status_code=403, detail="Cuenta sin negocio vinculado")
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT public_id, photos FROM places WHERE public_id=%s LIMIT 1",
            (int(managed_place_public_id),)
        )
        place = cursor.fetchone()
        if not place:
            raise HTTPException(status_code=403, detail="Cuenta sin negocio vinculado")
        public_id = int(place["public_id"])
        try:
            photos = json.loads(place.get("photos") or "[]")
        except Exception:
            photos = []
        if target not in photos:
            return {"detail": "Foto no encontrada en el negocio"}
        photos = [p for p in photos if p != target]
        cursor.execute(
            "UPDATE places SET photos=%s WHERE public_id=%s",
            (json.dumps(photos), public_id)
        )
        conn.commit()

        prefix = f"/web/img/businesses/{public_id}/"
        if target.startswith(prefix):
            file_path = BUSINESS_IMG_DIR / str(public_id) / target.split(prefix, 1)[1]
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
        return {"detail": "Foto eliminada"}
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="No se pudo eliminar la foto")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()




# ... (los demás endpoints de auth se mantienen igual) ...

# ------------------------------- FRONTEND -------------------------------
def _vue_dist_ready() -> bool:
    try:
        return VUE_DIST_INDEX.exists() and VUE_DIST_INDEX.is_file()
    except Exception:
        return False


def _safe_vue_dist_path(requested_path: str) -> Optional[Path]:
    rel = (requested_path or "").lstrip("/").strip()
    if not rel:
        return None
    target = (VUE_DIST_DIR / rel).resolve()
    try:
        target.relative_to(VUE_DIST_DIR.resolve())
    except Exception:
        return None
    return target


def _rack_frontend_root() -> Path:
    dist_index = RACK_FRONTEND_DIST_DIR / "index.html"
    if dist_index.exists() and dist_index.is_file():
        return RACK_FRONTEND_DIST_DIR
    return RACK_FRONTEND_DIR


def _rack_frontend_index() -> Path:
    root = _rack_frontend_root()
    index = root / "index.html"
    if index.exists() and index.is_file():
        return index
    raise HTTPException(status_code=404, detail="Rack frontend index.html no encontrado")


def _safe_rack_frontend_path(requested_path: str) -> Optional[Path]:
    rel = (requested_path or "").lstrip("/").strip()
    if not rel:
        return None
    root = _rack_frontend_root().resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except Exception:
        return None
    return target


def _rack_project_file(project_id: str) -> Path:
    cleaned = (project_id or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="project_id vacio")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{1,120}", cleaned):
        raise HTTPException(status_code=400, detail="project_id invalido")
    return RACK_BACKEND_DATA_DIR / f"{cleaned}.json"


@app.get("/rack/api/projects")
def rack_list_projects():
    items = []
    for file_path in sorted(RACK_BACKEND_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            project_id = str(data.get("id") or "").strip()
            name = str(data.get("name") or project_id or file_path.stem).strip() or file_path.stem
            if project_id:
                items.append({"id": project_id, "name": name})
        except Exception:
            continue
    return items


@app.get("/rack/api/projects/{project_id}")
def rack_get_project(project_id: str):
    file_path = _rack_project_file(project_id)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Proyecto corrupto")


@app.post("/rack/api/projects")
def rack_create_project(project: Dict[str, Any]):
    project_id = str((project or {}).get("id") or "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="El proyecto necesita campo id")
    file_path = _rack_project_file(project_id)
    if file_path.exists():
        raise HTTPException(status_code=409, detail="El proyecto ya existe")
    file_path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    return project


@app.put("/rack/api/projects/{project_id}")
def rack_save_project(project_id: str, project: Dict[str, Any]):
    payload_id = str((project or {}).get("id") or "").strip()
    if payload_id and payload_id != project_id:
        raise HTTPException(status_code=400, detail="project_id de URL y payload no coincide")
    normalized = dict(project or {})
    normalized["id"] = project_id
    file_path = _rack_project_file(project_id)
    file_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


# Sirve la página principal
@app.get("/")
def index():
    if _vue_dist_ready():
        return RedirectResponse(url="/app/", status_code=302)
    return RedirectResponse(url="/frontend.html", status_code=302)

@app.get("/login")
def login_page():
    return RedirectResponse(url="/login.html")

@app.get("/favicon.ico")
def favicon():
    return FileResponse(WEB_DIR / "icono" / "tsev2.png")

@app.get("/web/auth/login.htmlredirect{tail:path}")
def fix_legacy_login_redirect(request: Request, tail: str = ""):
    raw = (tail or "").lstrip("=")
    if not raw and request.url.query:
        raw = request.url.query
        if raw.startswith("redirect="):
            raw = raw[len("redirect="):]
    target = unquote(raw) if raw else str(request.base_url).rstrip("/") + "/"
    return RedirectResponse(
        url=f"/login.html?redirect={quote(target, safe='')}",
        status_code=307
    )

@app.get("/web/auth/register.htmlredirect{tail:path}")
def fix_legacy_register_redirect(request: Request, tail: str = ""):
    raw = (tail or "").lstrip("=")
    if not raw and request.url.query:
        raw = request.url.query
        if raw.startswith("redirect="):
            raw = raw[len("redirect="):]
    target = unquote(raw) if raw else str(request.base_url).rstrip("/") + "/"
    return RedirectResponse(
        url=f"/register.html?redirect={quote(target, safe='')}",
        status_code=307
    )


@app.get("/app")
@app.get("/app/")
def app_spa_index():
    if _vue_dist_ready():
        return FileResponse(VUE_DIST_INDEX, media_type="text/html; charset=utf-8")
    return RedirectResponse(url="/frontend.html", status_code=302)


@app.get("/app/{asset_path:path}")
def app_spa_assets(asset_path: str):
    if not _vue_dist_ready():
        return RedirectResponse(url="/frontend.html", status_code=302)
    target = _safe_vue_dist_path(asset_path)
    if target and target.exists() and target.is_file():
        return FileResponse(target)
    # SPA fallback for client-side routes.
    return FileResponse(VUE_DIST_INDEX, media_type="text/html; charset=utf-8")


@app.get("/rack")
@app.get("/rack/")
@app.get("/rack/index.html")
@app.get("/rack/frontend/index.html")
@app.get("/herramientas/rack")
@app.get("/herramientas/rack/")
@app.get("/herramientas/rack/index.html")
@app.get("/herramientas/rack/frontend/index.html")
def rack_spa_index():
    return FileResponse(_rack_frontend_index(), media_type="text/html; charset=utf-8")


@app.get("/rack/{asset_path:path}")
def rack_spa_assets(asset_path: str):
    target = _safe_rack_frontend_path(asset_path)
    if target and target.exists() and target.is_file():
        return FileResponse(target)
    return FileResponse(_rack_frontend_index(), media_type="text/html; charset=utf-8")


@app.get("/herramientas/rack/{asset_path:path}")
def rack_spa_assets_herramientas(asset_path: str):
    target = _safe_rack_frontend_path(asset_path)
    if target and target.exists() and target.is_file():
        return FileResponse(target)
    return FileResponse(_rack_frontend_index(), media_type="text/html; charset=utf-8")

# Rutas públicas limpias (sin /frontend en URL)
app.mount("/icono", StaticFiles(directory=WEB_DIR / "icono"), name="icono")
app.mount("/img", StaticFiles(directory=WEB_DIR / "img"), name="img")
app.mount("/creador_qr", StaticFiles(directory=WEB_DIR / "creador_qr"), name="creador_qr")
app.mount("/downloads", StaticFiles(directory=WEB_DIR / "downloads"), name="downloads")
app.mount("/user_avatars", StaticFiles(directory=AVATAR_DIR), name="user_avatars_public")
app.mount("/account", StaticFiles(directory=BASE_DIR / "account"), name="account_public")
app.mount("/manuales", StaticFiles(directory=WEB_DIR / "frontend" / "herramientas" / "manuales", html=True), name="manuales_public")
app.mount("/planos", StaticFiles(directory=WEB_DIR / "frontend" / "herramientas" / "planos", html=True), name="planos_public")
app.mount("/checklists", StaticFiles(directory=WEB_DIR / "frontend" / "herramientas" / "checklists", html=True), name="checklists_public")
app.mount("/herramientas", StaticFiles(directory=WEB_DIR / "frontend" / "herramientas", html=True), name="herramientas_public")
app.mount("/rack2", StaticFiles(directory=WEB_DIR / "frontend" / "rack2", html=True), name="rack2_public")
app.mount("/frontend", StaticFiles(directory=WEB_DIR / "frontend"), name="frontend_legacy")
app.mount("/administracion/assets", StaticFiles(directory=WEB_DIR / "administracion"), name="administracion_assets")

# Compatibilidad local (/web se permite en local; fuera se filtra por middleware)
app.mount("/web", StaticFiles(directory="web"), name="web")

@app.exception_handler(404)
async def redirect_unknown_paths(request: Request, exc: HTTPException):
    path = (request.url.path or "").lower()
    # Mantener 404 para rutas de API/administración/activos
    if path.startswith((
        "/api",
        "/admin",
        "/administracion",
        "/web",
        "/public",
        "/frontend",
        "/static",
        "/img",
        "/icono",
        "/downloads",
        "/manuales",
        "/planos",
        "/checklists",
        "/rack2",
        "/account",
        "/user_avatars",
    )):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    # Para cualquier otra URL inexistente, redirigir a frontend.html
    return RedirectResponse(url="/frontend.html", status_code=302)

app.include_router(router)
