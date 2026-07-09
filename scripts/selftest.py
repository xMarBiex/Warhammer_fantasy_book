#!/usr/bin/env python3
"""Test całości funkcjonalności KOS — jedno polecenie sprawdza wszystkie warstwy.

Poziomy (rosnący koszt):
  domyślnie   : Warstwa 2/3 (SQL + Graf) — wszystkie 10 narzędzi, bez klucza/modelu.
  --vectors   : Warstwa 4 (semantyka) — ładuje model e5 i odpytuje ChromaDB.
  --agent     : Warstwa 5 (agent na żywo) — wymaga ANTHROPIC_API_KEY; pełna pętla + strażnik.
  --all       : wszystko.

    python scripts/selftest.py
    python scripts/selftest.py --vectors
    ANTHROPIC_API_KEY=sk-... python scripts/selftest.py --all
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

OK, BAD = "✓", "✗"
results = []


def check(name, fn):
    try:
        detail = fn()
        results.append((True, name, detail))
        print(f"  {OK} {name}: {detail}")
    except Exception as e:  # noqa: BLE001
        results.append((False, name, f"{type(e).__name__}: {e}"))
        print(f"  {BAD} {name}: {type(e).__name__}: {e}")


def test_sql_graph():
    print("\n── Warstwa 2/3: SQL + Graf (10 narzędzi, bez klucza) ──")
    from agent import tools as T

    def nonempty(d, *keys):
        assert d.get("znaleziono"), d.get("info", "brak wyniku")
        for k in keys:
            assert d.get(k) not in (None, "", [], {}), f"puste pole {k}"
        return d

    check("profesja_szczegoly('akolita')", lambda: (
        lambda d: f"{d['nazwa']} WW {d['cechy_glowne'].get('WW')}, wyjścia {len(d['wyjscie_do'])}"
    )(nonempty(T.profesja_szczegoly("akolita"), "cechy_glowne", "wyjscie_do")))

    check("porownaj_ceche('WW','max')", lambda: (
        lambda d: ", ".join(x["profesja"] for x in d["wynik"])
    )(T.porownaj_ceche("WW", "max")))

    check("bron_szczegoly('halabarda')", lambda: (
        lambda d: f"obrażenia {d['obrazenia']}, cena {d['cena']}"
    )(nonempty(T.bron_szczegoly("halabarda"), "obrazenia")))

    check("pancerz_szczegoly('kolczuga')", lambda: (
        lambda d: f"{len(d['elementy'])} wariant(y), PZ {d['elementy'][0]['PZ']}"
    )(nonempty(T.pancerz_szczegoly("kolczuga"), "elementy")))

    check("czar_szczegoly('pancerz eteru')", lambda: (
        lambda d: f"PM {d['poziom_mocy']}, tradycja {d['tradycja']}"
    )(nonempty(T.czar_szczegoly("pancerz eteru"), "poziom_mocy")))

    check("czary_tradycji('ognia')", lambda: (
        lambda d: f"{d['tradycja']} — {d['liczba']} czarów"
    )(nonempty(T.czary_tradycji("ognia"), "czary")))

    check("czary_tradycji('morra') [odmiana]", lambda: (
        lambda d: f"{d['tradycja']} — {d['liczba']} czarów"
    )(nonempty(T.czary_tradycji("morra"), "czary")))

    check("cena_ekwipunku('koń')", lambda: (
        lambda d: "; ".join(f"{p['nazwa']} {p['cena']}" for p in d["pozycje"][:3])
    )(nonempty(T.cena_ekwipunku("koń"), "pozycje")))

    check("potwor_szczegoly('ork')", lambda: (
        lambda d: f"Żyw {d['cechy_drugorzedne'].get('Zyw')}, PZ {d['punkty_zbroi']}"
    )(nonempty(T.potwor_szczegoly("ork"), "cechy_glowne")))

    check("kto_zna('leczenie') [zależność grafu]", lambda: (
        lambda d: f"{len(d.get('profesje_z_umiejetnoscia', []))} profesji"
    )(nonempty(T.kto_zna("leczenie"))))

    # negatywne: pytanie o nieistniejącą encję
    check("obsługa braku ('xyzzy')", lambda: (
        "poprawnie zgłasza brak" if not T.bron_szczegoly("xyzzy").get("znaleziono")
        else (_ for _ in ()).throw(AssertionError("powinno zgłosić brak"))))


def test_vectors():
    print("\n── Warstwa 4: semantyka (ChromaDB + e5) ──")
    import chromadb
    sys.path.insert(0, HERE)
    from embedder import load_embedder, embed_query
    col = chromadb.PersistentClient(
        path=os.path.join(ROOT, "data", "chroma")).get_collection("warhammer")
    check("liczba wektorów", lambda: f"{col.count()} (proza + fakt-karty)")
    model = load_embedder()

    def q(text, want_source=None):
        r = col.query(query_embeddings=[embed_query(model, text).tolist()],
                      n_results=1, include=["documents", "metadatas"])
        md = r["metadatas"][0][0]
        if want_source:
            assert md.get("source") == want_source, f"source={md.get('source')}"
        return f"str.{md.get('page_start')} [{md.get('source')}] {r['documents'][0][0][:60]}…"

    check("proza: 'jak działa parowanie ciosu'", lambda: q("jak działa parowanie ciosu"))
    check("fakt tabelaryczny: 'ile obrażeń zadaje halabarda'",
          lambda: q("ile obrażeń zadaje halabarda", "tabela"))
    check("lore: 'kim są zabójcy trolli'", lambda: q("kim są zabójcy trolli"))


def test_agent():
    print("\n── Warstwa 5: agent na żywo (Claude API) ──")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"  {BAD} pominięto: brak ANTHROPIC_API_KEY (ustaw klucz, by przetestować agenta)")
        results.append((False, "agent (klucz)", "brak ANTHROPIC_API_KEY"))
        return
    from agent.agent import ask

    def ask1(q, expect_tool=None, expect_refuse=False):
        text, used = ask([{"role": "user", "content": q}])
        names = [u["tool"] for u in used]
        if expect_tool:
            assert expect_tool in names, f"nie użył {expect_tool} (użył: {names})"
        if expect_refuse:
            assert not used, f"nie powinien używać narzędzi (użył: {names})"
        return (f"narzędzia={names or '—'} · " + text.replace("\n", " ")[:90] + "…")

    check("fakt: 'statystyki akolity'",
          lambda: ask1("Jakie są statystyki akolity?", expect_tool="profesja_szczegoly"))
    check("zależność: 'które profesje znają leczenie'",
          lambda: ask1("Które profesje znają leczenie?", expect_tool="kto_zna"))
    check("czary: 'jakie czary ma tradycja ognia'",
          lambda: ask1("Jakie czary są w Tradycji Ognia?", expect_tool="czary_tradycji"))
    check("STRAŻNIK: pytanie poza tematem (ma odmówić, bez narzędzi)",
          lambda: ask1("Napisz mi funkcję sortującą w Pythonie.", expect_refuse=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vectors", action="store_true", help="testuj warstwę wektorową (ładuje e5)")
    ap.add_argument("--agent", action="store_true", help="testuj agenta na żywo (wymaga klucza)")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    print("=== KOS SELF-TEST ===")
    test_sql_graph()
    if args.vectors or args.all:
        test_vectors()
    if args.agent or args.all:
        test_agent()

    passed = sum(1 for ok, *_ in results if ok)
    total = len(results)
    print(f"\n=== WYNIK: {passed}/{total} OK ===")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
