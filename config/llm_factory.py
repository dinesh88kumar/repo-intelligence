"""
LLM factory — returns either a local Ollama LLM or a HuggingFace Inference API LLM
based on the application settings.
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def create_llm(settings: Settings | None = None, model_override: str | None = None) -> Any:
    """
    Create the appropriate LLM based on settings.

    When LOCAL_MODEL=True  → uses OllamaLLM (local)
    When LOCAL_MODEL=False → uses HuggingFaceEndpoint (API, much faster)

    Args:
        settings: Optional pre-loaded settings.
        model_override: Override model name.

    Returns:
        A LangChain-compatible LLM instance.
    """
    if settings is None:
        settings = load_settings()

    if settings.llm.local_model:
        # Use local Ollama
        from langchain_ollama.llms import OllamaLLM

        model_name = model_override or settings.llm.model_name
        logger.info("Using LOCAL Ollama model: %s", model_name)
        return OllamaLLM(model=model_name)
    else:
        # Use HuggingFace Inference API
        model_name = model_override or settings.llm.hf_model_name
        hf_token = settings.llm.hf_token

        if not hf_token:
            raise ValueError(
                "HF_TOKEN is required when LOCAL_MODEL=False. "
                "Set it in your .env file."
            )

        logger.info("Using HuggingFace Inference API model: %s", model_name)

        from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace

        endpoint = HuggingFaceEndpoint(
            repo_id=model_name,
            huggingfacehub_api_token=hf_token,
            temperature=settings.llm.temperature,
            max_new_tokens=2048,
        )
        return ChatHuggingFace(llm=endpoint)
