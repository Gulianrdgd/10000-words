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
    IRREGULAR_VERB_FORMS,
    _stem_matches,
    build_cloze,
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
        or levenshtein(answer, lemma) <= 3
    )


@pytest.mark.skipif(not WORDS_JSON.exists(), reason="words.json not built")
def test_every_authored_sentence_produces_an_answerable_cloze():
    """Across the whole dataset, every cloze must blank a real token and hand
    back an answer key that is actually the word being taught."""
    words = json.loads(WORDS_JSON.read_text())
    checked = 0
    failures = []
    for word in words:
        for sentence in word.get("sentences") or []:
            blanked, answer = build_cloze(sentence["fr"], word["lemma"])
            checked += 1
            if not answer or "____" not in blanked or not _answer_fits_the_lemma(answer, word["lemma"]):
                failures.append((word["lemma"], sentence["fr"], blanked, answer))
    assert checked > 0, "no sentences found to check"
    assert not failures, f"{len(failures)} of {checked} clozes are unanswerable: {failures[:5]}"


# --- interleaving -------------------------------------------------------------


def test_interleaving_avoids_runs_of_the_same_part_of_speech():
    pairs = [(card(), SimpleNamespace(id=str(i), pos=p)) for i, p in enumerate(["noun"] * 4 + ["verb"] * 4)]
    ordered = interleave_by_pos(pairs)
    assert len(ordered) == len(pairs)
    parts = [w.pos for _, w in ordered]
    longest_run = max(len(list(g)) for _, g in __import__("itertools").groupby(parts))
    assert longest_run < 4, f"got a run of {longest_run}: {parts}"
