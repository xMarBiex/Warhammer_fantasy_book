# Warhammer Fantasy — Knowledge Operating System (KOS)

> Specyfikacja źródłowa dostarczona przez użytkownika (2026-07-07). To jest
> kanoniczny dokument wymagań. Mapowanie na konkretne technologie w tym
> środowisku opisuje `docs/ARCHITECTURE.md`.

## Rola
Główny architekt systemu **Knowledge Operating System (KOS)** — nie chatbota,
lecz cyfrowego eksperta z pamięcią długoterminową, modelem świata, rozumieniem
zależności, wyszukiwaniem, wnioskowaniem i ciągłym uczeniem się z nowych źródeł.

## Główna zasada
**Model językowy NIE jest bazą wiedzy.** Model jest analitykiem, planistą,
interpretatorem i generatorem odpowiedzi. Prawdziwa wiedza mieszka w:
1. Graph Database
2. SQL Database
3. Vector Database
4. Document Store
5. Metadata Layer

## Pięć warstw

### Warstwa 1 — Document Intelligence
Zamiana dokumentów w dane strukturalne. Obsługa: PDF, skany, tabele,
ilustracje, przypisy, erraty, dodatki.
Pipeline: `PDF → OCR → Layout Analysis → Entity Extraction → Relationship
Extraction → Validation → Knowledge Graph → Database`.

### Warstwa 2 — Knowledge Graph Engine
Graf jest centrum rozumienia świata. Przechowuj **znaczenie**, nie tekst.

**Typy węzłów:** World, Race, Faction, Army, Unit, Character, Hero, Lord,
Weapon, Armour, Mount, Spell, MagicItem, Rule, Ability, Skill, Scenario,
Terrain, Building, Book, Edition, Author, FAQ, Errata.

**Typy relacji:** BELONGS_TO, CAN_EQUIP, CAN_USE, CAN_JOIN, RIDES, CASTS,
KNOWS, HAS_RULE, MODIFIES, COUNTERS, SYNERGIZES_WITH, REQUIRES, UPGRADED_FROM,
REPLACED_BY, DEFINED_IN, UPDATED_BY, EXPLAINS, REFERENCES.

**Każda relacja musi mieć:** źródło, stronę, książkę, edycję, poziom pewności.

### Warstwa 3 — Relational Intelligence (SQL)
SQL przechowuje dane wymagające precyzji. **Nigdy nie pytaj modelu o liczby.**
Units, StatLines, Costs, Weapons, Armour, Profiles, Movement, WeaponSkill,
BallisticSkill, Strength, Toughness, Wounds, Initiative, Attacks, Leadership,
Rules, Equipment.
Przykład: „Która jednostka ma największą Siłę?" → zapytanie SQL, nie AI.

### Warstwa 4 — Semantic Memory (Vector)
Przechowuje: lore, opisy, interpretacje zasad, przykłady, komentarze, FAQ.
**Nie przechowuje:** statystyk, tabel, kosztów.

### Warstwa 5 — Reasoning Engine
Najważniejsza część. Agent **przed odpowiedzią tworzy PLAN**.
Przykład: „Jaka armia najlepiej radzi sobie przeciwko krasnoludom?" → znajdź
cechy Krasnoludów → słabe strony → armie kontrujące → synergie → odpowiedź ze
źródłami.

## System planowania — klasyfikacja zapytań
| Typ | Opis | Źródło |
|---|---|---|
| FACT | Jedna informacja | SQL / Graph |
| EXPLANATION | Wyjaśnienie zasady | Vector + Graph |
| COMPARISON | Porównanie | SQL + Graph |
| STRATEGY | Analiza taktyczna | Graph + Vector + SQL |
| RESEARCH | Kompleksowe badanie | Wszystkie warstwy |

## Self-check (przed każdą odpowiedzią)
Czy mam źródło? Czy dane z tej samej edycji? Czy są sprzeczności? Czy potrzeba
dalszego wyszukiwania? Czy pewność wystarczająca?

## Confidence Engine
| Pewność | Znaczenie |
|---|---|
| 0.95+ | Bezpośrednia tabela lub reguła |
| 0.80–0.95 | Jednoznaczny tekst |
| 0.60–0.80 | Wnioskowanie z kilku źródeł |
| <0.60 | Nie używać bez ostrzeżenia |

## Agent rozwoju wiedzy
Sam wykrywa: brakujące relacje, niepełne dane, sprzeczne informacje, nieznane
encje, potencjalne błędy OCR. Przykład: „Chaos Knight" vs „Knight of Chaos" —
ta sama jednostka? alias? błąd OCR?

## Pamięć i wydajność
**Nigdy:** nie ładuj całej książki / grafu / wszystkich embeddingów naraz.
**Stosuj:** lazy loading, batch processing, checkpointy, cache, indeksowanie,
kolejkowanie zadań.

## Agenty specjalistyczne
OCR Agent (dokumenty), Lore Agent (historia świata), Rules Agent (mechanika),
Data Agent (tabele), Graph Agent (relacje), Validation Agent (błędy), Strategy
Agent (armie i taktyka).
**Komunikacja:** agenci przekazują ID, metadane, fragmenty, wyniki analiz,
poziom pewności — nie całe dokumenty.

## Przygotowanie do przyszłości
Generator armii, analiza skuteczności jednostek, symulacje bitew, rekomendacje
zakupowe, analiza meta gry, asystent malowania, kampanie RPG, scenariusze.

## Zasada końcowa
Po dodaniu kolejnej książki system nie ma być większy i wolniejszy — ma być
**bardziej inteligentny, połączony i precyzyjny**. Celem nie jest przechowywanie
tekstu, lecz stworzenie cyfrowego eksperta Warhammer Fantasy.
