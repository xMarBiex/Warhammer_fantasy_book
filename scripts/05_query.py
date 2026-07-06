#!/usr/bin/env python3
"""Krok 5: zapytanie do bazy wektorowej (retrieval) z cytowaniem stron.

Model E5 -> zapytanie z prefiksem "query: ". Zwraca top-k fragmentów z numerami
stron i podobieństwem kosinusowym.

    python scripts/05_query.py "jak działa parowanie ciosu?"
    python scripts/05_query.py "zasady inicjatywy" -k 5 --db data/chroma_test --collection test
"""
import argparse
import os
import sys

import chromadb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embedder import load_embedder, embed_query


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="pytanie po polsku")
    ap.add_argument("-k", type=int, default=5, help="ile fragmentów zwrócić")
    ap.add_argument("--db", default="data/chroma")
    ap.add_argument("--collection", default="warhammer")
    args = ap.parse_args()

    client = chromadb.PersistentClient(path=args.db)
    col = client.get_collection(args.collection)

    model = load_embedder()
    qemb = embed_query(model, args.query).tolist()

    res = col.query(query_embeddings=[qemb], n_results=args.k,
                    include=["documents", "metadatas", "distances"])

    print(f"\nPytanie: {args.query}\n{'='*70}")
    for doc, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        pages = (f"str. {m['page_start']}" if m["page_start"] == m["page_end"]
                 else f"str. {m['page_start']}-{m['page_end']}")
        print(f"\n[{pages}]  podobieństwo={1 - dist:.3f}")
        print(doc[:600].strip())


if __name__ == "__main__":
    main()
