# Evidence Provenance & Citation Integrity

Every source used in a research claim should have a stable `source_id`, source type, title, authors/organization when known, year/date, DOI or URL, retrieval date, access status, retrieval method, exact locator, rights/license status and limitations. Local source snapshots may include SHA-256 only when retention is lawful and appropriate.

## Access classes are not interchangeable

- `METADATA_ONLY`: bibliographic/item metadata only; no content claim.
- `ABSTRACT_ONLY`: abstract-level claims only; never infer unobserved methods, instruments, results or chapters.
- `PARTIAL_TEXT_REVIEWED`: cite only the exact reviewed sections and locators.
- `FULL_TEXT_REVIEWED`: use only after the full text was actually and lawfully reviewed.
- `NOT_ACCESSIBLE` / `RESTRICTED_UNAVAILABLE`: preserve missingness; do not bypass controls or substitute another work.

A claim-to-evidence link records whether the source supports, contradicts or contextualizes the claim, plus an exact locator, support level, review status and limitations. A reference appearing in a bibliography does not automatically support a nearby claim.

The validators check structure, uniqueness, date/URL shape, locators and referential integrity. They do not prove a source exists, a DOI resolves, a source is authoritative, a quotation is accurate or that the source actually supports the claim. Those require retrieval and claim-level review.

Never invent a DOI, URL, page, quotation, author, year, observation, approval, interview, statistic or source. Do not represent an abstract-only review as full-text review.

## Access-depth rules in the first engine release

- `METADATA_ONLY` may support bibliographic facts only (for example, title/author/year), with a metadata locator. It cannot support a substantive claim about a study's theory, method, sample, findings or conclusions.
- `ABSTRACT_ONLY` may support claims explicitly present in the abstract only. It cannot be used to infer unobserved chapter-level methods, instruments, analyses or results.
- `PARTIAL_TEXT_REVIEWED` supports claims only from the exact reviewed passage/section/table/figure and its recorded locator.
- `FULL_TEXT_REVIEWED` does not itself prove a claim is true; each claim still needs a precise locator and review.
- `NOT_ACCESSIBLE` and `RESTRICTED_UNAVAILABLE` are never content evidence. Keep them as missingness, not as inferred values.

The current validator enforces scope for metadata-only and abstract-only records, but it does not fetch the URL or inspect whether the cited passage actually supports the claim. Human review remains mandatory.
