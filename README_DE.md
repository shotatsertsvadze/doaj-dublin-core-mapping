# Von DOAJ zu Dublin Core: Mapping bibliografischer Metadaten

Ein Einstiegsprojekt zum Metadaten-Mapping: 1.000 bereinigte Zeitschriftenartikel
aus dem Directory of Open Access Journals (DOAJ) wurden in OpenRefine auf die
[DCMI Metadata Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)
abgebildet, in einer Konkordanz (Crosswalk) dokumentiert, als JSON-LD exportiert
und automatisiert geprüft.

Portfolio-Projekt 02. Grundlage ist der Ergebnisdatensatz aus Projekt 01,
[Bibliographic Metadata Quality Improvement with OpenRefine](https://github.com/shotatsertsvadze/bibliographic-metadata-quality).

Ausführliche englische Fassung: [README.md](README.md)

## Durchgeführte Arbeiten

**OpenRefine (manuell).** Zehn neue Spalten per GREL, u. a. `dcterms:title`,
`dcterms:identifier` (DOI als `https://doi.org/...`) sowie `creators_json`,
`subjects_json` und `issns_json`, in denen die mit `|` getrennten Mehrfachwerte
als JSON-Arrays vorliegen. Die exportierte Operationshistorie wurde über die
OpenRefine-API erneut angewendet; das Ergebnis ist byte-identisch mit der
exportierten Arbeitsdatei.

**Crosswalk.** Für jedes Feld sind Zielelement, Transformationsregel,
Kardinalität, Umgang mit fehlenden Werten, Prüfregel und semantische Grenzen
festgehalten ([`mapping/`](mapping/)).

**JSON-LD-Export.** Ein kurzes Python-Skript erzeugt 1.000 Artikelknoten.
Personen und Verlage sind `dcterms:Agent`-Knoten mit `foaf:name`. ISSN
stehen an einem eigenen Zeitschriftenknoten (`dcterms:isPartOf`), nicht am
Artikel. Fehlende Werte werden weggelassen, nicht ergänzt.

## Ergebnis

| | Wert |
| --- | --- |
| Datensätze | 1.000 |
| Personen- / Schlagwort- / ISSN-Werte | 4.006 / 7.271 / 1.041, vollständig erhalten |
| DOI | 977 (23 fehlen, nicht erfunden) |
| Prüfungen | 39 von 39 bestanden ([Bericht](reports/validation-report.md), englisch) |

Die JSON-LD-Datei wurde mit dem Prozessor pyld expandiert und in RDF
umgewandelt (32.174 Tripel).

## Grenzen

- Datumsangaben (`01/MM/2015`) bleiben unveränderte Zeichenketten, da die
  Reihenfolge von Tag und Monat nicht unabhängig belegt ist.
- Lizenzangaben (`CC BY` usw.) haben keine Versionsnummer und werden nicht mit
  einer bestimmten Creative-Commons-Version verknüpft.
- Keine Normdaten (GND, ORCID, ROR) für Personen und Verlage; kein kontrolliertes
  Vokabular für Schlagwörter nachgewiesen.
- Die Prüfungen belegen syntaktische Gültigkeit und Quelltreue, nicht die
  inhaltliche Richtigkeit der Angaben.

## Urheberschaft und KI-Unterstützung

Die OpenRefine-Arbeit wurde manuell von Shota Tsertsvadze durchgeführt. Skripte,
Crosswalk-Dokumentation, Berichte und README-Dateien entstanden mit dem
KI-Assistenten Claude Code (Anthropic).
