# Golden renders

`*.json` are report payloads — the same shape `report_content.py` produces.
`*.page-N.png` are downsampled fingerprints of each rendered PDF page, not
full-resolution screenshots: comparing raw pixels would fail on glyph
antialiasing alone. `_environment.png` is the canary that tells the tests
whether this machine renders text the way these references were made.

Changed the print template on purpose? Regenerate and **look at the result**
before committing it:

    REGENERATE_GOLDEN=1 pytest tests/test_golden_documents.py
    git diff --stat tests/golden

A reference regenerated without anyone looking is worse than no reference —
it turns a caught regression into a committed one.
