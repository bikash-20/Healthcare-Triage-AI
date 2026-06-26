"""Application package for the rural-health-triage backend.

The FastAPI instance is created lazily by ``create_app()`` (defined in
``main.py``). Tests can patch dependencies before ``create_app()`` runs by
setting environment variables or by monkeypatching ``main.llm_client``.
"""
from .main import create_app

app = create_app()

__all__ = ["create_app"]
