#!/usr/bin/env python3
"""Orkiestrator całego pipeline'u w iteracjach po ~20 stron, z testem po każdej.

Dla każdej paczki stron:
  1. OCR (render 300 DPI -> tesseract pol+eng), wznawialny (pomija gotowe strony)
  2. czyszczenie + chunking tej paczki (metadane stron)
  3. embedding (e5-large) + dodanie do trwałej bazy ChromaDB
  4. TEST: (a) self-retrieval — czy fragment z paczki jest wyszukiwalny,
           (b) zapytanie diagnostyczne — jak trafność rośnie z pokryciem

    python scripts/run_all.py data/raw/ksiega_zasad.pdf --batch 20
"""
import argparse
import importlib.util
import io
import json
import os
import sys
import time

import chromadb
import fitz
import pytesseract
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from embedder import load_embedder, embed_passages, embed_query, MODEL_NAME

# import funkcji chunkujących z 03_chunk.py (nazwa zaczyna się cyfrą)
_spec = importlib.util.spec_from_file_location("chunklib", os.path.join(HERE, "03_chunk.py"))
chunklib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chunklib)


def ocr_page(doc, i, dpi, lang, out_txt):
    if os.path.exists(out_txt):
        return open(out_txt, encoding="utf-8").read()
    pix = doc[i].get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    txt = pytesseract.image_to_string(img, lang=lang).strip()
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(txt)
    return txt


def chunk_pages(pages_dir, page_range):
    """Chunkuje wskazane strony (lista numerów) -> lista chunków."""
    import re
    paras = []
    for p in page_range:
        fp = os.path.join(pages_dir, f"page_{p:04d}.txt")
        if not os.path.exists(fp):
            continue
        txt = chunklib.clean_page(open(fp, encoding="utf-8").read())
        for para in txt.split("\n\n"):
            para = para.strip()
            if len(para) >= 15:
                paras.append((p, para))
    return chunklib.build_chunks(paras, target=1100, overlap=200)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--lang", default="pol+eng")
    ap.add_argument("--out", default="data/text")
    ap.add_argument("--db", default="data/chroma")
    ap.add_argument("--collection", default="warhammer")
    ap.add_argument("--diag", default="jak działa parowanie ciosu w walce wręcz",
                    help="zapytanie diagnostyczne uruchamiane po każdej paczce")
    args = ap.parse_args()

    pages_dir = os.path.join(args.out, "pages")
    os.makedirs(pages_dir, exist_ok=True)

    doc = fitz.open(args.pdf)
    n = doc.page_count
    print(f"PDF: {args.pdf}  stron={n}  paczka={args.batch}  model={MODEL_NAME}\n", flush=True)

    print("Ładuję model embeddingów...", flush=True)
    model = load_embedder()

    client = chromadb.PersistentClient(path=args.db)
    try:
        client.delete_collection(args.collection)
    except Exception:
        pass
    col = client.create_collection(
        args.collection,
        metadata={"model": MODEL_NAME, "is_e5": True, "hnsw:space": "cosine"})

    all_chunks = []
    total_chunks = 0
    empty_pages = 0
    t_start = time.time()

    batch_no = 0
    for start in range(1, n + 1, args.batch):
        batch_no += 1
        end = min(start + args.batch - 1, n)
        rng = list(range(start, end + 1))
        t0 = time.time()
        print(f"\n{'='*72}\nITERACJA {batch_no}: strony {start}-{end}\n{'='*72}", flush=True)

        # 1. OCR
        for i in rng:
            txt = ocr_page(doc, i - 1, args.dpi, args.lang,
                           os.path.join(pages_dir, f"page_{i:04d}.txt"))
            if len(txt) < 40:
                empty_pages += 1
        print(f"  [1] OCR gotowy ({time.time()-t0:.0f}s)", flush=True)

        # 2. chunking paczki
        chunks = chunk_pages(pages_dir, rng)
        for j, c in enumerate(chunks):
            c["id"] = f"chunk_{total_chunks + j:05d}"
        print(f"  [2] chunków w paczce: {len(chunks)}", flush=True)

        # 3. embedding + zapis do bazy
        if chunks:
            embs = [e.tolist() for e in embed_passages(model, [c["text"] for c in chunks])]
            col.add(
                ids=[c["id"] for c in chunks],
                embeddings=embs,
                documents=[c["text"] for c in chunks],
                metadatas=[{"page_start": c["page_start"], "page_end": c["page_end"]}
                           for c in chunks])
            total_chunks += len(chunks)
            all_chunks.extend(chunks)
        print(f"  [3] baza: {col.count()} wektorów łącznie", flush=True)

        # 4. TEST
        # (a) self-retrieval: bierzemy środkowy chunk paczki, pytamy jego początkiem
        if chunks:
            probe = chunks[len(chunks) // 2]
            q = " ".join(probe["text"].split()[:12])
            qemb = embed_query(model, q).tolist()
            r = col.query(query_embeddings=[qemb], n_results=1,
                          include=["metadatas", "distances"])
            hit_id = r["ids"][0][0]
            hit_m = r["metadatas"][0][0]
            # OK jeśli trafiony fragment nakłada się stronami z sondą
            # (przez zakładkę sąsiednie chunki bywają równie trafne)
            overlap = (hit_m["page_start"] <= probe["page_end"]
                       and hit_m["page_end"] >= probe["page_start"])
            ok = "OK" if overlap else f"MISS (trafił {hit_id})"
            print(f"  [4a] self-retrieval: {ok}  sim={1 - r['distances'][0][0]:.3f}", flush=True)

        # (b) zapytanie diagnostyczne
        qemb = embed_query(model, args.diag).tolist()
        r = col.query(query_embeddings=[qemb], n_results=1,
                      include=["metadatas", "distances"])
        m = r["metadatas"][0][0]
        pg = m["page_start"] if m["page_start"] == m["page_end"] else f"{m['page_start']}-{m['page_end']}"
        print(f"  [4b] diagnostyka \"{args.diag}\" -> str.{pg}  sim={1 - r['distances'][0][0]:.3f}", flush=True)
        print(f"  (iteracja {batch_no} w {time.time()-t0:.0f}s)", flush=True)

    # zapis pełnego chunks.jsonl
    with open(os.path.join(args.out, "chunks.jsonl"), "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\n{'#'*72}\nZAKOŃCZONO. Stron: {n} | pustych/graficznych: {empty_pages} | "
          f"chunków: {total_chunks} | wektorów: {col.count()}")
    print(f"Czas całości: {(time.time()-t_start)/60:.1f} min | baza: {args.db}")


if __name__ == "__main__":
    main()
