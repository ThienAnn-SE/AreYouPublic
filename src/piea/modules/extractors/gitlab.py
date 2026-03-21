"""GitLab profile extractor.

Uses the public GitLab Users API (no auth required for public profiles).

API docs: https://docs.gitlab.com/ee/api/users.html#for-normal-users
"""

from __future__ import annotations

import logging
from typing import Any

from piea.modules.extractors.base import BaseExtractor
from piea.modules.extractors.bio_parser import BioParser
from piea.modules.extractors.models import LinkedAccount, ProfileData

logger = logging.getLogger(__name__)

_API_URL = "https://gitlab.com/api/v4/users"
_BIO_PARSER = BioParser()


class GitLabExtractor(BaseExtractor):
    """Extracts profile data from the GitLab public Users API."""

    @property
    def platform_name(self) -> str:
        return "gitlab"

    async def extract(self, identifier: str) -> ProfileData | None:
        """Fetch GitLab profile for *identifier*.

        Args:
            identifier: GitLab username.

        Returns:
            ProfileData on success, None if user not found.

        Raises:
            ModuleAPIError: On unexpected API errors.
            ModuleTimeoutError: On request timeout.
        """
        response = await self._safe_get(_API_URL, params={"username": identifier})

        if response.status_code == 404:
            return None

        users: list[dict[str, Any]] = list(response.json())
        if not users:
            return None

        raw: dict[str, Any] = dict(users[0])
        return _build_profile(identifier, raw)


def _build_profile(identifier: str, raw: dict[str, Any]) -> ProfileData:
    """Parse a GitLab Users API response into ProfileData."""
    linked = _extract_linked_accounts(raw)
    bio_text = str(raw.get("bio") or "")
    linked.extend(_parse_bio_links(bio_text))

    return ProfileData(
        platform="GitLab",
        identifier=identifier,
        profile_url=str(raw.get("web_url") or f"https://gitlab.com/{identifier}"),
        display_name=str(raw.get("name") or "") or None,
        bio=bio_text or None,
        location=str(raw.get("location") or "") or None,
        linked_accounts=linked,
        raw_data=raw,
    )


def _extract_linked_accounts(raw: dict[str, Any]) -> list[LinkedAccount]:
    """Extract structured profile fields that reference external accounts."""
    linked: list[LinkedAccount] = []

    website = str(raw.get("website_url") or "")
    if website and website.startswith("http"):
        linked.append(
            LinkedAccount(
                identifier=website,
                profile_url=website,
                platform=None,
                evidence_type="api_field",
                confidence=0.85,
            )
        )

    twitter = str(raw.get("twitter") or "")
    if twitter:
        handle = twitter.lstrip("@")
        linked.append(
            LinkedAccount(
                identifier=handle,
                profile_url=f"https://twitter.com/{handle}",
                platform="twitter",
                evidence_type="api_field",
                confidence=0.9,
            )
        )

    linkedin = str(raw.get("linkedin") or "")
    if linkedin:
        linked.append(
            LinkedAccount(
                identifier=linkedin,
                profile_url=f"https://www.linkedin.com/in/{linkedin}",
                platform="linkedin",
                evidence_type="api_field",
                confidence=0.9,
            )
        )

    return linked


def _parse_bio_links(bio_text: str) -> list[LinkedAccount]:
    """Extract URL and Mastodon tokens from bio text."""
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
