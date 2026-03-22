"""OSINT data source modules for PIEA.

Each module implements BaseModule and is responsible for querying a single
external data source, parsing responses, and returning structured findings.
"""

from piea.modules.domain_intel import DomainIntelModule
from piea.modules.hunter import HunterModule
from piea.modules.paste_monitor import PasteMonitor
from piea.modules.search import (
    DisambiguationResult,
    EntityResolver,
    SearchModule,
)

__all__ = [
    "DisambiguationResult",
    "DomainIntelModule",
    "EntityResolver",
    "HunterModule",
    "PasteMonitor",
    "SearchModule",
]
