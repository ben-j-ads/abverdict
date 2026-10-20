import json
import threading
import unittest
import urllib.error
import urllib.request

from abverdict.server import make_server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = make_server(0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def post(self, path, body, headers=None):
        req = urllib.request.Request(self.base + path, json.dumps(body).encode(),
                                     {"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def get(self, path, headers=None):
        req = urllib.request.Request(self.base + path, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read(), e.headers

    def test_serves_ui_and_assets(self):
        code, body, h = self.get("/")
        self.assertEqual(code, 200)
        self.assertIn(b"did it win?", body)
        self.assertEqual(self.get("/app.js")[0], 200)
        self.assertEqual(self.get("/tokens.css")[0], 200)
        code, _, h = self.get("/fonts/Archivo-Bold.ttf")
        self.assertEqual((code, h["Content-Type"]), (200, "font/ttf"))

    def test_no_path_traversal(self):
        for p in ("/../server.py", "/..%2fserver.py", "/fonts/../../cli.py", "/nope"):
            self.assertEqual(self.get(p)[0], 404, p)

    def test_rejects_foreign_host(self):
        self.assertEqual(self.get("/", {"Host": "evil.example"})[0], 403)
        code, _ = self.post("/api/test", {}, {"Host": "evil.example"})
        self.assertEqual(code, 403)

    def test_api_test_arms(self):
        code, r = self.post("/api/test", {
            "arms": [{"name": "A", "conversions": 5000, "n": 100000}, {"name": "B", "conversions": 5400, "n": 100000}],
            "planned_n": 100000, "days": 14})
        self.assertEqual(code, 200)
        self.assertEqual(r["overall"], "WINNER")
        self.assertEqual({c["name"] for c in r["checks"]}, {"traffic split", "planned sample", "run length", "peeking", "variants"})

    def test_api_test_csv_and_mde(self):
        csv_text = "variant,visitors,conversions\nA,100000,5000\nB,100000,5010\n"
        code, r = self.post("/api/test", {"csv": csv_text, "planned_n": 100000, "mde": 0.1})
        self.assertEqual(code, 200)
        self.assertEqual(r["overall"], "NO MEANINGFUL DIFFERENCE")
        self.assertAlmostEqual(r["mde"], 0.005)

    def test_api_test_values_csv(self):
        rows = ["variant,value"] + [f"A,{10 + i % 5}" for i in range(200)] + [f"B,{13 + i % 5}" for i in range(200)]
        code, r = self.post("/api/test", {"csv": "\n".join(rows), "planned_n": 200})
        self.assertEqual((code, r["overall"]), (200, "WINNER"))

    def test_api_plan(self):
        code, r = self.post("/api/plan", {"metric": "conversion", "baseline": 0.05, "mde": 0.1, "daily_traffic": 2000})
        self.assertEqual((code, r["n_per_arm"], r["days"]), (200, 31234, 35))
        code, r = self.post("/api/plan", {"metric": "continuous", "sd": 10, "mde": 2})
        self.assertEqual((code, r["n_per_arm"]), (200, 393))

    def test_bad_requests_get_json_errors(self):
        self.assertEqual(self.post("/api/test", {"arms": [{"name": "A", "conversions": 1, "n": 10}]})[0], 400)
        self.assertEqual(self.post("/api/test", {"csv": "nonsense"})[0], 400)
        self.assertEqual(self.post("/api/plan", {"metric": "conversion", "baseline": 2, "mde": 0.1})[0], 400)
        self.assertEqual(self.post("/api/plan", {"mde": "abc", "baseline": 0.05})[0], 400)
        self.assertEqual(self.post("/api/nope", {})[0], 404)
        req = urllib.request.Request(self.base + "/api/test", b"x=1", {"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        cm.exception.close()
        self.assertEqual(cm.exception.code, 415)


if __name__ == "__main__":
    unittest.main()
