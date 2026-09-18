"""Grading rules — the logic that decides whether a review counts, and how
hard it was. Bugs here silently corrupt the FSRS schedule rather than showing
up on screen, so these are the cases worth pinning down."""
import pytest
from fsrs import Rating

from app.fsrs_engine import levenshtein, rating_for_answer, rating_for_spoken
from app.gender import display_form, gender_correct, production_answer, split_article
from app.routers.cards import PRONUNCIATION_PASS, _grade_typed


class FakeWord:
    def __init__(self, lemma, gender=None, pos="noun"):
        self.lemma = lemma
        self.gender = gender
        self.pos = pos


# --- nouns carry their gender -------------------------------------------------


@pytest.mark.parametrize(
    "lemma,gender,expected",
    [
        ("maison", "f", "la maison"),
        ("chien", "m", "le chien"),
        ("homme", "m", "l'homme"),  # elides
        ("héros", "m", "le héros"),  # aspirated h does not elide
    ],
)
def test_display_form_picks_the_article(lemma, gender, expected):
    assert display_form(lemma, gender) == expected


@pytest.mark.parametrize(
    "typed,expected_article,expected_bare",
    [
        ("la maison", "la", "maison"),
        ("une maison", "une", "maison"),
        ("maison", None, "maison"),
        ("l'homme", "l'", "homme"),
    ],
)
def test_split_article(typed, expected_article, expected_bare):
    article, bare = split_article(typed)
    assert (article, bare) == (expected_article, expected_bare)


def test_gender_correct_rejects_the_wrong_article():
    assert gender_correct("la", "f") is True
    assert gender_correct("le", "f") is False
    assert gender_correct(None, "f") is None or gender_correct(None, "f") is False


def test_a_noun_without_its_article_is_wrong():
    correct, _, gender_ok, expected = _grade_typed(FakeWord("maison", "f"), "maison")
    assert correct is False
    assert gender_ok is not True
    assert expected == production_answer("maison", "f")


def test_a_noun_with_the_wrong_article_is_wrong():
    correct, _, gender_ok, _ = _grade_typed(FakeWord("maison", "f"), "le maison")
    assert correct is False
    assert gender_ok is False


def test_a_noun_with_the_right_article_is_correct():
    correct, _, gender_ok, _ = _grade_typed(FakeWord("maison", "f"), "la maison")
    assert correct is True
    assert gender_ok is True


def test_one_typo_is_a_near_miss_not_a_failure():
    correct, near_miss, _, _ = _grade_typed(FakeWord("maison", "f"), "la maisen")
    assert (correct, near_miss) == (True, True)


def test_two_typos_fail():
    correct, _, _, _ = _grade_typed(FakeWord("maison", "f"), "la maasen")
    assert correct is False


def test_non_nouns_are_not_gender_graded():
    correct, _, gender_ok, expected = _grade_typed(FakeWord("manger", None, "verb"), "manger")
    assert (correct, gender_ok, expected) == (True, None, "manger")


# --- spoken answers -----------------------------------------------------------


def test_spoken_rating_tracks_the_score():
    assert rating_for_spoken(True, 95) == Rating.Easy
    assert rating_for_spoken(True, 82) == Rating.Good
    assert rating_for_spoken(True, 72) == Rating.Hard


def test_a_failed_spoken_answer_is_always_again():
    assert rating_for_spoken(False, 95) == Rating.Again
    assert rating_for_spoken(False, 10) == Rating.Again


def test_shaky_speech_comes_back_sooner_than_clean_speech():
    assert rating_for_spoken(True, 72) < rating_for_spoken(True, 95)


def test_the_pass_threshold_sits_between_fail_and_pass():
    assert rating_for_spoken(True, PRONUNCIATION_PASS) != Rating.Again
    assert 0 < PRONUNCIATION_PASS < 100


# --- typed ratings and distance ----------------------------------------------


def test_wrong_answers_rate_again():
    assert rating_for_answer(False, 1000) == Rating.Again


def test_a_near_miss_is_hard_not_good():
    assert rating_for_answer(True, 1000, near_miss=True) == Rating.Hard


@pytest.mark.parametrize(
    "a,b,distance", [("maison", "maison", 0), ("maison", "maisen", 1), ("maison", "", 6)]
)
def test_levenshtein(a, b, distance):
    assert levenshtein(a, b) == distance
