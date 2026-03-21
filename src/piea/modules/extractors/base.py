"""Abstract base class for platform profile extractors.

All concrete extractors inherit from BaseExtractor, which provides:
  - A shared httpx.AsyncClient (injected or auto-created)
  - _safe_get(): L007-compliant HTTP GET that catches HTTPStatusError and
    re-raises as ModuleAPIError so raw URLs (containing usernames) never leak
  - Uniform constructor pattern (optional http_client injection for testing)

Concrete extractors implement extract(identifier) -> ProfileData | None.
"""

from __future__ import annotations

import abc
import logging

import httpx

from piea.modules.base import ModuleAPIError, ModuleTimeoutError
from piea.modules.extractors.models import ProfileData

logger = logging.getLogger(__name__)

USER_AGENT = "PIEA-SecurityScanner/1.0 (https://github.com/ThienAnn-SE/AreYouPublic)"

_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 20.0


class BaseExtractor(abc.ABC):
    """Abstract base for platform-specific profile extractors.

    Args:
        http_client: Optional pre-configured httpx.AsyncClient.
            If None, one is created automatically and closed in close().
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(_READ_TIMEOUT, connect=_CONNECT_TIMEOUT),
            follow_redirects=True,
        )

    @property
    @abc.abstractmethod
    def platform_name(self) -> str:
        """Unique platform identifier (e.g. "github", "reddit")."""

    @abc.abstractmethod
    async def extract(self, identifier: str) -> ProfileData | None:
        """Fetch and parse the public profile for *identifier*.

        Args:
            identifier: Username or email depending on the platform.

        Returns:
            A populated ProfileData, or None if the profile does not exist
            (HTTP 404 or equivalent "not found" API response).

        Raises:
            ModuleAPIError: On unexpected HTTP errors (not 404).
            ModuleTimeoutError: On request timeout.
        """

    async def close(self) -> None:
        """Close the HTTP client if we created it."""
        if self._owns_client:
            await self._client.aclose()

    async def _safe_get(
        self, url: str, **kwargs: str | dict[str, str]
    ) -> httpx.Response:
        """GET *url*, catching transport errors with L007-compliant re-raises.

        The raw URL is never included in exception messages because URLs
        often contain usernames or hashed emails (PII).

        Args:
            url: The URL to GET.
            **kwargs: Additional kwargs forwarded to httpx.AsyncClient.get().

        Returns:
            The HTTP response (caller checks status_code before processing).

        Raises:
            ModuleTimeoutError: On httpx.TimeoutException.
            ModuleAPIError: On non-404 HTTP errors or network failures.
        """
        try:
            response = await self._client.get(url, **kwargs)  # type: ignore[arg-type]  # kwargs forwarded to httpx
        except httpx.TimeoutException as exc:
            raise ModuleTimeoutError(self.platform_name, "Request timed out") from exc
        except httpx.RequestError as exc:
            raise ModuleAPIError(
                self.platform_name, 0, "Network error during request"
            ) from exc

        if response.status_code >= 400 and response.status_code != 404:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # Re-raise without raw URL/username (L007)
                raise ModuleAPIError(
                    self.platform_name,
                    exc.response.status_code,
                    f"{self.platform_name} profile lookup failed",
                ) from None

        return response
