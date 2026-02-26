"""
QAForge -- Settings routes.

Prefix: /api/settings

Endpoints:
    GET  /llm           — current LLM configuration
    PUT  /llm           — update LLM configuration
    GET  /llm/providers — list available providers with configured status
"""

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from db_models import User
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    require_roles,
)
from models import LLMProviderInfo, LLMSettingsResponse, LLMSettingsUpdate, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
PROVIDER_INFO: Dict[str, Dict[str, Any]] = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "env_key": "ANTHROPIC_API_KEY",
        "models": ["claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001"],
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "env_key": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini"],
    },
    "groq": {
        "name": "Groq",
        "env_key": "GROQ_API_KEY",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    },
    "ollama": {
        "name": "Ollama (Local)",
        "env_key": "OLLAMA_BASE_URL",
        "models": ["llama3", "mistral"],
    },
    "mock": {
        "name": "Mock (Testing)",
        "env_key": "",
        "models": ["mock"],
    },
}

# In-memory settings (persists across requests but not restarts).
# In a real deployment this would be stored in the DB or a config table.
_llm_settings: Dict[str, str] = {
    "provider": os.environ.get("LLM_PROVIDER", "mock"),
    "model": os.environ.get("LLM_MODEL", "mock"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_provider_configured(provider_key: str) -> bool:
    """Check whether a provider's required env var is set."""
    info = PROVIDER_INFO.get(provider_key)
    if info is None:
        return False
    env_key = info.get("env_key", "")
    if not env_key:
        # mock provider is always configured
        return True
    return bool(os.environ.get(env_key))


def _get_available_providers() -> list[str]:
    """Return provider keys that have their env vars configured."""
    return [k for k in PROVIDER_INFO if _is_provider_configured(k)]


# ---------------------------------------------------------------------------
# GET /llm
# ---------------------------------------------------------------------------
@router.get(
    "/llm",
    response_model=LLMSettingsResponse,
    summary="Get current LLM configuration",
)
def get_llm_settings(
    current_user: User = Depends(get_current_user),
):
    """Return the current LLM provider and model configuration."""
    return LLMSettingsResponse(
        provider=_llm_settings["provider"],
        model=_llm_settings["model"],
        available_providers=_get_available_providers(),
    )


# ---------------------------------------------------------------------------
# PUT /llm
# ---------------------------------------------------------------------------
@router.put(
    "/llm",
    response_model=LLMSettingsResponse,
    summary="Update LLM configuration (admin only)",
)
def update_llm_settings(
    body: LLMSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """
    Update the active LLM provider and/or model.

    Validates that the selected provider is configured (env var present)
    and that the model is in the provider's model list.
    """
    if body.provider is not None:
        if body.provider not in PROVIDER_INFO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown provider '{body.provider}'. Available: {list(PROVIDER_INFO.keys())}",
            )

        if not _is_provider_configured(body.provider):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider '{body.provider}' is not configured. "
                       f"Set the {PROVIDER_INFO[body.provider]['env_key']} environment variable.",
            )

        _llm_settings["provider"] = body.provider

        # If provider changed but model not specified, default to first model
        if body.model is None:
            _llm_settings["model"] = PROVIDER_INFO[body.provider]["models"][0]

    if body.model is not None:
        provider = body.provider or _llm_settings["provider"]
        valid_models = PROVIDER_INFO.get(provider, {}).get("models", [])
        if body.model not in valid_models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{body.model}' is not valid for provider '{provider}'. "
                       f"Available: {valid_models}",
            )
        _llm_settings["model"] = body.model

    audit_log(
        db,
        user_id=current_user.id,
        action="update_llm_settings",
        entity_type="settings",
        details={
            "provider": _llm_settings["provider"],
            "model": _llm_settings["model"],
        },
        ip_address=get_client_ip(request),
    )

    logger.info(
        "LLM settings updated to %s/%s by %s",
        _llm_settings["provider"],
        _llm_settings["model"],
        current_user.email,
    )

    return LLMSettingsResponse(
        provider=_llm_settings["provider"],
        model=_llm_settings["model"],
        available_providers=_get_available_providers(),
    )


# ---------------------------------------------------------------------------
# GET /llm/providers
# ---------------------------------------------------------------------------
@router.get(
    "/llm/providers",
    summary="List available LLM providers",
)
def list_providers(
    current_user: User = Depends(get_current_user),
):
    """
    Return all known LLM providers with their configuration status.

    A provider is 'configured' if its required environment variable is set.
    """
    result: Dict[str, Any] = {}
    for key, info in PROVIDER_INFO.items():
        result[key] = LLMProviderInfo(
            name=info["name"],
            configured=_is_provider_configured(key),
            models=info["models"],
        ).model_dump()

    return result
