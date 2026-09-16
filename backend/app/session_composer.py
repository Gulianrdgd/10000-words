import json
import random

from app.models import Card, Word

# Which production modes are unlocked at a given mastery_level.
PRODUCTION_MODE_UNLOCKS = {
    0: [2],
    1: [2, 3],
    2: [2, 3],
    3: [2, 3, 4],
    4: [2, 3, 4],
    5: [2, 3, 4],
}


def pick_mode(card: Card, has_sentences: bool) -> int:
    if card.track == "recognition":
        return 1
    unlocked = PRODUCTION_MODE_UNLOCKS.get(card.mastery_level, [2, 3, 4])
    if not has_sentences:
        # Mode 3 (cloze) needs an example sentence to blank a word out of;
        # most of the bulk (automated-translation) tier has none.
        unlocked = [m for m in unlocked if m != 3] or [2]
    # weight towards the highest unlocked mode so mastered words escalate in difficulty
    weights = [i + 1 for i in range(len(unlocked))]
    return random.choices(unlocked, weights=weights, k=1)[0]


def pick_sentence(word: Word, card: Card) -> dict | None:
    sentences = json.loads(word.sentences_json)
    if not sentences:
        return None
    idx = card.sentence_cursor % len(sentences)
    return sentences[idx]


def build_mcq_options(word: Word, all_words: list[Word]) -> list[str]:
    same_pos = [w for w in all_words if w.pos == word.pos and w.id != word.id]
    same_pos.sort(key=lambda w: abs(w.frequency_rank - word.frequency_rank))
    distractors = [w.translation_en for w in same_pos[:15]]
    random.shuffle(distractors)
    options = [word.translation_en] + distractors[:3]
    random.shuffle(options)
    return options


# Present-tense forms of common irregular verbs used in curated_words.json,
# mapped back to their lemma. Regular verbs are matched by stem prefix instead
# (see _stem_matches) since e.g. "trouve" -> "trouver" needs no lookup table,
# but "suis" -> "être" or "vais" -> "aller" have no shared stem at all.
IRREGULAR_VERB_FORMS = {
    "suis": "être", "es": "être", "est": "être", "sommes": "être", "êtes": "être", "sont": "être",
    "ai": "avoir", "as": "avoir", "a": "avoir", "avons": "avoir", "avez": "avoir", "ont": "avoir",
    "vais": "aller", "vas": "aller", "va": "aller", "allons": "aller", "allez": "aller", "vont": "aller",
    "fais": "faire", "fait": "faire", "faisons": "faire", "faites": "faire", "font": "faire",
    "dis": "dire", "dit": "dire", "disons": "dire", "dites": "dire", "disent": "dire",
    "sais": "savoir", "sait": "savoir", "savons": "savoir", "savez": "savoir", "savent": "savoir",
    "peux": "pouvoir", "peut": "pouvoir", "pouvons": "pouvoir", "pouvez": "pouvoir", "peuvent": "pouvoir",
    "veux": "vouloir", "veut": "vouloir", "voulons": "vouloir", "voulez": "vouloir", "veulent": "vouloir",
    "dois": "devoir", "doit": "devoir", "devons": "devoir", "devez": "devoir", "doivent": "devoir",
    "viens": "venir", "vient": "venir", "venons": "venir", "venez": "venir", "viennent": "venir",
    "tiens": "tenir", "tient": "tenir", "tenons": "tenir", "tenez": "tenir", "tiennent": "tenir",
    "prends": "prendre", "prend": "prendre", "prenons": "prendre", "prenez": "prendre", "prennent": "prendre",
    "apprends": "apprendre", "apprend": "apprendre", "apprenons": "apprendre", "apprenez": "apprendre", "apprennent": "apprendre",
    "comprends": "comprendre", "comprend": "comprendre", "comprenons": "comprendre", "comprenez": "comprendre", "comprennent": "comprendre",
    "vis": "vivre", "vit": "vivre", "vivons": "vivre", "vivez": "vivre", "vivent": "vivre",
    "lis": "lire", "lit": "lire", "lisons": "lire", "lisez": "lire", "lisent": "lire",
    "bois": "boire", "boit": "boire", "buvons": "boire", "buvez": "boire", "boivent": "boire",
    "reçois": "recevoir", "reçoit": "recevoir", "recevons": "recevoir", "recevez": "recevoir", "reçoivent": "recevoir",
    "envoie": "envoyer", "envoies": "envoyer", "envoyons": "envoyer", "envoyez": "envoyer", "envoient": "envoyer",
    "faut": "falloir",
}

