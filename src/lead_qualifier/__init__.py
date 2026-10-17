"""Inbound lead qualification: enrich, score, draft, and log to a local CRM."""

from lead_qualifier.models import InboundLead, Qualification

__version__ = "0.1.0"
__all__ = ["InboundLead", "Qualification", "__version__"]
