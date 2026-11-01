"""Validate the working CSV and the JSON-LD export, then write
reports/validation-report.md.

Checks are grouped into: preservation, OpenRefine columns, JSON-LD structure,
mapping fidelity, JSON-LD processing (pyld), and crosswalk consistency.
Data quality observations are reported separately and never fail the run.

Usage: python scripts/validate.py
"""

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from pyld import jsonld

ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = ROOT / "data/input/bibliographic_metadata_cleaned.csv"
WORKING_CSV = ROOT / "data/intermediate/dublin_core_mapping_working.csv"
OUTPUT = ROOT / "data/output/doaj_dublin_core.jsonld"
CROSSWALK = ROOT / "mapping/crosswalk.csv"
REPORT = ROOT / "reports/validation-report.md"

DC = "http://purl.org/dc/terms/"
FOAF_NAME = "http://xmlns.com/foaf/0.1/name"
LANGUAGES = {"en", "es", "fr"}
LICENCES = {"CC BY", "CC BY-NC", "CC BY-NC-ND"}
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")
DOAJ_URL = re.compile(r"^https://doaj\.org/article/[0-9a-f]{32}$")
ISSN_PATTERN = re.compile(r"^\d{4}-\d{3}[\dX]$")

results = []


def check(group, name, passed, detail):
    results.append((group, name, bool(passed), detail))


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def split_pipe(value):
    """Python equivalent of the GREL used in OpenRefine: split on |, trim each part."""
    return [part.strip() for part in value.split("|")] if value.strip() else []


def blank_to_empty(value):
    return value.strip()


# --- Preservation --------------------------------------------------------------

def check_preservation(source, working, records):
    original_columns = list(source[0].keys())
    check("Preservation", "Record count", len(source) == len(working) == len(records) == 1000,
          f"input {len(source)}, working CSV {len(working)}, JSON-LD {len(records)}")
    check("Preservation", "Column count", len(working[0]) == 22 and len(original_columns) == 12,
          f"input {len(original_columns)}, working CSV {len(working[0])} "
          f"({len(working[0]) - len(original_columns)} added)")
    same = all(s[c] == w[c] for s, w in zip(source, working) for c in original_columns)
    check("Preservation", "12 original columns unchanged, row by row", same,
          "every original value in the working CSV equals the Project 01 output")
    same_order = [w["URL"] for w in working] == [r["@id"] for r in records]
    check("Preservation", "JSON-LD records in source order, one per row", same_order,
          "@id sequence equals the URL column sequence")


# --- OpenRefine columns ----------------------------------------------------------

def check_openrefine_columns(working):
    for column, base in [("creators_json", "Authors"), ("subjects_json", "Subjects"),
                         ("issns_json", "ISSNs")]:
        arrays = [json.loads(row[column]) for row in working]
        valid = all(isinstance(a, list) and all(isinstance(v, str) and v for v in a) for a in arrays)
        matches = all(a == split_pipe(row[base]) for a, row in zip(arrays, working))
        total = sum(len(a) for a in arrays)
        check("OpenRefine columns", f"{column} is a valid JSON array of non-empty strings", valid,
              f"{len(arrays)} arrays, {total} values")
        check("OpenRefine columns", f"{column} equals split({base}) in order", matches,
              "independent Python re-implementation of the GREL split/trim")
    for column, base in [("dcterms:title", "Title"), ("dcterms:creator", "Authors"),
                         ("dcterms:date", "Date"), ("dcterms:language", "Language_normalized"),
                         ("dcterms:publisher", "Publisher"), ("dcterms:license", "Licence")]:
        matches = all(row[column] == blank_to_empty(row[base]) for row in working)
        check("OpenRefine columns", f"{column} equals trimmed {base}", matches, "")
    expected = [("https://doi.org/" + r["DOI"].strip()) if r["DOI"].strip() else "" for r in working]
    matches = all(r["dcterms:identifier"] == e for r, e in zip(working, expected))
    check("OpenRefine columns", "dcterms:identifier equals https://doi.org/ + DOI", matches,
          f"{sum(bool(e) for e in expected)} DOI URIs, {sum(not e for e in expected)} blank")


