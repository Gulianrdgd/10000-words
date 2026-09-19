import json
import random

from app.models import Card, Word

# Which production modes are unlocked at a given mastery_level, easiest first.
# Mode 5 (dictation: hear the word, type it) sits between typed recall and
# cloze: the audio gives the word away, so it drills spelling and listening.
PRODUCTION_MODE_UNLOCKS = {
    0: [2],
    1: [2, 5, 3],
    2: [2, 5, 3],
    3: [2, 5, 3, 4],
    4: [2, 5, 3, 4],
    5: [2, 5, 3, 4],
}


def pick_mode(card: Card, has_sentences: bool) -> int:
    if card.track == "recognition":
        # First exposure is always the written word (mode 1); after that,
        # alternate with listening (mode 6) so recognition isn't text-only.
        return 1 if card.reps == 0 else random.choice([1, 6])
    unlocked = PRODUCTION_MODE_UNLOCKS.get(card.mastery_level, [2, 5, 3, 4])
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
    # Different words share a translation (918 same-POS collisions in the
    # dataset: "emploi" and "travaux" are both "work"), so distractors are
    # deduplicated and the correct answer excluded — otherwise a card can show
    # the right answer twice and mark one of them wrong.
    correct = word.translation_en.strip()
    seen = {correct.casefold()}
    distractors: list[str] = []
    for candidate in same_pos:
        translation = candidate.translation_en.strip()
        if translation.casefold() in seen:
            continue
        seen.add(translation.casefold())
        distractors.append(translation)
        if len(distractors) == 15:
            break

    random.shuffle(distractors)
    options = [correct] + distractors[:3]
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


_PUNCTUATION = ".,!?;:…«»\"()"
# French typography (and Tatoeba) is full of non-breaking spaces, which a plain
# split(" ") would swallow whole — blanking an entire sentence as one token.
_SPACES = "\xa0  \t\n"


def _normalize_token(token: str) -> str:
    token = token.strip(_PUNCTUATION).lower()
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
    # French verbs in -ayer/-uyer swap y for i when conjugated ("payer" ->
    # "paie"), which a plain prefix comparison would miss.
    token, stem = token.replace("y", "i"), stem.replace("y", "i")
    prefix_len = 0
    for a, b in zip(token, stem):
        if a != b:
            break
        prefix_len += 1
    return prefix_len >= min(3, len(stem))


def _token_forms(token: str) -> list[str]:
    """Every form a token could match on, most specific first.

    A token is ambiguous in both directions: "viens-tu" is the verb in front,
    "sous-effectif" is the word behind, and "aujourd'hui" is a lemma that
    contains its own apostrophe, so the whole bare token is offered too.
    """
    bare = token.strip(_PUNCTUATION).lower()
    forms = [bare, _normalize_token(token)]
    if "'" in bare:
        forms.append(bare.rsplit("'", 1)[-1])
    if "-" in bare:
        forms.extend(bare.split("-"))
    # a token can be wrapped in quotes ("'Spot'"), where the apostrophes are
    # delimiters rather than an elision
    forms.append(bare.strip("'"))
    return [f for f in dict.fromkeys(forms) if f]


def _prepare(sentence_fr: str) -> str:
    """Normalises the whitespace and apostrophes that split() and the elision
    rules would otherwise mishandle."""
    for space in _SPACES:
        sentence_fr = sentence_fr.replace(space, " ")
    # Tatoeba writes elisions with a curly apostrophe ("l’asile"), which the
    # elision handling — and the article rules used to grade the answer — only
    # recognise as a straight one.
    return sentence_fr.replace("’", "'")


def can_cloze(sentence_fr: str, lemma: str) -> bool:
    """Whether this sentence can pose a fair cloze for this word.

    False when the lemma isn't in the sentence as its own token — "Bonsoir!"
    can't test `soir`, because the word exists only inside another one. Without
    this check `build_cloze` falls back to the nearest token by edit distance
    and invents an answer the learner cannot give.
    """
    lemma = lemma.lower()
    forms = [_token_forms(w) for w in _prepare(sentence_fr).split(" ")]
    return any(
        lemma in token_forms
        or any(IRREGULAR_VERB_FORMS.get(f) == lemma for f in token_forms)
        or any(f not in _STOPWORDS and _stem_matches(f, lemma) for f in token_forms)
        for token_forms in forms
    )


def _find_cloze_index(words: list[str], lemma: str) -> int:
    lemma = lemma.lower()
    normalized = [_normalize_token(w) for w in words]
    forms = [_token_forms(w) for w in words]

    for i, token_forms in enumerate(forms):
        if lemma in token_forms:
            return i
    for i, token_forms in enumerate(forms):
        if any(IRREGULAR_VERB_FORMS.get(f) == lemma for f in token_forms):
            return i
    for i, token_forms in enumerate(forms):
        if any(f not in _STOPWORDS and _stem_matches(f, lemma) for f in token_forms):
            return i

    # fallback: closest edit-distance token, ignoring function words
    from app.fsrs_engine import levenshtein

    candidates = [i for i, tok in enumerate(normalized) if tok not in _STOPWORDS and tok]
    if not candidates:
        candidates = list(range(len(normalized)))
    return min(candidates, key=lambda i: levenshtein(normalized[i], lemma))


def _blank_core(core: str, lemma: str) -> tuple[str, str]:
    """Blanks the part of a token that is actually the lemma, returning
    (answer, display). Keeps an elided prefix ("j'ai" -> "j'____") and any
    hyphenated neighbours ("viens-tu" -> "____-tu", "sur-le-champ" for `champ`
    -> "sur-le-____"), but never splits a lemma that owns its own apostrophe
    ("aujourd'hui")."""
    target = lemma.lower()
    if core.lower() == target:
        return core, "____"
    if "'" in core and "'" not in target:
        prefix, _, rest = core.partition("'")
        # recurse: "d'auto-détection" for `détection` is an elision wrapping a
        # compound, and both halves need handling
        answer, display = _blank_core(rest, lemma)
        return answer, f"{prefix}'{display}"
    if "-" in core:
        parts = core.split("-")
        for i, part in enumerate(parts):
            if part.lower() == target or _stem_matches(part.lower(), target):
                return part, "-".join("____" if j == i else p for j, p in enumerate(parts))
        return parts[0], "-".join(["____", *parts[1:]])
    return core, "____"


def build_cloze(sentence_fr: str, lemma: str) -> tuple[str, str]:
    """Returns (sentence_with_blank, the_exact_word the learner must type).

    Handles elisions ("j'ai" -> keep "j'", blank "ai") and inverted question
    forms ("viens-tu" -> blank "viens", keep "-tu") so the blanked answer is
    always the bare word the learner is expected to produce.
    """
    words = _prepare(sentence_fr).split(" ")
    idx = _find_cloze_index(words, lemma)
    original = words[idx]
    # Strip punctuation from each end separately and put both back around the
    # blank: a token like "(maison)" or "«Renaissance»" is wrapped, not just
    # suffixed, and collecting punctuation from anywhere would eat the word.
    # A straight apostrophe is stripped only at the ends, where it's a quote
    # ("'Spot'"); an elision keeps its own ("l'homme"), for _blank_core to split.
    outer = _PUNCTUATION + "'"
    core = original.strip(outer)
    leading = original[: len(original) - len(original.lstrip(outer))]
    trailing = original[len(leading) + len(core) :]

    answer, display = _blank_core(core, lemma)
    words[idx] = leading + display + trailing
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
