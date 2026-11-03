"""ExhibitIQ ETL package (owner: data).

Responsibility: deterministic, reproducible processing of raw evidence into
data packages: cleaning, normalization, company de-duplication, quality and
completeness checks, package writing, and the single data-package validator
(which loads schemas from the local ``schemas/v1/`` directory).

Not in this package: crawling (see ``crawler``), and AI inference. Inferred
analysis must never be written back as sourced fact.

Skeleton only (P1-DATA-02). Readers/writers, the validator and run-log
formats arrive in later Issues. The data contract lives only in ``schemas/``;
never define fields here.
"""
