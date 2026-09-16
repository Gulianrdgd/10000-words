#!/usr/bin/env python3
"""
Enrich backend/app/data/words.json in place with:

  1. Noun gender ("m" | "f" | "mf" | "mp" | "fp"), from Lexique 3.83
     (lexique.org, CC BY-SA 4.0), falling back to English Wiktionary via
     kaikki.org for the ~7% of nouns Lexique leaves genderless (it blanks
     some very common ones like "maison", plus epicene nouns like "élève").
     When Wiktionary lists several noun homographs with different genders
     ("livre" m = book, f = pound), the one whose glosses mention our
     translation_en wins.
  2. An emoji picture for concrete words, matched on the exact CLDR emoji
     name (via emojibase-data) of a noun's translation, minus a blocklist of
     wrong-sense matches found by manual review, plus hand-picked emoji for
     common words a name match can't catch (eau, manger, rouge...).
  3. Example sentences for words that have none, from Tatoeba (tatoeba.org,
     CC BY 2.0 FR) French->English pairs. Picks sentences containing the
     lemma as an exact token, 3-12 tokens long, preferring ones whose other
     words are the most frequent (i.e. comprehensible). For nouns, a sentence
     is rejected if an adjacent article contradicts the noun's gender — a
     cheap filter against homograph senses ("le tour" vs "la tour").

Runs standalone on the existing words.json (word IDs never change, so a
user's review history stays attached) and is also called at the end of
build_dataset.py.
"""
import bz2
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
WORDS_PATH = SCRIPT_DIR.parent / "app" / "data" / "words.json"

LEXIQUE_URL = "http://www.lexique.org/databases/Lexique383/Lexique383.zip"
LEXIQUE_ZIP = SCRIPT_DIR / "lexique383.zip"
LEXIQUE_TSV = SCRIPT_DIR / "Lexique383.tsv"

KAIKKI_URL = "https://kaikki.org/dictionary/French/meaning/{a}/{ab}/{word}.jsonl"
KAIKKI_CACHE = SCRIPT_DIR / "kaikki_gender_cache.json"

TATOEBA_BASE = "https://downloads.tatoeba.org/exports/per_language"
TATOEBA_FILES = {
    "fra_sentences.tsv.bz2": f"{TATOEBA_BASE}/fra/fra_sentences.tsv.bz2",
    "eng_sentences.tsv.bz2": f"{TATOEBA_BASE}/eng/eng_sentences.tsv.bz2",
    "fra-eng_links.tsv.bz2": f"{TATOEBA_BASE}/fra/fra-eng_links.tsv.bz2",
}

FR_FREQ_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/fr/fr_50k.txt"
FR_FREQ_CACHE = SCRIPT_DIR / "fr_50k_raw.txt"

EMOJIBASE_URL = "https://cdn.jsdelivr.net/npm/emojibase-data@17.0.0/en/data.json"
EMOJIBASE_CACHE = SCRIPT_DIR / "emojibase_en.json"

# Name matches that picked the wrong sense of the translation (reviewed by hand).
EMOJI_BLOCKLIST = {
    "place", "touche", "cancer", "rock", "tir", "trompe", "nana", "grève", "planche", "banc",
    "ronde", "accroche", "pognon", "patte", "milan", "indic", "gonzesse", "mouchard", "rive",
    "brique", "sceau", "blouse", "gouffre", "forfait", "crosse", "lavabo", "livrée", "braguette",
    "cortège", "envolée", "lunette", "épi", "fourche", "navet", "chaire", "jugeote", "parterre",
    "averse", "roquette", "chaux", "chas", "mitard", "gisement", "molette", "huis", "pic",
    "blindage", "imprimeur", "paresse", "dodo", "garde",
}

