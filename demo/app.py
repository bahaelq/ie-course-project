#!/usr/bin/env python3
"""Minimal Demo-Server für die Information-Extraction UI.

- Keine externen Abhängigkeiten außer stdlib + ie_course (KISSKI).
- Start:  .venv/bin/python demo/app.py  (oder: python demo/app.py)
- Default: http://localhost:8000
- API:
    POST /api/extract  {text: "..."}
    GET  /api/config
    GET  /api/examples
    GET  /health

Nutzt ausschließlich extractor.py, welche wiederum ie_course.kisski_client wiederverwendet.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for p in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

DEMO_DIR = Path(__file__).resolve().parent
STATIC_DIR = DEMO_DIR / "static"

# Import nach Pfad-Setup
try:
    from demo.extractor import extract_job_ad, get_config_status  # type: ignore
    from demo.examples import EXAMPLES  # type: ignore
except ImportError:
    # Fallback wenn als `python demo/app.py` direkt
    import importlib.util

    spec = importlib.util.spec_from_file_location("extractor", DEMO_DIR / "extractor.py")
    assert spec and spec.loader
    ext_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ext_mod)  # type: ignore
    extract_job_ad = ext_mod.extract_job_ad  # type: ignore
    get_config_status = ext_mod.get_config_status  # type: ignore

    spec2 = importlib.util.spec_from_file_location("examples", DEMO_DIR / "examples.py")
    assert spec2 and spec2.loader
    ex_mod = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(ex_mod)  # type: ignore
    EXAMPLES = ex_mod.EXAMPLES  # type: ignore

MAX_BODY = 2 * 1024 * 1024  # 2 MB für JSON
MAX_UPLOAD = 9 * 1024 * 1024  # 9 MB für Upload (8 MB File + Overhead)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Schlichtes Logging ohne Secrets
        sys.stdout.write(f"[{self.client_address[0]}] {format % args}\n")

    def _set_headers(self, status: int = 200, content_type: str = "application/json", extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204, "text/plain")
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # --- API routes ---
        if path == "/api/config":
            data = get_config_status()
            self._set_headers(200, "application/json")
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/examples":
            # nur text + label, kein Secret
            payload = [{"id": ex["id"], "label": ex["label"], "short": ex["short"], "text": ex["text"]} for ex in EXAMPLES]
            self._set_headers(200, "application/json")
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/health":
            self._set_headers(200, "application/json")
            self.wfile.write(json.dumps({"status": "ok"}, ensure_ascii=False).encode())
            return

        # --- Static ---
        if path == "/" or path == "/index.html":
            file_path = STATIC_DIR / "index.html"
        else:
            # Sicherheits-Check: nur unter STATIC_DIR
            rel = path.lstrip("/")
            # Entferne query
            rel = rel.split("?")[0]
            # Blocke ".."
            if ".." in rel or rel.startswith("demo/"):
                self._set_headers(404, "text/plain; charset=utf-8")
                self.wfile.write(b"Not found")
                return
            file_path = STATIC_DIR / rel

        if file_path.exists() and file_path.is_file():
            ctype, _ = mimetypes.guess_type(str(file_path))
            if ctype is None:
                ctype = "application/octet-stream"
            # Text files als utf-8
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            self._set_headers(200, ctype)
            self.wfile.write(file_path.read_bytes())
            return

        # Fallback: für SPA – alles andere auf index.html wenn nicht api
        if not path.startswith("/api/"):
            fallback = STATIC_DIR / "index.html"
            if fallback.exists():
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(fallback.read_bytes())
                return

        self._set_headers(404, "application/json")
        self.wfile.write(json.dumps({"error": "Not found"}, ensure_ascii=False).encode())

    def _handle_extract(self):
        length = int(self.headers.get("content-length", 0) or 0)
        if length > MAX_BODY:
            self._set_headers(413, "application/json")
            self.wfile.write(json.dumps({"error": "Payload zu groß"}, ensure_ascii=False).encode())
            return
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._set_headers(400, "application/json")
            self.wfile.write(json.dumps({"error": "Ungültiges JSON"}, ensure_ascii=False).encode())
            return

        text = body.get("text", "")
        if not isinstance(text, str):
            self._set_headers(400, "application/json")
            self.wfile.write(json.dumps({"error": "Field 'text' muss ein String sein"}, ensure_ascii=False).encode())
            return

        # Extraction (nutzt bestehende Pipeline)
        try:
            result, error, diag = extract_job_ad(text)
        except Exception as exc:  # pragma: no cover
            # Nie Stacktrace an Client, nur Meldung loggen
            print(f"[extract] exception: {exc}", file=sys.stderr)
            self._set_headers(500, "application/json")
            self.wfile.write(json.dumps({"error": "Interner Fehler bei der Analyse. Bitte erneut versuchen."}, ensure_ascii=False).encode())
            return

        if error is not None:
            # 400 für User-Fehler, 502 für Upstream
            # config_missing -> 503 mit Hinweis
            is_config = diag is not None and isinstance(diag, dict) and "missing" in diag
            status = 503 if is_config else 400
            # Wenn KISSKI 500/599 etc., bleibt 400-Anzeige aber wir geben diag nicht nach außen außer Statuscode
            # Für Demo: error immer user-lesbar
            self._set_headers(status, "application/json")
            payload = {"error": error}
            # Diag nur für Debugging, aber keine Secrets
            if diag and not is_config:
                # filter Secrets
                safe_diag = {k: v for k, v in diag.items() if k not in ("api_key", "key")}
                payload["diag"] = safe_diag
            elif is_config:
                payload["missing"] = diag.get("missing")  # type: ignore
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode())
            return

        # Erfolg
        assert result is not None
        response = {
            "entities": result.get("entities"),
            "spans": result.get("spans"),
            "json": result.get("json"),
            "meta": result.get("meta"),
        }
        self._set_headers(200, "application/json")
        self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode("utf-8"))

    def _handle_upload(self):
        # Sicherheits-Checks: Content-Type muss multipart sein, Größe limitiert
        ctype = self.headers.get("content-type", "")
        if "multipart/form-data" not in ctype:
            self._set_headers(400, "application/json")
            self.wfile.write(json.dumps({"error": "Ungültiger Content-Type. Bitte als FormData senden."}, ensure_ascii=False).encode())
            return

        length = int(self.headers.get("content-length", 0) or 0)
        if length > MAX_UPLOAD:
            self._set_headers(413, "application/json")
            self.wfile.write(json.dumps({"error": "Datei zu groß. Maximale Größe: 8 MB."}, ensure_ascii=False).encode())
            return
        if length == 0:
            self._set_headers(400, "application/json")
            self.wfile.write(json.dumps({"error": "Keine Datei empfangen."}, ensure_ascii=False).encode())
            return

        # Multipart manuell parsen (ohne cgi – entfernt in Python 3.13)
        try:
            import re as _re

            raw = self.rfile.read(length)
            # Boundary extrahieren
            m = _re.search(r'boundary="?([^";\s]+)"?', ctype)
            if not m:
                self._set_headers(400, "application/json")
                self.wfile.write(json.dumps({"error": "Kein Boundary gefunden."}, ensure_ascii=False).encode())
                return
            boundary = m.group(1).encode("utf-8")
            # Split auf boundary
            # raw ist: --boundary\r\n headers\r\n\r\n data \r\n--boundary-- ...
            parts = raw.split(b"--" + boundary)
            filename = None
            file_data = None
            for part in parts:
                if not part or part == b"--" or part == b"--\r\n":
                    continue
                # part beginnt mit \r\n, dann Header
                # Suche \r\n\r\n als Header-Ende
                if b"\r\n\r\n" not in part:
                    continue
                header_block, body = part.split(b"\r\n\r\n", 1)
                # body endet mit \r\n vor nächstem Boundary – entferne trailing \r\n
                if body.endswith(b"\r\n"):
                    body = body[:-2]
                # Prüfe ob dies das file-Feld ist
                header_text = header_block.decode("utf-8", errors="ignore")
                if 'name="file"' not in header_text and "name='file'" not in header_text:
                    continue
                # Filename extrahieren
                fn_match = _re.search(r'filename="?([^";\r\n]+)"?', header_text)
                if fn_match:
                    filename = fn_match.group(1)
                else:
                    filename = "upload"
                file_data = body
                break

            if file_data is None:
                self._set_headers(400, "application/json")
                self.wfile.write(json.dumps({"error": "Kein Feld 'file' gefunden."}, ensure_ascii=False).encode())
                return
            if filename is None:
                filename = "upload"

            # file_data ist bereits bytes (kann leer sein)

        except Exception as exc:
            print(f"[upload] parse error: {exc}", file=sys.stderr)
            self._set_headers(400, "application/json")
            self.wfile.write(json.dumps({"error": "Datei konnte nicht gelesen werden. Die Datei ist möglicherweise beschädigt."}, ensure_ascii=False).encode())
            return

        # Extraktion – import hier, um zirkuläre Imports zu vermeiden
        try:
            # lazy import
            try:
                from demo.file_extract import extract_text_from_upload  # type: ignore
            except ImportError:
                import importlib.util as _ilu

                spec = _ilu.spec_from_file_location("file_extract", DEMO_DIR / "file_extract.py")
                assert spec and spec.loader
                fe_mod = _ilu.module_from_spec(spec)
                spec.loader.exec_module(fe_mod)  # type: ignore
                extract_text_from_upload = fe_mod.extract_text_from_upload  # type: ignore

            text, err, meta = extract_text_from_upload(filename, file_data)  # type: ignore
        except Exception as exc:
            print(f"[upload] extraction error: {exc}", file=sys.stderr)
            self._set_headers(500, "application/json")
            self.wfile.write(json.dumps({"error": "Datei konnte nicht gelesen werden."}, ensure_ascii=False).encode())
            return

        if err is not None:
            # Professionelle Fehlermeldungen je nach Grund, Status 400
            self._set_headers(400, "application/json")
            # meta enthält filename/size für UI-Anzeige, aber nicht den Text
            safe_meta = {k: v for k, v in (meta or {}).items() if k in ("filename", "size", "ext", "size_human")}
            self.wfile.write(json.dumps({"error": err, "meta": safe_meta}, ensure_ascii=False).encode())
            return

        # Erfolg – nur Text und Meta zurück, niemals Pfade/Secrets
        assert text is not None
        # Kürze nicht, aber sende Längeninfo
        safe_meta = {k: v for k, v in (meta or {}).items() if k in ("filename", "size", "ext", "size_human")}
        safe_meta["chars"] = len(text)
        safe_meta["words"] = len(text.split())
        self._set_headers(200, "application/json")
        self.wfile.write(json.dumps({"text": text, "meta": safe_meta}, ensure_ascii=False).encode("utf-8"))

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/extract":
            return self._handle_extract()
        if parsed.path == "/api/upload":
            return self._handle_upload()
        self._set_headers(404, "application/json")
        self.wfile.write(json.dumps({"error": "Not found"}, ensure_ascii=False).encode())
        return


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Job Information Extractor – Demo UI")
    p.add_argument("--port", type=int, default=8000, help="Port (default 8000)")
    p.add_argument("--host", type=str, default="127.0.0.1", help="Host (default 127.0.0.1)")
    return p.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    host, port = args.host, args.port

    # Versuche Port, bei EADDRINUSE nächsten probieren
    last_exc = None
    for try_port in [port, 8001, 8002, 8501, 3000]:
        try:
            server_address = (host, try_port)
            httpd = ThreadingHTTPServer(server_address, Handler)
            port = try_port
            break
        except OSError as exc:
            last_exc = exc
            continue
    else:
        print(f"Konnte keinen Port öffnen: {last_exc}", file=sys.stderr)
        return 1

    url = f"http://{host}:{port}"
    print("\n" + "="*64)
    print(" Job Information Extractor – Demo UI")
    print("="*64)
    print(f" ➜  Local:   {url}")
    print(f" ➜  Health:  {url}/health")
    print(f" ➜  API:     {url}/api/extract (POST)")
    print(f" ➜  Static:  {STATIC_DIR}")
    print("")
    print(" KISSKI-Status:")
    try:
        cfg = get_config_status()
        if cfg["configured"]:
            print(f"  ✓ konfiguriert (model={cfg['model']}, base_url={cfg['base_url']})")
        else:
            print(f"  ✗ fehlend: {', '.join(cfg['missing']) if cfg['missing'] else 'unbekannt'}")
            print("    → .env nach .env.example einrichten")
    except Exception as e:
        print(f"  ? Konnte Config nicht prüfen: {e}")
    print("")
    print(" Beenden mit Ctrl+C")
    print("="*64 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down…")
        httpd.shutdown()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