# --- JSON-LD structure ------------------------------------------------------------

def check_structure(document, records, allowed_keys):
    context = document.get("@context", {})
    check("JSON-LD structure", "Namespace URIs",
          context.get("dcterms") == DC and context.get("foaf") == "http://xmlns.com/foaf/0.1/",
          f"dcterms -> {context.get('dcterms')}")
    used = Counter(key for r in records for key in r)
    unexpected = set(used) - allowed_keys
    check("JSON-LD structure", "Only crosswalk properties used", not unexpected,
          f"unexpected keys: {sorted(unexpected) or 'none'}")
    check("JSON-LD structure", "Every record has @id and @type",
          used["@id"] == used["@type"] == len(records), f"@id {used['@id']}, @type {used['@type']}")
    ids = [r["@id"] for r in records]
    check("JSON-LD structure", "@id values unique DOAJ article URLs",
          len(set(ids)) == len(ids) and all(DOAJ_URL.match(i) for i in ids), f"{len(set(ids))} unique")
    empty = [k for r in records for k, v in r.items() if v in ("", [], None)]
    check("JSON-LD structure", "No empty values written", not empty, f"{len(empty)} empty values")
    agents = [a for r in records for a in r.get("dcterms:creator", []) + [r.get("dcterms:publisher", {})]]
    check("JSON-LD structure", "Creators and publishers are dcterms:Agent nodes with foaf:name",
          all(a == {"@type": "dcterms:Agent", "foaf:name": a.get("foaf:name")} and a["foaf:name"]
              for a in agents), f"{len(agents)} agent nodes")
    dates = [r["dcterms:date"] for r in records if "dcterms:date" in r]
    strings = sum(isinstance(d, str) for d in dates)
    check("JSON-LD structure", "Dates are untyped strings", strings == len(dates),
          f"{strings} of {len(dates)} dates are plain strings")


# --- Mapping fidelity (JSON-LD back to the source) ---------------------------------

def expected_record_values(row):
    return {
        "dcterms:title": row["Title"].strip(),
        "creators": split_pipe(row["Authors"]),
        "dcterms:identifier": ("https://doi.org/" + row["DOI"].strip()) if row["DOI"].strip() else None,
        "dcterms:date": row["Date"].strip(),
        "dcterms:language": row["Language_normalized"].strip() or None,
        "dcterms:subject": split_pipe(row["Subjects"]),
        "publisher": row["Publisher"].strip() or None,
        "issns": split_pipe(row["ISSNs"]),
        "dcterms:bibliographicCitation": row["Citation"] or None,
        "dcterms:license": row["Licence"].strip() or None,
    }


def actual_record_values(record):
    return {
        "dcterms:title": record.get("dcterms:title"),
        "creators": [a["foaf:name"] for a in record.get("dcterms:creator", [])],
        "dcterms:identifier": record.get("dcterms:identifier"),
        "dcterms:date": record.get("dcterms:date"),
        "dcterms:language": record.get("dcterms:language"),
        "dcterms:subject": record.get("dcterms:subject", []),
        "publisher": record.get("dcterms:publisher", {}).get("foaf:name"),
        "issns": record.get("dcterms:isPartOf", {}).get("dcterms:identifier", []),
        "dcterms:bibliographicCitation": record.get("dcterms:bibliographicCitation"),
        "dcterms:license": record.get("dcterms:license"),
    }