# Common, picturable words whose translation doesn't exactly name an emoji.
EMOJI_EXTRA = {
    # nouns
    "eau": "💧", "voiture": "🚗", "livre": "📖", "argent": "💶", "main": "✋", "cœur": "❤️",
    "nuit": "🌙", "lettre": "✉️", "arbre": "🌳", "fleur": "🌸", "pomme": "🍎", "lune": "🌙",
    "mer": "🌊", "pluie": "🌧️", "neige": "❄️", "ville": "🏙️", "bébé": "👶", "père": "👨",
    "mère": "👩", "vin": "🍷", "bière": "🍺", "café": "☕", "thé": "🍵", "lait": "🥛",
    "œuf": "🥚", "fromage": "🧀", "gâteau": "🎂", "musique": "🎵", "film": "🎬", "photo": "📷",
    "journal": "📰", "ordinateur": "💻", "cadeau": "🎁", "médecin": "🧑‍⚕️", "docteur": "🧑‍⚕️",
    "police": "🚓", "policier": "👮", "soldat": "🪖", "roi": "🤴", "reine": "👸",
    "lumière": "💡", "plage": "🏖️", "forêt": "🌲", "vent": "🌬️", "vélo": "🚲", "bras": "💪",
    "dent": "🦷", "sang": "🩸", "œil": "👁️", "bouteille": "🍾", "couteau": "🔪",
    "pistolet": "🔫", "épée": "🗡️", "sac": "👜", "chaussure": "👞", "chapeau": "🎩",
    "robe": "👗", "chemise": "👕", "lunettes": "👓", "horloge": "🕰️", "anniversaire": "🎂",
    "fête": "🎉", "vacances": "🏖️", "football": "⚽", "chanson": "🎵", "piano": "🎹",
    "vache": "🐄", "mouton": "🐑", "loup": "🐺", "serpent": "🐍", "abeille": "🐝",
    "cerise": "🍒", "raisin": "🍇", "riz": "🍚", "soupe": "🍲", "bonbon": "🍬",
    "chocolat": "🍫", "argent de poche": "💶", "feuille": "🍃", "jardin": "🪴", "clown": "🤡",
    "cadeaux": "🎁", "courrier": "📬", "carte": "🗺️", "drapeau": "🚩", "verre": "🥛",
    # verbs
    "manger": "🍽️", "boire": "🥤", "dormir": "😴", "courir": "🏃", "nager": "🏊", "lire": "📖",
    "écrire": "✍️", "chanter": "🎤", "danser": "💃", "pleurer": "😢", "rire": "😂",
    "marcher": "🚶", "parler": "🗣️", "écouter": "👂", "voir": "👀", "penser": "🤔",
    "aimer": "❤️", "appeler": "📞", "payer": "💳", "acheter": "🛒", "travailler": "💼",
    "cuisiner": "🍳", "conduire": "🚗", "voyager": "🧳", "jouer": "🎲", "embrasser": "💋",
    "sourire": "🙂", "tomber": "🤕", "gagner": "🏆", "chercher": "🔎", "attendre": "⏳",
    # adjectives
    "rouge": "🟥", "bleu": "🟦", "vert": "🟩", "jaune": "🟨", "noir": "⬛", "blanc": "⬜",
    "violet": "🟪", "marron": "🟫", "heureux": "😊", "triste": "😢", "fatigué": "😴",
    "malade": "🤒", "chaud": "🥵", "froid": "🥶", "content": "😊", "fou": "🤪", "mort": "💀",
    "riche": "🤑", "surpris": "😮", "effrayé": "😨", "amoureux": "😍", "énervé": "😠",
}

SENTENCES_PER_WORD = 2
MIN_TOKENS, MAX_TOKENS = 3, 12
UNKNOWN_RANK = 60_000

_TOKEN_RE = re.compile(r"[a-zàâäéèêëïîôöùûüÿçœæ]+")

MASC_ARTICLES = {"le", "un", "du", "au", "ce", "cet", "mon", "ton", "son"}
FEM_ARTICLES = {"la", "une", "cette", "ma", "ta", "sa"}


def _fetch(url: str, path: Path) -> None:
    if not path.exists():
        print(f"Fetching {url} ...")
        urllib.request.urlretrieve(url, path)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower().replace("’", "'"))


# --- gender -------------------------------------------------------------------


