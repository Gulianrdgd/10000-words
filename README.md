# 1000 Mots — French Vocabulary Trainer

A spaced-repetition French vocabulary app: FastAPI + SQLite backend running
[FSRS](https://github.com/open-spaced-repetition/py-fsrs) scheduling, and a
SvelteKit + Tailwind PWA frontend for the review/goals/progress screens.

Pedagogy: retrieval-first, interleaved by part of speech, dual-track mastery
(recognition vs. production tracked as separate FSRS cards per word), four
escalating review modes, weekly goals with a soft (freeze-protected) streak.

## Scope note on the dataset — how it actually reaches 10,000 words

This sandboxed build environment's network egress only reaches
GitHub/PyPI/npm — Tatoeba's sentence corpus, bilingual dictionary APIs, and
LLM APIs (used in the original plan for sentence generation/validation) are
unreachable. `backend/scripts/build_dataset.py` works around that with a
two-tier pipeline:

1. **Curated tier (~340 words, with sentences).** Hand-authored translation,
   POS, CEFR estimate and 2 example sentences each, covering every core
   closed-class word (pronouns, articles, possessives, prepositions) plus the
   highest-frequency verbs/nouns/adjectives/adverbs. Closed-class words are
   curated deliberately: an automated dictionary handles them badly (see
   below), and there are few enough of them (~150 in French) to just get
   right by hand.
2. **Bulk tier (~9,660 words, no sentences).** Built from
   [pquentin/wiktionary-translations](https://github.com/pquentin/wiktionary-translations)
   (a ~81k-row French-Wiktionary extraction), cross-referenced against real
   frequency rank from
   [hermitdave/FrequencyWords](https://github.com/hermitdave/FrequencyWords).
   Wiktionary lists every sense of a word, so picking the right one matters:
   the picker prefers a French/English cognate when one exists (fixes
   `milieu` → "mean" instead of "milieu"), else the most frequent English
   candidate word (fixes `est` → "east" instead of recognizing it's really
   the verb "is"). Both heuristics have known failure modes — cognates can be
   false friends (`retard` → "retard", `avocat` → "advocate" instead of
   "lawyer") — so `build_dataset.py` also carries an explicit, verified
   `TRANSLATION_OVERRIDES` table and exclude-lists (redundant conjugated
   forms, profanity, proper-noun collisions) built by manually auditing the
   generated output rank-by-rank through roughly the top 2,500 words.

Net effect: the ~2,500 most-used words (the ones a learner actually spends
most of their time on) got hand-verified; quality past that point is
good-but-automated and occasionally imprecise. Growing the curated tier or
tightening the bulk-tier heuristics is just editing `curated_words.json` /
`build_dataset.py` and re-running it — nothing else in the app changes.

Because 9,660 of the 10,000 words have no example sentence, `session_composer.py`
never offers mode 3 (sentence cloze) for a sentence-less word — it falls back
to modes 1/2/4, which don't need one.

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
  token that was blanked — verified against all 674 authored sentences
  (mode 3 is only ever offered for one of the ~337 curated words that has
  sentences; see the dataset scope note above).
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
