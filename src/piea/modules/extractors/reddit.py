"""Reddit profile extractor.

Uses Reddit's public JSON API (no auth required for public user profiles).
Reddit requires a non-default User-Agent string that identifies the application
and contact information — using the default httpx agent results in 403 errors.

API docs: https://www.reddit.com/dev/api#GET_user_{username}_about
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from piea.modules.base import ModuleAPIError
from piea.modules.extractors.base import USER_AGENT, BaseExtractor
from piea.modules.extractors.bio_parser import BioParser
from piea.modules.extractors.models import LinkedAccount, ProfileData

logger = logging.getLogger(__name__)

_API_BASE = "https://www.reddit.com/user"
_BIO_PARSER = BioParser()


class RedditExtractor(BaseExtractor):
    """Extracts profile data from the Reddit public JSON API.

    Uses a custom User-Agent per Reddit's API guidelines.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        # Reddit requires an identifiable User-Agent or returns 403
        owns = http_client is None
        client = http_client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
        )
        super().__init__(http_client=client)
        self._owns_client = owns  # fix: we created the client above, so we own it

    @property
    def platform_name(self) -> str:
        return "reddit"

    async def extract(self, identifier: str) -> ProfileData | None:
        """Fetch Reddit user profile for *identifier*.

        Args:
            identifier: Reddit username (without u/ prefix).

        Returns:
            ProfileData on success, None if user not found (404) or
            suspended/shadow-banned (403).

        Raises:
            ModuleAPIError: On unexpected API errors (not 403/404).
            ModuleTimeoutError: On request timeout.
        """
        url = f"{_API_BASE}/{identifier}/about.json"
        try:
            response = await self._safe_get(url)
        except ModuleAPIError as exc:
            # 403 = suspended/shadow-banned account — treat as not found
            if exc.status_code == 403:
                return None
            raise

        if response.status_code == 404:
            return None

        raw: dict[str, Any] = response.json()
        return _build_profile(identifier, raw)


def _build_profile(identifier: str, raw: dict[str, Any]) -> ProfileData:
    """Parse a Reddit about.json response into ProfileData."""
    data: dict[str, Any] = dict(raw.get("data") or {})
    subreddit: dict[str, Any] = dict(data.get("subreddit") or {})
    description = str(subreddit.get("public_description") or "")

    linked = _parse_bio_links(description)

    return ProfileData(
        platform="Reddit",
        identifier=identifier,
        profile_url=f"https://www.reddit.com/user/{identifier}",
        display_name=None,  # Reddit does not expose real names via public API
        bio=description or None,
        location=None,
        linked_accounts=linked,
        raw_data=raw,
    )


def _parse_bio_links(bio_text: str) -> list[LinkedAccount]:
    """Extract URL and Mastodon tokens from the public description."""
    if not bio_text:
        return []
    tokens = _BIO_PARSER.parse(bio_text)
    return [
        LinkedAccount(
            identifier=t.normalized_value,
            profile_url=t.raw_value,
            platform=t.platform,
            evidence_type="bio_mention",
            confidence=t.confidence * 0.8,
        )
        for t in tokens
        if t.token_type in ("url", "mastodon_handle")
    ]
