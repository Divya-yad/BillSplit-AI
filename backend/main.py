"""
FastAPI application entry point for BillSplit AI backend.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.bills import router as bills_router
from storage.db import init_db

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise DB. Shutdown: nothing to clean up."""
    await init_db()
    yield


app = FastAPI(
    title="BillSplit AI",
    description="Turn a restaurant bill photo into a verified, per-person cost breakdown.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React dev server (and any origin in dev)
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bills_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "BillSplit AI"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
