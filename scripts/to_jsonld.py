"""Convert the OpenRefine working CSV into Dublin Core JSON-LD.

Each CSV row becomes one article node. Values come from the dcterms:* and
*_json columns created in OpenRefine; Citation and URL come from the original
DOAJ columns. Blank values are left out, never filled in.

Usage: python scripts/to_jsonld.py
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKING_CSV = ROOT / "data/intermediate/dublin_core_mapping_working.csv"
OUTPUT = ROOT / "data/output/doaj_dublin_core.jsonld"

CONTEXT = {
    "dcterms": "http://purl.org/dc/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
}


def agent(name):
    """dcterms:creator and dcterms:publisher point to agents, not strings."""
    return {"@type": "dcterms:Agent", "foaf:name": name}


def serial(issns):
    """The journal the article belongs to; ISSNs identify the journal, not the article."""
    return {"@type": "dcterms:BibliographicResource", "dcterms:identifier": issns}


def to_record(row):
    creators = json.loads(row["creators_json"])
    subjects = json.loads(row["subjects_json"])
    issns = json.loads(row["issns_json"])
    record = {
        "@id": row["URL"],
        "@type": "dcterms:BibliographicResource",
        "dcterms:title": row["dcterms:title"],
        "dcterms:creator": [agent(name) for name in creators],
        "dcterms:identifier": row["dcterms:identifier"],
        "dcterms:date": row["dcterms:date"],
        "dcterms:language": row["dcterms:language"],
        "dcterms:subject": subjects,
        "dcterms:publisher": agent(row["dcterms:publisher"]) if row["dcterms:publisher"] else "",
        "dcterms:isPartOf": serial(issns) if issns else "",
        "dcterms:bibliographicCitation": row["Citation"],
        "dcterms:license": row["dcterms:license"],
    }
    return {key: value for key, value in record.items() if value not in ("", [])}


def main():
    with WORKING_CSV.open(encoding="utf-8", newline="") as f:
        records = [to_record(row) for row in csv.DictReader(f)]
    document = {"@context": CONTEXT, "@graph": records}
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} records to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
