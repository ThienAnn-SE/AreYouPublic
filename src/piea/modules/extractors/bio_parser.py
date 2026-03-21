"""Bio/description text parser for cross-platform identifier extraction.

Scans free-text bio fields and produces typed BioToken objects for each
recognisable identifier. Patterns are applied in priority order so that
more-specific patterns (e.g. Mastodon handles) take precedence over
more-generic ones (e.g. plain email addresses).

All patterns are compiled once at module load time (FR-4.2).
"""

from __future__ import annotations

import re

from piea.modules.extractors.models import BioToken

# ---------------------------------------------------------------------------
# Compiled patterns (in priority order — most specific first)
# ---------------------------------------------------------------------------

# Mastodon: @user@instance.tld — must be checked before plain email
_RE_MASTODON = re.compile(r"@([a-zA-Z0-9_.-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")

# Plain email addresses (RFC 5322 simplified)
_RE_EMAIL = re.compile(r"\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b")

# Full https:// or http:// URLs
_RE_URL = re.compile(r"https?://[^\s\"'<>)}\]]{3,}")

# Bare @handle (Twitter / X / generic social handle)
_RE_HANDLE = re.compile(r"(?<![/@\w])@([a-zA-Z0-9_]{1,50})(?!\.[a-zA-Z])")

# Bare domain references: something.tld (2+ char TLD, not inside a URL)
_RE_DOMAIN = re.compile(
    r"(?<![/@\w])([a-zA-Z0-9\-]{2,63}\.(?:com|org|net|io|dev|me|co|uk|de|fr|jp|app)){1}"
)

# ---------------------------------------------------------------------------
# Platform URL fingerprints: (compiled pattern, platform_name)
# ---------------------------------------------------------------------------

_URL_PLATFORM_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"github\.com/([a-zA-Z0-9_.-]+)"), "github"),
    (re.compile(r"gitlab\.com/([a-zA-Z0-9_.-]+)"), "gitlab"),
    (re.compile(r"twitter\.com/([a-zA-Z0-9_]+)"), "twitter"),
    (re.compile(r"x\.com/([a-zA-Z0-9_]+)"), "twitter"),
    (re.compile(r"linkedin\.com/in/([a-zA-Z0-9_-]+)"), "linkedin"),
    (re.compile(r"keybase\.io/([a-zA-Z0-9_]+)"), "keybase"),
    (re.compile(r"instagram\.com/([a-zA-Z0-9_.]+)"), "instagram"),
    (re.compile(r"youtube\.com/@([a-zA-Z0-9_.]+)"), "youtube"),
    (re.compile(r"twitch\.tv/([a-zA-Z0-9_]+)"), "twitch"),
    (re.compile(r"reddit\.com/u(?:ser)?/([a-zA-Z0-9_-]+)"), "reddit"),
    (re.compile(r"mastodon\.social/@([a-zA-Z0-9_]+)"), "mastodon"),
    (re.compile(r"bsky\.app/profile/([a-zA-Z0-9_.:-]+)"), "bluesky"),
    (re.compile(r"dev\.to/([a-zA-Z0-9_-]+)"), "dev.to"),
    (re.compile(r"medium\.com/@([a-zA-Z0-9_]+)"), "medium"),
    (re.compile(r"stackoverflow\.com/users/\d+/([a-zA-Z0-9_-]+)"), "stackoverflow"),
    (re.compile(r"soundcloud\.com/([a-zA-Z0-9_-]+)"), "soundcloud"),
    (re.compile(r"npmjs\.com/~([a-zA-Z0-9_-]+)"), "npm"),
]


