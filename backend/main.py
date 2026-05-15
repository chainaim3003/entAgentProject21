"""
main.py — FastAPI entrypoint.

  • Initializes the SQLite checkpointer for LangGraph
  • Initializes the memory store schema
  • Compiles the graph
  • Mounts CORS + the API router
  • Runs uvicorn

Run with:  python -m main
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import memory_store
from api import router
from config import settings
from graph import build_graph


logger = logging.getLogger("hedge_advisor")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: bring up persistence + graph, tear down cleanly."""
    logger.info("Initializing memory store at %s", settings.memory_db_path)
    memory_store.init_db()

    logger.info("Initializing LangGraph checkpointer at %s", settings.checkpoint_db_path)
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
        graph_app = build_graph().compile(checkpointer=checkpointer)
        app.state.graph_app = graph_app
        app.state.runs = {}  # thread_id -> asyncio.Task registry
        logger.info("Graph compiled. Ready on %s:%s", settings.host, settings.port)
        try:
            yield
        finally:
            logger.info("Shutting down. Cancelling %d in-flight runs.", len(app.state.runs))
            for task in app.state.runs.values():
                if not task.done():
                    task.cancel()


app = FastAPI(
    title="ACTUS Hedge Advisor",
    version="0.1.0",
    description="Bow-tie multi-agent hedge-decision system. See DESIGN.md.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
