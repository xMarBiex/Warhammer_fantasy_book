# Tabele → wiedza strukturalna + integracja z bazą wektorową

## Problem
Tesseract nie czyta tabel (siatka, liczby, symbole) — zamienia je w śmieci.
Model czyta tabele **wzrokowo** z renderu strony. Więc ekstrakcja tabel to:
render strony PDF → odczyt wzrokowy → zapis do **strukturalnego JSON**.

## Model danych (`tables/*.json`) — źródło prawdy
Każdy typ tabeli = osobna kolekcja rekordów z polami:

- **professions.json** — profesje: `name, type (podstawowa/zaawansowana), page,
  main{WW,US,K,Odp,Zr,Int,SW,Ogd}, secondary{A,Żyw,S,Wt,Sz,Mag,PO,PP},
  skills, talents, trappings, entries, exits`
- **weapons.json** — broń: `name, group, damage, reach/range, qualities, price, enc, page`
- **armour.json** — pancerz: `name, locations, AP, penalty, price, page`
- **items.json** — ekwipunek/usługi: `name, category, price, availability, enc, page`
- **spells.json** — czary: `name, tradition/domain, cn (poziom mocy), range, target,
  duration, effect, page`
- **criticals.json** — trafienia krytyczne: `location, roll, effect, page`
- **bestiary.json** — potwory: `name, profile{cechy}, skills, talents, special, page`

Numer strony przechowujemy **drukowany** (tak jak w książce).

## Integracja z bazą wektorową — dwa tory (oba potrzebne)

1. **Fact-cards (spięcie z wektorami).** Każdy rekord zamieniamy w zdanie-fakt
   po polsku (`build_facts.py`), np.:
   > „Akolita — profesja podstawowa (str. 32). Cechy główne: WW +5, US +5,
   > Odp +5, Int +10, SW +10, Ogd +10. Żywotność +2. Umiejętności: …"
   Fakt-karty **embedujemy do ChromaDB** obok prozy oraz wstrzykujemy do strony
   mobilnej. Wyszukiwanie (semantyczne/tekstowe) je znajduje, a że zdanie zawiera
   dokładne liczby — **odpowiedź jest dokładna**.

2. **Struktura (dokładne i filtrowane zapytania).** JSON zostaje jako baza do
   zapytań, których wektory nie zrobią dobrze:
   - „wszystkie czary tradycji ognia" → filtr `spells` po `tradition=ogień`
   - „najtańszy miecz" / „ile kosztuje lina" → sort/lookup po `price`
   - „jakie obrażenia zadaje halabarda" → `weapons.damage`
   Oraz do **ładnego renderu** (karta cech, lista czarów, cennik).

## Router zapytań — jak system znajduje odpowiedź

```
zapytanie → wykryj INTENCJĘ + ENCJĘ:
  „cechy / statystyki / profesja X"      → professions[name≈X]         → karta cech
  „cena / koszt / ile kosztuje X"        → items/weapons/armour[name≈X]→ price
  „obrażenia / zadaje / broń X"          → weapons[name≈X]             → damage
  „czary / zaklęcia tradycji/dziedziny Y"→ spells[tradition≈Y]         → lista
  „potwór / bestia X"                    → bestiary[name≈X]            → profil
  (brak dopasowania)                     → wyszukiwanie prozy (wektory)
```
Encję dopasowujemy tolerancyjnie (bez ogonków, po prefiksie — jak w wyszukiwarce).
W UI karta faktu ląduje **na górze** wyników, nad fragmentami prozy.

## Pipeline
```
scripts/render_tables.py   # renderuje strony z tabelami do obrazów
   → (model czyta wzrokowo) → tables/*.json        # ręcznie kuratorowane, źródło prawdy
scripts/build_facts.py     # tables/*.json → facts.json (zdania-fakty + struktura do renderu)
   → scripts/build_mobile.py   # wstrzykuje facts do strony mobilnej
   → scripts/04_build_vectordb.py (rozszerzony)  # embeduje fakt-karty do ChromaDB
```

## Status
- ✅ Metoda i schemat (ten dokument)
- ✅ Pilotaż: `professions.json` (Akolita, Banita, Berserker z Norski, Chłop),
  fakt-karty, integracja z wyszukiwarką mobilną, dokładna odpowiedź na „statystyki akolity"
- ⬜ Reszta profesji (Rozdz. III), broń/pancerz/ekwipunek (V), trafienia krytyczne (VI),
  czary (VII), bestiariusz (XI) — ekstrakcja partiami
