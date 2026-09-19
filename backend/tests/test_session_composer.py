"""Session composition: which mode a card gets, and — the important one — that
a cloze blank and its answer key are always the same token.

The README claims cloze correctness was verified against every authored
sentence. This re-runs that claim on each test run instead of trusting it.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.fsrs_engine import levenshtein
from app.session_composer import (
    _PUNCTUATION,
    IRREGULAR_VERB_FORMS,
    _stem_matches,
    build_cloze,
    build_mcq_options,
    can_cloze,
    interleave_by_pos,
    pick_mode,
)

WORDS_JSON = Path(__file__).resolve().parents[1] / "app" / "data" / "words.json"


def card(track="recognition", reps=0, mastery_level=0):
    return SimpleNamespace(track=track, reps=reps, mastery_level=mastery_level)


# --- mode selection -----------------------------------------------------------


def test_a_words_first_exposure_is_always_written():
    assert {pick_mode(card(reps=0), True) for _ in range(50)} == {1}


def test_later_recognition_alternates_reading_and_listening():
    assert {pick_mode(card(reps=3), True) for _ in range(80)} == {1, 6}


def test_production_never_serves_a_recognition_mode():
    modes = {pick_mode(card("production", reps=2, mastery_level=m), True) for m in range(6) for _ in range(40)}
    assert modes.isdisjoint({1, 6})


def test_cloze_is_never_offered_without_a_sentence():
    modes = {pick_mode(card("production", reps=2, mastery_level=m), False) for m in range(6) for _ in range(40)}
    assert 3 not in modes


# --- cloze answer keys --------------------------------------------------------


def test_build_cloze_blanks_the_word_and_returns_that_exact_token():
    blanked, answer = build_cloze("La maison est grande.", "maison")
    assert "____" in blanked
    assert "maison" not in blanked
    assert answer == "maison"


def test_build_cloze_handles_conjugations_sharing_no_stem():
    # être -> suis: the blanked token is what gets graded, not the infinitive
    blanked, answer = build_cloze("Je suis fatigué.", "être")
    assert "____" in blanked
    assert answer.lower() in {"suis", "être"}
    assert answer not in blanked


@pytest.mark.parametrize(
    "sentence,lemma,expected_answer",
    [
        # the lemma sat behind the hyphen and "en" was blanked instead
        ("Notre département est en sous-effectif.", "effectif", "effectif"),
        # the lemma owns its apostrophe; splitting it left the answer as "hui"
        ("Aujourd'hui, il fait beau.", "aujourd'hui", "aujourd'hui"),
        # non-breaking spaces made the whole sentence one token, blanking it all
        ("Il\xa0te\xa0faut\xa0te\xa0déplacer.", "déplacer", "déplacer"),
        # multi-hyphen: the lemma is the last part
        ("Dois-je partir sur-le-champ ?", "champ", "champ"),
        # an elision wrapping a compound
        ("Le programme d'auto-détection des langues ne fonctionne plus.", "détection", "détection"),
        # the original behaviour must survive all of the above
        ("Que fais-tu ?", "faire", "fais"),
        # wrapped in punctuation: both delimiters must survive the blank
        ("Il y a une (maison) ici.", "maison", "maison"),
        ("Le mot «Renaissance» veut dire quoi ?", "renaissance", "Renaissance"),
        # wrapping apostrophes are quotes, not an elision
        ("Le chien est appelé 'Spot' par la famille.", "spot", "Spot"),
    ],
)
def test_cloze_blanks_the_lemma_not_a_neighbour(sentence, lemma, expected_answer):
    blanked, answer = build_cloze(sentence, lemma)
    # the answer keeps the sentence's own capitalisation ("Aujourd'hui")
    assert answer.lower() == expected_answer.lower()
    assert "____" in blanked
    assert blanked.count("____") == 1


def _answer_fits_the_lemma(answer: str, lemma: str) -> bool:
    """The learner is shown the lemma's meaning and must produce the blanked
    token, so the two have to be the same word — an unrelated answer key makes
    the card unanswerable (this is what caught 'en' being blanked for
    'effectif' in "Notre département est en sous-effectif")."""
    answer, lemma = answer.lower(), lemma.lower()
    return (
        answer == lemma
        or _stem_matches(answer, lemma)
        or IRREGULAR_VERB_FORMS.get(answer) == lemma
        # a tight budget on purpose: a loose one hid "(maiso" being returned
        # for "maison" when punctuation was stripped from the wrong end
        or levenshtein(answer, lemma) <= 1
    )


def test_a_blanked_answer_never_keeps_punctuation():
    """The answer key is graded against what the learner types, so it must be
    the bare word — no brackets, quotes or terminators clinging to it."""
    for sentence, lemma in [
        ("Il y a une (maison) ici.", "maison"),
        ("Le mot «Renaissance» veut dire quoi ?", "renaissance"),
        ("C'est une maison.", "maison"),
    ]:
        _, answer = build_cloze(sentence, lemma)
        assert not any(ch in _PUNCTUATION for ch in answer), f"{answer!r} from {sentence!r}"


@pytest.mark.parametrize(
    "sentence,lemma",
    [
        ("Bonsoir!", "soir"),  # the word exists only inside another
        ("Bonjour, comment vas-tu?", "jour"),
    ],
)
def test_a_sentence_without_the_word_is_not_offered_as_a_cloze(sentence, lemma):
    assert can_cloze(sentence, lemma) is False


@pytest.mark.parametrize(
    "sentence,lemma",
    [
        ("La maison est grande.", "maison"),
        ("Je paie l'addition.", "payer"),  # -ayer verbs swap y for i
        ("Je suis fatigué.", "être"),
        ("Notre département est en sous-effectif.", "effectif"),
    ],
)
def test_a_sentence_containing_the_word_is_cloze_able(sentence, lemma):
    assert can_cloze(sentence, lemma) is True


@pytest.mark.skipif(not WORDS_JSON.exists(), reason="words.json not built")
def test_every_cloze_the_app_would_serve_is_answerable():
    """Across the whole dataset, every cloze that passes can_cloze() — the
    same gate cards.py uses — must blank a real token and return an answer key
    that is the word being taught."""
    words = json.loads(WORDS_JSON.read_text())
    checked = skipped = 0
    failures = []
    for word in words:
        for sentence in word.get("sentences") or []:
            if not can_cloze(sentence["fr"], word["lemma"]):
                skipped += 1
                continue
            blanked, answer = build_cloze(sentence["fr"], word["lemma"])
            checked += 1
            if not answer or "____" not in blanked or not _answer_fits_the_lemma(answer, word["lemma"]):
                failures.append((word["lemma"], sentence["fr"], blanked, answer))
    assert checked > 0, "no sentences found to check"
    assert not failures, f"{len(failures)} of {checked} clozes are unanswerable: {failures[:5]}"
    # the gate should be excluding a small tail, not most of the dataset
    assert skipped / (checked + skipped) < 0.10, f"can_cloze rejected {skipped}/{checked + skipped}"


# --- multiple choice ----------------------------------------------------------


def word(id, translation, pos="noun", rank=1):
    return SimpleNamespace(id=id, translation_en=translation, pos=pos, frequency_rank=rank)


def test_mcq_options_never_repeat_a_translation():
    """Different words share a translation ("emploi" and "travaux" are both
    "work"), which would render the same option twice with one marked wrong."""
    target = word("1", "work", rank=1)
    others = [word(str(i), "work", rank=i) for i in range(2, 12)] + [
        word("50", "house", rank=50),
        word("51", "tree", rank=51),
    ]
    options = build_mcq_options(target, [target, *others])
    assert len(options) == len(set(options)), options
    assert options.count("work") == 1


def test_mcq_options_always_contain_the_answer():
    target = word("1", "house")
    others = [word(str(i), f"other{i}", rank=i) for i in range(2, 20)]
    for _ in range(20):
        assert "house" in build_mcq_options(target, [target, *others])


# --- interleaving -------------------------------------------------------------


def test_interleaving_avoids_runs_of_the_same_part_of_speech():
    pairs = [(card(), SimpleNamespace(id=str(i), pos=p)) for i, p in enumerate(["noun"] * 4 + ["verb"] * 4)]
    ordered = interleave_by_pos(pairs)
    assert len(ordered) == len(pairs)
    parts = [w.pos for _, w in ordered]
    longest_run = max(len(list(g)) for _, g in __import__("itertools").groupby(parts))
    assert longest_run < 4, f"got a run of {longest_run}: {parts}"
