"""errors — typed exceptions for GENUINE faults (not for verdicts).

Design note (answering the review honestly): a *verdict* like INSIDE_THE_BOX or MUST_BE_AUDITED is
legitimate DATA — the engine returns it the way a chess engine returns 'illegal move', not as a fault.
So we do NOT raise on verdicts. We DO raise on real programming errors: an unknown pack, a malformed
spec, an assumption that does not exist in the given pack.

Each exception subclasses the stdlib type a caller would historically have caught (KeyError/ValueError),
so adding these is fully backward-compatible: existing `except KeyError` / `except ValueError` keep working.
"""
from __future__ import annotations


class OUTLIER_MCBError(Exception):
    """Base class for every OUTLIER_MCB fault. Catch this to catch them all."""


class PackNotFoundError(OUTLIER_MCBError, KeyError):
    """A DomainPack was requested by a name that is not registered."""


class InvalidPackError(OUTLIER_MCBError, ValueError):
    """A DomainPack (built or elicited) failed schema validation."""


class AssumptionNotFoundError(OUTLIER_MCBError, KeyError):
    """A named assumption does not exist in the given pack."""
