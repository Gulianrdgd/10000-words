"""End-to-end behaviour through the API: the daily pace and its override, the
registration cap, and that a spoken answer is graded on both what was said and
how it sounded."""
import os

import pytest

from app import auth
from app.routers import speech


def _due(client, headers, **params):
    query = "&".join(f"{k}={v}" for k, v in {"limit": 50, **params}.items())
    res = client.get(f"/cards/due?{query}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _review(client, headers, card_id, **body):
    res = client.post(f"/cards/{card_id}/review", json=body, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# --- the daily pace is a default, not a cap -----------------------------------


def test_new_words_stop_at_the_daily_pace(client, auth):
    first = _due(client, auth)
    assert first["new_words_introduced_today"] == first["daily_new_word_limit"]
    again = _due(client, auth)
    assert again["new_words_introduced_today"] == first["daily_new_word_limit"]


def test_extra_new_unlocks_words_past_the_pace(client, auth):
    baseline = _due(client, auth)["new_words_introduced_today"]
    pushed = _due(client, auth, extra_new=5)
    assert pushed["new_words_introduced_today"] == baseline + 5


def test_extra_new_is_bounded(client, auth):
    assert client.get("/cards/due?extra_new=999", headers=auth).status_code == 422
    assert client.get("/cards/due?extra_new=-1", headers=auth).status_code == 422


# --- spoken answers -----------------------------------------------------------


def _a_production_card(client, headers):
    for c in _due(client, headers, extra_new=10)["cards"]:
        if c["track"] == "recognition":
            _review(client, headers, c["card_id"], mode=1, correct=True, latency_ms=1500)
    cards = [c for c in _due(client, headers)["cards"] if c["mode"] in (2, 5)]
    if not cards:
        pytest.skip("no production card became available")
    return cards[0]

def test_a_mumbled_but_correct_word_still_fails(client, auth):
    card = _a_production_card(client, auth)
    result = _review(
        client, auth, card["card_id"],
        mode=card["mode"],
        typed_answer=card["expected_answer"] or card["lemma"],
        pronunciation_score=40,
        latency_ms=3000,
    )
    assert result["correct"] is False, "a bad score must fail even a perfect transcription"
    assert result["rating"] == 1


def test_a_clear_correct_word_passes(client, auth):
    card = _a_production_card(client, auth)
    result = _review(
        client, auth, card["card_id"],
        mode=card["mode"],
        typed_answer=card["expected_answer"] or card["lemma"],
        pronunciation_score=95,
        latency_ms=3000,
    )
    assert result["correct"] is True
    assert result["rating"] == 4


def test_the_spoken_score_is_stored_for_later_stats(client, auth):
    card = _a_production_card(client, auth)
    _review(
        client, auth, card["card_id"],
        mode=card["mode"],
        typed_answer=card["expected_answer"] or card["lemma"],
        pronunciation_score=64,
        phonemes=[{"p": "ʁ", "a": 30}, {"p": "a", "a": 90}],
        latency_ms=3000,
    )
    stats = client.get("/stats/pronunciation", headers=auth).json()
    assert stats["attempts"] >= 1
    assert any(w["word_id"] == card["word_id"] for w in stats["worst_words"])


def test_a_review_replayed_offline_is_only_applied_once(client, auth):
    card = _due(client, auth)["cards"][0]
    body = dict(mode=1, correct=True, latency_ms=1200, client_review_id="fixed-id-123")
    first = _review(client, auth, card["card_id"], **body)
    second = _review(client, auth, card["card_id"], **body)
    assert first["rating"] == second["rating"]
    assert first["mastery_level"] == second["mastery_level"]


# --- the client can't grade a card however it likes ---------------------------


def test_a_recognition_card_cannot_be_self_reported(client, auth):
    """Mode 4 is an honour-system self-report. Accepting it on a recognition
    card would let any client mark words known without being graded."""
    card = _due(client, auth)["cards"][0]
    assert card["track"] == "recognition"
    res = client.post(
        f"/cards/{card['card_id']}/review",
        json={"mode": 4, "self_reported_correct": True, "latency_ms": 100},
        headers=auth,
    )
    assert res.status_code == 400


def test_an_unknown_mode_is_refused(client, auth):
    card = _due(client, auth)["cards"][0]
    res = client.post(
        f"/cards/{card['card_id']}/review",
        json={"mode": 99, "correct": True, "latency_ms": 100},
        headers=auth,
    )
    assert res.status_code == 400


def test_an_out_of_range_score_is_refused(client, auth):
    """The score picks the FSRS rating, so 10000 would buy an 'Easy'."""
    card = _due(client, auth)["cards"][0]
    for score in (10000, -5):
        res = client.post(
            f"/cards/{card['card_id']}/review",
            json={"mode": 1, "correct": True, "pronunciation_score": score, "latency_ms": 100},
            headers=auth,
        )
        assert res.status_code == 422, f"score {score} was accepted"


def test_an_absurd_weekly_goal_is_refused(client, auth):
    """target_words drives the daily new-word pace, so it needs bounds."""
    for target in (0, -10, 100000):
        assert client.post("/goals", json={"target_words": target}, headers=auth).status_code == 422
    assert client.post("/goals", json={"target_words": 30}, headers=auth).status_code == 200


# --- registration cap ---------------------------------------------------------


def test_registration_is_open_when_unset(client, monkeypatch):
    monkeypatch.setattr(auth, "MAX_USERS", None)
    res = client.post("/auth/register", json={"username": "openreg", "password": "test12345"})
    assert res.status_code == 200


def test_registration_is_refused_once_the_cap_is_reached(client, monkeypatch):
    monkeypatch.setattr(auth, "MAX_USERS", 0)
    res = client.post("/auth/register", json={"username": "toomany", "password": "test12345"})
    assert res.status_code == 403
    assert "closed" in res.json()["detail"].lower()


def test_login_still_works_when_registration_is_closed(client, monkeypatch):
    monkeypatch.setattr(auth, "MAX_USERS", None)
    client.post("/auth/register", json={"username": "existing", "password": "test12345"})
    monkeypatch.setattr(auth, "MAX_USERS", 1)
    res = client.post("/auth/login", json={"username": "existing", "password": "test12345"})
    assert res.status_code == 200


def test_max_users_parses_the_environment(monkeypatch):
    monkeypatch.setenv("MAX_USERS", "3")
    assert auth._max_users() == 3
    monkeypatch.setenv("MAX_USERS", "")
    assert auth._max_users() is None
    monkeypatch.setenv("MAX_USERS", "not-a-number")
    assert auth._max_users() is None  # bad config must not lock everyone out


# --- speech token -------------------------------------------------------------


def test_assess_is_503_without_a_key(client, auth):
    res = client.post("/speech/assess?reference_text=la%20maison", content=b"fake-audio", headers=auth)
    assert res.status_code == 503


def test_assess_requires_a_login(client):
    assert client.post("/speech/assess?reference_text=x", content=b"a").status_code in (401, 403)


def test_assess_needs_a_reference_text(client, auth):
    """The reference is what the score is measured against; without it Azure
    would happily transcribe and report nothing useful."""
    assert client.post("/speech/assess", content=b"a", headers=auth).status_code == 422
    assert (
        client.post("/speech/assess?reference_text=", content=b"a", headers=auth).status_code == 422
    )


def test_assess_rejects_an_oversized_recording(client, auth, monkeypatch):
    """Bounded so a signed-in client can't have the server hold gigabytes in
    memory, or spend Azure quota on them."""
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "testregion")
    oversized = b"\0" * (speech.MAX_AUDIO_BYTES + 1024)
    res = client.post(
        "/speech/assess?reference_text=la%20maison", content=oversized, headers=auth
    )
    assert res.status_code == 413


def test_assess_rejects_an_empty_recording(client, auth, monkeypatch):
    """A recording that captured nothing shouldn't cost an Azure round trip."""
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "testregion")
    res = client.post("/speech/assess?reference_text=la%20maison", content=b"", headers=auth)
    assert res.status_code == 400


def test_speech_token_is_503_without_a_key(client, auth):
    assert "AZURE_SPEECH_KEY" not in os.environ
    assert client.get("/speech/token", headers=auth).status_code == 503


def test_speech_token_requires_a_login(client):
    assert client.get("/speech/token").status_code in (401, 403)
