"""The one condition every data-backed module shares: "the grid isn't here yet."

Deliberately its own tiny stdlib-only module rather than a name on `provider.py`.
The §3 boundary forbids a sibling from importing `provider` at all (enforced in
`tests/test_architecture.py`), so a base class living there could not be
subclassed by the eleven `*DataMissing` exceptions that need it. Keeping it
separate lets the API translate "data absent" to a 503 **once**, in one exception
handler, without any sibling learning that a provider exists.

Nothing here knows about HTTP either — `api/_errors.py` owns that mapping.
"""

from __future__ import annotations


class DataMissing(RuntimeError):
    """A module's backing data (a MIST grid, a baked cube, a MESA run) is absent.

    Subclassed by every sibling's own `*DataMissing` (and by
    `provider.ProviderDataMissing`) so each can still be caught precisely, while
    the API maps the whole family to a single actionable 503. Stays a
    `RuntimeError` so existing `except RuntimeError` call sites are unaffected.

    The message is the operator-facing hint — say how to fetch the data.
    """
