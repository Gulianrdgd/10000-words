from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, SessionLocal, engine
from app.routers import cards, goals, stats, words
from app.seed import seed_words_and_cards

app = FastAPI(title="French Vocabulary API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards.router)
app.include_router(goals.router)
app.include_router(stats.router)
app.include_router(words.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_words_and_cards(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
