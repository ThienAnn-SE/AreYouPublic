"""Unit tests for the ConsentService."""

import pytest
from pydantic import ValidationError

from piea.core.consent import (
    CURRENT_CONSENT_TEXT_VERSION,
    VALID_ATTESTATION_TYPES,
    ConsentInput,
    ConsentRequiredError,
    ConsentService,
    ConsentValidationError,
)


# ---------------------------------------------------------------------------
# ConsentInput validation
# ---------------------------------------------------------------------------


class TestConsentInput:
    """Tests for the Pydantic input model."""

    def test_valid_self_attestation(self):
        data = ConsentInput(
            attestation_type="self",
            operator_name="Alice Tester",
            operator_ip="192.168.1.1",
            consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
        )
        assert data.attestation_type == "self"

    def test_valid_authorized_third_party(self):
        data = ConsentInput(
            attestation_type="authorized_third_party",
            operator_name="Bob Pentester",
            operator_ip="10.0.0.1",
            consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
        )
        assert data.attestation_type == "authorized_third_party"

    def test_rejects_invalid_attestation_type(self):
        with pytest.raises(ValidationError, match="Must be one of"):
            ConsentInput(
                attestation_type="unauthorized",
                operator_name="Eve",
                operator_ip="1.2.3.4",
                consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
            )

    def test_rejects_invalid_ip(self):
        with pytest.raises(ValidationError, match="not a valid IP"):
            ConsentInput(
                attestation_type="self",
                operator_name="Alice",
                operator_ip="not-an-ip",
                consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
            )

    def test_accepts_ipv6(self):
        data = ConsentInput(
            attestation_type="self",
            operator_name="Alice",
            operator_ip="::1",
            consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
        )
        assert data.operator_ip == "::1"


# ---------------------------------------------------------------------------
# ConsentService.create
# ---------------------------------------------------------------------------


class TestConsentServiceCreate:
    """Tests for consent record creation."""

    async def test_create_returns_record_with_id(self, consent_service):
        data = ConsentInput(
            attestation_type="self",
            operator_name="Alice Tester",
            operator_ip="192.168.1.1",
            consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
        )
        record = await consent_service.create(data)
        assert record.id is not None
        assert record.attestation_type == "self"
        assert record.operator_name == "Alice Tester"

    async def test_create_rejects_blank_name(self, consent_service):
        data = ConsentInput(
            attestation_type="self",
            operator_name="   ",
            operator_ip="1.2.3.4",
            consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
        )
        with pytest.raises(ConsentValidationError, match="operator_name"):
            await consent_service.create(data)

    async def test_create_rejects_short_name(self, consent_service):
        data = ConsentInput(
            attestation_type="self",
            operator_name="A",
            operator_ip="1.2.3.4",
            consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
        )
        with pytest.raises(ConsentValidationError, match="at least 2"):
            await consent_service.create(data)

    async def test_create_rejects_wrong_consent_version(self, consent_service):
        data = ConsentInput(
            attestation_type="self",
            operator_name="Alice",
            operator_ip="1.2.3.4",
            consent_text_version="0.1",
        )
        with pytest.raises(ConsentValidationError, match="consent_text_version"):
            await consent_service.create(data)


# ---------------------------------------------------------------------------
# ConsentService.assert_valid_for_scan
# ---------------------------------------------------------------------------


class TestConsentServiceAssertValid:
    """Tests for the scan-time consent gate."""

    async def test_valid_record_passes(self, consent_service):
        data = ConsentInput(
            attestation_type="self",
            operator_name="Alice",
            operator_ip="1.2.3.4",
            consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
        )
        record = await consent_service.create(data)
        result = await consent_service.assert_valid_for_scan(record.id)
        assert result.id == record.id

    async def test_missing_record_raises_consent_required(self, consent_service):
        from uuid import uuid4

        with pytest.raises(ConsentRequiredError):
            await consent_service.assert_valid_for_scan(uuid4())

    async def test_stale_version_rejected(self, consent_service, monkeypatch):
        """Simulate a consent text version bump after the record was created."""
        data = ConsentInput(
            attestation_type="self",
            operator_name="Alice",
            operator_ip="1.2.3.4",
            consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
        )
        record = await consent_service.create(data)

        # Simulate bumping the consent text version after record creation.
        import piea.core.consent as consent_mod
        monkeypatch.setattr(consent_mod, "CURRENT_CONSENT_TEXT_VERSION", "2.0")

        with pytest.raises(ConsentValidationError, match="version"):
            await consent_service.assert_valid_for_scan(record.id)
