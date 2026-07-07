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

-- Miejsce na kolejne tabele SQL (do zrobienia po ekstrakcji tabel):
--   weapon_stats, armour_stats, item_costs, spell_stats, critical_hits, bestiary_profiles
