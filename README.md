# 1000 Mots — French Vocabulary Trainer

A spaced-repetition French vocabulary app: FastAPI + SQLite backend running
[FSRS](https://github.com/open-spaced-repetition/py-fsrs) scheduling, and a
SvelteKit + Tailwind PWA frontend for the review/goals/progress screens.

Pedagogy: retrieval-first, interleaved by part of speech, dual-track mastery
(recognition vs. production tracked as separate FSRS cards per word), four
escalating review modes, weekly goals with a soft (freeze-protected) streak.

## Scope note on the dataset

This sandboxed build environment's network egress only reaches
GitHub/PyPI/npm — Tatoeba's sentence corpus, bilingual dictionary APIs, and
LLM APIs (used in the original plan for sentence generation/validation) are
unreachable. So instead of 1000 words sourced from Tatoeba + LLM-generated
fillers, this ships a **curated ~285-word seed set** (hand-authored
translations, POS tags, CEFR estimates, 2 example sentences each), covering
the pronouns/articles/top verbs/nouns/adjectives/adverbs that make up most
of everyday spoken French. Frequency ranks are still genuine, cross-referenced
against the real [hermitdave/FrequencyWords](https://github.com/hermitdave/FrequencyWords)
French corpus. `backend/scripts/build_dataset.py` is written so growing the
deck is mechanical: add more entries to `curated_words.json` (or wire in a
real sentence corpus / LLM call) and re-run it.

## Architecture

```
backend/
  scripts/build_dataset.py   # fetches frequency corpus, builds app/data/words.json
  scripts/curated_words.json # hand-authored word + sentence data
  app/
    main.py                  # FastAPI app, CORS, startup seeding
    models.py                # SQLAlchemy: Word, Card, Review, WeeklyGoal, WordMastery, UserStreak
    fsrs_engine.py            # py-fsrs wrapper (rating heuristic, UTC tz-fix, Levenshtein)
    session_composer.py       # POS interleaving, mode selection, MCQ distractors, cloze blanking
    streaks.py                 # soft streak with freeze days
    routers/
      cards.py                # GET /cards/due, POST /cards/{id}/review
      goals.py                # GET/POST /goals, GET /goals/{week}/review
      stats.py                # GET /stats/growth
      words.py                # GET /words (progress browser)

frontend/
  src/routes/
    +page.svelte              # review session (all 4 modes)
    goals/+page.svelte        # weekly goal + last week's review
    progress/+page.svelte     # growth chart, streak, word list
  src/lib/
    api.ts                    # typed fetch client
    components/review/*       # McqCard, TypedCard (modes 2/3), FreeProductionCard, FeedbackBanner
    components/GrowthChart.svelte
```

## Design decisions worth knowing

- **Single user, no auth.** All tables carry a `user_id` column (matching the
  original schema) but the API always uses a constant `"default"` user.
  Wiring real auth later is additive, not a rewrite.
- **Review modes ↔ tracks.** Track `recognition` always serves mode 1 (MCQ).
  Track `production` escalates through modes 2 → 3 → 4 as that word's
  production `mastery_level` rises, per the plan's "unlock, don't gate
  strictly" rule.
- **New-word scaffolding.** A word's `production` card stays hidden
  (`introduced=False`) until its `recognition` card has been reviewed at
  least once — so brand-new words are always seen in recognition mode first.
- **Cloze correctness.** French conjugations often share no stem with their
  infinitive (`être` → `suis`, `aller` → `vais`). `session_composer.py`
  carries a small irregular-verb lookup plus stem-prefix matching so the
  blanked word (and the answer key used to grade it) is always the exact
  token that was blanked — verified against all 570 authored sentences.
- **SQLite + UTC datetimes.** SQLite silently drops tzinfo on round-trip;
  `fsrs_engine._as_utc` re-attaches it before handing datetimes to the FSRS
  scheduler, which requires timezone-aware UTC.
- **Not implemented (stretch, per the plan's own build order):** real push
  notifications (Phase 5's web-push backend/service-worker plumbing). The
  PWA is installable (manifest + offline-caching service worker via
  `@vite-pwa/sveltekit`) but there's no notification server here.

## Running it

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# regenerate the dataset (optional — app/data/words.json is already committed)
python3 scripts/build_dataset.py

uvicorn app.main:app --reload --port 8000
```

The SQLite DB (`app/data/app.db`) and word/card rows are created and seeded
automatically on first startup.

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api -> http://127.0.0.1:8000
```

For a production build, set `VITE_API_BASE_URL` to your deployed backend's
absolute URL (the dev proxy only exists in `vite dev`), then:

```bash
npm run build   # static PWA output in frontend/build/
```
