from __future__ import annotations

import httpx

_clients: dict[tuple[str, float], httpx.AsyncClient] = {}


def shared_async_client(
    *,
    base_url: str = "",
    timeout_seconds: float = 60.0,
) -> httpx.AsyncClient:
    """Reuse warm TLS connections across requests.

    Creating a client per call costs a full DNS + TLS handshake (roughly
    0.3-0.8s against HF, Fish Audio and Gemini), which is noticeable in the
    voice loop where three providers are chained.
    """
    key = (base_url, timeout_seconds)
    client = _clients.get(key)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=300.0),
        )
        _clients[key] = client
    return client


async def close_shared_clients() -> None:
    for client in list(_clients.values()):
        if not client.is_closed:
            await client.aclose()
    _clients.clear()
