#!/usr/bin/env python3
"""Krok 4: embeddingi + zapis do bazy wektorowej (ChromaDB, trwała).

Wejście : data/text/chunks.jsonl
Wyjście : data/chroma/  (kolekcja 'warhammer')

Model embeddingów: domyślnie wielojęzyczny E5 (dobry dla polskiego), lokalnie
przez sentence-transformers. Dla modeli E5 dokładany jest wymagany prefiks
"passage: " (dokumenty) / "query: " (zapytania).

    python scripts/04_build_vectordb.py
    python scripts/04_build_vectordb.py --model intfloat/multilingual-e5-large
"""
import argparse
import json
import os

import chromadb
from sentence_transformers import SentenceTransformer


def load_chunks(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="data/text/chunks.jsonl")
    ap.add_argument("--db", default="data/chroma")
    ap.add_argument("--collection", default="warhammer")
    ap.add_argument("--model", default="intfloat/multilingual-e5-base")
    ap.add_argument("--batch", type=int, default=64)
    args = ap.parse_args()

    rows = load_chunks(args.chunks)
    print(f"Chunków: {len(rows)}  |  model: {args.model}")

    model = SentenceTransformer(args.model)
    is_e5 = "e5" in args.model.lower()

    texts = [("passage: " + r["text"]) if is_e5 else r["text"] for r in rows]
    print("Liczę embeddingi...")
    emb = model.encode(texts, batch_size=args.batch, show_progress_bar=True,
                       normalize_embeddings=True)

    client = chromadb.PersistentClient(path=args.db)
    # świeża kolekcja od zera (idempotentnie)
    try:
        client.delete_collection(args.collection)
    except Exception:
        pass
    col = client.create_collection(
        args.collection,
        metadata={"model": args.model, "is_e5": is_e5, "hnsw:space": "cosine"},
    )

    col.add(
        ids=[r["id"] for r in rows],
        embeddings=[e.tolist() for e in emb],
        documents=[r["text"] for r in rows],
        metadatas=[{"page_start": r["page_start"], "page_end": r["page_end"]}
                   for r in rows],
    )
    print(f"OK. Zapisano {col.count()} wektorów do {args.db} "
          f"(kolekcja '{args.collection}', wymiar {len(emb[0])}).")


if __name__ == "__main__":
    main()
