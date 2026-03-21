"""Unit tests for T2.5 — platform-specific profile extractors and bio parser.

All HTTP calls are mocked with respx. No real network traffic is made.
Test data uses RFC 2606 reserved domains (example.com, example.org)
and RFC 5737 addresses only.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from piea.modules.base import ModuleAPIError, ModuleTimeoutError
from piea.modules.extractors.bio_parser import BioParser
from piea.modules.extractors.github import GitHubExtractor
from piea.modules.extractors.gitlab import GitLabExtractor
from piea.modules.extractors.gravatar import GravatarExtractor, _hash_email
from piea.modules.extractors.keybase import KeybaseExtractor
from piea.modules.extractors.mastodon import MastodonExtractor
from piea.modules.extractors.models import ProfileData
from piea.modules.extractors.reddit import RedditExtractor

# ---------------------------------------------------------------------------
# BioParser
# ---------------------------------------------------------------------------


class TestBioParser:
    parser = BioParser()

    def test_empty_string_returns_no_tokens(self) -> None:
        assert self.parser.parse("") == []

    def test_whitespace_only_returns_no_tokens(self) -> None:
        assert self.parser.parse("   \n\t  ") == []

    def test_plain_text_no_identifiers_returns_empty(self) -> None:
        tokens = self.parser.parse("Hello, world. I like coding.")
        assert tokens == []

    def test_extracts_https_url(self) -> None:
        tokens = self.parser.parse("Visit https://example.com for more info.")
        urls = [t for t in tokens if t.token_type == "url"]
        assert any("example.com" in t.raw_value for t in urls)

    def test_extracts_github_url_and_maps_platform(self) -> None:
        tokens = self.parser.parse("My code: https://github.com/testuser")
        github_tokens = [t for t in tokens if t.platform == "github"]
        assert len(github_tokens) == 1

    def test_extracts_twitter_url_and_maps_platform(self) -> None:
        tokens = self.parser.parse("Follow me: https://twitter.com/testuser")
        twitter_tokens = [t for t in tokens if t.platform == "twitter"]
        assert len(twitter_tokens) == 1

    def test_mastodon_handle_classified_not_as_email(self) -> None:
        """Double-@ handle format must produce mastodon_handle, not email (overlap test)."""
        tokens = self.parser.parse("Find me at @alice@example.com")
        types = {t.token_type for t in tokens}
        assert "mastodon_handle" in types
        assert "email" not in types

    def test_mastodon_handle_not_duplicated(self) -> None:
        """Only one token per Mastodon handle — no overlap double-count."""
        tokens = self.parser.parse("@alice@example.com")
        mastodon = [t for t in tokens if t.token_type == "mastodon_handle"]
        assert len(mastodon) == 1

    def test_mastodon_platform_set_correctly(self) -> None:
        tokens = self.parser.parse("Toot at @bob@example.org")
        m = next(t for t in tokens if t.token_type == "mastodon_handle")
        assert m.platform == "mastodon"

    def test_extracts_email_address(self) -> None:
        tokens = self.parser.parse("Contact: user@example.com")
        emails = [t for t in tokens if t.token_type == "email"]
        assert any("example.com" in t.normalized_value for t in emails)

    def test_at_handle_extracted(self) -> None:
        tokens = self.parser.parse("Twitter: @testuser2025")
        handles = [t for t in tokens if t.token_type == "handle"]
        assert any("testuser2025" in t.normalized_value for t in handles)

    def test_duplicate_url_not_repeated(self) -> None:
        text = "https://example.com https://example.com"
        tokens = self.parser.parse(text)
        urls = [t for t in tokens if t.token_type == "url"]
        assert len(urls) == 1

    def test_keybase_url_maps_platform(self) -> None:
        tokens = self.parser.parse("Proof: https://keybase.io/testuser")
        keybase = [t for t in tokens if t.platform == "keybase"]
        assert len(keybase) == 1

    def test_confidence_within_range(self) -> None:
        tokens = self.parser.parse(
            "https://github.com/alice @alice@example.com user@example.com"
        )
        for t in tokens:
            assert 0.0 <= t.confidence <= 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_github_response(username: str = "testuser") -> dict:
    return {
        "login": username,
        "name": "Test User",
        "bio": "Building open-source tools. https://example.com",
        "location": "Testville",
        "email": "testuser@example.org",
        "twitter_username": "testuser_tw",
        "blog": "https://blog.example.com",
        "public_repos": 42,
        "followers": 100,
        "avatar_url": "https://avatars.githubusercontent.com/u/1",
        "created_at": "2020-01-01T00:00:00Z",
    }


def _mock_gitlab_response(username: str = "testuser") -> list:
    return [
        {
            "id": 1,
            "username": username,
            "name": "Test GitLab User",
            "bio": "GitLab developer",
            "location": "Testland",
            "web_url": f"https://gitlab.com/{username}",
            "website_url": "https://example.com",
            "twitter": "testuser_gl",
            "linkedin": "testuser-gl",
        }
    ]


def _mock_keybase_response(username: str = "testuser") -> dict:
    return {
        "status": {"code": 0},
        "them": [
            {
                "basics": {"username": username},
                "profile": {
                    "full_name": "Test Keybase User",
                    "bio": "Security researcher",
                    "location": "Testcity",
                },
                "proofs_summary": {
                    "all": [
                        {
                            "proof_type": "github",
                            "nametag": username,
                            "proof_url": f"https://gist.github.com/{username}/abc123",
                        },
                        {
                            "proof_type": "twitter",
                            "nametag": f"{username}_tw",
                            "proof_url": f"https://twitter.com/{username}_tw/status/1",
                        },
                    ]
                },
            }
        ],
    }


def _mock_mastodon_response(username: str = "testuser") -> dict:
    return {
        "id": "1234",
        "username": username,
        "acct": username,
        "display_name": "Test Mastodon User",
        "note": "<p>Open-source dev. https://example.com</p>",
        "url": f"https://mastodon.social/@{username}",
        "fields": [
            {
                "name": "Website",
                "value": "https://example.org",
                "verified_at": "2024-01-01T00:00:00.000Z",
            },
            {
                "name": "GitHub",
                "value": "https://github.com/testuser",
                "verified_at": None,
            },
        ],
    }


def _mock_gravatar_response(email_hash: str) -> dict:
    return {
        "entry": [
            {
                "id": email_hash,
                "hash": email_hash,
                "preferredUsername": "testuser",
                "displayName": "Test Gravatar User",
                "aboutMe": "Developer and open-source contributor.",
                "urls": [
                    {"value": "https://example.com", "title": "Personal site"},
                ],
                "accounts": [
                    {
                        "domain": "github.com",
                        "display": "testuser",
                        "url": "https://github.com/testuser",
                        "shortname": "github",
                        "verified": True,
                    }
                ],
            }
        ]
    }


def _mock_reddit_response(username: str = "testuser") -> dict:
    return {
        "kind": "t2",
        "data": {
            "name": f"t2_{username}",
            "id": "abc123",
            "total_karma": 1234,
            "created_utc": 1609459200.0,
            "subreddit": {
                "public_description": "Redditor. Check my stuff at https://example.com",
                "subscribers": 5,
            },
        },
    }


# ---------------------------------------------------------------------------
# GitHubExtractor
# ---------------------------------------------------------------------------


class TestGitHubExtractor:
    @pytest.mark.asyncio
    async def test_returns_profile_data_on_200(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/users/testuser").mock(
                return_value=httpx.Response(200, json=_mock_github_response())
            )
            extractor = GitHubExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert isinstance(result, ProfileData)
        assert result.display_name == "Test User"
        assert result.location == "Testville"
        assert result.bio is not None

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/users/nobody").mock(
                return_value=httpx.Response(404)
            )
            extractor = GitHubExtractor()
            result = await extractor.extract("nobody")
            await extractor.close()

        assert result is None

    @pytest.mark.asyncio
    async def test_twitter_field_becomes_linked_account(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/users/testuser").mock(
                return_value=httpx.Response(200, json=_mock_github_response())
            )
            extractor = GitHubExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        twitter_links = [a for a in result.linked_accounts if a.platform == "twitter"]
        assert len(twitter_links) == 1
        assert twitter_links[0].evidence_type == "api_field"
        assert twitter_links[0].confidence >= 0.8

    @pytest.mark.asyncio
    async def test_blog_field_becomes_linked_account(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/users/testuser").mock(
                return_value=httpx.Response(200, json=_mock_github_response())
            )
            extractor = GitHubExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        blog_links = [
            a for a in result.linked_accounts if "blog.example.com" in a.profile_url
        ]
        assert len(blog_links) == 1

    @pytest.mark.asyncio
    async def test_email_field_captured(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/users/testuser").mock(
                return_value=httpx.Response(200, json=_mock_github_response())
            )
            extractor = GitHubExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        assert "testuser@example.org" in result.emails

    @pytest.mark.asyncio
    async def test_raises_module_api_error_on_500(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/users/testuser").mock(
                return_value=httpx.Response(500)
            )
            extractor = GitHubExtractor()
            with pytest.raises(ModuleAPIError):
                await extractor.extract("testuser")
            await extractor.close()

    @pytest.mark.asyncio
    async def test_raises_module_timeout_error_on_timeout(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/users/testuser").mock(
                side_effect=httpx.TimeoutException("timeout")
            )
            extractor = GitHubExtractor()
            with pytest.raises(ModuleTimeoutError):
                await extractor.extract("testuser")
            await extractor.close()

    @pytest.mark.asyncio
    async def test_raw_data_preserved(self) -> None:
        raw = _mock_github_response()
        with respx.mock:
            respx.get("https://api.github.com/users/testuser").mock(
                return_value=httpx.Response(200, json=raw)
            )
            extractor = GitHubExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        assert result.raw_data["login"] == "testuser"


# ---------------------------------------------------------------------------
# MastodonExtractor
# ---------------------------------------------------------------------------


class TestMastodonExtractor:
    @pytest.mark.asyncio
    async def test_returns_profile_on_first_instance_hit(self) -> None:
        instance = "mastodon.social"
        with respx.mock:
            respx.get(f"https://{instance}/api/v1/accounts/lookup").mock(
                return_value=httpx.Response(200, json=_mock_mastodon_response())
            )
            extractor = MastodonExtractor(instances=[instance])
            result = await extractor.extract("testuser")
            await extractor.close()

        assert isinstance(result, ProfileData)
        assert result.display_name == "Test Mastodon User"

    @pytest.mark.asyncio
    async def test_falls_back_to_second_instance_on_404(self) -> None:
        with respx.mock:
            respx.get("https://mastodon.social/api/v1/accounts/lookup").mock(
                return_value=httpx.Response(404)
            )
            respx.get("https://fosstodon.org/api/v1/accounts/lookup").mock(
                return_value=httpx.Response(200, json=_mock_mastodon_response())
            )
            extractor = MastodonExtractor(
                instances=["mastodon.social", "fosstodon.org"]
            )
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        assert "fosstodon.org" in result.identifier

    @pytest.mark.asyncio
    async def test_returns_none_when_all_instances_miss(self) -> None:
        with respx.mock:
            respx.get("https://mastodon.social/api/v1/accounts/lookup").mock(
                return_value=httpx.Response(404)
            )
            extractor = MastodonExtractor(instances=["mastodon.social"])
            result = await extractor.extract("nobody")
            await extractor.close()

        assert result is None

    @pytest.mark.asyncio
    async def test_verified_link_has_confidence_1(self) -> None:
        with respx.mock:
            respx.get("https://mastodon.social/api/v1/accounts/lookup").mock(
                return_value=httpx.Response(200, json=_mock_mastodon_response())
            )
            extractor = MastodonExtractor(instances=["mastodon.social"])
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        verified = [
            a for a in result.linked_accounts if a.evidence_type == "verified_link"
        ]
        assert len(verified) >= 1
        assert all(a.confidence == 1.0 for a in verified)

    @pytest.mark.asyncio
    async def test_unverified_field_has_lower_confidence(self) -> None:
        with respx.mock:
            respx.get("https://mastodon.social/api/v1/accounts/lookup").mock(
                return_value=httpx.Response(200, json=_mock_mastodon_response())
            )
            extractor = MastodonExtractor(instances=["mastodon.social"])
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        api_fields = [
            a for a in result.linked_accounts if a.evidence_type == "api_field"
        ]
        assert all(a.confidence < 1.0 for a in api_fields)


# ---------------------------------------------------------------------------
# KeybaseExtractor
# ---------------------------------------------------------------------------


class TestKeybaseExtractor:
    @pytest.mark.asyncio
    async def test_returns_profile_with_proofs(self) -> None:
        with respx.mock:
            respx.get("https://keybase.io/_/api/1.0/user/lookup.json").mock(
                return_value=httpx.Response(200, json=_mock_keybase_response())
            )
            extractor = KeybaseExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert isinstance(result, ProfileData)
        assert result.platform == "Keybase"

    @pytest.mark.asyncio
    async def test_all_proofs_have_confidence_1(self) -> None:
        with respx.mock:
            respx.get("https://keybase.io/_/api/1.0/user/lookup.json").mock(
                return_value=httpx.Response(200, json=_mock_keybase_response())
            )
            extractor = KeybaseExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        assert all(a.confidence == 1.0 for a in result.linked_accounts)

    @pytest.mark.asyncio
    async def test_all_proofs_have_keybase_proof_evidence_type(self) -> None:
        with respx.mock:
            respx.get("https://keybase.io/_/api/1.0/user/lookup.json").mock(
                return_value=httpx.Response(200, json=_mock_keybase_response())
            )
            extractor = KeybaseExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        assert all(a.evidence_type == "keybase_proof" for a in result.linked_accounts)

    @pytest.mark.asyncio
    async def test_github_proof_maps_platform(self) -> None:
        with respx.mock:
            respx.get("https://keybase.io/_/api/1.0/user/lookup.json").mock(
                return_value=httpx.Response(200, json=_mock_keybase_response())
            )
            extractor = KeybaseExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        github_links = [a for a in result.linked_accounts if a.platform == "github"]
        assert len(github_links) == 1

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_them(self) -> None:
        with respx.mock:
            respx.get("https://keybase.io/_/api/1.0/user/lookup.json").mock(
                return_value=httpx.Response(
                    200, json={"status": {"code": 0}, "them": []}
                )
            )
            extractor = KeybaseExtractor()
            result = await extractor.extract("nobody")
            await extractor.close()

        assert result is None


# ---------------------------------------------------------------------------
# GitLabExtractor
# ---------------------------------------------------------------------------


class TestGitLabExtractor:
    @pytest.mark.asyncio
    async def test_returns_profile_on_200(self) -> None:
        with respx.mock:
            respx.get("https://gitlab.com/api/v4/users").mock(
                return_value=httpx.Response(200, json=_mock_gitlab_response())
            )
            extractor = GitLabExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert isinstance(result, ProfileData)
        assert result.display_name == "Test GitLab User"

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_list(self) -> None:
        with respx.mock:
            respx.get("https://gitlab.com/api/v4/users").mock(
                return_value=httpx.Response(200, json=[])
            )
            extractor = GitLabExtractor()
            result = await extractor.extract("nobody")
            await extractor.close()

        assert result is None

    @pytest.mark.asyncio
    async def test_twitter_field_extracted(self) -> None:
        with respx.mock:
            respx.get("https://gitlab.com/api/v4/users").mock(
                return_value=httpx.Response(200, json=_mock_gitlab_response())
            )
            extractor = GitLabExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        twitter_links = [a for a in result.linked_accounts if a.platform == "twitter"]
        assert len(twitter_links) == 1

    @pytest.mark.asyncio
    async def test_linkedin_field_extracted(self) -> None:
        with respx.mock:
            respx.get("https://gitlab.com/api/v4/users").mock(
                return_value=httpx.Response(200, json=_mock_gitlab_response())
            )
            extractor = GitLabExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        linkedin_links = [a for a in result.linked_accounts if a.platform == "linkedin"]
        assert len(linkedin_links) == 1


# ---------------------------------------------------------------------------
# GravatarExtractor
# ---------------------------------------------------------------------------


class TestGravatarExtractor:
    @pytest.mark.asyncio
    async def test_constructs_correct_md5_url(self) -> None:
        email = "testuser@example.com"
        expected_hash = _hash_email(email)
        with respx.mock:
            route = respx.get(f"https://www.gravatar.com/{expected_hash}.json").mock(
                return_value=httpx.Response(
                    200, json=_mock_gravatar_response(expected_hash)
                )
            )
            extractor = GravatarExtractor()
            result = await extractor.extract(email)
            await extractor.close()

        assert route.called
        assert result is not None

    @pytest.mark.asyncio
    async def test_raw_email_not_in_identifier(self) -> None:
        """The identifier field must be the MD5 hash, not the raw email."""
        email = "testuser@example.com"
        email_hash = _hash_email(email)
        with respx.mock:
            respx.get(f"https://www.gravatar.com/{email_hash}.json").mock(
                return_value=httpx.Response(
                    200, json=_mock_gravatar_response(email_hash)
                )
            )
            extractor = GravatarExtractor()
            result = await extractor.extract(email)
            await extractor.close()

        assert result is not None
        assert result.identifier == email_hash
        assert email not in result.identifier

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self) -> None:
        email = "nobody@example.com"
        email_hash = _hash_email(email)
        with respx.mock:
            respx.get(f"https://www.gravatar.com/{email_hash}.json").mock(
                return_value=httpx.Response(404)
            )
            extractor = GravatarExtractor()
            result = await extractor.extract(email)
            await extractor.close()

        assert result is None

    @pytest.mark.asyncio
    async def test_display_name_extracted(self) -> None:
        email = "testuser@example.com"
        email_hash = _hash_email(email)
        with respx.mock:
            respx.get(f"https://www.gravatar.com/{email_hash}.json").mock(
                return_value=httpx.Response(
                    200, json=_mock_gravatar_response(email_hash)
                )
            )
            extractor = GravatarExtractor()
            result = await extractor.extract(email)
            await extractor.close()

        assert result is not None
        assert result.display_name == "Test Gravatar User"

    @pytest.mark.asyncio
    async def test_urls_array_becomes_linked_accounts(self) -> None:
        email = "testuser@example.com"
        email_hash = _hash_email(email)
        with respx.mock:
            respx.get(f"https://www.gravatar.com/{email_hash}.json").mock(
                return_value=httpx.Response(
                    200, json=_mock_gravatar_response(email_hash)
                )
            )
            extractor = GravatarExtractor()
            result = await extractor.extract(email)
            await extractor.close()

        assert result is not None
        assert len(result.linked_accounts) >= 1
        assert any("example.com" in a.profile_url for a in result.linked_accounts)


# ---------------------------------------------------------------------------
# RedditExtractor
# ---------------------------------------------------------------------------


class TestRedditExtractor:
    @pytest.mark.asyncio
    async def test_returns_profile_on_200(self) -> None:
        with respx.mock:
            respx.get("https://www.reddit.com/user/testuser/about.json").mock(
                return_value=httpx.Response(200, json=_mock_reddit_response())
            )
            extractor = RedditExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert isinstance(result, ProfileData)
        assert result.platform == "Reddit"

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self) -> None:
        with respx.mock:
            respx.get("https://www.reddit.com/user/nobody/about.json").mock(
                return_value=httpx.Response(404)
            )
            extractor = RedditExtractor()
            result = await extractor.extract("nobody")
            await extractor.close()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_403_suspended(self) -> None:
        with respx.mock:
            respx.get("https://www.reddit.com/user/suspended/about.json").mock(
                return_value=httpx.Response(403)
            )
            extractor = RedditExtractor()
            result = await extractor.extract("suspended")
            await extractor.close()

        assert result is None

    @pytest.mark.asyncio
    async def test_bio_links_extracted_from_public_description(self) -> None:
        with respx.mock:
            respx.get("https://www.reddit.com/user/testuser/about.json").mock(
                return_value=httpx.Response(200, json=_mock_reddit_response())
            )
            extractor = RedditExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        url_links = [
            a for a in result.linked_accounts if "example.com" in a.profile_url
        ]
        assert len(url_links) >= 1

    @pytest.mark.asyncio
    async def test_uses_piea_user_agent_not_default_httpx(self) -> None:
        """Reddit returns 403 for the default httpx User-Agent."""
        extractor = RedditExtractor()
        ua = extractor._client.headers.get("user-agent", "")
        assert "PIEA" in ua
        await extractor.close()

    @pytest.mark.asyncio
    async def test_raw_data_preserved(self) -> None:
        raw = _mock_reddit_response()
        with respx.mock:
            respx.get("https://www.reddit.com/user/testuser/about.json").mock(
                return_value=httpx.Response(200, json=raw)
            )
            extractor = RedditExtractor()
            result = await extractor.extract("testuser")
            await extractor.close()

        assert result is not None
        assert "data" in result.raw_data
