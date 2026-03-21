"""Gravatar profile extractor.

Gravatar profiles are keyed by the MD5 hash of a normalised email address —
not by username. This extractor's identifier parameter is therefore an email.

The MD5 hash is computed locally and never logged; only the hash is sent
to Gravatar's servers. Per NFR-S3, the raw email is not embedded in any URL.

API docs: https://en.gravatar.com/site/implement/profiles/json/
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from piea.modules.extractors.base import BaseExtractor
from piea.modules.extractors.bio_parser import BioParser
from piea.modules.extractors.models import LinkedAccount, ProfileData

logger = logging.getLogger(__name__)

_API_BASE = "https://www.gravatar.com"
_BIO_PARSER = BioParser()


class GravatarExtractor(BaseExtractor):
    """Extracts Gravatar profile data keyed by email address.

    Note: the ``identifier`` parameter for this extractor is an email
    address, not a username. The extractor hashes it before sending any
    network request so the raw email is never transmitted.
    """

    @property
    def platform_name(self) -> str:
        return "gravatar"

    async def extract(self, identifier: str) -> ProfileData | None:
        """Fetch Gravatar profile for the email *identifier*.

        Args:
            identifier: Email address. Normalised and MD5-hashed before use.

        Returns:
            ProfileData on success, None if no Gravatar profile exists (404).

        Raises:
            ModuleAPIError: On unexpected API errors.
            ModuleTimeoutError: On request timeout.
        """
        email_hash = _hash_email(identifier)
        url = f"{_API_BASE}/{email_hash}.json"
        response = await self._safe_get(url)

        if response.status_code == 404:
            return None

        raw: dict[str, Any] = response.json()
        return _build_profile(identifier, email_hash, raw)


def _hash_email(email: str) -> str:
    """Compute the Gravatar MD5 hash for *email*.

    Per Gravatar's spec: trim whitespace, lowercase, then MD5.
    The hash is used in URLs; the raw email is not sent to the server.
    """
    normalised = email.strip().lower()
    return hashlib.md5(normalised.encode("utf-8")).hexdigest()  # noqa: S324 — MD5 required by Gravatar API spec; used as profile key, not for password storage


def _build_profile(email: str, email_hash: str, raw: dict[str, Any]) -> ProfileData:
    """Parse a Gravatar JSON response into ProfileData."""
    entry_list: list[dict[str, Any]] = list(raw.get("entry") or [])
    entry: dict[str, Any] = dict(entry_list[0]) if entry_list else {}

    linked = _extract_linked_accounts(entry)
    about_text = str(entry.get("aboutMe") or "")
    linked.extend(_parse_bio_links(about_text))

    display_name = (
        str(entry.get("displayName") or "")
        or str(entry.get("preferredUsername") or "")
        or None
    )

    return ProfileData(
        platform="Gravatar",
        identifier=email_hash,  # use the hash as identifier, not the raw email
        profile_url=f"{_API_BASE}/{email_hash}",
        display_name=display_name,
        bio=about_text or None,
        location=None,
        linked_accounts=linked,
        raw_data=raw,
    )


def _extract_linked_accounts(entry: dict[str, Any]) -> list[LinkedAccount]:
    """Extract URL objects from the Gravatar ``urls`` array."""
    linked: list[LinkedAccount] = []
    urls: list[dict[str, Any]] = list(entry.get("urls") or [])
    for url_obj in urls:
        value = str(url_obj.get("value") or "")
        if not value.startswith("http"):
            continue
        title = str(url_obj.get("title") or "")
        linked.append(
            LinkedAccount(
                identifier=title or value,
                profile_url=value,
                platform=None,
                evidence_type="api_field",
                confidence=0.8,
            )
        )

    accounts: list[dict[str, Any]] = list(entry.get("accounts") or [])
    for account in accounts:
        shortname = str(account.get("shortname") or "")
        url = str(account.get("url") or "")
        if not url:
            continue
        linked.append(
            LinkedAccount(
                identifier=shortname or url,
                profile_url=url,
                platform=shortname or None,
                evidence_type="api_field",
                confidence=0.85,
            )
        )

    return linked


def _parse_bio_links(bio_text: str) -> list[LinkedAccount]:
    """Extract URL tokens from the aboutMe field."""
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
        if t.token_type == "url"
    ]
