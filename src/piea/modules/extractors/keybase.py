"""Keybase profile extractor.

Keybase provides cryptographically verified proofs linking a username to
accounts on other platforms. All extracted proofs receive confidence=1.0
and evidence_type="keybase_proof" per FR-4.1.

API docs: https://keybase.io/docs/api/1.0/call/user/lookup
"""

from __future__ import annotations

import logging
from typing import Any

from piea.modules.extractors.base import BaseExtractor
from piea.modules.extractors.models import LinkedAccount, ProfileData

logger = logging.getLogger(__name__)

_API_URL = "https://keybase.io/_/api/1.0/user/lookup.json"

# Maps Keybase proof type strings to known platform names
_PROOF_TYPE_MAP: dict[str, str] = {
    "twitter": "twitter",
    "github": "github",
    "reddit": "reddit",
    "hackernews": "hackernews",
    "mastodon": "mastodon",
    "facebook": "facebook",
    "coinbase": "coinbase",
    "stellar": "stellar",
}


class KeybaseExtractor(BaseExtractor):
    """Extracts cryptographically verified cross-platform proofs from Keybase."""

    @property
    def platform_name(self) -> str:
        return "keybase"

    async def extract(self, identifier: str) -> ProfileData | None:
        """Fetch Keybase user profile and all proof objects.

        Args:
            identifier: Keybase username.

        Returns:
            ProfileData with LinkedAccount per verified proof, or None on 404.

        Raises:
            ModuleAPIError: On unexpected API errors.
            ModuleTimeoutError: On request timeout.
        """
        response = await self._safe_get(_API_URL, params={"usernames": identifier})

        if response.status_code == 404:
            return None

        raw: dict[str, Any] = response.json()
        return _build_profile(identifier, raw)


def _build_profile(identifier: str, raw: dict[str, Any]) -> ProfileData | None:
    """Parse the Keybase lookup response into ProfileData."""
    them: list[dict[str, Any]] = list(raw.get("them") or [])
    if not them:
        return None

    user: dict[str, Any] = dict(them[0])
    profile_raw: dict[str, Any] = dict(user.get("profile") or {})

    linked = _extract_proofs(user)

    return ProfileData(
        platform="Keybase",
        identifier=identifier,
        profile_url=f"https://keybase.io/{identifier}",
        display_name=str(profile_raw.get("full_name") or "") or None,
        bio=str(profile_raw.get("bio") or "") or None,
        location=str(profile_raw.get("location") or "") or None,
        linked_accounts=linked,
        raw_data=raw,
    )


def _extract_proofs(user: dict[str, Any]) -> list[LinkedAccount]:
    """Extract all Keybase proof objects as LinkedAccounts."""
    linked: list[LinkedAccount] = []
    proofs_summary: dict[str, Any] = dict(user.get("proofs_summary") or {})
    all_proofs: list[dict[str, Any]] = list(proofs_summary.get("all") or [])

    for proof in all_proofs:
        proof_type = str(proof.get("proof_type") or "")
        nametag = str(proof.get("nametag") or "")
        proof_url = str(proof.get("proof_url") or "")

        if not nametag:
            continue

        platform = _PROOF_TYPE_MAP.get(proof_type, proof_type or None)
        linked.append(
            LinkedAccount(
                identifier=nametag,
                profile_url=proof_url or f"https://{platform}.com/{nametag}"
                if platform
                else proof_url,
                platform=platform,
                evidence_type="keybase_proof",
                confidence=1.0,
            )
        )

    return linked
