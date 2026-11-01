# From DOAJ to Dublin Core: Bibliographic Metadata Mapping

A beginner-level metadata mapping project: 1,000 cleaned journal article
records from the Directory of Open Access Journals (DOAJ) are mapped to
[DCMI Metadata Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)
in OpenRefine, documented in a crosswalk, exported as JSON-LD and validated.

Portfolio Project 02. It builds on Project 01,
[Bibliographic Metadata Quality Improvement with OpenRefine](https://github.com/shotatsertsvadze/bibliographic-metadata-quality),
which produced the input dataset.

German summary: [README_DE.md](README_DE.md)

| | Result |
| --- | --- |
| Records | 1,000 in, 1,000 out |
| OpenRefine operations | 10 column additions, replayed with an identical result |
| Creator / subject / ISSN values | 4,006 / 7,271 / 1,041, all preserved |
| DOI identifiers | 977 (23 missing, not generated) |
| JSON-LD | expands and converts to RDF with pyld (32,174 triples) |
| Validation | 39 of 39 checks passed ([report](reports/validation-report.md)) |

## 1. Why metadata interoperability matters

Digital libraries exchange records with aggregators, discovery systems and
other institutions. A local CSV with pipe-delimited author lists can be read
only by someone who knows its conventions. Mapping it to a shared vocabulary
such as Dublin Core, and publishing it in a standard syntax such as JSON-LD,
lets other systems interpret the same fields without that knowledge. The
mapping must stay faithful to the source: a crosswalk that invents licence
versions, date formats or authority links produces records that look complete
but are wrong.

## 2. Source data and limitations

- **Input:** [`data/input/bibliographic_metadata_cleaned.csv`](data/input/bibliographic_metadata_cleaned.csv),
  the output of Project 01 (byte-identical copy). 1,000 records, 12 columns.
- **Origin:** the `doaj-article-sample.csv` file from the
  [Library Carpentry OpenRefine lesson](https://librarycarpentry.github.io/lc-open-refine/),
  derived from DOAJ article metadata.
- **Limitations of the source:**
  - multivalued fields (authors, subjects, ISSNs) are stored as `|`-delimited strings
  - no authority identifiers for people, publishers or subjects
  - dates are `01/MM/2015`, so the day/month order cannot be read from the value alone
  - licences are labels without version numbers (`CC BY`, `CC BY-NC`, `CC BY-NC-ND`)
  - 23 records have no DOI, 15 no language, 6 no licence
  - subjects mix free keywords with what look like Library of Congress
    Classification captions and notations, with no scheme declared

## 3. OpenRefine work

The mapping columns were created manually in OpenRefine 3.10.0. The exported
operation history,
[`openrefine/dublin-core-operations.json`](openrefine/dublin-core-operations.json),
contains 10 `core/column-addition` operations:

| New column | Based on | GREL logic |
| --- | --- | --- |
| `dcterms:title` | Title | trim; null if blank |
| `dcterms:creator` | Authors | trim; null if blank |
| `creators_json` | Authors | split on `\|`, trim each, JSON array; `[]` if blank |
| `dcterms:identifier` | DOI | `"https://doi.org/" + value.trim()`; null if blank |
| `dcterms:language` | Language_normalized | trim; null if blank |
| `dcterms:publisher` | Publisher | trim; null if blank |
| `subjects_json` | Subjects | split on `\|`, trim each, JSON array |
| `dcterms:date` | Date | trim; null if blank |
| `issns_json` | ISSNs | split on `\|`, trim each, JSON array |
| `dcterms:license` | Licence | trim; null if blank |

Example (`creators_json`):

```
if(isBlank(value), "[]",
   "[" + forEach(value.split("|"), author, author.trim().jsonize()).join(",") + "]")
```

The result was exported as
[`data/intermediate/dublin_core_mapping_working.csv`](data/intermediate/dublin_core_mapping_working.csv):
1,000 records, 22 columns (12 original + 10 new). The 12 original columns are
unchanged.

**Replay check.** [`scripts/replay_openrefine.py`](scripts/replay_openrefine.py)
uses the OpenRefine HTTP API to create a temporary project from the input CSV,
apply the 10 operations, export the result and compare it with the working CSV.
Result against OpenRefine 3.10.0: identical header and rows, and a
byte-identical file ([report](reports/openrefine-replay.md)).

## 4. Mapping methodology

1. Read each DCMI term's definition, range and usage note on the official page.
2. Map one source field to one target property, using the parsed OpenRefine
   columns for multivalued fields.
3. Choose literal or node values according to the term's range.
4. Leave a property out when the source value is blank.
5. Record transformation rule, cardinality, missing-value behaviour, validation
   rule and semantic limitations per field.

The specification is in [`mapping/crosswalk.csv`](mapping/crosswalk.csv), with
the reasoning in [`mapping/crosswalk.md`](mapping/crosswalk.md).

## 5. Representing creators, subjects, identifiers and dates

- **Creators:** one `dcterms:Agent` node with `foaf:name` per name, in source
  order and spelling, because `dcterms:creator` has "Range Includes
  `dcterms:Agent`". No authority identifiers are added. RDF does not keep the
  order of repeated properties; it is kept in the JSON array and in the source CSV.
- **Subjects:** one `dcterms:subject` literal per value. No controlled
  vocabulary is claimed.
- **Identifiers:** DOIs as `https://doi.org/...` literals in
  `dcterms:identifier`. ISSNs identify the journal, so they sit on a separate
  journal node linked with `dcterms:isPartOf`, never on the article itself.
- **Dates:** untyped strings (`01/11/2015`). For 857 of 858 records from a
  monthly journal the middle component equals the issue number, which suggests
  DD/MM/YYYY, but this is internal evidence only, so no conversion was made.
- **Citation** maps to `dcterms:bibliographicCitation`; **licence** labels stay
  literals without invented version links.

## 6. JSON-LD transformation

[`scripts/to_jsonld.py`](scripts/to_jsonld.py) (about 60 lines) reads the
working CSV and writes
[`data/output/doaj_dublin_core.jsonld`](data/output/doaj_dublin_core.jsonld):
one `@graph` with 1,000 article nodes. The context declares only the
`dcterms` (`http://purl.org/dc/terms/`) and `foaf` namespaces. Unicode is
written as characters, and output is deterministic.

```json
{
  "@id": "https://doaj.org/article/d9fe469f75a0442382b84ba4f50007ee",
  "@type": "dcterms:BibliographicResource",
  "dcterms:title": "Metagenomic Analysis of Upwelling-Affected Brazilian Coastal Seawater ...",
  "dcterms:creator": [
    {"@type": "dcterms:Agent", "foaf:name": "Rafael R. C. Cuadrat"},
    {"@type": "dcterms:Agent", "foaf:name": "Juliano C. Cury"},
    {"@type": "dcterms:Agent", "foaf:name": "Alberto M. R. Dávila"}
  ],
  "dcterms:identifier": "https://doi.org/10.3390/ijms161226101",
  "dcterms:date": "01/11/2015",
  "dcterms:language": "en",
  "dcterms:subject": ["PKS", "NRPS", "metagenomics", "...", "Chemistry", "QD1-999", "Science", "Q"],
  "dcterms:publisher": {"@type": "dcterms:Agent", "foaf:name": "MDPI AG"},
  "dcterms:isPartOf": {"@type": "dcterms:BibliographicResource", "dcterms:identifier": ["1422-0067"]},
  "dcterms:bibliographicCitation": "International Journal of Molecular Sciences, Vol 16, Iss 12, Pp 28285-28295 (2015)",
  "dcterms:license": "CC BY"
}
```

The DOAJ article URL is used as `@id` because it is present and unique in all
records; the DOI is missing for 23.

## 7. Validation

[`scripts/validate.py`](scripts/validate.py) runs 39 checks in six groups and
writes [`reports/validation-report.md`](reports/validation-report.md):

- **Preservation:** record and column counts; original columns unchanged; one
  JSON-LD record per row, in order.
- **OpenRefine columns:** each new column is recomputed in Python from its base
  column and compared; JSON arrays are valid.
- **JSON-LD structure:** namespaces, `@id`/`@type`, agent nodes, no empty values,
  dates untyped.
- **Mapping fidelity:** every mapped value is compared back to the source,
  including creator and subject order; DOI, language and licence consistency.
- **JSON-LD processing:** expansion and N-Quads conversion with
  [pyld](https://github.com/digitalbazaar/pyld), no values dropped, all
  properties resolve to DCMI IRIs.
- **Crosswalk:** properties in the output equal the targets in `crosswalk.csv`;
  every CSV column is documented.

Result of the latest run: **39 of 39 checks passed.** The validator was also
run against deliberately corrupted copies of the output (reordered creators,
removed DOI, invented DOI, undeclared property, typed date); each change was
detected.

These checks establish syntactic validity and fidelity to the source. They
cannot prove semantic accuracy, for example that a name refers to the right
person or which date convention DOAJ used.

## 8. Reproducibility

Requires Python 3.13 or later (tested with 3.13.3 and 3.14.7). Running the two
scripts below regenerates the committed output and report byte for byte.

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python scripts/to_jsonld.py
```

```bash
.venv/bin/python scripts/validate.py
```

Optional, with OpenRefine running at `http://127.0.0.1:3333`:

```bash
.venv/bin/python scripts/replay_openrefine.py
```

## 9. Unresolved metadata quality problems

- 23 records without DOI, 15 without language, 6 without licence.
- Date convention not independently confirmed; dates are not ISO 8601.
- 44 of 4,006 creator names appear inverted ("Surname, Initials"); others are in direct order.
- 41 records repeat a subject value.
- Two ISSNs use a lowercase check character (`2076-393x`, `2075-163x`).
- Print and electronic ISSNs are not distinguished; journal titles are only
  inside the unstructured `Citation` string.
- No authority identifiers (ORCID, GND, ROR) for creators or publishers.
- Licence labels cannot be resolved to a specific Creative Commons version.

## 10. Skills demonstrated

- Mapping a flat bibliographic CSV to DCMI Metadata Terms using term ranges and usage notes
- Splitting multivalued fields with GREL in OpenRefine
- Writing a crosswalk with cardinality, missing-value and validation rules
- Producing JSON-LD and testing it with a JSON-LD processor
- Replaying an OpenRefine operation history through its API
- Separating syntactic validity, mapping fidelity and semantic accuracy
- Documenting limitations instead of filling gaps with assumptions

## Authorship and AI assistance

The OpenRefine work (the 10 column-addition operations and the working CSV)
was done manually by Shota Tsertsvadze. The Python scripts, the crosswalk
documentation, the reports and these README files were produced with the AI
coding assistant Claude Code (Anthropic), working from those files.
Commits containing AI-generated work carry a `Co-Authored-By` trailer.

## License and attribution

- Code and documentation: MIT, see [LICENSE](LICENSE).
- Data: derived from the Library Carpentry OpenRefine lesson data,
  Copyright (c) The Carpentries, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  The files in `data/intermediate/` and `data/output/` are modified versions;
  the changes are documented in `mapping/`. The underlying article metadata comes
  from [DOAJ](https://doaj.org), which releases article metadata under CC0 1.0
  ([DOAJ terms](https://doaj.org/terms/)).
- The `Licence` field describes each article, not the metadata.
