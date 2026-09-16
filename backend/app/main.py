import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth, push
from app.database import SessionLocal, engine
from app.routers import cards, goals, stats, words
from app.seed import ensure_cards_for_all_users, sync_words, upgrade_schema


@asynccontextmanager
async def lifespan(_app: FastAPI):
    upgrade_schema(engine)
    db = SessionLocal()
    try:
        sync_words(db)
        ensure_cards_for_all_users(db)
    finally:
        db.close()
    reminders = asyncio.create_task(push.reminder_loop())
    yield
    reminders.cancel()


app = FastAPI(title="French Vocabulary API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cards.router)
app.include_router(goals.router)
app.include_router(stats.router)
app.include_router(words.router)
app.include_router(push.router)


@app.get("/health")
def health():
    return {"status": "ok"}
