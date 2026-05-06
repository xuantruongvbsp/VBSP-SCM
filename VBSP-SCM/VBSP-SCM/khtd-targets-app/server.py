import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_PATH = os.path.join(BASE_DIR, "store.json")


def _read_json_body(handler: BaseHTTPRequestHandler):
    length = int(handler.headers.get("content-length", "0") or "0")
    raw = handler.rfile.read(length) if length > 0 else b""
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _load_store():
    if not os.path.exists(STORE_PATH):
        return {"periods": [], "targets": {}, "lastSync": {"status": "never", "at": None}}
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_store(store):
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def _json(handler: BaseHTTPRequestHandler, status: int, data):
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", "application/json; charset=utf-8")
    handler.send_header("content-length", str(len(payload)))
    handler.send_header("access-control-allow-origin", "*")
    handler.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
    handler.send_header("access-control-allow-headers", "content-type")
    handler.end_headers()
    handler.wfile.write(payload)


def _text(handler: BaseHTTPRequestHandler, status: int, content_type: str, text: str):
    payload = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", content_type)
    handler.send_header("content-length", str(len(payload)))
    handler.send_header("access-control-allow-origin", "*")
    handler.end_headers()
    handler.wfile.write(payload)


def _guess_content_type(path: str):
    lower = path.lower()
    if lower.endswith(".html"):
        return "text/html; charset=utf-8"
    if lower.endswith(".js"):
        return "text/javascript; charset=utf-8"
    if lower.endswith(".css"):
        return "text/css; charset=utf-8"
    if lower.endswith(".json"):
        return "application/json; charset=utf-8"
    if lower.endswith(".svg"):
        return "image/svg+xml"
    if lower.endswith(".png"):
        return "image/png"
    return "application/octet-stream"


def _safe_join(base: str, url_path: str):
    rel = url_path.lstrip("/")
    rel = rel.replace("..", "")
    return os.path.join(base, rel)


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
        self.send_header("access-control-allow-headers", "content-type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/status":
            store = _load_store()
            return _json(self, 200, {"periods": store.get("periods", []), "lastSync": store.get("lastSync", {})})

        if path == "/api/targets":
            qs = parse_qs(parsed.query)
            unit_type = (qs.get("unitType") or [""])[0]
            period = (qs.get("period") or [""])[0]
            store = _load_store()
            period_block = (store.get("targets") or {}).get(period) or {}
            rows = period_block.get(unit_type) or []
            return _json(self, 200, {"rows": rows, "periods": store.get("periods", [])})

        if path.startswith("/src/") or path.startswith("/assets/") or path == "/index.html":
            abs_path = _safe_join(BASE_DIR, path)
            if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
                return _text(self, 404, "text/plain; charset=utf-8", "Not found")
            with open(abs_path, "rb") as f:
                data = f.read()
            ctype = _guess_content_type(abs_path)
            self.send_response(200)
            self.send_header("content-type", ctype)
            self.send_header("content-length", str(len(data)))
            self.send_header("access-control-allow-origin", "*")
            self.end_headers()
            self.wfile.write(data)
            return

        abs_index = os.path.join(BASE_DIR, "index.html")
        if os.path.exists(abs_index):
            with open(abs_index, "r", encoding="utf-8") as f:
                return _text(self, 200, "text/html; charset=utf-8", f.read())
        return _text(self, 404, "text/plain; charset=utf-8", "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/sheets/preview":
            body = _read_json_body(self) or {}
            sheet_url = (body.get("sheetUrl") or "").strip()
            sheet_name = (body.get("sheetName") or "").strip()
            period = (body.get("period") or "").strip()

            errors = []
            if not sheet_url:
                errors.append({"rowIndex": -1, "message": "Thiếu sheetUrl"})
            if not sheet_name:
                errors.append({"rowIndex": -1, "message": "Thiếu sheetName"})
            if not period:
                errors.append({"rowIndex": -1, "message": "Thiếu period"})

            store = _load_store()
            sample_period = period if period in (store.get("targets") or {}) else "2026-Q2"
            sample = ((store.get("targets") or {}).get(sample_period) or {}).get("CN") or []
            preview_rows = sample[:10]
            preview = {
                "period": period,
                "source": {"sheetUrl": sheet_url, "sheetName": sheet_name},
                "rows": preview_rows,
                "errors": errors,
            }

            store["lastSync"] = {
                "status": "success" if len(errors) == 0 else "error",
                "at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                "sheetUrl": sheet_url,
                "sheetName": sheet_name,
                "period": period,
            }
            _save_store(store)
            return _json(self, 200, {"preview": preview})

        if path == "/api/targets/save":
            body = _read_json_body(self) or {}
            period = (body.get("period") or "").strip()
            unit_type = (body.get("unitType") or "").strip()
            rows = body.get("rows") or []
            if not period or unit_type not in ("CN", "PGD"):
                return _json(self, 400, {"success": False, "message": "Thiếu period hoặc unitType"})
            if not isinstance(rows, list):
                return _json(self, 400, {"success": False, "message": "rows không hợp lệ"})

            normalized = []
            for r in rows:
                try:
                    target_value = float(r.get("targetValue"))
                except Exception:
                    target_value = 0.0
                normalized.append(
                    {
                        "period": period,
                        "unitType": unit_type,
                        "unitCode": str(r.get("unitCode") or "").strip(),
                        "unitName": str(r.get("unitName") or "").strip(),
                        "level": str(r.get("level") or "").strip(),
                        "parentUnitCode": r.get("parentUnitCode"),
                        "targetValue": target_value,
                    }
                )

            store = _load_store()
            store.setdefault("targets", {})
            store["targets"].setdefault(period, {})
            store["targets"][period][unit_type] = normalized
            if period not in store.get("periods", []):
                store.setdefault("periods", []).append(period)
            _save_store(store)
            return _json(self, 200, {"success": True, "message": "OK"})

        return _json(self, 404, {"success": False, "message": "Not found"})


def main():
    host = os.environ.get("KHTD_HOST", "127.0.0.1")
    port = int(os.environ.get("KHTD_PORT", "5174"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"KHTD demo server running at http://{host}:{port}/")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
