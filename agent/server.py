#!/usr/bin/env python3
"""Serwer okna dialogowego agenta KOS.

Serwuje interfejs czatu (agent/chat.html) i endpoint /api/chat, który uruchamia
Reasoning Engine (agent.ask) z narzędziami KOS. Rozmowa trzymana po stronie
klienta (pełna historia w każdym żądaniu).

    ANTHROPIC_API_KEY=... python agent/server.py            # http://127.0.0.1:8000
    ANTHROPIC_API_KEY=... python agent/server.py --port 8080
"""
import argparse
import base64
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from agent.agent import ask  # noqa: E402

CHAT_HTML = os.path.join(HERE, "chat.html")
BROWSER_HTML = os.path.join(os.path.dirname(HERE), "web", "kos.html")

# Hasło dostępu — potrzebne, gdy serwer jest wystawiony do internetu (tunel
# Cloudflare). Ustaw zmienną KOS_PASSWORD, a przeglądarka poprosi o hasło.
# Puste = brak ochrony (praca lokalna na localhost tylko dla siebie).
PASSWORD = os.environ.get("KOS_PASSWORD", "")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # cisza
        pass

    def _authorized(self):
        """True, gdy brak hasła (localhost) albo podano poprawne w Basic Auth."""
        if not PASSWORD:
            return True
        hdr = self.headers.get("Authorization", "")
        if not hdr.startswith("Basic "):
            return False
        try:
            raw = base64.b64decode(hdr[6:]).decode("utf-8")
        except Exception:  # noqa: BLE001
            return False
        _, _, pw = raw.partition(":")  # login dowolny, liczy się hasło
        return hmac.compare_digest(pw, PASSWORD)

    def _require_auth(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Warhammer Fantasy KOS"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if not self._authorized():
            self._require_auth()
            return
        if self.path in ("/", "/index.html"):
            with open(CHAT_HTML, encoding="utf-8") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path in ("/przegladarka", "/browse"):
            # przeglądarka strukturalna (lookupy bez API) — jeśli zbudowana
            if os.path.exists(BROWSER_HTML):
                with open(BROWSER_HTML, encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            else:
                self._send(404, "Uruchom: python kos/export_web.py",
                           "text/plain; charset=utf-8")
        elif self.path == "/health":
            self._send(200, json.dumps({"ok": True,
                       "key": bool(os.environ.get("ANTHROPIC_API_KEY"))}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if not self._authorized():
            self._require_auth()
            return
        if self.path != "/api/chat":
            self._send(404, json.dumps({"error": "not found"}))
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            messages = payload.get("messages", [])
            if not messages:
                self._send(400, json.dumps({"error": "brak wiadomości"}))
                return
            reply, used = ask(messages)
            self._send(200, json.dumps({"reply": reply, "tools": used},
                                       ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"},
                                       ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠ Brak ANTHROPIC_API_KEY — /api/chat zwróci błąd do czasu ustawienia klucza.",
              file=sys.stderr)
    if PASSWORD:
        print("🔒 Ochrona hasłem WŁĄCZONA (KOS_PASSWORD) — przeglądarka poprosi o hasło.",
              file=sys.stderr)
    else:
        print("🔓 Bez hasła — OK dla localhost. Do udostępniania w internecie ustaw KOS_PASSWORD.",
              file=sys.stderr)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Agent KOS słucha na http://{args.host}:{args.port}  (Ctrl+C aby zakończyć)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
