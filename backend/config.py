"""
config.py — All environment configuration.

Single source of truth for endpoints, secrets, and limits.
No hardcoding anywhere else in the codebase.
No defaults for required values — fails fast on startup if anything is missing.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # REQUIRED — Gemini reasoning
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.5-flash", description="Gemini model name")

    # REQUIRED — DRAPS MCP server (the knot)
    draps_mcp_url: str = Field(..., description="DRAPS MCP server base URL")

    # REQUIRED — ACTUS-Mentor REST API (disclosure)
    actus_mentor_url: str = Field(..., description="ACTUS-Mentor REST API base URL")

    # OPTIONAL — X-API-Key header for ACTUS-Mentor.
    # Set this only if the ACTUS-Mentor server has API_SECRET_KEY enabled.
    # Leave blank otherwise (ACTUS-Mentor disables auth when API_SECRET_KEY is unset).
    actus_mentor_api_key: str = Field(default="", description="X-API-Key for ACTUS-Mentor")

    # OPTIONAL — ACTUS risk engine (eventsBatch) for the v2_direct dispatch path.
    # Iter-6a: when dispatch='v2_direct', simulation_node POSTs ACTUS contract
    # batches DIRECTLY to {actus_server_url}/eventsBatch, bypassing DRAPS. Defaulted
    # (NOT a required-blank field) so existing draps_v1 / supplied runs and the
    # 243-test baseline don't require a new env var — only v2_direct runs read it.
    # Mirrors the Postman collection's hardcoded http://127.0.0.1:8083/eventsBatch.
    actus_server_url: str = Field(
        default="http://127.0.0.1:8083",
        description="ACTUS risk-engine base URL for the v2_direct direct eventsBatch POST",
    )

    # Persistence (defaults to local SQLite)
    checkpoint_db_url: str = Field(default="sqlite:///./checkpoints.db")
    memory_db_url: str = Field(default="sqlite:///./memory.db")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    cors_allowed_origins: str = Field(default="http://localhost:5173")

    # Workflow limits
    max_validator_retries: int = Field(default=3, ge=1, le=10)

    @field_validator("gemini_api_key", "draps_mcp_url", "actus_mentor_url")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("required value is blank")
        return v.strip()

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def checkpoint_db_path(self) -> str:
        """Extract the SQLite file path from the URL for SqliteSaver."""
        if not self.checkpoint_db_url.startswith("sqlite:///"):
            raise ValueError(
                f"CHECKPOINT_DB_URL must start with sqlite:/// (got {self.checkpoint_db_url}). "
                "Non-SQLite checkpointers require a different setup; see LangGraph docs."
            )
        return self.checkpoint_db_url.removeprefix("sqlite:///")

    @property
    def memory_db_path(self) -> str:
        """Extract the SQLite file path from the URL for the memory store."""
        if not self.memory_db_url.startswith("sqlite:///"):
            raise ValueError(
                f"MEMORY_DB_URL must start with sqlite:/// (got {self.memory_db_url}). "
                "Non-SQLite memory backends require implementing a new memory_store."
            )
        return self.memory_db_url.removeprefix("sqlite:///")


# Singleton — instantiated once at import. Fails fast on missing required env vars.
settings = Settings()
