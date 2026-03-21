"""Username enumeration sub-package for PIEA.

Checks a target username across 50+ public platforms concurrently.
The platform registry lives in config/platforms.json and can be
extended without any code changes (NFR-SC2).

Public interface:
    UsernameModule — BaseModule implementation (main entry point)
    PlatformCheckResult — Result type for a single platform check
    CheckStatus — Enum: FOUND, NOT_FOUND, ERROR, RATE_LIMITED
"""

from piea.modules.username.checker import CheckStatus, PlatformCheckResult
from piea.modules.username.module import UsernameModule

__all__ = ["CheckStatus", "PlatformCheckResult", "UsernameModule"]
