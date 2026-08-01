from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import documents, files, jobs, tkp
from app.config import get_settings

app = FastAPI(title="GyanKosh API", version="0.1.0")

_origins = [o.strip() for o in get_settings().cors_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(jobs.router)
app.include_router(tkp.router)
app.include_router(files.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
