#!/usr/bin/env python3
"""Krok 4: embeddingi + zapis do bazy wektorowej (ChromaDB, trwała).

Wejście : data/text/chunks.jsonl
Wyjście : data/chroma/  (kolekcja 'warhammer')

Model: intfloat/multilingual-e5-large przez fastembed (ONNX, lokalnie, z GCS).
Odległość: cosine. Do dokumentów dokładany jest prefiks "passage: ".

    python scripts/04_build_vectordb.py
    python scripts/04_build_vectordb.py --chunks data/text_test/chunks.jsonl --db data/chroma_test --collection test
"""
import argparse
import json
import os
import sys

import chromadb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embedder import load_embedder, embed_passages, MODEL_NAME


def load_chunks(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_facts(path):
    """Fakt-karty z tabel jako dokumenty wektorowe (proza + tabele w jednej bazie)."""
    if not os.path.exists(path):
        return []
    rows = []
    for i, f in enumerate(json.load(open(path, encoding="utf-8"))):
        pg = f.get("page", 0)
        rows.append({"id": f"fact-{f['type']}-{i}", "text": f["fact"],
                     "page_start": pg, "page_end": pg, "source": "tabela",
                     "kind": f["type"]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="data/text/chunks.jsonl")
    ap.add_argument("--facts", default="data/tables/facts.json")
    ap.add_argument("--db", default="data/chroma")
    ap.add_argument("--collection", default="warhammer")
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    rows = load_chunks(args.chunks)
    for r in rows:
        r.setdefault("source", "proza")
    facts = load_facts(args.facts)
    rows += facts
    print(f"Dokumentów: {len(rows)} (proza {len(rows)-len(facts)} + tabele {len(facts)})"
          f"  |  model: {MODEL_NAME}")

    model = load_embedder()
    print("Liczę embeddingi...")
    embeddings = [e.tolist() for e in embed_passages(
        model, [r["text"] for r in rows], batch_size=args.batch)]
    dim = len(embeddings[0]) if embeddings else 0

    client = chromadb.PersistentClient(path=args.db)
    try:
        client.delete_collection(args.collection)
    except Exception:
        pass
    col = client.create_collection(
        args.collection,
        metadata={"model": MODEL_NAME, "is_e5": True, "hnsw:space": "cosine"},
    )
    col.add(
        ids=[r["id"] for r in rows],
        embeddings=embeddings,
        documents=[r["text"] for r in rows],
        metadatas=[{"page_start": r["page_start"], "page_end": r["page_end"],
                    "source": r.get("source", "proza"), "kind": r.get("kind", "")}
                   for r in rows],
    )
    print(f"OK. Zapisano {col.count()} wektorów (wymiar {dim}) do {args.db} "
          f"(kolekcja '{args.collection}').")


if __name__ == "__main__":
    main()
