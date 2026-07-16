#!/usr/bin/env python3
"""Agent KOS — Reasoning Engine (Warstwa 5) na lokalnym Bielku przez Ollamę.

Zamiennik agent/agent.py (Claude API) — ten sam kontrakt ask(messages, on_event)
-> (tekst, użyte_narzędzia). Wymaga uruchomionej Ollamy i pobranego modelu:

    ollama pull hf.co/speakleash/Bielik-1.5B-v3.0-Instruct-GGUF:Q8_0
    ollama serve                            # jeśli jeszcze nie działa
    python agent/ollama_agent.py "statystyki akolity"

Wywoływanie narzędzi NIE korzysta z natywnego `tools` API Ollamy — tylko
Bielik-11B-v3.0 ma do tego szablon w Ollamie, mniejsze warianty (4.5B, 1.5B)
zwracają błąd "does not support tools". Zamiast tego model dostaje opis
narzędzi w prompt-cie i ma zawsze odpowiadać jednym obiektem JSON, którego
strukturę (w tym dozwolone nazwy narzędzi jako `enum`) wymusza JSON Schema
przekazany w `format` (structured outputs Ollamy — ograniczone dekodowanie
gramatyczne, nie tylko "prośba" w prompt-cie). Dzięki temu model fizycznie nie
może wygenerować nieistniejącej nazwy narzędzia — mniejsze modele (1.5B, 4.5B)
mylą się w dosłownym odtwarzaniu takich identyfikatorów. Działa z dowolnym
modelem, niezależnie od natywnego wsparcia "tools".
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.agent import SYSTEM  # reuse istniejący prompt roli/ograniczeń  # noqa: E402
from agent.tools import TOOLS, run_tool, w_temacie_gry  # noqa: E402

# Model: zmień przez zmienną KOS_MODEL bez edycji kodu. Domyślnie 4.5B — test
# 20 pytań pokazał wyraźnie lepszą trafność niż 1.5B (16/20 vs 9/20 poprawnych),
# kosztem ~7x dłuższego czasu odpowiedzi. Warianty do wyboru:
#   SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0              (domyślny, ~1-5 min/pytanie, 8K kontekstu)
#   hf.co/speakleash/Bielik-1.5B-v3.0-Instruct-GGUF:Q8_0   (najszybszy, ~30-100s/pytanie, mniej trafny)
#   SpeakLeash/bielik-11b-v3.0-instruct:Q4_K_M             (bardzo wolny na CPU, 32K kontekstu)
MODEL = os.environ.get("KOS_MODEL", "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MAX_TOOL_ROUNDS = 6
NUM_CTX = int(os.environ.get("KOS_NUM_CTX", "8192"))
# Niska temperatura = mniej "kreatywnych" literówek w nazwach (np. odmiana
# polskich rzeczowników) i bardziej powtarzalne trzymanie się formatu JSON.
TEMPERATURE = float(os.environ.get("KOS_TEMPERATURE", "0.2"))
# Ile Ollama trzyma model w pamięci po ostatnim zapytaniu — bez tego domyślne
# 5 minut i każde pytanie po dłuższej przerwie płaci ~kilkanaście-kilkadziesiąt
# sekund za ponowne wczytanie modelu.
KEEP_ALIVE = os.environ.get("KOS_KEEP_ALIVE", "30m")
# Sekundy na pojedyncze zapytanie do Ollamy — na CPU bez GPU jedna runda z
# długim system promptem potrafi trwać kilka-kilkanaście minut.
REQUEST_TIMEOUT = int(os.environ.get("KOS_REQUEST_TIMEOUT", "1800"))


def _describe_tools():
    lines = []
    for t in TOOLS:
        props = t["input_schema"].get("properties", {})
        params = ", ".join(f'{k}: {v.get("type", "string")}' for k, v in props.items())
        lines.append(f'- {t["name"]}({params}) — {t["description"]}')
    return "\n".join(lines)


_TOOL_NAMES = [t["name"] for t in TOOLS]

# JSON Schema egzekwowany przez Ollamę (structured outputs, grammar-constrained
# decoding) — "tool" MUSI być jedną z prawdziwych nazw narzędzi, model nie
# może wygenerować literówki/wymyślonej nazwy.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["tool", "answer"]},
        "tool": {"type": "string", "enum": _TOOL_NAMES},
        "args": {"type": "object"},
        "text": {"type": "string"},
    },
    "required": ["action"],
}


SYSTEM_WITH_TOOLS = SYSTEM + f"""

# NARZĘDZIA (dostęp do warstw danych — nie zgaduj liczb, użyj narzędzia)
{_describe_tools()}

Zawsze odpowiadaj WYŁĄCZNIE pojedynczym obiektem JSON, w jednym z dwóch formatów:

1) Gdy potrzebujesz danych z narzędzia:
   {{"action": "tool", "tool": "<nazwa_narzędzia>", "args": {{"<parametr>": "<wartość>"}}}}

