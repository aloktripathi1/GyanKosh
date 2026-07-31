from fastapi import FastAPI

from app.api import documents, jobs, tkp

app = FastAPI(title="GyanKosh API", version="0.1.0")

app.include_router(documents.router)
app.include_router(jobs.router)
app.include_router(tkp.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
