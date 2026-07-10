#!/usr/bin/env python3
"""Serwer okna dialogowego agenta KOS.

Serwuje interfejs czatu (agent/chat.html) i endpoint /api/chat, który uruchamia
Reasoning Engine (agent.ask) z narzędziami KOS. Rozmowa trzymana po stronie
klienta (pełna historia w każdym żądaniu).

Backend LLM wybierany zmienną KOS_BACKEND (domyślnie "ollama" — lokalny
Bielik). Ustaw KOS_BACKEND=claude, by wrócić na Claude API.

    python agent/server.py                                  # http://127.0.0.1:8000
    KOS_BACKEND=claude ANTHROPIC_API_KEY=... python agent/server.py
"""
import argparse
import base64
import hmac
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

BACKEND = os.environ.get("KOS_BACKEND", "ollama")
if BACKEND == "claude":
    from agent.agent import ask  # noqa: E402
else:
    from agent.ollama_agent import ask  # noqa: E402
from kos.query import KOS  # noqa: E402

CHAT_HTML = os.path.join(HERE, "chat.html")
BROWSER_HTML = os.path.join(os.path.dirname(HERE), "web", "kos.html")

# ThreadingHTTPServer obsługuje żądania w wielu wątkach — sqlite3 wolno używać
# tylko w wątku, w którym powstało połączenie (patrz agent/tools.py::_get_kos).
_local = threading.local()


def _get_kos():
    if not hasattr(_local, "kos"):
        try:
            _local.kos = KOS()
        except FileNotFoundError:
            _local.kos = None
    return _local.kos

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
        parsed = urlsplit(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            with open(CHAT_HTML, encoding="utf-8") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif path in ("/przegladarka", "/browse"):
            # przeglądarka strukturalna (lookupy bez API) — jeśli zbudowana
            if os.path.exists(BROWSER_HTML):
                with open(BROWSER_HTML, encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            else:
                self._send(404, "Uruchom: python kos/export_web.py",
                           "text/plain; charset=utf-8")
        elif path == "/health":
            ready = (bool(os.environ.get("ANTHROPIC_API_KEY")) if BACKEND == "claude"
                     else True)  # ollama: gotowość sprawdza się dopiero przy /api/chat
            self._send(200, json.dumps({"ok": True, "backend": BACKEND, "key": ready}))
        elif path == "/api/professions":
            kos = _get_kos()
            if kos is None:
                self._send(503, json.dumps({"error": "baza KOS niedostępna"}))
                return
            self._send(200, json.dumps(kos.list_professions(), ensure_ascii=False))
        elif path == "/api/profession":
            kos = _get_kos()
            if kos is None:
                self._send(503, json.dumps({"error": "baza KOS niedostępna"}))
                return
            node_id = parse_qs(parsed.query).get("id", [""])[0]
            stats = kos.profession_stats(node_id)
            if not stats:
                self._send(404, json.dumps({"error": "nie znaleziono profesji"}))
                return
            entries, exits = kos.career_neighbors(node_id)
            stats["node_id"] = node_id
            stats["entries"] = entries
            stats["exits"] = exits
            self._send(200, json.dumps(stats, ensure_ascii=False))
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
    if BACKEND == "claude":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("⚠ Brak ANTHROPIC_API_KEY — /api/chat zwróci błąd do czasu ustawienia klucza.",
                  file=sys.stderr)
    else:
        from agent.ollama_agent import MODEL as _OLLAMA_MODEL
        print(f"[i] Backend: Ollama, model={_OLLAMA_MODEL}. "
              "Upewnij się, że `ollama serve` działa i model jest pobrany.",
              file=sys.stderr)
    if PASSWORD:
        print("[LOCK] Ochrona haslem WLACZONA (KOS_PASSWORD) - przegladarka poprosi o haslo.",
              file=sys.stderr)
    else:
        print("[i] Bez hasla - OK dla localhost. Do udostepniania w internecie ustaw KOS_PASSWORD.",
              file=sys.stderr)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Agent KOS słucha na http://{args.host}:{args.port}  (Ctrl+C aby zakończyć)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