def load_lexique_genders(nouns: set[str]) -> tuple[dict[str, str], set[str]]:
    """Returns ({noun: gender}, plural_only_nouns) for nouns Lexique genders."""
    _fetch(LEXIQUE_URL, LEXIQUE_ZIP)
    if not LEXIQUE_TSV.exists():
        with zipfile.ZipFile(LEXIQUE_ZIP) as z:
            z.extract("Lexique383.tsv", SCRIPT_DIR)

    weights: dict[str, dict[str, float]] = {}
    numbers: dict[str, set[str]] = {}
    with open(LEXIQUE_TSV, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            ortho = row["ortho"]
            if row["cgram"] != "NOM" or ortho not in nouns:
                continue
            numbers.setdefault(ortho, set()).add(row["nombre"])
            if row["genre"]:
                freq = float(row["freqfilms2"] or 0) + float(row["freqlivres"] or 0)
                weights.setdefault(ortho, {}).setdefault(row["genre"], 0.0)
                weights[ortho][row["genre"]] += freq + 0.01

    genders = {noun: max(w, key=w.get) for noun, w in weights.items()}
    plural_only = {noun for noun, nums in numbers.items() if nums == {"p"}}
    return genders, plural_only


def _normalize_wiktionary_gender(arg: str) -> str | None:
    # "mfbysense" (élève, enfant): masculine or feminine depending on who it refers to
    arg = arg.replace("-", "").replace("bysense", "")
    return arg if arg in {"m", "f", "mf", "mp", "fp"} else None


def kaikki_gender(word: str, translation_en: str, cache: dict) -> str | None:
    if word in cache:
        return cache[word]
    url = KAIKKI_URL.format(
        a=urllib.parse.quote(word[0]),
        ab=urllib.parse.quote(word[:2]),
        word=urllib.parse.quote(word),
    )
    entries = []
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            for line in resp.read().decode("utf-8").splitlines():
                entry = json.loads(line)
                if entry.get("pos") == "noun" and entry.get("word") == word:
                    entries.append(entry)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    time.sleep(0.05)

    candidates: list[tuple[str, str]] = []  # (gender, all glosses joined)
    for entry in entries:
        for tmpl in entry.get("head_templates", []):
            if tmpl.get("name") != "fr-noun":
                continue
            gender = _normalize_wiktionary_gender(tmpl.get("args", {}).get("1", ""))
            if gender:
                glosses = " ".join(g for s in entry.get("senses", []) for g in s.get("glosses", []))
                candidates.append((gender, glosses.lower()))

    result = None
    if candidates:
        distinct = {g for g, _ in candidates}
        result = candidates[0][0]
        if len(distinct) > 1:
            key = translation_en.lower().split(" / ")[0]
            for gender, glosses in candidates:
                if re.search(rf"\b{re.escape(key)}\b", glosses):
                    result = gender
                    break
    cache[word] = result
    return result


def add_genders(words: list[dict]) -> None:
    nouns = {w["lemma"].split()[0] for w in words if w["pos"] == "noun"}
    genders, plural_only = load_lexique_genders(nouns)

    cache = json.loads(KAIKKI_CACHE.read_text(encoding="utf-8")) if KAIKKI_CACHE.exists() else {}
    looked_up = 0
    for w in words:
        if w["pos"] != "noun":
            w["gender"] = None
            continue
        head = w["lemma"].split()[0]
        gender = genders.get(head)
        if gender and head in plural_only:
            gender += "p"
        if gender is None:
            gender = kaikki_gender(head, w["translation_en"], cache)
            looked_up += 1
            if looked_up % 50 == 0:
                KAIKKI_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                print(f"  kaikki lookups: {looked_up}")
        w["gender"] = gender
    KAIKKI_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


# --- emoji -------------------------------------------------------------------


def add_emoji(words: list[dict]) -> None:
    _fetch(EMOJIBASE_URL, EMOJIBASE_CACHE)
    by_name: dict[str, str] = {}
    for e in json.loads(EMOJIBASE_CACHE.read_text(encoding="utf-8")):
        # skip unsorted entries, skin-tone components and flags
        if e.get("group") not in (None, 2, 9):
            by_name.setdefault(e["label"].lower(), e["emoji"])

    for w in words:
        w["emoji"] = EMOJI_EXTRA.get(w["lemma"])
        if w["emoji"] or w["pos"] != "noun" or w["lemma"] in EMOJI_BLOCKLIST:
            continue
        for sense in re.split(r"\s*[/,;]\s*", w["translation_en"].lower()):
            sense = re.sub(r"^(a|an|the)\s+", "", re.sub(r"\(.*?\)", "", sense).strip())
            if sense in by_name:
                w["emoji"] = by_name[sense]
                break


# --- sentences ----------------------------------------------------------------


def load_rank_map() -> dict[str, int]:
    _fetch(FR_FREQ_URL, FR_FREQ_CACHE)
    ranks: dict[str, int] = {}
    with open(FR_FREQ_CACHE, encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            ranks.setdefault(line.split()[0].strip().lower(), i)
    return ranks


def _read_tsv_bz2(name: str):
    path = SCRIPT_DIR / name
    _fetch(TATOEBA_FILES[name], path)
    with bz2.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n").split("\t")


def load_tatoeba_pairs() -> list[tuple[str, str]]:
    links: dict[str, list[str]] = {}
    for fra_id, eng_id in _read_tsv_bz2("fra-eng_links.tsv.bz2"):
        links.setdefault(fra_id, []).append(eng_id)
    wanted_eng = {e for ids in links.values() for e in ids}
    eng = {sid: text for sid, _lang, text in _read_tsv_bz2("eng_sentences.tsv.bz2") if sid in wanted_eng}

    pairs = []
    for sid, _lang, text in _read_tsv_bz2("fra_sentences.tsv.bz2"):
        translations = [eng[e] for e in links.get(sid, []) if e in eng]
        if translations:
            pairs.append((text, min(translations, key=len)))
    return pairs


def _gender_conflicts(tokens: list[str], idx: int, gender: str | None) -> bool:
    if not gender or gender == "mf" or idx == 0:
        return False
    prev = tokens[idx - 1]
    if gender.startswith("m"):
        return prev in FEM_ARTICLES
    return prev in MASC_ARTICLES


def add_sentences(words: list[dict]) -> None:
    targets = {w["lemma"]: w for w in words if not w["sentences"] and " " not in w["lemma"]}
    ranks = load_rank_map()
    pairs = load_tatoeba_pairs()
    print(f"Loaded {len(pairs)} Tatoeba fr-en pairs")

    # lemma -> [(difficulty, length, fr, en)]
    found: dict[str, list[tuple[int, int, str, str]]] = {}
    seen_fr: set[str] = set()
    for fr, en in pairs:
        if fr in seen_fr:
            continue
        seen_fr.add(fr)
        tokens = tokenize(fr)
        if not (MIN_TOKENS <= len(tokens) <= MAX_TOKENS):
            continue
        for idx, tok in enumerate(tokens):
            word = targets.get(tok)
            if word is None or _gender_conflicts(tokens, idx, word.get("gender")):
                continue
            difficulty = max(
                (ranks.get(t, UNKNOWN_RANK) for i, t in enumerate(tokens) if i != idx), default=0
            )
            found.setdefault(tok, []).append((difficulty, len(tokens), fr, en))

    for lemma, candidates in found.items():
        candidates.sort()
        chosen: list[dict] = []
        used_en: set[str] = set()
        for _difficulty, _length, fr, en in candidates:
            if en in used_en:
                continue
            chosen.append({"fr": fr, "en": en})
            used_en.add(en)
            if len(chosen) == SENTENCES_PER_WORD:
                break
        targets[lemma]["sentences"] = chosen


def enrich(words: list[dict]) -> list[dict]:
    add_genders(words)
    add_emoji(words)
    add_sentences(words)
    return words


def main():
    with open(WORDS_PATH, encoding="utf-8") as f:
        words = json.load(f)
    enrich(words)
    with open(WORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)
        f.write("\n")
    nouns = [w for w in words if w["pos"] == "noun"]
    print(
        f"Wrote {len(words)} words: {sum(1 for w in nouns if w['gender'])}/{len(nouns)} nouns gendered, "
        f"{sum(1 for w in words if w['emoji'])} with emoji, "
        f"{sum(1 for w in words if w['sentences'])} with example sentences"
    )


if __name__ == "__main__":
    sys.exit(main())
