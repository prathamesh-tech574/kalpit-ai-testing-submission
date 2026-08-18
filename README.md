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

## How to run it yourself

```bash
pip install -r requirements.txt

# Also need Tesseract with Hindi language data (Ubuntu/Debian):
apt-get install -y tesseract-ocr tesseract-ocr-hin poppler-utils

# 1. Rasterize every page of each PDF at 300 DPI, e.g.:
pdftoppm -png -r 300 -f 1 -l 1 docA.pdf original_images/docA_p1
#    (repeat for each page of each document -- 27+22+37 = 86 pages total)

# 2. Run OCR on the originals
for f in original_images/*.png; do
  name=$(basename "$f" .png)
  tesseract "$f" "ocr_output/original/${name}" -l hin+eng --psm 4
done

# 3. Create degraded versions
python3 degrade.py

# 4. Run OCR on the degraded versions
for f in degraded_images/*.png; do
  name=$(basename "$f" _degraded.png)
  tesseract "$f" "ocr_output/degraded/${name}" -l hin+eng --psm 4
done

# 5. Run the evaluation pipeline (prints console summary + writes CSVs)
python3 evaluate.py

# 6. Build the polished Excel report + error examples
python3 build_report.py
```

## Headline results (see `report/evaluation_report.xlsx` for full detail)

Full-document coverage: all 86 pages (27+22+37) transcribed and tested.

- **Avg CER** (82 text-bearing pages, excluding the 3 known-blank pages which are reported separately below): 26.8% (original) → 48.1% (degraded) — a **+21.3 percentage-point** increase under degradation
- **Avg WER**: 42.8% (original) → 66.9% (degraded) — a **+24.1 percentage-point** increase
- **Critical field accuracy** (30 fields total across 3 documents): **raw exact match** 70.0% (original) → 70.0% (degraded); **normalized exact match** (tolerant of date-separator style and letter-case differences only, e.g. `09-01-2026` vs `09/01/2026`, or `Badoni` vs `BADONI`) also 70.0% → 70.0%. Raw exact match is the primary, stricter metric per the assignment's requirement; normalized is reported alongside it, not instead of it. (Field matching is case-insensitive: several fields in these documents are printed in ALL CAPS in one part of the page and Title Case elsewhere by the source system itself -- e.g. the tehsil name appears as "BADONI" in a table -- which is a source formatting difference, not an OCR transcription error, and should not be scored as a field-accuracy failure.)
- Fields that failed on the original images (unaffected by degradation, so a pre-existing OCR weakness): survey/khasra numbers, registration numbers, and registration dates across all 3 documents — numeric/ID fields are consistently the weakest category, which is a meaningful finding for a land-registry system.

**Note on WER exceeding 100% on some pages:** WER = (substitutions + deletions + insertions) / reference word count, so it is not capped at 100% — a page where OCR inserts far more words than the reference contains (e.g. reading noise as extra text) can legitimately show WER above 1.0. This appears on a handful of the shortest/most degraded pages in this dataset and is expected `jiwer` behaviour, not a bug.

### Blank-page robustness finding (highlighted in the report as its own sheet)

docB has three genuinely blank pages: 2, 4, and 6.

| Page | Original image | Degraded image |
|---|---|---|
| docB p2 | **FAIL** — OCR produced ~30 words of meaningless text from scan noise | **FAIL** — same, on the degraded version |
| docB p4 | PASS — correctly returned empty output | PASS |
| docB p6 | PASS — correctly returned empty output | PASS |

This is the single most concrete, unambiguous finding in this submission:
**a blank page can produce non-empty OCR output**, and a pipeline that only
checks "is there text?" would silently accept fabricated content from page
2 while correctly handling pages 4 and 6. This is why CER/WER and a
dedicated empty-input test are both necessary — text-similarity metrics
alone cannot catch a false-positive detection on blank input.

These numbers are **intentionally unglamorous** — the brief is explicit that
"high OCR accuracy numbers are not the main goal," and a bare Tesseract run
with no document-specific tuning, against real (not cherry-picked) Madhya
Pradesh government documents, was left as-is rather than optimized. The
strategy document explains what a production pipeline would do differently.

## Suspicious / unsupported-token check — methodology note

This check flags OCR output tokens (length ≥ 4 characters) that have no
plausible edit-distance relationship to any token in that page's ground
truth. It is a **heuristic for surfacing output that deserves human
review**, not a certain proof of "hallucination" or "rewriting" — since we
only observe the final OCR text, not how the engine produced it, a
token-similarity check can be fooled in both directions (e.g. two correctly
read words merged by a missing space can look "unsupported," while a single
wrong digit in a long ID can look "supported" by edit-distance despite being
a materially different value).

In this run, 937 tokens were flagged. The large majority are ordinary OCR
recognition errors — for example, Tesseract's `eng` language-model component
reading a misrecognized Devanagari glyph as a Latin-alphabet fragment (e.g.
`fase`, `wart`, `args`) — not evidence of the system inventing content. The
one flagged case that IS an unambiguous, concrete finding is the blank-page
result above, where a blank ground-truth page produced entirely fabricated
non-empty output; that case is reported separately and highlighted in the
Excel report specifically because it doesn't depend on the token-similarity
heuristic at all.