_STOPWORDS = {
    "je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "le", "la", "les", "l", "un", "une", "des", "de", "du", "d",
    "ce", "cet", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "notre", "votre", "leur", "leurs",
    "que", "qui", "à", "dans", "pour", "avec", "sur", "sous", "et", "ou",
    "mais", "donc", "car", "ne", "pas", "est", "sont", "a", "ai", "plus", "très", "bien",
}


def _normalize_token(token: str) -> str:
    token = token.strip(".,!?;:…").lower()
    if "'" in token:
        token = token.rsplit("'", 1)[-1]
    if "-" in token:
        # inverted question forms ("viens-tu", "peux-tu"): the verb comes first
        token = token.split("-", 1)[0]
    return token


def _stem(lemma: str) -> str:
    if lemma.endswith(("er", "ir", "re")):
        return lemma[:-2]
    if lemma.endswith("oir"):
        return lemma[:-3]
    return lemma


def _stem_matches(token: str, lemma: str) -> bool:
    stem = _stem(lemma)
    if len(stem) < 2:
        return token == lemma
    prefix_len = 0
    for a, b in zip(token, stem):
        if a != b:
            break
        prefix_len += 1
    return prefix_len >= min(3, len(stem))


def _find_cloze_index(words: list[str], lemma: str) -> int:
    lemma = lemma.lower()
    normalized = [_normalize_token(w) for w in words]

    for i, tok in enumerate(normalized):
        if tok == lemma:
            return i
    for i, tok in enumerate(normalized):
        if IRREGULAR_VERB_FORMS.get(tok) == lemma:
            return i
    for i, tok in enumerate(normalized):
        if tok not in _STOPWORDS and _stem_matches(tok, lemma):
            return i

    # fallback: closest edit-distance token, ignoring function words
    from app.fsrs_engine import levenshtein

    candidates = [i for i, tok in enumerate(normalized) if tok not in _STOPWORDS and tok]
    if not candidates:
        candidates = list(range(len(normalized)))
    return min(candidates, key=lambda i: levenshtein(normalized[i], lemma))


def build_cloze(sentence_fr: str, lemma: str) -> tuple[str, str]:
    """Returns (sentence_with_blank, the_exact_word the learner must type).

    Handles elisions ("j'ai" -> keep "j'", blank "ai") and inverted question
    forms ("viens-tu" -> blank "viens", keep "-tu") so the blanked answer is
    always the bare word the learner is expected to produce.
    """
    words = sentence_fr.split(" ")
    idx = _find_cloze_index(words, lemma)
    original = words[idx]
    trailing = "".join(ch for ch in original if ch in ".,!?;:…")
    core = original[: len(original) - len(trailing)] if trailing else original

    if "'" in core:
        prefix, _, rest = core.partition("'")
        answer = rest
        display = f"{prefix}'____"
    elif "-" in core:
        verb_part, _, rest = core.partition("-")
        answer = verb_part
        display = f"____-{rest}"
    else:
        answer = core
        display = "____"

    words[idx] = display + trailing
    return " ".join(words), answer


def interleave_by_pos(cards_with_words: list[tuple[Card, Word]]) -> list[tuple[Card, Word]]:
    """Groups by POS and round-robins across groups so the same POS doesn't repeat back-to-back."""
    buckets: dict[str, list[tuple[Card, Word]]] = {}
    for card, word in cards_with_words:
        buckets.setdefault(word.pos, []).append((card, word))
    for bucket in buckets.values():
        random.shuffle(bucket)

    order = list(buckets.keys())
    random.shuffle(order)

    result: list[tuple[Card, Word]] = []
    while any(buckets[pos] for pos in order):
        for pos in order:
            if buckets[pos]:
                result.append(buckets[pos].pop())
    return result
