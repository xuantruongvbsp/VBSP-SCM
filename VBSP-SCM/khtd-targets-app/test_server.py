import json
import threading
import time
import urllib.request


def _req(method, url, body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as res:
        raw = res.read().decode("utf-8")
        return res.status, json.loads(raw)


def run():
    from server import Handler
    from http.server import ThreadingHTTPServer

    host = "127.0.0.1"
    port = 5179
    httpd = ThreadingHTTPServer((host, port), Handler)

    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    time.sleep(0.2)

    status, data = _req("GET", f"http://{host}:{port}/api/status")
    assert status == 200
    assert "periods" in data

    status, data = _req(
        "POST",
        f"http://{host}:{port}/api/sheets/preview",
        {"sheetUrl": "https://docs.google.com/spreadsheets/d/demo", "sheetName": "KHTD", "period": "2026-Q2"},
    )
    assert status == 200
    assert "preview" in data

    status, data = _req("GET", f"http://{host}:{port}/api/targets?unitType=CN&period=2026-Q2")
    assert status == 200
    assert isinstance(data.get("rows"), list)

    rows = data.get("rows")
    if rows:
        rows[0]["targetValue"] = 123.0

    status, data = _req("POST", f"http://{host}:{port}/api/targets/save", {"period": "2026-Q2", "unitType": "CN", "rows": rows})
    assert status == 200
    assert data.get("success") is True

    httpd.shutdown()


if __name__ == "__main__":
    run()

