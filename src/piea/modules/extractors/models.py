"""Value objects produced by platform profile extractors.

These are pure data containers — no business logic, no I/O.
T2.6 (graph crawler) consumes them to build GraphNode/GraphEdge rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LinkedAccount:
    """A cross-platform account reference discovered on a profile.

    Attributes:
        identifier: The username or handle on the linked platform.
        profile_url: The full URL to the linked profile.
        platform: Platform name (e.g. "twitter"), or None if unrecognised.
        evidence_type: How the link was found:
            - "api_field"      — structured field in the API response
            - "verified_link"  — ``rel="me"`` link verified by the platform
            - "bio_mention"    — extracted from free-text bio
            - "keybase_proof"  — cryptographically verified by Keybase
        confidence: 0.0–1.0 likelihood that the link is accurate.
    """

    identifier: str
    profile_url: str
    platform: str | None
    evidence_type: str
    confidence: float


@dataclass(frozen=True, slots=True)
class BioToken:
    """A single identifier extracted from free-text bio/description.

    Attributes:
        token_type: Semantic type: "url", "handle", "email", "domain",
            or "mastodon_handle".
        raw_value: The text as it appeared in the bio.
        normalized_value: Cleaned, lowercased form for deduplication.
        platform: Platform name if the identifier maps to a known platform.
        confidence: 0.0–1.0 likelihood of the attribution being correct.
    """

    token_type: str
    raw_value: str
    normalized_value: str
    platform: str | None
    confidence: float


@dataclass(frozen=True, slots=True)
class ProfileData:
    """Structured data extracted from a single public profile.

    This is the output contract for all BaseExtractor implementations.
    T2.6 converts these into GraphNode rows and schedules further
    extraction for each LinkedAccount.

    Attributes:
        platform: Platform identifier (matches PlatformConfig.platform).
        identifier: The username/handle on this platform.
        profile_url: Canonical URL of the profile page.
        display_name: Real name or display name if publicly visible.
        bio: Raw bio/description text (used by BioParser downstream).
        location: Self-reported location string.
        emails: Email addresses found directly in structured API fields
            (not bio-parsed — those go through LinkedAccount).
        linked_accounts: Cross-platform accounts discovered via API
            fields, verified links, or bio parsing.
        raw_data: Full API response payload for persistence to GraphNode.raw_data.
    """

    platform: str
    identifier: str
    profile_url: str
    display_name: str | None = None
    bio: str | None = None
    location: str | None = None
    emails: list[str] = field(default_factory=list)
    linked_accounts: list[LinkedAccount] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
