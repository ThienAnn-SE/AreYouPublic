"""Pydantic models for scan creation requests."""

from pydantic import BaseModel, EmailStr, field_validator, model_validator


class ConsentAttestation(BaseModel):
    """Inline consent data submitted alongside the scan request.

    The frontend collects this from the operator before enabling the submit button.
    """

    attestation_type: str  # "self" | "authorized_third_party"
    operator_name: str
    consent_text_version: str


class ScanRequest(BaseModel):
    """Input model for POST /api/v1/scans.

    At least one of (target_name, target_email, target_username) must be
    provided — the cross-field validator below enforces this.

    Fields:
        target_username: Primary seed for username enumeration and graph crawling.
        target_email:    Used for breach lookup (HIBP) and Gravatar.
        target_name:     Used for search module entity resolution.
        target_domain:   Optional domain for WHOIS/DNS intelligence.
        max_depth:       Override graph crawl depth (1–3); defaults to system setting.
        modules:         Restrict which modules run; empty list means all modules.
        consent:         Operator consent attestation (collected by the frontend).
    """

    target_username: str | None = None
    target_email: EmailStr | None = None
    target_name: str | None = None
    target_domain: str | None = None

    max_depth: int = 3
    modules: list[str] = []

    consent: ConsentAttestation

    @field_validator("max_depth")
    @classmethod
    def depth_in_range(cls, v: int) -> int:
        if not 1 <= v <= 3:
            raise ValueError("max_depth must be between 1 and 3")
        return v

    @field_validator("target_username")
    @classmethod
    def username_no_whitespace(cls, v: str | None) -> str | None:
        if v is not None and v != v.strip():
            raise ValueError(
                "target_username must not have leading or trailing whitespace"
            )
        return v

    @model_validator(mode="after")
    def at_least_one_target(self) -> "ScanRequest":
        """Reject requests with no scan targets at all.

        Any single target field is accepted — even target_name alone, which
        only enables the search module. A limited scan is still a valid scan;
        an empty scan is not.
        """
        if not any([self.target_username, self.target_email, self.target_name]):
            raise ValueError(
                "At least one target field must be provided "
                "(target_username, target_email, or target_name)."
            )
        return self
