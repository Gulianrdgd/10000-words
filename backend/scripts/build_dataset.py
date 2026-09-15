#!/usr/bin/env python3
"""
Build words.json for the French vocabulary app — 10,000 words.

Pipeline:
  1. Fetch the hermitdave/FrequencyWords French frequency corpus from GitHub
     (real-world frequency ranking, ~50k word forms) and its English
     counterpart (used only to score candidate translations, see step 4).
  2. Load our curated word list (curated_words.json): ~285 hand-authored
     entries (translation, POS, CEFR estimate, 2 example sentences each) for
     the highest-frequency words, including all closed-class function words
     (pronouns, articles, prepositions...) that a bulk dictionary handles
     badly (see step 4).
  3. Fetch pquentin/wiktionary-translations' French-Wiktionary extraction
     (~81k French headword -> English translation rows) to fill out the
     remaining ~9,715 words needed to reach 10,000, ranked by real French
     word frequency.
  4. For each bulk headword, multiple candidate translations often exist
     (Wiktionary lists every sense). Picking the wrong one is common for
     polysemous words ("est" the verb vs. "est" = east). We score every
     candidate by ENGLISH word frequency and keep the most common one — a
     cheap proxy for "primary sense" that works well in practice, verified
     against dozens of spot-checks during development.
  5. Merge: curated entries (with sentences) for the top tier, bulk entries
     (no sentences — see the app's session_composer, which only offers
     modes 1/2 for sentence-less words) for the rest. Sort by real
     frequency_rank, write backend/app/data/words.json.

Scope note: the original plan called for Tatoeba-sourced example sentences
for all 1000+ words. This sandboxed environment's network egress only
reaches GitHub/PyPI/npm — Tatoeba and dictionary/LLM APIs are unreachable —
so only the curated tier has example sentences; the bulk tier trades sentence
context for reaching real 10,000-word coverage. See the README for the
full rationale.
"""
import csv
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

FR_FREQ_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/fr/fr_50k.txt"
FR_FREQ_CACHE = SCRIPT_DIR / "fr_50k_raw.txt"

EN_FREQ_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/en/en_50k.txt"
EN_FREQ_CACHE = SCRIPT_DIR / "en_50k_raw.txt"

DICT_URL = "https://raw.githubusercontent.com/pquentin/wiktionary-translations/master/frwiktionary-20140612-euradicfmt.csv"
DICT_CACHE = SCRIPT_DIR / "frwiktionary_raw.csv"

CURATED_PATH = SCRIPT_DIR / "curated_words.json"
OUTPUT_PATH = SCRIPT_DIR.parent / "app" / "data" / "words.json"

TARGET_WORD_COUNT = 10_000

POS_MAP = {"S": "noun", "V": "verb", "J": "adjective", "D": "adverb"}

_WORD_RE = re.compile(r"^[a-zàâäéèêëïîôöùûüçñ]+$")
_MULTI_WORD_TRANSLATION_PENALTY = 20_000
_UNSEEN_ENGLISH_WORD_RANK = 60_000
_COGNATE_RATIO_THRESHOLD = 0.35

# Headwords that are really just inflected/conjugated surface forms of a word
# already covered elsewhere (often the curated tier), or dictionary noise
# (an abbreviation artifact, a proper-noun collision). fr_50k.txt ranks raw
# word FORMS, not lemmas, so e.g. "est" (the extremely common verb form of
# "être") independently outranks and collides with the unrelated noun
# headword "est" ("east") -- found by manually auditing the first ~1000
# generated entries.
EXCLUDE_BULK_HEADWORDS = {
    "est", "vu", "sera", "sam", "amis", "écoutez", "folle", "con",
    "grosse", "vieille", "chère", "henry",
    "ha", "gagne", "claire", "amène", "robert", "salaud", "vendu", "noire",
    "vole", "bel",
    # Given-name / ethnonym / brand-name headword collisions, and a handful
    # of entries whose only dictionary sense is an obscure moth/butterfly
    # species' common name -- both dictionary-extraction artifacts with
    # ~zero value as vocabulary to learn.
    "kim", "maria", "laura", "ron", "thompson", "andi", "mam", "adi", "dia",
    "gao", "bai", "sui", "chong", "pare", "tama", "kei", "wu", "wan", "ga",
    "mina", "yi", "han", "gupta", "bora", "crow", "texan", "liberty",
    "canadienne", "tupperware", "minerve", "cassandre", "eden", "ottawa",
    "apollon", "pegase", "diane", "tiffany", "vulcain", "déplacée",
    "rouillée", "risée", "mere", "moïse", "alaska", "cie",
}

