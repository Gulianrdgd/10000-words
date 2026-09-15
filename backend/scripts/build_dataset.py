#!/usr/bin/env python3
"""
Build words.json for the French vocabulary app.

Pipeline:
  1. Fetch the hermitdave/FrequencyWords French frequency corpus from GitHub
     (real-world frequency ranking, ~50k word forms).
  2. Load our curated word list (curated_words.json) with hand-authored
     translations, POS tags, CEFR estimates and example sentences.
  3. Cross-reference each curated lemma against the frequency corpus to
     assign a genuine frequency_rank; lemmas not found (rare in the corpus
     due to inflection/multi-word entries) are ranked after all matched
     entries, in curated-list order.
  4. Write backend/app/data/words.json, sorted by frequency_rank.

Note on scope: the original plan called for 1000 words sourced from Tatoeba
sentence pairs plus LLM-generated/validated filler sentences. This sandboxed
environment's network egress only reaches GitHub/PyPI/npm (Tatoeba, dictionary
APIs, and LLM APIs are unreachable), so this script ships a curated ~280-word
seed set with hand-authored sentences instead. The pipeline is intentionally
kept in this shape so it's trivial to extend: add more entries to
curated_words.json (or wire in a real sentence corpus / LLM call in
`fetch_sentences_for_unmatched`) to grow toward the full 1000.
"""
import json
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
FREQ_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/fr/fr_50k.txt"
FREQ_CACHE = SCRIPT_DIR / "fr_50k_raw.txt"
CURATED_PATH = SCRIPT_DIR / "curated_words.json"
OUTPUT_PATH = SCRIPT_DIR.parent / "app" / "data" / "words.json"


def fetch_frequency_corpus() -> dict[str, int]:
    """Return {word: rank} from the FrequencyWords French corpus (1-indexed)."""
    if not FREQ_CACHE.exists():
        print(f"Fetching {FREQ_URL} ...")
        urllib.request.urlretrieve(FREQ_URL, FREQ_CACHE)
    ranks: dict[str, int] = {}
    with open(FREQ_CACHE, encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            word = line.split()[0].strip().lower()
            if word not in ranks:
                ranks[word] = i
    return ranks


def load_curated() -> list[dict]:
    with open(CURATED_PATH, encoding="utf-8") as f:
        return json.load(f)


def build() -> list[dict]:
    freq_ranks = fetch_frequency_corpus()
    curated = load_curated()

    matched = []
    unmatched = []
    for entry in curated:
        lemma_key = entry["lemma"].lower().split()[0].replace("'", "")
        rank = freq_ranks.get(entry["lemma"].lower()) or freq_ranks.get(lemma_key)
        if rank is not None:
            matched.append((rank, entry))
        else:
            unmatched.append(entry)

    matched.sort(key=lambda pair: pair[0])
    next_rank = (matched[-1][0] if matched else 0) + 1

    words = []
    for rank, entry in matched:
        words.append({**entry, "frequency_rank": rank})
    for entry in unmatched:
        words.append({**entry, "frequency_rank": next_rank})
        next_rank += 1

    words.sort(key=lambda w: w["frequency_rank"])
    ordered_words = []
    for i, w in enumerate(words, start=1):
        ordered_words.append({
            "id": f"w{i:04d}",
            "lemma": w["lemma"],
            "pos": w["pos"],
            "frequency_rank": w["frequency_rank"],
            "translation_en": w["translation_en"],
            "cefr_estimate": w["cefr_estimate"],
            "sentences": w["sentences"],
        })

    return ordered_words


def main():
    words = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {len(words)} words to {OUTPUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
