"""Downloads through the relay with a Spanish IP: signature, which hosts use it and retries.

A local server plays relay.php: it checks the signature the same way
(HMAC-SHA256 of ts + "\\n" + url, in the x-ts and x-firma headers).
"""
import hashlib
import hmac
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from generador import descargas

KEY = "clave-de-prueba"
ICGC = "https://datacloud.icgc.cat/datacloud/adreces-simplificat/csv/"


class FakeRelay(BaseHTTPRequestHandler):
    answers: list[int] = []
    seen: list[dict] = []

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        url, ts, signature = query["url"][0], self.headers["x-ts"], self.headers["x-firma"]
        expected = hmac.new(KEY.encode(), f"{ts}\n{url}".encode(), hashlib.sha256).hexdigest()
        self.seen.append({"path": self.path, "url": url})
        status = self.answers.pop(0) if self.answers else 200
        if not hmac.compare_digest(expected, signature or ""):
            status = 403
        self.send_response(status)
        self.end_headers()
        self.wfile.write(f"through the relay: {url}".encode())

    def log_message(self, *_):
        pass


class Relay(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), FakeRelay)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        FakeRelay.answers, FakeRelay.seen = [], []
        self.base = f"http://127.0.0.1:{self.server.server_port}/relay.php"
        for patch in (mock.patch.dict("os.environ", {"RELAY_CLAVE": KEY, "RELAY_URL": self.base}),
                      mock.patch.object(descargas.time, "sleep")):
            patch.start()
            self.addCleanup(patch.stop)

    def test_icgc_goes_through_the_relay_signed_and_keeps_its_url(self):
        got = descargas.fetch(ICGC)
        self.assertEqual(got.content, f"through the relay: {ICGC}".encode())
        self.assertEqual(got.url, ICGC)
        self.assertEqual(FakeRelay.seen[0]["url"], ICGC)
        self.assertTrue(FakeRelay.seen[0]["path"].startswith("/relay.php/?url="))

    def test_new_signature_on_each_attempt(self):
        FakeRelay.answers = [502]  # network failure at the relay: retried
        with mock.patch.object(descargas, "relay", wraps=descargas.relay) as relay:
            got = descargas.fetch(ICGC)
        self.assertEqual(got.content, f"through the relay: {ICGC}".encode())
        self.assertEqual(relay.call_count, 2)

    def test_bad_signature_is_not_retried(self):
        with mock.patch.dict("os.environ", {"RELAY_CLAVE": "otra"}):
            with self.assertRaisesRegex(RuntimeError, "403"):
                descargas.fetch(ICGC)
        self.assertEqual(len(FakeRelay.seen), 1)


class Direct(unittest.TestCase):
    def test_without_key_goes_direct(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(descargas.relay(ICGC), (ICGC, {}))

    def test_other_hosts_go_direct(self):
        with mock.patch.dict("os.environ", {"RELAY_CLAVE": KEY, "RELAY_URL": "http://relay.example/r.php"}):
            for url in ("https://www.ine.es/x", "https://datacloud.icgc.cat.example.com/"):
                self.assertEqual(descargas.relay(url), (url, {}))

    def test_post_never_goes_through_the_relay(self):
        sent = []

        def capture(request, timeout):
            sent.append(request.full_url)
            raise descargas.urllib.error.HTTPError(request.full_url, 404, "x", {}, None)

        with mock.patch.dict("os.environ", {"RELAY_CLAVE": KEY, "RELAY_URL": "http://relay.example/r.php"}), \
                mock.patch.object(descargas.urllib.request, "urlopen", capture):
            with self.assertRaises(RuntimeError):
                descargas.fetch(ICGC, data={"a": "b"})
        self.assertEqual(sent, [ICGC])


class Redirecting(BaseHTTPRequestHandler):
    seen: list[tuple[str, str | None]] = []

    def do_GET(self):
        self.seen.append((self.path, self.headers.get("api_key")))
        if self.path == "/api":
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"data")

    def log_message(self, *_):
        pass


class KeyInHeader(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), Redirecting)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        Redirecting.seen = []
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def test_a_request_with_a_key_does_not_follow_redirects(self):
        with self.assertRaises(RuntimeError) as caught:
            descargas.fetch(self.base + "/api", headers={"api_key": KEY}, attempts=1)
        self.assertEqual(Redirecting.seen, [("/api", KEY)])
        self.assertNotIn(KEY, str(caught.exception))

    def test_without_headers_redirects_are_followed(self):
        with mock.patch.object(descargas.time, "sleep"):
            self.assertEqual(descargas.fetch(self.base + "/api").content, b"data")
        self.assertEqual(Redirecting.seen, [("/api", None), ("/elsewhere", None)])


if __name__ == "__main__":
    unittest.main()
