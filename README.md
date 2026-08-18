# AI Testing Engineer Submission
OCR & Document AI Evaluation for Sale Deed Documents (Kalpit Pvt Ltd)

## What this is

An automated evaluation pipeline for testing OCR quality on the 3 provided
Madhya Pradesh sale-deed PDFs, with full-document coverage (every page of
all 3 documents, 86 pages total — not a page sample), covering:

- Ground truth creation (full text + structured critical fields)
- OCR execution (Tesseract, Hindi + English)
- Robustness testing via realistic image degradation
- Automated metrics: CER, WER, critical-field exact-match accuracy (raw and
  normalized), suspicious/unsupported-token check
- Original-vs-degraded comparison
- Excel + console + markdown reporting

## Documents used

| Label | Source file | Pages | Type |
|---|---|---|---|
| docA | `MP22IGR17182026A100034741.pdf` | 27 | Born-digital PDF (has text layer) |
| docB | `DocScanner_Apr_21__2026_6-48_PM.pdf` | 22 | **Genuine scanned photo** (no text layer at all) |
| docC | `MP22IGR17182025A100911603__2_.pdf` | 37 | Born-digital PDF (has text layer) |

**docB contains three genuinely blank pages** (2, 4, and 6), confirmed by
visual inspection of the rendered images. These are kept in the ground
truth as empty text and are the basis of the blank-page robustness finding
below.

## Tool used

**Tesseract OCR 5.3.4** (`tesseract-ocr-hin` language pack), run via the
`tesseract` CLI at `--psm 4` (assume a single column of text of variable
sizes), language mode `hin+eng` (both Hindi and English enabled, since these
documents mix Devanagari text with Latin-script names, addresses, and IDs).
Chosen because it's free/open-source, widely deployed, and gives a realistic
baseline for how classical OCR handles government Hindi documents — the
brief explicitly says high accuracy isn't the goal, so a "good enough,
realistic" engine was preferred over hand-tuning for a top score.

## Repository structure

```
├── docA.pdf, docB.pdf, docC.pdf        # copies of the 3 source PDFs
├── requirements.txt
├── README.md                           # this file
│
├── ground_truth/
│   ├── docA_ground_truth.md            # ONE document per source PDF (as the assignment
│   ├── docB_ground_truth.md            # asks: "for each of the 3 documents, create ground
│   ├── docC_ground_truth.md            # truth"). Each contains the full text of every page,
│   │                                    # the structured critical fields, and difficulty notes.
│   ├── critical_fields.json            # same structured fields, machine-readable (used by evaluate.py)
│   └── page_text/                      # underlying per-page raw text (the 3 .md files above
│                                        # are generated from these)
│
├── original_images/                    # 300 DPI renders of every page (the "clean" OCR input)
├── degraded_images/                    # after degrade.py: rotation+contrast+blur+JPEG
│
├── ocr_output/
│   ├── original/                       # Tesseract output on original_images/
│   └── degraded/                       # Tesseract output on degraded_images/
│
├── evaluation/
│   ├── results.csv                     # per-page CER/WER, original vs degraded, with pp deltas
│   ├── field_results.csv               # per-field raw + normalized exact-match, original vs degraded
│   └── suspicious_tokens.csv           # flagged unexplained tokens (see methodology note below)
│
├── report/
│   ├── evaluation_report.xlsx          # formatted, multi-tab Excel report (includes a dedicated
│   │                                    # "Blank Page Finding" sheet, highlighted)
│   └── error_examples.md               # side-by-side ground truth vs OCR excerpts
│
├── strategy/
│   └── TESTING_STRATEGY.md             # answers to all 5 strategy questions
│
├── degrade.py                          # creates degraded image versions
├── evaluate.py                         # main evaluation pipeline (CER/WER/fields/suspicious-tokens)
├── build_report.py                     # builds the Excel report + error examples doc
├── build_ground_truth_docs.py          # builds the 3 ground truth .md documents above
└── fix_ground_truth_extraction.py      # extracts page_text/ using pdftotext -layout + deduplication
                                         # (pdftotext's default and -raw modes were found to follow the
                                         #  PDF's internal storage order rather than visual reading order
                                         #  on these documents, and to store some paragraphs multiple
                                         #  times internally despite rendering once visually -- this
                                         #  script corrects both issues; see methodology notes in
                                         #  critical_fields.json for detail)
```

## Live evaluation UI

For presenting this on UI, there's also a
small local web app with a real "Run" button per document:

```bash
python app.py
```

Then open **http://localhost:5000** in a browser. Clicking a document's
"Run Evaluation" button sends a request to the local server, which
re-executes the actual scoring logic (`evaluation_lib.py`, a reusable
version of the same code in `evaluate.py`) against that document's
ground truth and OCR files on disk, and displays fresh results in the
page — including the blank-page finding shown as color-coded pass/fail
cards. This is real computation on each click, not a pre-recorded demo;
stop the server with Ctrl+C when done.

 