2) Gdy masz już wystarczające dane, by odpowiedzieć graczowi:
   {{"action": "answer", "text": "<pełna odpowiedź po polsku>"}}

Gdy w kolejnej wiadomości dostaniesz "WYNIK NARZĘDZIA" — to są już prawdziwe
dane z Księgi Zasad. NIGDY nie wołaj ponownie tego samego narzędzia z tymi
samymi lub podobnymi argumentami — od razu odpowiedz {{"action": "answer", ...}}
na podstawie tych danych.

Jeśli konkretne narzędzie (np. `czar_szczegoly`, `bron_szczegoly`,
`profesja_szczegoly`) zwróci `"znaleziono": false` — NIE poddawaj się od razu.
To, że danej rzeczy nie ma w konkretnej tabeli, nie znaczy że jej nie ma w
Księdze Zasad — mechaniki, zasady i lore (np. punkty przeznaczenia, testy
cech, zasady walki) są opisane prozą, nie tabelą. W takim wypadku spróbuj
`szukaj_zasad`, zanim odpowiesz, że nie masz danych.

Przykład 1 (dane konkretnej profesji):
Użytkownik: jakie sa statystyki akolity?
Ty: {{"action": "tool", "tool": "profesja_szczegoly", "args": {{"nazwa": "Akolita"}}}}
[system]: WYNIK NARZĘDZIA: {{"znaleziono": true, "nazwa": "Akolita", "cechy_glowne": {{"WW": "+5"}}, "strona": 32, ...}}
Ty: {{"action": "answer", "text": "Akolita ma modyfikator WW +5 (Księga Zasad, str. 32)."}}

Przykład 2 (pytanie o rekordową wartość cechy — słowa: „która/jaka profesja ma
największe/najwyższe/najlepsze”, „podaj profesje z najwyższym” — to ZAWSZE
`porownaj_ceche`, NIGDY `profesja_szczegoly` ani `szukaj_zasad`, bo cecha
„WW” nie jest nazwą profesji):
Użytkownik: podaj profesje z najwyzszym WW
Ty: {{"action": "tool", "tool": "porownaj_ceche", "args": {{"cecha": "WW", "tryb": "max"}}}}
[system]: WYNIK NARZĘDZIA: {{"znaleziono": true, "cecha": "WW", "wynik": [{{"profesja": "Fechtmistrz", "wartosc": "+20", "strona": 50}}, {{"profesja": "Zabójca demonów", "wartosc": "+20", "strona": 44}}]}}
Ty: {{"action": "answer", "text": "Największy modyfikator WW (+20) mają Fechtmistrz i Zabójca demonów (Księga Zasad, tabele cech)."}}

# KRYTYCZNE — powyższe przykłady to TYLKO wzór FORMATU odpowiedzi, nie źródło
# faktów. „Fechtmistrz”/„Akolita”/„+20”/„+5” to wartości z przykładu dla WW —
# dla innej cechy (US, K, Odp…) czy innej profesji BĘDĄ INNE. Zawsze bierz
# nazwy i liczby WYŁĄCZNIE z najnowszego "WYNIK NARZĘDZIA" w tej rozmowie,
# nigdy z przykładu powyżej. Jeśli wynik ma tylko jedną profesję — podaj
# jedną, NIE dopisuj drugiej z pamięci czy z przykładu."""


def _chat(messages):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "format": RESPONSE_SCHEMA,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"num_ctx": NUM_CTX, "temperature": TEMPERATURE},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    # CPU-only inference na słabszym sprzęcie bywa bardzo wolne (długi system
    # prompt + brak GPU) — hojny timeout, żeby nie przerywać w połowie generacji.
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read())


