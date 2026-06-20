"""Vendored third-party code, kept verbatim and isolated from our own modules.

`read_mist_models.py` is MIST's *own* `.track.eep` parser (spec §6: "reuse
MIST's own `read_mist_models.py` parser instead of reinventing the format").
It is committed here rather than fetched at build time because, unlike the data
*location* (which moved hosts + versions — see `fetch_mist.py`), the parser API
is stable, and committing it keeps the test suite runnable offline.

Source: https://github.com/jieunchoi/MIST_codes — scripts/read_mist_models.py
Do not edit; replace wholesale if upstream changes.
"""
