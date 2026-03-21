"""GitHub profile extractor.

Calls the GitHub Users API (public, no auth required for basic data).
An optional GITHUB_TOKEN env var raises the rate limit from 60 to 5 000 req/hr.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from piea.modules.extractors.base import BaseExtractor
from piea.modules.extractors.bio_parser import BioParser
from piea.modules.extractors.models import LinkedAccount, ProfileData

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com/users"
_PROFILE_BASE = "https://github.com"
_BIO_PARSER = BioParser()


class GitHubExtractor(BaseExtractor):
    """Extracts profile data from the GitHub Users API.

    API docs: https://docs.github.com/en/rest/users/users#get-a-user

    Args:
        http_client: Optional pre-configured httpx.AsyncClient.
        github_token: Optional GitHub personal access token. Falls back to
            the GITHUB_TOKEN environment variable if not supplied.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        github_token: str | None = None,
    ) -> None:
        token = github_token or os.environ.get("GITHUB_TOKEN", "")
        headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        owns = http_client is None
        client = http_client or httpx.AsyncClient(
            headers={"User-Agent": "PIEA-SecurityScanner/1.0", **headers},
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
        )
        super().__init__(http_client=client)
        self._owns_client = owns  # fix: we created the client above, so we own it

    @property
    def platform_name(self) -> str:
        return "github"

    async def extract(self, identifier: str) -> ProfileData | None:
        """Fetch GitHub user profile for *identifier*.

        Args:
            identifier: GitHub username.

        Returns:
            ProfileData on success, None if user not found (HTTP 404).

        Raises:
            ModuleAPIError: On unexpected HTTP errors.
            ModuleTimeoutError: On request timeout.
        """
        url = f"{_API_BASE}/{identifier}"
        response = await self._safe_get(url)

        if response.status_code == 404:
            return None

        raw: dict[str, Any] = response.json()
        return _build_profile(identifier, raw)


def _build_profile(identifier: str, raw: dict[str, Any]) -> ProfileData:
    """Parse a GitHub API response into ProfileData."""
    linked = _extract_linked_accounts(raw)
    bio_text = str(raw.get("bio") or "")
    linked.extend(_parse_bio_links(bio_text))

    return ProfileData(
        platform="GitHub",
        identifier=identifier,
        profile_url=f"{_PROFILE_BASE}/{identifier}",
        display_name=str(raw.get("name") or "") or None,
        bio=bio_text or None,
        location=str(raw.get("location") or "") or None,
        emails=_extract_emails(raw),
        linked_accounts=linked,
        raw_data=raw,
    )


def _extract_linked_accounts(raw: dict[str, Any]) -> list[LinkedAccount]:
    """Pull structured fields that point to external accounts."""
    linked: list[LinkedAccount] = []

    twitter = str(raw.get("twitter_username") or "")
    if twitter:
        linked.append(
            LinkedAccount(
                identifier=twitter,
                profile_url=f"https://twitter.com/{twitter}",
                platform="twitter",
                evidence_type="api_field",
                confidence=0.9,
            )
        )

    blog = str(raw.get("blog") or "")
    if blog and blog.startswith("http"):
        linked.append(
            LinkedAccount(
                identifier=blog,
                profile_url=blog,
                platform=None,
                evidence_type="api_field",
                confidence=0.8,
            )
        )

    return linked


def _extract_emails(raw: dict[str, Any]) -> list[str]:
    """Return email addresses visible in the public API response."""
    email = str(raw.get("email") or "")
    return [email] if email else []


def _parse_bio_links(bio_text: str) -> list[LinkedAccount]:
    """Run BioParser on the bio and convert URL tokens to LinkedAccounts."""
    if not bio_text:
        return []
    tokens = _BIO_PARSER.parse(bio_text)
    return [
        LinkedAccount(
            identifier=t.normalized_value,
            profile_url=t.raw_value if t.token_type == "url" else t.raw_value,
            platform=t.platform,
            evidence_type="bio_mention",
            confidence=t.confidence * 0.8,  # bio is less reliable than API fields
        )
        for t in tokens
        if t.token_type in ("url", "mastodon_handle")
    ]
