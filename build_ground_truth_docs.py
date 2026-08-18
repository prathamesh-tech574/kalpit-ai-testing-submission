"""
Builds ONE ground-truth document per source PDF (as the assignment actually
asks: "for each of the 3 documents, create accurate ground truth"), each
containing all 3 required parts together in one file:
  1. Full readable text transcription (of the pages reviewed)
  2. Structured critical fields
  3. Notes on difficulties

Reads from ground_truth/page_text/ (the per-page text, kept as the
underlying source of truth) and ground_truth/critical_fields.json
(the structured fields), and merges them into 3 single documents.
"""
import json
import os

PAGE_LABELS = {}

DOC_TITLES = {
    "docA": "Document A -- MP22IGR17182026A100034741.pdf\n(Sellers: Braj Kishor Rawat & Neetendra Rawat -> Buyer: Gyanmanjari Rawat)",
    "docB": "Document B -- DocScanner_Apr_21__2026_6-48_PM.pdf\n(Sellers: Suman Pal & family -> Buyer: Barelal Singh Gurjar)",
    "docC": "Document C -- MP22IGR17182025A100911603__2_.pdf\n(Sellers: Jakesh Jatav & Neelam Jatav -> Buyers: Shishupal & Vishal Jatav)",
}

DOC_PAGES = {
    "docA": [f"p{i}" for i in range(1, 28)],
    "docB": [f"p{i}" for i in range(1, 23)],
    "docC": [f"p{i}" for i in range(1, 38)],
}

FIELD_DISPLAY_NAMES = {
    "owner_names": "Owner Name(s)",
    "father_husband_name": "Father / Husband Name",
    "buyer_names": "Buyer Name(s)",
    "survey_khasra_number": "Survey / Plot / Khasra Number",
    "area": "Area",
    "village": "Village",
    "tehsil": "Tehsil",
    "district": "District",
    "registration_number": "Registration Number",
    "registration_date": "Registration Date",
}

def read(path):
    return open(path, encoding="utf-8").read().strip() if os.path.exists(path) else "(not available)"

with open("ground_truth/critical_fields.json", encoding="utf-8") as f:
    all_fields = json.load(f)

general_notes = all_fields["methodology_notes"]

for doc_key in ["docA", "docB", "docC"]:
    lines = []
    lines.append(f"# Ground Truth -- {DOC_TITLES[doc_key]}\n")
    lines.append("This document contains everything the assignment asks for, "
                  "for this one source PDF, in one place:\n"
                  "1. Full readable text transcription\n"
                  "2. Structured critical fields\n"
                  "3. Notes on difficulties encountered\n")
    lines.append("---\n")

    # -------- Scope note --------
    pages = DOC_PAGES[doc_key]
    lines.append("## Scope of this ground truth\n")
    lines.append(
        f"**All {len(pages)} pages** of this source PDF were transcribed and used "
        f"for ground truth -- full-document coverage, not a page sample. "
        f"See 'Notes on difficulties' at the end of this document for how each "
        f"page's text was obtained (automated extraction with manual verification "
        f"for born-digital PDFs, or fully manual transcription for the scanned "
        f"document) and for known limitations (e.g. table row/column order).\n"
    )

    # -------- Part 1: Full text transcription --------
    lines.append("## 1. Full readable text transcription\n")
    for page in pages:
        lines.append(f"### {PAGE_LABELS.get(page, page)}\n")
        text = read(f"ground_truth/page_text/{doc_key}_{page}.txt")
        lines.append("```")
        lines.append(text)
        lines.append("```\n")

    # -------- Part 2: Structured critical fields --------
    lines.append("## 2. Structured critical fields\n")
    lines.append("| Field | Value | Note |")
    lines.append("|---|---|---|")
    doc_fields = all_fields[doc_key]["fields"]
    for fname, finfo in doc_fields.items():
        display = FIELD_DISPLAY_NAMES.get(fname, fname)
        val = finfo["value"]
        val_display = ", ".join(val) if isinstance(val, list) else val
        lines.append(f"| {display} | {val_display} | {finfo['note']} |")
    lines.append("")

    blank_note = all_fields[doc_key].get("blank_pages_note")
    if blank_note:
        lines.append(f"**Blank pages:** {blank_note}\n")

    # Also give a machine-readable JSON version of just this document's fields
    lines.append("**Same fields, as JSON** (for the automated evaluation script to read):\n")
    lines.append("```json")
    lines.append(json.dumps({doc_key: all_fields[doc_key]}, ensure_ascii=False, indent=2))
    lines.append("```\n")

    # -------- Part 3: Notes on difficulties --------
    lines.append("## 3. Notes on difficulties encountered\n")
    lines.append("These notes apply across all 3 documents in this submission "
                  "(the difficulties were common to all of them):\n")
    for note in general_notes:
        lines.append(f"- {note}")
    lines.append("")

    out_path = f"ground_truth/{doc_key}_ground_truth.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {out_path}")
