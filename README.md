# 1000 Mots — French Vocabulary Trainer

A spaced-repetition French vocabulary app: FastAPI + SQLite backend running
[FSRS](https://github.com/open-spaced-repetition/py-fsrs) scheduling, and a
SvelteKit + Tailwind PWA frontend for the review/goals/progress screens.

Pedagogy: retrieval-first, interleaved by part of speech, dual-track mastery
(recognition vs. production tracked as separate FSRS cards per word), five
escalating review modes (including dictation), noun gender drilled as part of
the word, browser text-to-speech audio, weekly goals with a soft
(freeze-protected) streak. Accounts sync progress across devices; reviews
answered offline queue up and sync later; optional daily push reminders.

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

### Enrichment: noun gender and example sentences

`backend/scripts/enrich_dataset.py` (also run at the end of `build_dataset.py`)
edits `words.json` in place, keeping word IDs stable:

- **Gender** for 6,108 of 6,201 nouns, from
  [Lexique 3.83](http://www.lexique.org) (CC BY-SA 4.0), falling back to
  English Wiktionary via [kaikki.org](https://kaikki.org) where Lexique leaves
  it blank (it blanks some very common nouns like `maison`, and epicene ones
  like `élève`). Homographs are resolved by matching our translation against
  each sense's glosses (`livre` m = book, f = pound). The ~90 left ungendered
  are mostly mis-tagged proper nouns/adjectives from the bulk tier.
- **Pictures** (emoji) for 463 concrete words: nouns whose translation
  exactly matches a Unicode CLDR emoji name (via
  [emojibase-data](https://github.com/milesj/emojibase)), minus a hand-reviewed
  blocklist of wrong-sense matches (`banc` → bank 🏦), plus hand-picked emoji
  for common verbs, colors and feelings. Abstract words deliberately get none.
  Emoji keep the app offline-capable with zero image hosting.
- **Example sentences** for bulk words, from [Tatoeba](https://tatoeba.org)
  (CC BY 2.0 FR) French–English pairs: sentences containing the exact lemma,
  3–12 tokens, preferring ones whose other words are most frequent. Nouns
  skip sentences whose article contradicts their gender (a cheap homograph
  filter). Coverage went from 337 to 8,723 words. Automated, so a sentence
  occasionally uses a different sense than the translation.

Words still without a sentence never get mode 3 (sentence cloze) — they fall
back to the modes that don't need one.

## Architecture

```
backend/
  scripts/build_dataset.py   # fetches frequency corpus, builds app/data/words.json
  scripts/curated_words.json # hand-authored word + sentence data
  scripts/enrich_dataset.py  # adds noun gender + Tatoeba sentences to words.json
  app/
    main.py                  # FastAPI app, CORS, startup seeding
    models.py                # SQLAlchemy: Word, Card, Review, WeeklyGoal, WordMastery, UserStreak
    fsrs_engine.py            # py-fsrs wrapper (rating heuristic, UTC tz-fix, Levenshtein)
    session_composer.py       # POS interleaving, mode selection, MCQ distractors, cloze blanking
    streaks.py                 # soft streak with freeze days
    gender.py                  # article forms, gender grading
    auth.py                    # accounts + bearer tokens (/auth/*)
    push.py                    # web push reminders (/push/*) + background loop
    routers/
      cards.py                # GET /cards/due, POST /cards/{id}/review
      goals.py                # GET/POST /goals, GET /goals/{week}/review
      stats.py                # GET /stats/growth, GET /stats/activity
      words.py                # GET /words (progress browser), GET /words/{id}

frontend/
  src/routes/
    +page.svelte              # review session (all 5 modes)
    login/ settings/          # sign in; session length, audio, reminders, account
    words/[id]/+page.svelte   # word detail: sentences, mastery, review history
    goals/+page.svelte        # weekly goal + last week's review
    progress/+page.svelte     # growth chart, streak, word list
  src/lib/
    api.ts                    # typed fetch client (bearer token)
    offline.svelte.ts         # offline review queue + session cache
    grading.ts, speech.ts     # local grading mirror; Web Speech API wrapper
    components/review/*       # McqCard, TypedCard (modes 2/3), DictationCard, FreeProductionCard, FeedbackBanner
    components/ActivityCalendar.svelte
    components/GrowthChart.svelte
```

## Design decisions worth knowing

- **Accounts.** Username/password (stdlib scrypt) with opaque bearer tokens
  (`app/auth.py`); every table's `user_id` is the account. Databases from the
  single-user version stored everything under `"default"`: the first account
  registered on such a database inherits that history. Startup adds missing
  columns and refreshes word data from `words.json` (`seed.py`), so an
  existing `app.db` upgrades in place.
- **Review modes ↔ tracks.** Track `recognition` always serves mode 1 (MCQ).
  Track `production` escalates through modes 2 (typed) → 5 (dictation: hear
  it, type it) → 3 (cloze) → 4 (free production) as that word's production
  `mastery_level` rises, per the plan's "unlock, don't gate strictly" rule.
- **Gender is part of the word.** Nouns are shown with their article
  (`la maison`, `l'homme`, `le héros`). Typed production and dictation answers
  for a gendered noun must include a gender-revealing article (`le/la/un/une`;
  elided nouns expect `un homme`): the right word with the wrong or missing
  gender is graded wrong, and each review records `gender_correct`, shown per
  word on its detail page. `app/gender.py` holds the rules, including a list
  of aspirated-h nouns that don't elide.
- **Audio** uses the browser's Web Speech API (`speechSynthesis`) with a
  French voice — no backend or API cost. Dictation falls back to typed recall
  on browsers without it.
- **Offline.** The service worker precaches the app shell; the current
  session's cards are cached in localStorage; reviews that can't reach the
  server are graded locally for feedback (`grading.ts` mirrors the server) and
  queued (`offline.svelte.ts`). Each review carries a `client_review_id`
  (replays apply once) and `reviewed_at` (FSRS schedules from when it was
  really answered).
- **Push reminders** (`app/push.py`): Web Push with VAPID keys generated on
  first start into `app/data/vapid_private.pem`. A background loop sends at
  most one reminder per device per local day, at or after the chosen hour,
  only when cards are due and there's been no review that day. Set
  `PUSH_CONTACT` (a `mailto:`/`https:` URL) in production. On iOS, push only
  works for the app added to the Home Screen.
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
- **Keyboard shortcuts.** 1–4 pick an MCQ answer, Enter checks/continues,
  P (Alt+P while typing) plays audio.

## Running it

### Backend

Uses [uv](https://docs.astral.sh/uv/) for the virtualenv and dependencies
(declared in `pyproject.toml`, locked in `uv.lock`).

```bash
cd backend
uv sync

# regenerate the dataset (optional — app/data/words.json is already committed)
uv run scripts/build_dataset.py

uv run uvicorn app.main:app --reload --port 8000
```

The SQLite DB (`app/data/app.db`) and word rows are created automatically on
first startup; a user's cards are created when they register.

### Frontend

Uses [Deno](https://deno.com) 2 as the package manager and task runner
(it reads `package.json`; dependencies are locked in `deno.lock`).

```bash
cd frontend
deno install
deno task dev     # http://localhost:5173, proxies /api -> http://127.0.0.1:8000
deno task check   # svelte-check
```

For a production build, set `VITE_API_BASE_URL` to your deployed backend's
absolute URL (the dev proxy only exists in `vite dev`), then:

```bash
deno task build   # static PWA output in frontend/build/
```
