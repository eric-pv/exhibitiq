"""ExhibitIQ crawler package (owner: data).

Responsibility: acquire source material (HTML, PDF, CSV, Excel, manual entry)
and preserve it as immutable raw evidence with provenance: source ID,
retrieval time and content hash.

Not in this package: cleaning, de-duplication and packaging (see ``etl``),
and any AI analysis (owned by ``skills/exhibitiq/``).

Skeleton only (P1-DATA-02). Per-exhibition extractors and the source
registration mechanism are Phase 2 work. The data contract lives only in
``schemas/``; never define fields here.
"""
