"""Mastery is decided by FSRS stability, not by a tally of right answers.

The distinction that matters: four correct answers seconds apart must NOT count
the same as four spread over weeks. The old counter couldn't tell them apart.
"""
from types import SimpleNamespace

import pytest

from app.models import Card
from app.routers.cards import MASTERY_STABILITY_DAYS, _mastered


class FakeQuery:
    def __init__(self, cards):
        self._cards = cards

    def filter(self, *_args):
        return self

    def all(self):
        return self._cards


class FakeDb:
    def __init__(self, cards):
        self._cards = cards

    def query(self, model):
        assert model is Card
        return FakeQuery(self._cards)


def card(stability, reps=5):
    return SimpleNamespace(stability=stability, reps=reps, mastery_level=5)


def _check(cards):
    return _mastered(FakeDb(cards), "u", "w")


def test_both_tracks_must_be_stable():
    assert _check([card(MASTERY_STABILITY_DAYS + 1), card(MASTERY_STABILITY_DAYS + 1)]) is True


def test_recognizing_a_word_is_not_producing_it():
    """A strong recognition card cannot carry a weak production card."""
    assert _check([card(90.0), card(2.0)]) is False


def test_just_below_the_threshold_is_not_mastered():
    assert _check([card(MASTERY_STABILITY_DAYS - 0.1), card(99.0)]) is False


def test_a_never_reviewed_card_is_not_mastered():
    assert _check([card(None, reps=0), card(99.0)]) is False


def test_a_card_with_no_stability_yet_is_not_mastered():
    assert _check([card(None), card(99.0)]) is False


def test_a_word_missing_one_of_its_two_cards_is_not_mastered():
    assert _check([card(99.0)]) is False


def test_a_high_counter_no_longer_masters_a_fragile_word():
    """The old rule was `mastery_level >= 4` on both cards; these cards have
    mastery_level 5 and would have passed it, but FSRS says they'd be forgotten
    within days."""
    cards = [card(1.0), card(1.5)]
    assert all(c.mastery_level >= 4 for c in cards), "fixture should pass the old rule"
    assert _check(cards) is False


# --- through the real scheduler ----------------------------------------------


def test_cramming_does_not_master_a_word(client, auth):
    """Answering the same word correctly several times in one sitting should
    not be enough — this is exactly what the counter got wrong."""
    due = client.get("/cards/due?limit=50", headers=auth).json()["cards"]
    card_id = due[0]["card_id"]
    word_id = due[0]["word_id"]
    mastered = False
    for _ in range(6):
        res = client.post(
            f"/cards/{card_id}/review",
            json={"mode": 1, "correct": True, "latency_ms": 1200},
            headers=auth,
        ).json()
        mastered = mastered or res["word_mastered"]
    assert mastered is False, "six rapid correct answers must not master a word"

    detail = client.get(f"/words/{word_id}", headers=auth).json()
    assert any(t["stability_days"] is not None for t in detail["tracks"])


@pytest.mark.parametrize("threshold", [MASTERY_STABILITY_DAYS])
def test_the_threshold_is_a_sane_horizon(threshold):
    assert 7 <= threshold <= 180