class BioParser:
    """Extracts typed cross-platform identifiers from free-text bio strings.

    All methods are stateless — the class holds no mutable state.
    Usage::

        tokens = BioParser().parse("Find me at https://github.com/alice or @alice@mastodon.example.com")
    """

    def parse(self, text: str) -> list[BioToken]:
        """Extract all recognisable identifiers from *text*.

        Patterns are applied in priority order. Text positions consumed by
        a higher-priority match are excluded from lower-priority passes to
        avoid double-counting.

        Args:
            text: Free-text bio, description, or note field.

        Returns:
            List of BioToken objects, de-duplicated by normalized_value.
        """
        if not text.strip():
            return []

        tokens: list[BioToken] = []
        seen_normalized: set[str] = set()
        # Track character spans already consumed by a match
        consumed_spans: list[tuple[int, int]] = []

        tokens.extend(self._extract_mastodon(text, consumed_spans, seen_normalized))
        tokens.extend(self._extract_urls(text, consumed_spans, seen_normalized))
        tokens.extend(self._extract_emails(text, consumed_spans, seen_normalized))
        tokens.extend(self._extract_handles(text, consumed_spans, seen_normalized))

        return tokens

    # -------------------------------------------------------------------
    # Private extraction helpers
    # -------------------------------------------------------------------

    def _extract_mastodon(
        self,
        text: str,
        consumed: list[tuple[int, int]],
        seen: set[str],
    ) -> list[BioToken]:
        tokens = []
        for m in _RE_MASTODON.finditer(text):
            if _overlaps(m.span(), consumed):
                continue
            raw = m.group(0)
            normalized = raw.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            consumed.append(m.span())
            tokens.append(
                BioToken(
                    token_type="mastodon_handle",
                    raw_value=raw,
                    normalized_value=normalized,
                    platform="mastodon",
                    confidence=0.95,
                )
            )
        return tokens

    def _extract_urls(
        self,
        text: str,
        consumed: list[tuple[int, int]],
        seen: set[str],
    ) -> list[BioToken]:
        tokens = []
        for m in _RE_URL.finditer(text):
            if _overlaps(m.span(), consumed):
                continue
            raw = m.group(0).rstrip(".,;:)")
            normalized = raw.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            consumed.append(m.span())
            platform, confidence = _classify_url(raw)
            tokens.append(
                BioToken(
                    token_type="url",
                    raw_value=raw,
                    normalized_value=normalized,
                    platform=platform,
                    confidence=confidence,
                )
            )
        return tokens

    def _extract_emails(
        self,
        text: str,
        consumed: list[tuple[int, int]],
        seen: set[str],
    ) -> list[BioToken]:
        tokens = []
        for m in _RE_EMAIL.finditer(text):
            if _overlaps(m.span(), consumed):
                continue
            raw = m.group(1)
            normalized = raw.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            consumed.append(m.span())
            tokens.append(
                BioToken(
                    token_type="email",
                    raw_value=raw,
                    normalized_value=normalized,
                    platform=None,
                    confidence=0.9,
                )
            )
        return tokens

    def _extract_handles(
        self,
        text: str,
        consumed: list[tuple[int, int]],
        seen: set[str],
    ) -> list[BioToken]:
        tokens = []
        for m in _RE_HANDLE.finditer(text):
            if _overlaps(m.span(), consumed):
                continue
            raw = m.group(0)
            normalized = raw.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            consumed.append(m.span())
            tokens.append(
                BioToken(
                    token_type="handle",
                    raw_value=raw,
                    normalized_value=normalized,
                    platform=None,  # ambiguous without context
                    confidence=0.5,
                )
            )
        return tokens


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _overlaps(span: tuple[int, int], consumed: list[tuple[int, int]]) -> bool:
    """Return True if *span* overlaps any interval in *consumed*."""
    start, end = span
    return any(s < end and e > start for s, e in consumed)


def _classify_url(url: str) -> tuple[str | None, float]:
    """Map a URL to a platform name and confidence score.

    Args:
        url: A full https:// URL.

    Returns:
        Tuple of (platform_name or None, confidence 0.0–1.0).
    """
    for pattern, platform in _URL_PLATFORM_PATTERNS:
        if pattern.search(url):
            return platform, 0.85
    return None, 0.6
