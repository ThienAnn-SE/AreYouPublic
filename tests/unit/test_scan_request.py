"""Unit tests for ScanRequest validation."""

import pytest
from pydantic import ValidationError

from piea.api.schemas.scan_request import ConsentAttestation, ScanRequest
from piea.core.consent import CURRENT_CONSENT_TEXT_VERSION


def _consent() -> ConsentAttestation:
    """Helper to build a valid consent block."""
    return ConsentAttestation(
        attestation_type="self",
        operator_name="Alice",
        consent_text_version=CURRENT_CONSENT_TEXT_VERSION,
    )


class TestScanRequest:
    """Tests for ScanRequest input validation."""

    def test_username_only_is_valid(self):
        req = ScanRequest(target_username="alice", consent=_consent())
        assert req.target_username == "alice"

    def test_email_only_is_valid(self):
        req = ScanRequest(target_email="alice@example.com", consent=_consent())
        assert req.target_email == "alice@example.com"

    def test_name_only_is_valid(self):
        req = ScanRequest(target_name="Alice Tester", consent=_consent())
        assert req.target_name == "Alice Tester"

    def test_all_targets_valid(self):
        req = ScanRequest(
            target_username="alice",
            target_email="alice@example.com",
            target_name="Alice Tester",
            consent=_consent(),
        )
        assert req.target_username == "alice"

    def test_no_targets_rejected(self):
        with pytest.raises(ValidationError, match="At least one target"):
            ScanRequest(consent=_consent())

    def test_domain_alone_not_sufficient(self):
        """target_domain is supplementary — not a scan seed on its own."""
        with pytest.raises(ValidationError, match="At least one target"):
            ScanRequest(target_domain="example.com", consent=_consent())

    def test_max_depth_bounds(self):
        with pytest.raises(ValidationError, match="max_depth"):
            ScanRequest(target_username="alice", max_depth=0, consent=_consent())

        with pytest.raises(ValidationError, match="max_depth"):
            ScanRequest(target_username="alice", max_depth=4, consent=_consent())

    def test_username_whitespace_rejected(self):
        with pytest.raises(ValidationError, match="whitespace"):
            ScanRequest(target_username="  alice  ", consent=_consent())