def check_fidelity(working, records):
    mismatches = Counter()
    for row, record in zip(working, records):
        expected, actual = expected_record_values(row), actual_record_values(record)
        for field in expected:
            if expected[field] != actual[field]:
                mismatches[field] += 1
    check("Mapping fidelity", "Every mapped value round-trips to the source", not mismatches,
          f"mismatches: {dict(mismatches) or 'none'} (order and spelling of creators/subjects included)")
    creators = sum(len(r.get("dcterms:creator", [])) for r in records)
    subjects = sum(len(r.get("dcterms:subject", [])) for r in records)
    issns = sum(len(r.get("dcterms:isPartOf", {}).get("dcterms:identifier", [])) for r in records)
    check("Mapping fidelity", "Value totals preserved", (creators, subjects, issns) == (4006, 7271, 1041),
          f"creators {creators}, subjects {subjects}, ISSNs {issns}")

    with_doi = [r for r in working if r["DOI"].strip()]
    dois = [r["DOI"].strip() for r in with_doi]
    identifiers = [r["dcterms:identifier"] for r in records if "dcterms:identifier" in r]
    check("Identifiers", "DOI identifiers only where the source has a DOI",
          len(identifiers) == len(with_doi) == 977, f"{len(identifiers)} identifiers, {1000 - len(identifiers)} omitted")
    check("Identifiers", "DOIs well-formed and unique",
          all(DOI_PATTERN.match(d) for d in dois) and len(set(dois)) == len(dois), f"{len(set(dois))} unique DOIs")
    check("Identifiers", "All identifiers are https://doi.org/ URIs",
          all(i.startswith("https://doi.org/10.") for i in identifiers), "")

    languages = Counter(r.get("dcterms:language", "") for r in records)
    raw_ok = all(r["Language_normalized"] == {"EN": "en", "English": "en", "ES": "es", "FR": "fr", "": ""}
                 .get(r["Language"]) for r in working)
    check("Language", "Codes limited to en/es/fr and consistent with raw Language",
          set(languages) - {""} <= LANGUAGES and raw_ok, f"distribution: {dict(languages)}")

    licences = Counter(r.get("dcterms:license", "") for r in records)
    check("Licence", "Licence labels unchanged, no versions or links added",
          set(licences) - {""} <= LICENCES, f"distribution: {dict(licences)}")


# --- JSON-LD processing with pyld ----------------------------------------------

def check_processing(document, records):
    expanded = jsonld.expand(document)
    check("JSON-LD processing", "pyld expansion succeeds", len(expanded) == len(records),
          f"{len(expanded)} expanded nodes")
    properties = {p for node in expanded for p in node if not p.startswith("@")}
    check("JSON-LD processing", "All expanded properties are absolute DCMI IRIs",
          all(p.startswith(DC) for p in properties), f"{len(properties)} distinct properties")
    compact_values = sum(len(v) if isinstance(v, list) else 1
                         for r in records for k, v in r.items() if not k.startswith("@"))
    expanded_values = sum(len(v) for node in expanded for k, v in node.items() if not k.startswith("@"))
    check("JSON-LD processing", "No values dropped during expansion", compact_values == expanded_values,
          f"compact {compact_values}, expanded {expanded_values}")
    creator_names = [c[FOAF_NAME][0]["@value"] for n in expanded for c in n.get(DC + "creator", [])]
    check("JSON-LD processing", "Creator order preserved in expanded form",
          creator_names == [a["foaf:name"] for r in records for a in r.get("dcterms:creator", [])],
          f"{len(creator_names)} creator names")

    nquads = jsonld.to_rdf(document, {"format": "application/n-quads"})
    triples = nquads.strip().splitlines()
    subject_triples = sum(f"<{DC}subject>" in t for t in triples)
    unique_subjects = sum(len(set(r.get("dcterms:subject", []))) for r in records)
    check("JSON-LD processing", "RDF conversion succeeds", triples and subject_triples == unique_subjects,
          f"{len(triples)} triples; {subject_triples} dcterms:subject triples, expected {unique_subjects} "
          "(distinct subject values per record; duplicates collapse in RDF)")
    non_ascii = any(ord(ch) > 127 for ch in OUTPUT.read_text(encoding="utf-8"))
    check("JSON-LD processing", "Unicode written as characters, not escapes", non_ascii,
          "output contains non-ASCII characters such as accented names")


# --- Crosswalk consistency ------------------------------------------------------

def check_crosswalk(working, records, crosswalk):
    mapped = {row["target_property"].split("/")[0] for row in crosswalk if not row["target_property"].startswith("(")}
    used = {key for r in records for key in r}
    check("Crosswalk", "Crosswalk targets equal properties used in JSON-LD", mapped == used,
          f"only in crosswalk: {sorted(mapped - used) or 'none'}; only in output: {sorted(used - mapped) or 'none'}")
    documented = {row["working_column"] for row in crosswalk}
    undocumented = set(working[0]) - documented
    check("Crosswalk", "Every working CSV column is documented", not undocumented,
          f"undocumented: {sorted(undocumented) or 'none'}")
    return mapped


