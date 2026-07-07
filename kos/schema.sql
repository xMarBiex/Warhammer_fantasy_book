-- Warhammer Fantasy — Knowledge Operating System (KOS)
-- Embedded store: Graph (Warstwa 2) + SQL (Warstwa 3) + Metadata (Warstwa 5/meta)
-- w jednym pliku SQLite. Vector (Warstwa 4) = ChromaDB osobno. Document Store
-- (Warstwa 1) = data/text/*. Zob. docs/ARCHITECTURE.md.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Metadata Layer ─────────────────────────────────────────────────────────
-- Źródła (książka + edycja). Każdy fakt wskazuje na jedno źródło.
CREATE TABLE IF NOT EXISTS sources (
  id        TEXT PRIMARY KEY,          -- np. 'ksiega-zasad-2e'
  book      TEXT NOT NULL,             -- 'Warhammer Fantasy Roleplay — Księga Zasad'
  edition   TEXT NOT NULL,             -- '2'
  system    TEXT NOT NULL,             -- 'WFRP' | 'WFB'
  language  TEXT NOT NULL DEFAULT 'pl',
  author    TEXT,
  notes     TEXT
);

-- ── Knowledge Graph (Warstwa 2) ────────────────────────────────────────────
-- Węzły: encje świata. `data` = pełny rekord (JSON) dla renderu/kontekstu.
CREATE TABLE IF NOT EXISTS nodes (
  id         TEXT PRIMARY KEY,         -- 'prof:akolita', 'book:ksiega-zasad-2e'
  type       TEXT NOT NULL,            -- Profession, Weapon, Spell, Book, ...
  name       TEXT NOT NULL,
  name_fold  TEXT NOT NULL,            -- nazwa bez polskich znaków, lowercase (do dopasowań)
  data       TEXT,                     -- JSON: pełny rekord encji
  source_id  TEXT REFERENCES sources(id),
  page       INTEGER,
  confidence REAL NOT NULL DEFAULT 0.95
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_fold ON nodes(name_fold);

-- Krawędzie: relacje z prowenancją i pewnością (wymóg specyfikacji).
CREATE TABLE IF NOT EXISTS edges (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  src        TEXT NOT NULL,            -- id węzła źródłowego
  rel        TEXT NOT NULL,            -- ADVANCES_TO, DEFINED_IN, CAN_USE, ...
  dst        TEXT NOT NULL DEFAULT '', -- id węzła docelowego ('' gdy niezmaterializowany)
  dst_name   TEXT NOT NULL DEFAULT '', -- nazwa docelowa (gdy węzeł jeszcze nie istnieje)
  source_id  TEXT REFERENCES sources(id),
  page       INTEGER,
  confidence REAL NOT NULL DEFAULT 0.95,
  UNIQUE(src, rel, dst, dst_name)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src, rel);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst, rel);

-- ── Relational Intelligence / SQL (Warstwa 3) ──────────────────────────────
-- Precyzyjne dane liczbowe. „Nigdy nie pytaj modelu o liczby" — pytaj tu.
-- Modyfikatory cech profesji WFRP (stringi '+10'/'+5'/'—' zachowane wiernie).
CREATE TABLE IF NOT EXISTS profession_stats (
  node_id   TEXT PRIMARY KEY REFERENCES nodes(id),
  name      TEXT NOT NULL,
  kind      TEXT NOT NULL,             -- 'podstawowa' | 'zaawansowana'
  page      INTEGER,
  -- cechy główne
  WW TEXT, US TEXT, K TEXT, Odp TEXT, Zr TEXT, Int TEXT, SW TEXT, Ogd TEXT,
  -- cechy drugorzędne
  A TEXT, Zyw TEXT, S TEXT, Wt TEXT, Sz TEXT, Mag TEXT, PO TEXT, PP TEXT,
  skills    TEXT,
  talents   TEXT,
  trappings TEXT,
  source_id TEXT REFERENCES sources(id),
  confidence REAL NOT NULL DEFAULT 0.95
);
CREATE INDEX IF NOT EXISTS idx_prof_kind ON profession_stats(kind);

-- Oręż (Tabela 5-4 Broń biała, 5-5 Broń strzelecka, Amunicja; str. 110).
CREATE TABLE IF NOT EXISTS weapon_stats (
  node_id      TEXT PRIMARY KEY REFERENCES nodes(id),
  name         TEXT NOT NULL,
  klasa        TEXT NOT NULL,             -- 'biała' | 'strzelecka' | 'amunicja'
  page         INTEGER,
  cena         TEXT,                      -- np. '20 zk', '3 s', '—'
  obciazenie   TEXT,                      -- punkty Obciążenia (string; bywa '—')
  kategoria    TEXT,                      -- grupa oręża, np. 'Dwuręczna'
  sila_broni   TEXT,                      -- obrażenia: 'S', 'S-4', 'S+1', '3'…
  zasieg       TEXT,                      -- tylko strzelecka, np. '30/60'
  przeladowanie TEXT,                     -- tylko strzelecka, np. 'Akcja'
  cechy        TEXT,                      -- cechy oręża (np. 'druzgoczący, szybki')
  dostepnosc   TEXT,
  dwureczna    INTEGER NOT NULL DEFAULT 0,-- 1 = wymaga dwóch rąk
  source_id    TEXT REFERENCES sources(id),
  confidence   REAL NOT NULL DEFAULT 0.95
);
CREATE INDEX IF NOT EXISTS idx_weapon_klasa ON weapon_stats(klasa);

-- Pancerz (Tabela 5-6: Opancerzenie złożone; str. 114).
CREATE TABLE IF NOT EXISTS armour_stats (
  node_id    TEXT PRIMARY KEY REFERENCES nodes(id),
  name       TEXT NOT NULL,              -- np. 'Hełm', 'Kolczuga'
  material   TEXT NOT NULL,              -- 'skórzana' | 'kolcza' | 'płytowa'
  page       INTEGER,
  cena       TEXT,
  obciazenie TEXT,
  lokacje    TEXT,                       -- chronione lokacje, np. 'korpus, ręce'
  pz         INTEGER,                    -- Punkty Zbroi
  dostepnosc TEXT,
  source_id  TEXT REFERENCES sources(id),
  confidence REAL NOT NULL DEFAULT 0.95
);
CREATE INDEX IF NOT EXISTS idx_armour_material ON armour_stats(material);

-- Czary (Rozdział VII: Magia). Tradycja = szkoła/dziedzina magii.
CREATE TABLE IF NOT EXISTS spell_stats (
  node_id       TEXT PRIMARY KEY REFERENCES nodes(id),
  name          TEXT NOT NULL,
  tradycja      TEXT NOT NULL,           -- np. 'Magia powszechna', 'Tradycja Ognia'
  pm            INTEGER,                  -- Wymagany Poziom Mocy (liczba do rzucenia)
  czas_rzucania TEXT,
  zasieg        TEXT,
  czas_trwania  TEXT,
  skladnik      TEXT,
  opis          TEXT,
  page          INTEGER,
  source_id     TEXT REFERENCES sources(id),
  confidence    REAL NOT NULL DEFAULT 0.95
);
CREATE INDEX IF NOT EXISTS idx_spell_tradycja ON spell_stats(tradycja);

-- Ekwipunek i usługi (Tabele 5-9…5-19; str. 119–126). Ceny w SQL.
CREATE TABLE IF NOT EXISTS item_costs (
  node_id    TEXT PRIMARY KEY REFERENCES nodes(id),
  name       TEXT NOT NULL,
  kategoria  TEXT NOT NULL,              -- np. 'Oświetlenie', 'Wierzchowce', 'Trucizny'
  cena       TEXT,
  obciazenie TEXT,
  dostepnosc TEXT,
  page       INTEGER,
  source_id  TEXT REFERENCES sources(id),
  confidence REAL NOT NULL DEFAULT 0.95
);
CREATE INDEX IF NOT EXISTS idx_item_kat ON item_costs(kategoria);

-- Bestiariusz (Rozdział XI). Profile potworów — wartości BEZWZGLĘDNE (nie modyfikatory).
CREATE TABLE IF NOT EXISTS bestiary_profiles (
  node_id   TEXT PRIMARY KEY REFERENCES nodes(id),
  name      TEXT NOT NULL,
  page      INTEGER,
  WW TEXT, US TEXT, K TEXT, Odp TEXT, Zr TEXT, Int TEXT, SW TEXT, Ogd TEXT,
  A TEXT, Zyw TEXT, S TEXT, Wt TEXT, Sz TEXT, Mag TEXT, PO TEXT, PP TEXT,
  skills        TEXT,
  talents       TEXT,
  special       TEXT,                 -- zasady specjalne
  armour        TEXT,                 -- zbroja
  armour_points TEXT,                 -- Punkty Zbroi wg lokacji
  weapons       TEXT,                 -- uzbrojenie
  source_id  TEXT REFERENCES sources(id),
  confidence REAL NOT NULL DEFAULT 0.95
);

-- Miejsce na kolejne tabele SQL (do zrobienia po ekstrakcji tabel):
--   critical_hits
