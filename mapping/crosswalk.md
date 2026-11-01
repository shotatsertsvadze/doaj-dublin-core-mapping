# Crosswalk: DOAJ CSV to DCMI Metadata Terms

The full field-level specification (transformation rule, cardinality,
missing-value behaviour, validation rule, semantic limitations, origin) is in
[`crosswalk.csv`](crosswalk.csv). `scripts/validate.py` checks the JSON-LD
export against that file. This page explains the design decisions.

Reference: [DCMI Metadata Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)
(namespace `http://purl.org/dc/terms/`). Definitions and usage notes below were
checked against that page on 2026-11-01.

## Summary

| Source field | Target | Cardinality | Origin |
| --- | --- | --- | --- |
| URL | `@id` of the article node | 1 | script |
| (constant) | `@type` `dcterms:BibliographicResource` | 1 | script |
| Title | `dcterms:title` | 1 | OpenRefine + script |
| Authors | `dcterms:creator` → `dcterms:Agent` / `foaf:name` | 0..n | OpenRefine + script |
| DOI | `dcterms:identifier` (`https://doi.org/...`) | 0..1 | OpenRefine + script |
| Date | `dcterms:date` (untyped string) | 1 | OpenRefine + script |
| Language_normalized | `dcterms:language` (BCP 47 literal) | 0..1 | Project 01 + OpenRefine + script |
| Subjects | `dcterms:subject` (literals) | 0..n | OpenRefine + script |
| ISSNs | `dcterms:isPartOf` → journal node → `dcterms:identifier` | 0..1 node, 1..n ISSNs | OpenRefine + script |
| Publisher | `dcterms:publisher` → `dcterms:Agent` / `foaf:name` | 0..1 | OpenRefine + script |
| Citation | `dcterms:bibliographicCitation` | 0..1 | script |
| Licence | `dcterms:license` (literal label) | 0..1 | OpenRefine + script |

"OpenRefine" means a column created by the operations in
[`../openrefine/dublin-core-operations.json`](../openrefine/dublin-core-operations.json).
"script" means [`../scripts/to_jsonld.py`](../scripts/to_jsonld.py).

Missing values are never filled: if a source value is blank, the property is
left out of the record.

## Decisions

**Resource identifier.** Each article node uses its DOAJ article URL as `@id`.
It is present and unique in all 1,000 records. The DOI would identify the work
more directly, but 23 records have none, and mixing two identifier types as
`@id` would make the dataset inconsistent. The DOAJ URL identifies the DOAJ
article record, which is a limitation.

**Creators.** `dcterms:creator` has "Range Includes `dcterms:Agent`", so each
name becomes an agent node with `foaf:name`, instead of a string.
Names come from `creators_json` (split in OpenRefine) with original spelling
and order. No ORCID, GND or VIAF identifiers are added because the source has
none. The JSON array keeps the source order, and JSON-LD expansion preserves it,
but RDF treats repeated properties as an unordered set. The order is therefore
also recoverable from the original `Authors` column. An ordered list
(for example `bibo:authorList`) was not added, to keep the model simple.
44 of 4,006 names contain a comma and look inverted ("Surname, Initials");
they were not reordered.

**Subjects.** One `dcterms:subject` literal per value from `subjects_json`.
DCMI recommends a URI from a controlled vocabulary. Some values look like
Library of Congress Classification captions and notations (for example
`Physics`, `QC1-999`), mixed with free keywords. Since the source does not say
which values come from which scheme, no vocabulary is claimed. 41 records repeat
a subject value; the JSON keeps the repetition, RDF conversion collapses it.

**Identifiers.** DCMI says persistent identifiers "should be provided as HTTP
URIs" and gives `dcterms:identifier` the range `rdfs:Literal`. DOIs are therefore
written as string literals in the form `https://doi.org/10....`, built in
OpenRefine. 23 records have no DOI and get no identifier.

**Dates.** All 1,000 values have the form `01/MM/2015`, with the first component
always `01`. That fits both "first day of each month" (DD/MM/YYYY) and "January
1 to 12" (MM/DD/YYYY). Internal evidence favours DD/MM: for 857 of 858
International Union of Crystallography records (a monthly journal) the middle
component equals the issue number in `Citation`. This is not independent
confirmation, so the value is kept as an untyped string rather than converted
to ISO 8601. The lifecycle event (publication, issue date, record creation) is
not stated in the source.

**Language.** The DCMI usage note allows "a literal value consisting of an IETF
BCP 47 language tag". The codes `en`, `es`, `fr` from Project 01 are written
as plain literals. 15 records have no language.

**Publisher.** Like creator, `dcterms:publisher` has "Range Includes
`dcterms:Agent`", so the name becomes an agent node with `foaf:name`.

**ISSNs.** An ISSN identifies a serial, not an article. Writing an ISSN directly
as the article's `dcterms:identifier` would be wrong. Writing it as the value of
`dcterms:isPartOf` would also be wrong: DCMI states that `isPartOf` "is intended
to be used with non-literal values". The ISSNs are therefore placed on a
separate journal node, and the article points to it with `dcterms:isPartOf`.
41 records have two ISSNs; they are assumed to be the print and electronic ISSN
of the same journal (DOAJ's journal model), but which is which is not recorded.
Two ISSNs end in a lowercase `x` and are kept as in the source.

**Citation.** `dcterms:bibliographicCitation` is "a bibliographic reference for
the resource" with range `rdfs:Literal`. The DOAJ `Citation` value
(for example `Entropy, Vol 17, Iss 12, Pp 7848-7858 (2015)`) gives the journal,
volume, issue, pages and year of the article itself, so the mapping fits. It
is partial (no authors or title) and unstructured. This field was not part of
the OpenRefine operations.

**Licence.** DCMI recommends a URI for the licence document, but allows a literal.
The source has only `CC BY`, `CC BY-NC` and `CC BY-NC-ND`, without version
numbers. Linking to any specific Creative Commons version (2.0, 3.0, 4.0) would
invent information, so the labels are kept as literals.

## Audit trail

The original DOAJ columns are kept unchanged in
`data/intermediate/dublin_core_mapping_working.csv` (verified against the
Project 01 output). The `@id` of each JSON-LD record equals the `URL` column, so
every exported record can be joined back to its source row.
