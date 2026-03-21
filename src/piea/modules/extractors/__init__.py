"""Platform-specific profile extractor package for PIEA.

Each extractor fetches a public profile API, parses the response,
and returns a ProfileData value object for consumption by the
T2.6 graph crawler.

Public interface:
    BaseExtractor   — Abstract base; all extractors implement extract()
    ProfileData     — Value object: display_name, bio, linked_accounts, raw_data
    LinkedAccount   — A cross-platform account reference with confidence score
    BioToken        — A parsed identifier from free-text bio text
    BioParser       — Extracts BioTokens from bio strings

Platform extractors:
    GitHubExtractor, MastodonExtractor, KeybaseExtractor,
    GitLabExtractor, GravatarExtractor, RedditExtractor
"""

from piea.modules.extractors.base import BaseExtractor
from piea.modules.extractors.bio_parser import BioParser
from piea.modules.extractors.github import GitHubExtractor
from piea.modules.extractors.gitlab import GitLabExtractor
from piea.modules.extractors.gravatar import GravatarExtractor
from piea.modules.extractors.keybase import KeybaseExtractor
from piea.modules.extractors.mastodon import MastodonExtractor
from piea.modules.extractors.models import BioToken, LinkedAccount, ProfileData
from piea.modules.extractors.reddit import RedditExtractor

__all__ = [
    "BaseExtractor",
    "BioParser",
    "BioToken",
    "GitHubExtractor",
    "GitLabExtractor",
    "GravatarExtractor",
    "KeybaseExtractor",
    "LinkedAccount",
    "MastodonExtractor",
    "ProfileData",
    "RedditExtractor",
]
