#!/usr/bin/env python3
"""Lekki serwer wyszukiwarki bazy wektorowej (stdlib, bez Flaska).

Ładuje model embeddingów i bazę ChromaDB RAZ przy starcie, serwuje stronę
web/index.html oraz endpoint /api/query?q=...&k=... zwracający JSON.

    python scripts/webapp.py
    python scripts/webapp.py --port 8000 --db data/chroma
Następnie otwórz w przeglądarce:  http://localhost:8000
"""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import chromadb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from embedder import load_embedder, embed_query, MODEL_NAME

MODEL = None
COL = None
INDEX_HTML = os.path.join(ROOT, "web", "index.html")


def make_handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # ciszej
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                with open(INDEX_HTML, "rb") as fh:
                    self._send(200, fh.read(), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/query":
                qs = parse_qs(parsed.query)
                query = (qs.get("q", [""])[0]).strip()
                try:
                    k = max(1, min(20, int(qs.get("k", ["5"])[0])))
                except ValueError:
                    k = 5
                if not query:
                    self._send(200, json.dumps({"results": []}))
                    return
                try:
                    qemb = embed_query(MODEL, query).tolist()
                    res = COL.query(query_embeddings=[qemb], n_results=k,
                                    include=["documents", "metadatas", "distances"])
                    out = []
                    for doc, m, dist in zip(res["documents"][0], res["metadatas"][0],
                                            res["distances"][0]):
                        out.append({
                            "text": doc.strip()[:700],
                            "page_start": m["page_start"],
                            "page_end": m["page_end"],
                            "similarity": round(1 - dist, 4),
                        })
                    self._send(200, json.dumps({"results": out}, ensure_ascii=False))
                except Exception as e:
                    self._send(200, json.dumps({"error": str(e)}))
                return
            self._send(404, json.dumps({"error": "not found"}))
    return Handler


def main():
    global MODEL, COL
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--db", default="data/chroma")
    ap.add_argument("--collection", default="warhammer")
    args = ap.parse_args()

    print(f"Ładuję model {MODEL_NAME} i bazę {args.db} ...")
    MODEL = load_embedder()
    client = chromadb.PersistentClient(path=args.db)
    COL = client.get_collection(args.collection)
    print(f"Baza gotowa: {COL.count()} wektorów.")

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(args.db))
    print(f"\n  ➜  Otwórz w przeglądarce:  http://localhost:{args.port}\n")
    print("  (Ctrl-C aby zatrzymać)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano.")


if __name__ == "__main__":
    main()
