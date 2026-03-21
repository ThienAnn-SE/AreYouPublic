"""Consent gate service for PIEA.

This module is the ethical enforcer: no scan may begin without a valid
ConsentRecord. The ConsentService creates, validates, and retrieves
consent records. It is the only code path that produces a consent_record_id
that the Scan table requires as a non-nullable foreign key.

Consent text version history:
  1.0  — 2026-03-21  Initial consent text
"""

from __future__ import annotations

import ipaddress
from uuid import UUID

from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piea.db.models import ConsentRecord

# Bump this constant when the legal consent text changes.
# Old records remain valid for their scans; new scans require re-consent.
CURRENT_CONSENT_TEXT_VERSION = "1.0"

# Valid attestation types that the operator may choose from.
VALID_ATTESTATION_TYPES = frozenset({"self", "authorized_third_party"})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConsentError(Exception):
    """Base class for consent-related errors."""


class ConsentValidationError(ConsentError):
    """Raised when the consent input fails validation."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"Consent validation failed on '{field}': {reason}")


class ConsentRequiredError(ConsentError):
    """Raised when a scan is attempted without a valid consent record."""

    def __init__(self, scan_id: UUID | None = None) -> None:
        msg = "A valid consent record is required before a scan can begin."
        if scan_id:
            msg += f" (scan_id={scan_id})"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class ConsentInput(BaseModel):
    """Data collected from the operator before a scan begins.

    Fields:
        attestation_type: Either "self" (scanning own information) or
            "authorized_third_party" (has documented written authorization).
        operator_name: Full name of the person authorizing the scan.
        operator_ip: IPv4 or IPv6 address of the requesting client.
        consent_text_version: Version of the consent text the operator agreed to.
            Must match CURRENT_CONSENT_TEXT_VERSION.
    """

    attestation_type: str
    operator_name: str
    operator_ip: str
    consent_text_version: str

    @field_validator("attestation_type")
    @classmethod
    def attestation_type_must_be_valid(cls, v: str) -> str:
        if v not in VALID_ATTESTATION_TYPES:
            raise ValueError(f"Must be one of: {sorted(VALID_ATTESTATION_TYPES)}")
        return v

    @field_validator("operator_ip")
    @classmethod
    def operator_ip_must_be_valid(cls, v: str) -> str:
        try:
            ipaddress.ip_address(v)
        except ValueError:
            raise ValueError(f"'{v}' is not a valid IP address") from None
        return v


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ConsentService:
    """Manages consent record creation and validation.

    All public methods are async because they perform database I/O.

    Usage:
        service = ConsentService(db_session)
        record = await service.create(consent_input)
        # Pass record.id to the scan creation logic.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, data: ConsentInput) -> ConsentRecord:
        """Validate the consent input and persist a new ConsentRecord.

        Args:
            data: Validated ConsentInput from the operator.

        Returns:
            The newly created and persisted ConsentRecord.

        Raises:
            ConsentValidationError: If any field fails business-rule validation.
        """
        self._validate(data)

        record = ConsentRecord(
            attestation_type=data.attestation_type,
            operator_name=data.operator_name,
            operator_ip=data.operator_ip,
            consent_text_version=data.consent_text_version,
        )
        self._db.add(record)
        await self._db.flush()  # assigns the UUID without committing the transaction
        return record

    async def get_by_id(self, consent_id: UUID) -> ConsentRecord | None:
        """Retrieve a consent record by its primary key.

        Args:
            consent_id: UUID of the consent record to look up.

        Returns:
            The ConsentRecord, or None if not found.
        """
        result = await self._db.execute(
            select(ConsentRecord).where(ConsentRecord.id == consent_id)
        )
        return result.scalar_one_or_none()

    async def assert_valid_for_scan(self, consent_id: UUID) -> ConsentRecord:
        """Assert that a consent record exists and is still valid for use.

        Call this from the scan creation path to enforce the gate.

        Args:
            consent_id: UUID supplied by the caller claiming to have consent.

        Returns:
            The ConsentRecord (passed through for use in building the Scan).

        Raises:
            ConsentRequiredError: If the record does not exist.
            ConsentValidationError: If the record's text version is outdated.
        """
        record = await self.get_by_id(consent_id)
        if record is None:
            raise ConsentRequiredError()

        # Strict version enforcement: the operator must have agreed to the
        # exact current consent text. Any version mismatch — even a minor
        # wording fix — requires re-consent. This maximises legal clarity
        # at the cost of some UX friction on text updates.
        if record.consent_text_version != CURRENT_CONSENT_TEXT_VERSION:
            raise ConsentValidationError(
                "consent_text_version",
                f"Consent record was created under version "
                f"'{record.consent_text_version}', but the current consent "
                f"text is version '{CURRENT_CONSENT_TEXT_VERSION}'. "
                "The operator must re-submit consent before this scan can proceed.",
            )

        return record

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    def _validate(self, data: ConsentInput) -> None:
        """Apply business-rule validation beyond what Pydantic enforces.

        Raises:
            ConsentValidationError: On the first rule that fails.
        """
        # Rule 1: operator_name must not be blank or whitespace-only
        if not data.operator_name.strip():
            raise ConsentValidationError(
                "operator_name", "Operator name must not be blank."
            )

        # Rule 2: operator_name must meet minimum length to be a real name
        if len(data.operator_name.strip()) < 2:
            raise ConsentValidationError(
                "operator_name",
                "Operator name must be at least 2 characters.",
            )

        # Rule 3: consent text version must match what the system currently shows.
        # We enforce this here (not just in assert_valid_for_scan) so that a
        # client posting an outdated version string at creation time is rejected
        # immediately — they were shown stale consent text.
        if data.consent_text_version != CURRENT_CONSENT_TEXT_VERSION:
            raise ConsentValidationError(
                "consent_text_version",
                f"Expected version '{CURRENT_CONSENT_TEXT_VERSION}', "
                f"got '{data.consent_text_version}'. "
                "Reload the consent form and try again.",
            )
