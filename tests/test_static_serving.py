"""Conditional-request and gzip behavior of the static asset helper."""
import gzip
import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import bottle

HV = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HV))


def _load():
    spec = importlib.util.spec_from_file_location("hv_app", HV / "hypervisor-app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


APP = _load()


def _get(root, path, headers=None):
    env = {"REQUEST_METHOD": "GET", "PATH_INFO": "/" + path, "wsgi.input": None}
    for k, v in (headers or {}).items():
        env["HTTP_" + k.upper().replace("-", "_")] = v
    bottle.request.bind(env)
    bottle.response.bind()
    resp = APP._static_response(path, root)
    body = resp.body.read() if hasattr(resp.body, "read") else (resp.body or b"")
    return resp, body


class StaticServingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.text = ("body { color: red; }\n" * 500)
        Path(self.root, "style.css").write_bytes(self.text.encode())
        Path(self.root, "logo.png").write_bytes(b"\x89PNG" * 100)

    def tearDown(self):
        self.tmp.cleanup()

    def test_200_then_304(self):
        r1, b1 = _get(self.root, "style.css")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.get_header("Cache-Control"), "no-cache")
        self.assertEqual(b1.decode(), self.text)
        r2, b2 = _get(self.root, "style.css", {"If-None-Match": r1.get_header("ETag")})
        self.assertEqual(r2.status_code, 304)
        self.assertEqual(b2, b"")
        r3, _ = _get(self.root, "style.css", {"If-Modified-Since": r1.get_header("Last-Modified")})
        self.assertEqual(r3.status_code, 304)

    def test_fresh_after_change(self):
        r1, _ = _get(self.root, "style.css")
        time.sleep(0.02)
        p = Path(self.root, "style.css")
        p.write_text(self.text + "a{}\n", encoding="utf-8")
        os.utime(p, None)
        r2, b2 = _get(self.root, "style.css", {"If-None-Match": r1.get_header("ETag")})
        self.assertEqual(r2.status_code, 200)
        self.assertIn("a{}", b2.decode())

    def test_gzip(self):
        r, b = _get(self.root, "style.css", {"Accept-Encoding": "gzip, deflate"})
        self.assertEqual(r.get_header("Content-Encoding"), "gzip")
        self.assertEqual(gzip.decompress(b).decode(), self.text)
        self.assertLess(len(b), len(self.text))
        self.assertEqual(r.get_header("Vary"), "Accept-Encoding")
        r2, _ = _get(self.root, "style.css",
                     {"Accept-Encoding": "gzip", "If-None-Match": r.get_header("ETag")})
        self.assertEqual(r2.status_code, 304)

    def test_no_gzip_without_header_or_for_binary(self):
        r, _ = _get(self.root, "style.css")
        self.assertIsNone(r.get_header("Content-Encoding"))
        r, _ = _get(self.root, "logo.png", {"Accept-Encoding": "gzip"})
        self.assertIsNone(r.get_header("Content-Encoding"))

    def test_gzip_q_values(self):
        for hdr in ("gzip", "gzip, deflate, br", "*", "*;q=0.5", "GZIP;q=1"):
            r, _ = _get(self.root, "style.css", {"Accept-Encoding": hdr})
            self.assertEqual(r.get_header("Content-Encoding"), "gzip", hdr)
        for hdr in ("gzip;q=0", "gzip;q=0.0", "deflate, gzip; q=0", "*;q=0", "gzip;q=0, *"):
            r, _ = _get(self.root, "style.css", {"Accept-Encoding": hdr})
            self.assertIsNone(r.get_header("Content-Encoding"), hdr)

    def test_traversal_rejected_with_gzip(self):
        Path(self.root, "..", "outside.js").resolve().write_text("x" * 100)
        try:
            for hdr in ({"Accept-Encoding": "gzip"}, {}):
                r, _ = _get(self.root, "../outside.js", hdr)
                self.assertEqual(r.status_code, 403)
        finally:
            Path(self.root, "..", "outside.js").resolve().unlink()

    def test_malformed_if_modified_since(self):
        r, _ = _get(self.root, "style.css", {"If-Modified-Since": "garbage"})
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
