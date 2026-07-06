#!/usr/bin/env python3
"""Krok 5: zapytanie do bazy wektorowej (retrieval) z cytowaniem stron.

    python scripts/05_query.py "jak działa parowanie ciosu?"
    python scripts/05_query.py "zasady inicjatywy" -k 5
"""
import argparse

import chromadb
from sentence_transformers import SentenceTransformer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="pytanie po polsku")
    ap.add_argument("-k", type=int, default=5, help="ile fragmentów zwrócić")
    ap.add_argument("--db", default="data/chroma")
    ap.add_argument("--collection", default="warhammer")
    args = ap.parse_args()

    client = chromadb.PersistentClient(path=args.db)
    col = client.get_collection(args.collection)
    meta = col.metadata or {}
    model_name = meta.get("model", "intfloat/multilingual-e5-base")
    is_e5 = meta.get("is_e5", "e5" in model_name.lower())

    model = SentenceTransformer(model_name)
    q = ("query: " + args.query) if is_e5 else args.query
    qemb = model.encode([q], normalize_embeddings=True)[0].tolist()

    res = col.query(query_embeddings=[qemb], n_results=args.k,
                    include=["documents", "metadatas", "distances"])

    print(f"\nPytanie: {args.query}\n{'='*70}")
    for doc, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        pages = (f"str. {m['page_start']}" if m["page_start"] == m["page_end"]
                 else f"str. {m['page_start']}-{m['page_end']}")
        sim = 1 - dist  # cosine distance -> podobieństwo
        print(f"\n[{pages}]  podobieństwo={sim:.3f}")
        print(doc[:600].strip())


if __name__ == "__main__":
    main()
