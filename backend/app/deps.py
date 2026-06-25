"""Shared FastAPI dependency providers."""
from temporalio.client import Client as TemporalClient

_temporal_client: TemporalClient | None = None


def set_temporal_client(client: TemporalClient) -> None:
    global _temporal_client
    _temporal_client = client


def get_temporal_client() -> TemporalClient:
    if _temporal_client is None:
        raise RuntimeError("Temporal client not initialized")
    return _temporal_client
