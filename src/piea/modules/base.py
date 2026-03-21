"""Base module interface for all OSINT data source modules.

Every module (HIBP, username enumeration, graph crawler, etc.) must
subclass BaseModule and implement the execute() method. This gives the
scan orchestrator a uniform interface to invoke modules concurrently.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    """Finding severity levels, ordered from most to least severe."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ---------------------------------------------------------------------------
# Module result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModuleFinding:
    """A single finding produced by a module.

    Attributes:
        finding_type: Machine-readable finding type (e.g. "breach_exposure").
        severity: How severe this finding is.
        category: Broad category (e.g. "breach", "username", "domain").
        title: Human-readable one-line summary.
        description: Detailed explanation of the finding.
        platform: Source platform name, if applicable.
        evidence: Structured evidence supporting the finding.
        remediation_action: What the user should do about it.
        remediation_effort: Estimated effort: "easy", "moderate", "hard".
        remediation_url: Optional URL with remediation steps.
        weight: Suggested scoring weight (0.0–1.0). The risk scorer may
            override this based on its own taxonomy.
    """

    finding_type: str
    severity: Severity
    category: str
    title: str
    description: str
    platform: str | None
    evidence: dict[str, object]
    remediation_action: str
    remediation_effort: str
    remediation_url: str | None = None
    weight: float = 0.5


@dataclass(frozen=True, slots=True)
class ModuleResult:
    """The complete output of a module execution.

    Attributes:
        module_name: Identifier for the module that produced this result.
        success: Whether the module completed without fatal errors.
        findings: List of findings discovered by the module.
        errors: List of non-fatal error messages encountered during execution.
        cached: Whether the result was served from cache.
        metadata: Additional module-specific metadata.
    """

    module_name: str
    success: bool
    findings: list[ModuleFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    cached: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Module errors
# ---------------------------------------------------------------------------


class ModuleError(Exception):
    """Base exception for all module-level errors."""

    def __init__(self, module_name: str, message: str) -> None:
        self.module_name = module_name
        super().__init__(f"[{module_name}] {message}")


class ModuleAPIError(ModuleError):
    """Raised when an external API returns an unexpected error."""

    def __init__(
        self, module_name: str, status_code: int, detail: str = ""
    ) -> None:
        self.status_code = status_code
        msg = f"API returned HTTP {status_code}"
        if detail:
            msg += f": {detail}"
        super().__init__(module_name, msg)


class ModuleTimeoutError(ModuleError):
    """Raised when an external API call exceeds its timeout."""


class RateLimitExceededError(ModuleError):
    """Raised when the module hits an external rate limit."""

    def __init__(self, module_name: str, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after is not None:
            msg += f" (retry after {retry_after:.1f}s)"
        super().__init__(module_name, msg)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScanInputs:
    """Inputs provided to every module for a scan.

    Not all modules use every field — a module should read only what it needs.
    """

    email: str | None = None
    username: str | None = None
    full_name: str | None = None


class BaseModule(abc.ABC):
    """Abstract base class for OSINT data source modules.

    Subclasses must implement:
        name: A unique module identifier string.
        execute(): The main scanning logic.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique identifier for this module (e.g. 'hibp', 'username_enum')."""

    @abc.abstractmethod
    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Run the module's scan logic against the given inputs.

        Args:
            inputs: Scan seed data (email, username, full name).

        Returns:
            A ModuleResult with any findings and/or errors.

        This method must NOT raise exceptions for recoverable errors.
        Instead, return a ModuleResult with success=False and the error
        in the errors list. Only raise for truly unrecoverable situations.
        """

    async def close(self) -> None:
        """Clean up resources (HTTP clients, connections, etc.).

        Override this if the module holds long-lived resources.
        """
