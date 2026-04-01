"""Async GraphQL client for the D&D 5e API.

Uses ``httpx.AsyncClient`` to send POST requests to the GraphQL endpoint.
Provides high-level ``fetch_list`` and ``fetch_detail`` methods that accept
a :class:`~bot.models.state.Category` and return parsed JSON data.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://www.dnd5eapi.co/graphql/2014"
TIMEOUT = 15.0  # seconds


class APIError(Exception):
    """Raised when the GraphQL API returns an error or is unreachable."""


class DnDClient:
    """Async wrapper around the D&D 5e GraphQL API."""

    def __init__(self, url: str = GRAPHQL_URL, timeout: float = TIMEOUT) -> None:
        self._url = url
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create (or reuse) an ``httpx.AsyncClient``."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _execute(
        self, query: str, variables: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query and return the parsed JSON ``data`` dict.

        Raises :class:`APIError` on network or GraphQL errors.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = await client.post(self._url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP %s from D&D API: %s", exc.response.status_code, exc)
            raise APIError(f"API returned HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Network error contacting D&D API: %s", exc)
            raise APIError("Could not reach the D&D API. Please try again later.") from exc

        body = response.json()
        if "errors" in body:
            msg = body["errors"][0].get("message", "Unknown GraphQL error")
            logger.error("GraphQL error: %s", msg)
            raise APIError(f"GraphQL error: {msg}")

        return body.get("data", {})

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    async def fetch_list(
        self,
        query: str,
        field: str,
        skip: int = 0,
        limit: int = 11,
        paginated: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch a list of items for a category.

        When *paginated* is ``True``, ``skip`` and ``limit`` are passed as
        GraphQL variables.  We request ``limit`` items (caller should ask for
        PAGE_SIZE + 1 to detect "has next page").
        """
        variables: dict[str, Any] = {}
        if paginated:
            variables = {"skip": skip, "limit": limit}

        data = await self._execute(query, variables or None)
        items: list[dict[str, Any]] = data.get(field, [])
        return items

    async def fetch_detail(
        self, query: str, field: str, index: str
    ) -> dict[str, Any]:
        """Fetch the full detail of a single item by its index slug."""
        data = await self._execute(query, {"index": index})
        item: dict[str, Any] = data.get(field, {})
        if not item:
            raise APIError(f"Item '{index}' not found.")
        return item


# Module-level singleton
dnd_client = DnDClient()