# --- Data quality observations (reported, never fail) ----------------------------

def issn_check_digit_ok(issn):
    digits = issn.replace("-", "").upper()
    total = sum(int(d) * w for d, w in zip(digits[:7], range(8, 1, -1)))
    check_digit = (11 - total % 11) % 11
    return digits[7] == ("X" if check_digit == 10 else str(check_digit))


def observations(working):
    issns = [i for r in working for i in split_pipe(r["ISSNs"])]
    subjects = [split_pipe(r["Subjects"]) for r in working]
    names = [n for r in working for n in split_pipe(r["Authors"])]
    dates = [r["Date"] for r in working]
    acta = [(r["Date"].split("/")[1], re.search(r"Iss (\d+)", r["Citation"]))
            for r in working if r["Publisher"] == "International Union of Crystallography"]
    acta_match = sum(m is not None and int(month) == int(m.group(1)) for month, m in acta)
    return [
        f"Missing DOI: {sum(not r['DOI'].strip() for r in working)} records (not fabricated).",
        f"Missing language: {sum(not r['Language_normalized'] for r in working)} records.",
        f"Missing licence: {sum(not r['Licence'].strip() for r in working)} records.",
        f"ISSNs not matching NNNN-NNNC (uppercase X): {[i for i in issns if not ISSN_PATTERN.match(i)]} "
        "(kept as in source).",
        f"ISSNs with a valid check digit: {sum(issn_check_digit_ok(i) for i in issns)} of {len(issns)}.",
        f"Records with repeated subject values: {sum(len(set(s)) != len(s) for s in subjects)}.",
        f"Creator names containing a comma (likely inverted 'Surname, Initials'): "
        f"{sum(',' in n for n in names)} of {len(names)}.",
        f"Date pattern: {dict(Counter(re.sub(r'[0-9]', 'N', d) for d in dates))}; first component values: "
        f"{sorted(set(d.split('/')[0] for d in dates))}; middle component values: "
        f"{sorted(set(d.split('/')[1] for d in dates))}.",
        f"Date convention, internal evidence only: for {acta_match} of {len(acta)} International Union of "
        "Crystallography records the middle date component equals the issue number in Citation. "
        "This suggests DD/MM/YYYY but is not independent confirmation, so dates stay strings.",
        f"Distinct publishers: {len({r['Publisher'] for r in working})}.",
    ]


def write_report(notes):
    passed = sum(r[2] for r in results)
    lines = ["# Validation report", "",
             "Generated by `scripts/validate.py`. Results below are from an actual run.", "",
             f"**{passed} of {len(results)} checks passed.**", "",
             "| Group | Check | Result | Detail |", "| --- | --- | --- | --- |"]
    lines += [f"| {g} | {n} | {'PASS' if p else 'FAIL'} | {d.replace('|', '/')} |" for g, n, p, d in results]
    lines += ["", "## Data quality observations (not failures)", ""] + [f"- {n}" for n in notes]
    lines += ["", "## Scope of these checks", "",
              "- Syntactic validity: the export is processed by pyld (JSON-LD expansion and RDF conversion).",
              "- Mapping fidelity: every mapped value is compared with the source CSV.",
              "- Semantic accuracy (whether a value is true for the article, whether a name is the right "
              "person, which date convention applies) cannot be proven by these checks. See "
              "`mapping/crosswalk.md` for known limitations."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    source, working = read_csv(INPUT_CSV), read_csv(WORKING_CSV)
    document = json.loads(OUTPUT.read_text(encoding="utf-8"))
    records = document["@graph"]
    crosswalk = read_csv(CROSSWALK)

    check_preservation(source, working, records)
    check_openrefine_columns(working)
    mapped = check_crosswalk(working, records, crosswalk)
    check_structure(document, records, mapped)
    check_fidelity(working, records)
    check_processing(document, records)
    write_report(observations(working))

    for group, name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {group}: {name}  {detail}")
    failed = sum(not r[2] for r in results)
    print(f"\n{len(results) - failed} of {len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