def _find_json_object(text):
    """Zwraca pierwszy zbalansowany blok {...} w tekście albo None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _not_found(result):
    """Rozpoznaje odpowiedź narzędzia mówiącą 'nie znaleziono' (a nie realne
    dane) — sygnał, że warto spróbować szukaj_zasad zamiast się poddawać."""
    return isinstance(result, dict) and (result.get("znaleziono") is False or "blad" in result)


def _echoes_followup(answer, followup):
    """Bardzo mały model pod presją długiego kontekstu czasem zamiast
    wykonać instrukcję — dosłownie ją kopiuje jako swoją 'odpowiedź'
    (degeneracja typowa dla 1-2B modeli). Wykrywamy to porównując początek
    odpowiedzi z treścią komunikatu, który właśnie wysłaliśmy."""
    a = answer.strip()
    return len(a) >= 20 and a[:60].lower() in followup.lower()


def _parse_envelope(content):
    """Parsuje odpowiedź modelu jako obiekt {"action": "tool"|"answer", ...}.

    `format: "json"` w Ollamie gwarantuje poprawną składnię JSON, ale dla
    pewności (obudowanie w ``` albo dodatkowy tekst) i tak wyciągamy pierwszy
    zbalansowany blok {...} zamiast ufać całej treści."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    block = _find_json_object(text) or text
    try:
        obj = json.loads(block)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


_OFF_TOPIC_REPLY = ("Odpowiadam wyłącznie na pytania o grę Warhammer Fantasy Roleplay — "
                     "to pytanie wygląda na spoza tematu. Zapytaj mnie o profesje, zasady, "
                     "czary, ekwipunek albo świat gry.")


def ask(messages, on_event=None):
    """Uruchamia pętlę tool-use na lokalnym Bieliku i zwraca (tekst, użyte_narzędzia)."""
    # Strażnik tematu w kodzie, PRZED wywołaniem modelu — testy pokazały, że
    # sam model (1.5B i 4.5B) czasem ignoruje instrukcję z system promptu
    # i odpowiada wprost na pytania spoza gry (patrz w_temacie_gry).
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if last_user and not w_temacie_gry(last_user):
        return _OFF_TOPIC_REPLY, []

    convo = [{"role": "system", "content": SYSTEM_WITH_TOOLS}]
    convo += [{"role": m["role"], "content": m["content"]} for m in messages]
    used = []
    fallback = "Nie udało mi się sformułować odpowiedzi na to pytanie — spróbuj przeformułować."
    prev_followup = None

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            data = _chat(convo)
        except (urllib.error.URLError, TimeoutError) as e:
            return (f"Nie udało się połączyć z Ollamą pod {OLLAMA_URL} ({e}). "
                    "Upewnij się, że działa `ollama serve` i model jest pobrany "
                    f"(`ollama pull {MODEL}`).", used)

        content = ((data.get("message") or {}).get("content") or "").strip()
        obj = _parse_envelope(content)

        # model nie trzymał się formatu — potraktuj surowy tekst jako odpowiedź
        if obj is None or obj.get("action") not in ("tool", "answer"):
            return content or fallback, used

        if obj["action"] == "answer":
            text = (obj.get("text") or "").strip()
            if prev_followup and _echoes_followup(text, prev_followup):
                # model skopiował instrukcję zamiast na nią odpowiedzieć —
                # to NIE jest realna odpowiedź, nie pokazuj jej użytkownikowi
                return ("Mam potrzebne dane, ale nie udało mi się z nich "
                        "sformułować odpowiedzi — spróbuj zadać pytanie "
                        "prościej albo inaczej.", used)
            return text or fallback, used

        name = obj.get("tool")
        args = obj.get("args") or {}
        if not isinstance(name, str):
            return content or fallback, used

        if on_event:
            on_event(f"{name}({args})")
        used.append({"tool": name, "input": args})
        result = run_tool(name, args)
        convo.append({"role": "assistant", "content": content})

        # Komunikaty celowo krótkie i bez wklejonych przykładów JSON — dłuższe,
        # "gotowe do skopiowania" instrukcje model czasem kopiuje dosłownie
        # jako własną odpowiedź zamiast je wykonać (patrz _echoes_followup).
        wynik = "WYNIK: " + json.dumps(result, ensure_ascii=False)
        if _not_found(result) and name == "szukaj_zasad":
            followup = (wynik + "\n\nWyszukiwanie nic nie dało. Spróbuj innego, "
                        "krótszego pytania w szukaj_zasad, a jeśli znowu się nie "
                        "uda — szczerze przyznaj, że nie masz tych danych.")
        elif _not_found(result):
            # pole "info" bywa konkretną podpowiedzią co do WŁAŚCIWEGO
            # narzędzia (np. profesja_szczegoly -> porownaj_ceche dla
            # skrótu cechy) — nie nadpisuj jej sztywnym "spróbuj szukaj_zasad",
            # tylko każ modelowi się do niej zastosować.
            followup = (wynik + "\n\nNie znaleziono. Zastosuj się do podpowiedzi "
                        'w polu "info" i użyj właściwego narzędzia. Jeśli żadne '
                        "nie pomoże, przyznaj że nie masz tych danych.")
        elif name == "szukaj_zasad":
            followup = (wynik + "\n\nMasz już fragmenty księgi. Napisz "
                        "odpowiedź dla gracza na ich podstawie, z numerem "
                        "strony. Nie szukaj ponownie.")
        else:
            followup = (wynik + "\n\nMasz już dane. Odpowiedz teraz graczowi "
                        "na ich podstawie.")
        convo.append({"role": "user", "content": followup})
        prev_followup = followup

    return ("Przekroczono limit kroków rozumowania — spróbuj zawęzić pytanie.", used)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "jakie są statystyki akolity i do jakich profesji może awansować?"
    ans, used = ask([{"role": "user", "content": q}],
                     on_event=lambda e: print(f"  ↳ {e}", file=sys.stderr))
    print(ans)