# A handful of profane/vulgar entries that surface early (this frequency
# corpus is subtitle-derived) and aren't worth teaching by default.
EXCLUDE_PROFANITY = {
    "merde", "putain", "foutre", "gueule", "bordel", "cul", "connard",
    "salope", "chier", "couillon", "bite", "niquer", "enculé", "branler", "pute",
    "foutu",
}

# Verified corrections for specific bulk headwords where the automated
# picker (cognate match, then English-frequency fallback) still lands on a
# wrong or misleadingly generic sense -- found via manual audit of the
# generated output, ranks 1-1000.
TRANSLATION_OVERRIDES: dict[str, tuple[str, str]] = {
    "protéger": ("verb", "protect"),
    "décider": ("verb", "decide"),
    "abord": ("noun", "approach"),
    "marche": ("noun", "walk"),
    "face": ("noun", "face"),
    "part": ("noun", "share"),
    "super": ("adjective", "great"),
    "blague": ("noun", "joke"),
    "utiliser": ("verb", "use"),
    "sac": ("noun", "bag"),
    # Classic French/English "false friends": identical or near-identical
    # spelling to an English word with a *different* meaning, which the
    # cognate-priority tier above cannot tell apart from a true cognate.
    "car": ("conjunction", "because"),
    "grave": ("adjective", "serious"),
    "retard": ("noun", "delay"),
    "état": ("noun", "state"),
    "nouvelle": ("noun", "news"),
    "désolé": ("adjective", "sorry"),
    "garde": ("noun", "guard"),
    "écrit": ("adjective", "written"),
    "avocat": ("noun", "lawyer"),
    "actuellement": ("adverb", "currently"),
    "assister": ("verb", "attend"),
    "blesser": ("verb", "injure"),
    "bras": ("noun", "arm"),
    "coin": ("noun", "corner"),
    "collège": ("noun", "middle school"),
    "commander": ("verb", "order"),
    "crayon": ("noun", "pencil"),
    "déception": ("noun", "disappointment"),
    "éventuellement": ("adverb", "possibly"),
    "journée": ("noun", "day"),
    "librairie": ("noun", "bookstore"),
    "location": ("noun", "rental"),
    "monnaie": ("noun", "change"),
    "patron": ("noun", "boss"),
    "phrase": ("noun", "sentence"),
    "physicien": ("noun", "physicist"),
    "préservatif": ("noun", "condom"),
    "prune": ("noun", "plum"),
    "sale": ("adjective", "dirty"),
    "sensible": ("adjective", "sensitive"),
    "sympathique": ("adjective", "nice"),
    "veste": ("noun", "jacket"),
    "large": ("adjective", "wide"),
    "but": ("noun", "goal"),
    "dame": ("noun", "lady"),
    "clé": ("noun", "key"),
    "prise": ("noun", "grip"),
    "bière": ("noun", "beer"),
    "entrée": ("noun", "entrance"),
    "enceinte": ("adjective", "pregnant"),
    "sol": ("noun", "ground"),
    "mignon": ("adjective", "cute"),
    "flic": ("noun", "cop"),
    "lycée": ("noun", "high school"),
    "poser": ("verb", "to place"),
    "lâche": ("adjective", "cowardly"),
    "enlever": ("verb", "remove"),
    "permis": ("noun", "permit"),
    "frappé": ("adjective", "struck"),
    "frapper": ("verb", "hit"),
    "agir": ("verb", "to act"),
    "chapeau": ("noun", "hat"),
    "valeur": ("noun", "value"),
    "malin": ("adjective", "cunning"),
    "poids": ("noun", "weight"),
    "cent": ("adjective", "hundred"),
    "poulet": ("noun", "chicken"),
    "connaissance": ("noun", "knowledge"),
    "flingue": ("noun", "gun"),
    "chinois": ("adjective", "Chinese"),
    "couche": ("noun", "layer"),
    "puissance": ("noun", "power"),
    "épée": ("noun", "sword"),
    "puce": ("noun", "flea"),
    "canon": ("noun", "cannon"),
    "côte": ("noun", "coast"),
    "piscine": ("noun", "swimming pool"),
    "inquiet": ("adjective", "worried"),
    "taire": ("verb", "to silence"),
    "gants": ("noun", "gloves"),
    "sou": ("noun", "penny"),
    "passagère": ("adjective", "passing"),
    "fiancée": ("noun", "fiancée"),
}


