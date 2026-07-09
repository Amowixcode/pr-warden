from __future__ import annotations


class PRWardenError(Exception):
    """Base exception for pr-warden domain errors."""


class VectorStoreError(PRWardenError):
    """Raised when a ChromaDB operation fails."""
