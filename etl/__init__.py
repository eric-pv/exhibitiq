"""ExhibitIQ ETL package (owner: data).

Responsibility: deterministic, reproducible processing of raw evidence into
data packages: cleaning, normalization, company de-duplication, quality and
completeness checks, package writing, and the single data-package validator
(which loads schemas from the local ``schemas/v1/`` directory).

Not in this package: crawling (see ``crawler``), and AI inference. Inferred
analysis must never be written back as sourced fact.

Contents: ``jsonl`` / ``hashing`` / ``package`` read and write data packages
byte-reproducibly (D1-04). The single data-package validator (D1-05) is not
here yet. The data contract lives only in ``schemas/``; never define fields
here.
"""