def _fetch(url: str, cache_path: Path) -> None:
    if not cache_path.exists():
        print(f"Fetching {url} ...")
        urllib.request.urlretrieve(url, cache_path)


def load_rank_map(cache_path: Path) -> dict[str, int]:
    ranks: dict[str, int] = {}
    with open(cache_path, encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            word = line.split()[0].strip().lower()
            if word not in ranks:
                ranks[word] = i
    return ranks


def load_curated() -> list[dict]:
    with open(CURATED_PATH, encoding="utf-8") as f:
        return json.load(f)


def cefr_estimate_for_rank(rank: int) -> str:
    if rank <= 1000:
        return "A1"
    if rank <= 3000:
        return "A2"
    if rank <= 6000:
        return "B1"
    return "B2"


def build_bulk_dictionary() -> dict[str, list[tuple[str, str]]]:
    """Returns {french_headword: [(pos_code, english_translation), ...]}."""
    by_word: dict[str, list[tuple[str, str]]] = {}
    with open(DICT_CACHE, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        for row in reader:
            if len(row) < 5:
                continue
            fr, pos, _label, en, _en_pos = row[0], row[1], row[2], row[3], row[4]
            by_word.setdefault(fr, []).append((pos, en))
    return by_word


def _is_plausible_translation(en: str) -> bool:
    stripped = en.replace(" ", "").replace("-", "")
    return bool(stripped) and stripped.isalpha() and len(en) > 1


def _english_commonness_rank(en: str, en_ranks: dict[str, int]) -> int:
    key = en.lower()
    if " " in key:
        # Multi-word phrases are deprioritized but still rankable, using
        # their rarest component word so "get up" doesn't outrank "rise".
        sub_ranks = [en_ranks.get(w, _UNSEEN_ENGLISH_WORD_RANK) for w in key.split()]
        return max(sub_ranks) + _MULTI_WORD_TRANSLATION_PENALTY
    return en_ranks.get(key, _UNSEEN_ENGLISH_WORD_RANK)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _levenshtein(a: str, b: str) -> int:
    a, b = a.lower(), b.lower()
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def _cognate_ratio(fr: str, en: str) -> float:
    """0.0 = identical spelling; used to catch French/English cognates
    (milieu/milieu, dossier/dossier, protéger/protect) that the pure
    English-frequency heuristic below would lose to an unrelated but far
    more common English word appearing elsewhere in the same headword's
    sense list (e.g. "milieu" -> "mean", "protéger" -> "back")."""
    fr_norm = _strip_accents(fr.lower())
    return _levenshtein(fr_norm, en.lower()) / max(len(fr_norm), len(en))


def pick_best_translation(
    fr: str, entries: list[tuple[str, str]], en_ranks: dict[str, int]
) -> tuple[str, str] | None:
    # Proper-noun collisions (Sam, Amis, Sera...) almost always come from
    # obscure/wrong senses, so lowercase candidates are strongly preferred;
    # only fall back to a capitalized one if it's all that's on offer.
    candidates = [(pos, en) for pos, en in entries if _is_plausible_translation(en) and en[:1].islower()]
    if not candidates:
        candidates = [(pos, en) for pos, en in entries if _is_plausible_translation(en)]
    if not candidates:
        return None

    cognates = [
        (pos, en) for pos, en in candidates if " " not in en and _cognate_ratio(fr, en) <= _COGNATE_RATIO_THRESHOLD
    ]
    if cognates:
        cognates.sort(key=lambda pe: _cognate_ratio(fr, pe[1]))
        return cognates[0]

    candidates.sort(key=lambda pe: _english_commonness_rank(pe[1], en_ranks))
    return candidates[0]


def build_bulk_words(
    fr_ranks: dict[str, int],
    en_ranks: dict[str, int],
    exclude_lemmas: set[str],
    count_needed: int,
) -> list[dict]:
    dictionary = build_bulk_dictionary()

    candidates: list[tuple[int, str, str, str]] = []  # (rank, lemma, pos, translation)
    for fr, entries in dictionary.items():
        # Single-token, lowercase headwords only: multi-word phrases, proper
        # nouns (capitalized) and elided/hyphenated forms are noisy at scale.
        if not fr.islower() or not _WORD_RE.match(fr):
            continue
        if fr in exclude_lemmas or fr in EXCLUDE_BULK_HEADWORDS or fr in EXCLUDE_PROFANITY:
            continue
        rank = fr_ranks.get(fr)
        if rank is None:
            continue

        if fr in TRANSLATION_OVERRIDES:
            pos, translation = TRANSLATION_OVERRIDES[fr]
        else:
            best = pick_best_translation(fr, entries, en_ranks)
            if best is None:
                continue
            pos_code, translation = best
            pos = POS_MAP.get(pos_code, "noun")
        candidates.append((rank, fr, pos, translation))

    candidates.sort(key=lambda c: c[0])
    candidates = candidates[:count_needed]

    return [
        {
            "lemma": lemma,
            "pos": pos,
            "translation_en": translation,
            "cefr_estimate": cefr_estimate_for_rank(rank),
            "sentences": [],
            "frequency_rank": rank,
        }
        for rank, lemma, pos, translation in candidates
    ]


def build() -> list[dict]:
    _fetch(FR_FREQ_URL, FR_FREQ_CACHE)
    _fetch(EN_FREQ_URL, EN_FREQ_CACHE)
    _fetch(DICT_URL, DICT_CACHE)

    fr_ranks = load_rank_map(FR_FREQ_CACHE)
    en_ranks = load_rank_map(EN_FREQ_CACHE)
    curated = load_curated()

    matched = []
    unmatched = []
    for entry in curated:
        lemma_key = entry["lemma"].lower().split()[0].replace("'", "")
        rank = fr_ranks.get(entry["lemma"].lower()) or fr_ranks.get(lemma_key)
        if rank is not None:
            matched.append({**entry, "frequency_rank": rank})
        else:
            unmatched.append(entry)

    matched.sort(key=lambda w: w["frequency_rank"])
    next_rank = (matched[-1]["frequency_rank"] if matched else 0) + 1
    for entry in unmatched:
        matched.append({**entry, "frequency_rank": next_rank})
        next_rank += 1

    curated_words = matched
    curated_lemmas = {w["lemma"].lower() for w in curated_words}

    bulk_words = build_bulk_words(
        fr_ranks,
        en_ranks,
        exclude_lemmas=curated_lemmas,
        count_needed=max(0, TARGET_WORD_COUNT - len(curated_words)),
    )

    words = curated_words + bulk_words
    words.sort(key=lambda w: w["frequency_rank"])

    ordered_words = []
    for i, w in enumerate(words, start=1):
        ordered_words.append(
            {
                "id": f"w{i:05d}",
                "lemma": w["lemma"],
                "pos": w["pos"],
                "frequency_rank": w["frequency_rank"],
                "translation_en": w["translation_en"],
                "cefr_estimate": w["cefr_estimate"],
                "sentences": w["sentences"],
            }
        )

    return ordered_words


def main():
    words = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with_sentences = sum(1 for w in words if w["sentences"])
    print(f"Wrote {len(words)} words to {OUTPUT_PATH} ({with_sentences} with example sentences)")


if __name__ == "__main__":
    sys.exit(main())
