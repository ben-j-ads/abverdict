"""Local web interface: `abverdict serve`.

Stdlib only. Binds to localhost, serves the static UI from abverdict/web and a
tiny JSON API (`/api/plan`, `/api/test`) that wraps the same functions the CLI uses.
Nothing leaves your machine.
"""
from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .io import read_csv_text
from .planning import conversion_n_per_arm, continuous_n_per_arm, make_plan
from .report import plan_to_dict, report_to_dict
from .verdict import Arm, analyze

WEB = Path(__file__).parent / "web"
MAX_BODY = 1_000_000
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def _num(body: dict, key: str, default=None, cast=float):
    v = body.get(key, default)
    if v in (None, ""):
        return default
    try:
        return cast(v)
    except (TypeError, ValueError):
        raise ValueError(f"'{key}' must be a number") from None


def handle_plan(body: dict) -> dict:
    arms = _num(body, "arms", 2, int)
    alpha = _num(body, "alpha", 0.05)
    power = _num(body, "power", 0.8)
    comparisons = max(arms - 1, 1)
    mde = _num(body, "mde")
    if mde is None:
        raise ValueError("'mde' is required")
    if body.get("metric") == "continuous":
        sd = _num(body, "sd")
        if sd is None:
            raise ValueError("'sd' is required for a continuous metric")
        n, kind = continuous_n_per_arm(sd, mde, alpha, power, comparisons), "continuous"
    else:
        baseline = _num(body, "baseline")
        if baseline is None:
            raise ValueError("'baseline' is required")
        n = conversion_n_per_arm(baseline, mde, relative=not body.get("absolute"),
                                 alpha=alpha, power=power, comparisons=comparisons)
        kind = "conversion"
    return plan_to_dict(make_plan(n, kind, arms, alpha, power, _num(body, "daily_traffic")))


def handle_test(body: dict) -> dict:
    days = _num(body, "days", None, int)
    if body.get("csv"):
        arms, file_days = read_csv_text(body["csv"], (body.get("control") or None))
        days = days or file_days
    else:
        arms = []
        for row in body.get("arms") or []:
            name = str(row.get("name", "")).strip()
            if not name:
                raise ValueError("every variant needs a name")
            arms.append(Arm(name, _num(row, "n", None, int) or 0, conversions=_num(row, "conversions", None, int)))
        if any(a.conversions is None for a in arms):
            raise ValueError("every variant needs a conversion count")
    mde = _num(body, "mde")
    if mde is not None and arms and not body.get("absolute"):
        base = arms[0].rate if arms[0].conversions is not None else abs(arms[0].mean)
        mde *= base  # the UI sends a relative lift (0.05 = 5%)
    split = body.get("split")
    split = [float(x) for x in str(split).replace(":", "/").split("/")] if split else None
    report = analyze(arms, alpha=_num(body, "alpha", 0.05), planned_n=_num(body, "planned_n", None, int),
                     days=days, looks=_num(body, "looks", 1, int), mde=mde, split=split)
    return report_to_dict(report)


API = {"/api/plan": handle_plan, "/api/test": handle_test}
STATIC = {"/": "index.html"}


class Handler(BaseHTTPRequestHandler):
    server_version = "abverdict"

    def log_message(self, *args):  # keep the terminal quiet
        pass

    def _host_ok(self) -> bool:
        # Refuse requests whose Host isn't localhost (DNS-rebinding protection).
        host = self.headers.get("Host") or ""
        name = host.split("]")[0] + "]" if host.startswith("[") else host.rsplit(":", 1)[0]
        return name in LOCAL_HOSTS

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "forbidden host"})
        path = self.path.split("?", 1)[0]
        rel = STATIC.get(path, path.lstrip("/"))
        target = (WEB / rel).resolve()
        if WEB.resolve() not in target.parents or not target.is_file():
            return self._json(404, {"error": "not found"})
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".ttf":
            ctype = "font/ttf"
        self._send(200, target.read_bytes(), ctype)

    def do_POST(self):
        if not self._host_ok():
            return self._json(403, {"error": "forbidden host"})
        fn = API.get(self.path.split("?", 1)[0])
        if fn is None:
            return self._json(404, {"error": "not found"})
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._json(415, {"error": "send application/json"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._json(413, {"error": "request too large"})
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("expected a JSON object")
            self._json(200, fn(body))
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            self._json(400, {"error": str(e) or "bad request"})


def make_server(port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port: int = 8765, open_browser: bool = True) -> None:
    httpd = make_server(port)
    url = f"http://localhost:{httpd.server_address[1]}/"
    print(f"abverdict is running at {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()
