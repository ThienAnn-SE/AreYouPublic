"""Mastodon profile extractor.

Mastodon is a federated network — a user may be on any instance.
This extractor tries a curated list of large instances in order,
stopping on the first successful response.

The Mastodon API ``fields`` array exposes ``rel="me"`` verified links
which receive the highest confidence (1.0) per FR-4.1.

API docs: https://docs.joinmastodon.org/methods/accounts/
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from piea.modules.extractors.base import BaseExtractor
from piea.modules.extractors.bio_parser import BioParser
from piea.modules.extractors.models import LinkedAccount, ProfileData

logger = logging.getLogger(__name__)

# Ordered by instance size — check most likely instances first
_MASTODON_INSTANCES = [
    "mastodon.social",
    "fosstodon.org",
    "hachyderm.io",
    "infosec.exchange",
    "mastodon.online",
    "tech.lgbt",
]

_BIO_PARSER = BioParser()


class MastodonExtractor(BaseExtractor):
    """Extracts profile data from a Mastodon instance API.

    Tries each instance in _MASTODON_INSTANCES in order and returns the
    first successful result. Returns None only when all instances return 404.

    Args:
        http_client: Optional pre-configured httpx.AsyncClient.
        instances: Override the default instance list (used in tests).
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        instances: list[str] | None = None,
    ) -> None:
        super().__init__(http_client=http_client)
        self._instances = instances or _MASTODON_INSTANCES

    @property
    def platform_name(self) -> str:
        return "mastodon"

    async def extract(self, identifier: str) -> ProfileData | None:
        """Fetch Mastodon account for *identifier* across known instances.

        Args:
            identifier: Mastodon username (without ``@`` prefix).

        Returns:
            ProfileData from the first instance that has the account,
            or None if not found on any tried instance.

        Raises:
            ModuleAPIError: On unexpected HTTP errors from all instances.
            ModuleTimeoutError: On request timeout.
        """
        for instance in self._instances:
            result = await self._try_instance(identifier, instance)
            if result is not None:
                return result
        return None

    async def _try_instance(self, identifier: str, instance: str) -> ProfileData | None:
        """Attempt to fetch the account from a single Mastodon instance."""
        url = f"https://{instance}/api/v1/accounts/lookup"
        response = await self._safe_get(url, params={"acct": identifier})

        if response.status_code == 404:
            return None

        raw: dict[str, Any] = response.json()
        logger.debug("Found @%s on %s", identifier, instance)
        return _build_profile(identifier, instance, raw)


def _build_profile(identifier: str, instance: str, raw: dict[str, Any]) -> ProfileData:
    """Parse a Mastodon account API response into ProfileData."""
    linked = _extract_verified_links(raw)
    note_text = _strip_html(str(raw.get("note") or ""))
    linked.extend(_parse_bio_links(note_text))

    return ProfileData(
        platform="Mastodon",
        identifier=f"{identifier}@{instance}",
        profile_url=str(raw.get("url") or f"https://{instance}/@{identifier}"),
        display_name=str(raw.get("display_name") or "") or None,
        bio=note_text or None,
        location=None,  # Mastodon API does not expose a structured location field
        linked_accounts=linked,
        raw_data=raw,
    )


def _extract_verified_links(raw: dict[str, Any]) -> list[LinkedAccount]:
    """Extract ``rel="me"`` verified links from the ``fields`` array."""
    linked: list[LinkedAccount] = []
    fields: list[dict[str, Any]] = list(raw.get("fields") or [])
    for field in fields:
        verified_at = field.get("verified_at")
        value = str(field.get("value") or "")
        if not value.startswith("http"):
            continue
        linked.append(
            LinkedAccount(
                identifier=value,
                profile_url=value,
                platform=None,
                evidence_type="verified_link" if verified_at else "api_field",
                confidence=1.0 if verified_at else 0.8,
            )
        )
    return linked


def _parse_bio_links(bio_text: str) -> list[LinkedAccount]:
    """Extract URL tokens from bio text via BioParser."""
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


def _strip_html(text: str) -> str:
    """Remove HTML tags from Mastodon note fields."""
    return re.sub(r"<[^>]+>", " ", text).strip()
