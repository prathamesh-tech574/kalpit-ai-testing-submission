"""
Automated OCR Evaluation Pipeline
==================================
For each (document, page) pair, compares:
  - Ground truth text  vs  OCR output on the ORIGINAL page image
  - Ground truth text  vs  OCR output on the DEGRADED page image

Computes:
  A. Full-text quality: Character Error Rate (CER), Word Error Rate (WER)
  B. Critical field quality: raw exact-match AND normalized exact-match
     accuracy per field, per document
  C. Suspicious / unsupported-token check: a heuristic that flags OCR
     tokens not explainable as a garbled version of any ground-truth
     token. This flags output for human investigation -- it does not
     claim to prove semantic hallucination, since we only observe the
     final text, not how the OCR engine produced it.
  D. Original vs degraded comparison (CER_delta_pp / WER_delta_pp,
     in percentage points; positive = got worse under degradation)

Outputs:
  - evaluation/results.csv       (per page/version CER, WER, deltas)
  - evaluation/field_results.csv (per document, per field, raw + normalized match)
  - evaluation/suspicious_tokens.csv (flagged tokens with context)
  - Console summary
"""
import os
import re
import json
import csv
from jiwer import wer, cer

GT_DIR = "ground_truth/page_text"
OCR_ORIG_DIR = "ocr_output/original"
OCR_DEG_DIR = "ocr_output/degraded"
EVAL_DIR = "evaluation"
os.makedirs(EVAL_DIR, exist_ok=True)

PAGES = ([("docA", f"p{i}") for i in range(1, 28)] +
         [("docB", f"p{i}") for i in range(1, 23)] +
         [("docC", f"p{i}") for i in range(1, 38)])

DOC_PAGES = {"docA": [f"p{i}" for i in range(1, 28)],
             "docB": [f"p{i}" for i in range(1, 23)],
             "docC": [f"p{i}" for i in range(1, 38)]}

KNOWN_BLANK_PAGES = {("docB", "p2"), ("docB", "p4"), ("docB", "p6")}


def read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def normalize(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def normalize_for_field_match(text):
    t = re.sub(r"\s+", "", text)
    t = t.replace("/", "-").replace(".", "-")
    return t


def tokenize(text):
    return re.findall(r"[\w\u0900-\u097F]+", text.lower())


def levenshtein(a, b):
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def suspicious_token_check(gt_text, ocr_text, edit_ratio_threshold=0.5, min_len=4):
    gt_tokens = set(tokenize(gt_text))
    ocr_tokens = tokenize(ocr_text)
    flagged = []
    for tok in ocr_tokens:
        if len(tok) < min_len:
            continue
        if tok in gt_tokens:
            continue
        best_ratio = 0
        for g in gt_tokens:
            if abs(len(g) - len(tok)) > max(len(tok), len(g)) * edit_ratio_threshold:
                continue
            dist = levenshtein(tok, g)
            ratio = 1 - dist / max(len(tok), len(g))
            if ratio > best_ratio:
                best_ratio = ratio
        if best_ratio < 0.5:
            flagged.append(tok)
    return flagged


def field_match(field_value, haystack_text):
    """Raw exact-match check (whitespace-insensitive AND case-insensitive):
    does the ground-truth field value appear verbatim in the OCR'd text?
    Case-insensitive because several fields in these documents are printed
    in a mix of Title Case and ALL CAPS by the source system itself (e.g.
    the tehsil name appears as 'BADONI' in a table on one part of the page
    and would be transcribed as 'Badoni' in ground truth) -- that is a
    formatting difference in the source, not an OCR transcription error,
    and should not be counted as a field-accuracy failure."""
    if isinstance(field_value, list):
        return any(field_match(v, haystack_text) for v in field_value)
    val_norm = re.sub(r"\s+", "", str(field_value)).lower()
    haystack_norm = re.sub(r"\s+", "", haystack_text).lower()
    return bool(val_norm) and val_norm in haystack_norm


def field_match_normalized(field_value, haystack_text):
    if isinstance(field_value, list):
        return any(field_match_normalized(v, haystack_text) for v in field_value)
    val_norm = normalize_for_field_match(str(field_value)).lower()
    haystack_norm = normalize_for_field_match(haystack_text).lower()
    return bool(val_norm) and val_norm in haystack_norm


results = []
for doc, page in PAGES:
    gt = normalize(read(f"{GT_DIR}/{doc}_{page}.txt"))
    ocr_orig = normalize(read(f"{OCR_ORIG_DIR}/{doc}_{page}.txt"))
    ocr_deg = normalize(read(f"{OCR_DEG_DIR}/{doc}_{page}.txt"))
    is_blank_page = (doc, page) in KNOWN_BLANK_PAGES

    cer_orig = cer(gt, ocr_orig) if gt and ocr_orig else (0.0 if not gt and not ocr_orig else (1.0 if not gt else None))
    wer_orig = wer(gt, ocr_orig) if gt and ocr_orig else (0.0 if not gt and not ocr_orig else (1.0 if not gt else None))
    cer_deg = cer(gt, ocr_deg) if gt and ocr_deg else (0.0 if not gt and not ocr_deg else (1.0 if not gt else None))
    wer_deg = wer(gt, ocr_deg) if gt and ocr_deg else (0.0 if not gt and not ocr_deg else (1.0 if not gt else None))

    results.append({
        "document": doc, "page": page,
        "is_known_blank_page": is_blank_page,
        "gt_chars": len(gt), "gt_words": len(gt.split()),
        "CER_original": round(cer_orig, 4) if cer_orig is not None else "",
        "WER_original": round(wer_orig, 4) if wer_orig is not None else "",
        "CER_degraded": round(cer_deg, 4) if cer_deg is not None else "",
        "WER_degraded": round(wer_deg, 4) if wer_deg is not None else "",
        "CER_delta_pp": round((cer_deg - cer_orig) * 100, 2) if (cer_orig is not None and cer_deg is not None) else "",
        "WER_delta_pp": round((wer_deg - wer_orig) * 100, 2) if (wer_orig is not None and wer_deg is not None) else "",
    })

with open(f"{EVAL_DIR}/results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

with open("ground_truth/critical_fields.json", encoding="utf-8") as f:
    fields = json.load(f)

field_rows = []
for doc in ["docA", "docB", "docC"]:
    doc_fields = fields[doc]["fields"]
    combined_orig = " ".join(normalize(read(f"{OCR_ORIG_DIR}/{doc}_{p}.txt")) for p in DOC_PAGES[doc])
    combined_deg = " ".join(normalize(read(f"{OCR_DEG_DIR}/{doc}_{p}.txt")) for p in DOC_PAGES[doc])
    for fname, finfo in doc_fields.items():
        val = finfo["value"]
        field_rows.append({
            "document": doc,
            "field": fname,
            "ground_truth_value": json.dumps(val, ensure_ascii=False) if isinstance(val, list) else val,
            "match_original_raw": field_match(val, combined_orig),
            "match_original_normalized": field_match_normalized(val, combined_orig),
            "match_degraded_raw": field_match(val, combined_deg),
            "match_degraded_normalized": field_match_normalized(val, combined_deg),
        })

with open(f"{EVAL_DIR}/field_results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=field_rows[0].keys())
    writer.writeheader()
    writer.writerows(field_rows)

field_acc_orig_raw = sum(r["match_original_raw"] for r in field_rows) / len(field_rows)
field_acc_deg_raw = sum(r["match_degraded_raw"] for r in field_rows) / len(field_rows)
field_acc_orig_norm = sum(r["match_original_normalized"] for r in field_rows) / len(field_rows)
field_acc_deg_norm = sum(r["match_degraded_normalized"] for r in field_rows) / len(field_rows)

suspicious_rows = []
for doc, page in PAGES:
    gt = normalize(read(f"{GT_DIR}/{doc}_{page}.txt"))
    for label, ocr_dir in [("original", OCR_ORIG_DIR), ("degraded", OCR_DEG_DIR)]:
        ocr_text = normalize(read(f"{ocr_dir}/{doc}_{page}.txt"))
        is_blank_page = (doc, page) in KNOWN_BLANK_PAGES
        if is_blank_page:
            if ocr_text:
                suspicious_rows.append({
                    "document": doc, "page": page, "version": label,
                    "suspicious_token": "[ENTIRE OUTPUT -- BLANK PAGE PRODUCED NON-EMPTY OCR TEXT]",
                })
            continue
        if not gt or not ocr_text:
            continue
        flagged = suspicious_token_check(gt, ocr_text)
        for tok in flagged:
            suspicious_rows.append({"document": doc, "page": page, "version": label, "suspicious_token": tok})

with open(f"{EVAL_DIR}/suspicious_tokens.csv", "w", newline="", encoding="utf-8") as f:
    if suspicious_rows:
        writer = csv.DictWriter(f, fieldnames=suspicious_rows[0].keys())
        writer.writeheader()
        writer.writerows(suspicious_rows)
    else:
        f.write("document,page,version,suspicious_token\n")

print("=" * 70)
print("OCR EVALUATION SUMMARY")
print("=" * 70)

scored_results = [r for r in results if not r["is_known_blank_page"]]
valid_orig_cer = [r["CER_original"] for r in scored_results if r["CER_original"] != ""]
valid_orig_wer = [r["WER_original"] for r in scored_results if r["WER_original"] != ""]
valid_deg_cer = [r["CER_degraded"] for r in scored_results if r["CER_degraded"] != ""]
valid_deg_wer = [r["WER_degraded"] for r in scored_results if r["WER_degraded"] != ""]

print(f"\nOverall (avg across {len(valid_orig_cer)} text-bearing pages; "
      f"{len(KNOWN_BLANK_PAGES)} known-blank pages reported separately below):")
print(f"  Original  -> CER: {sum(valid_orig_cer)/len(valid_orig_cer):.4f}   WER: {sum(valid_orig_wer)/len(valid_orig_wer):.4f}")
print(f"  Degraded  -> CER: {sum(valid_deg_cer)/len(valid_deg_cer):.4f}   WER: {sum(valid_deg_wer)/len(valid_deg_wer):.4f}")
print(f"  Degradation impact -> CER +{(sum(valid_deg_cer)/len(valid_deg_cer) - sum(valid_orig_cer)/len(valid_orig_cer))*100:.2f}pp"
      f"   WER +{(sum(valid_deg_wer)/len(valid_deg_wer) - sum(valid_orig_wer)/len(valid_orig_wer))*100:.2f}pp")

print(f"\nPer-page results:")
for r in results:
    tag = " [BLANK PAGE]" if r["is_known_blank_page"] else ""
    print(f"  {r['document']}_{r['page']}{tag}: CER {r['CER_original']}->{r['CER_degraded']}  |  WER {r['WER_original']}->{r['WER_degraded']}")

print(f"\n--- Blank-page robustness finding ---")
for doc, page in sorted(KNOWN_BLANK_PAGES):
    ocr_o = read(f"{OCR_ORIG_DIR}/{doc}_{page}.txt").strip()
    ocr_d = read(f"{OCR_DEG_DIR}/{doc}_{page}.txt").strip()
    status_o = "FAIL -- produced non-empty output on blank input" if ocr_o else "PASS -- correctly returned empty output"
    status_d = "FAIL -- produced non-empty output on blank input" if ocr_d else "PASS -- correctly returned empty output"
    print(f"  {doc}_{page}: original={status_o} | degraded={status_d}")

print(f"\nCritical field accuracy across all {len(field_rows)} fields (owner/buyer names counted as one field per document, matching if ANY listed name is found):")
print(f"  RAW exact match        -> Original: {field_acc_orig_raw:.1%}   Degraded: {field_acc_deg_raw:.1%}")
print(f"  NORMALIZED exact match -> Original: {field_acc_orig_norm:.1%}   Degraded: {field_acc_deg_norm:.1%}")
print(f"  (Normalized match tolerates whitespace and date-separator style differences only -- e.g. 09-01-2026 vs 09/01/2026 -- never spelling/digit differences. Raw match is the primary, stricter metric.)")

print(f"\nFields that failed RAW exact match on ORIGINAL images (need attention regardless of degradation):")
for r in field_rows:
    if not r["match_original_raw"]:
        print(f"  [{r['document']}] {r['field']}: {r['ground_truth_value']}")

non_blank_suspicious = [r for r in suspicious_rows if "BLANK PAGE" not in r["suspicious_token"]]
blank_page_failures = [r for r in suspicious_rows if "BLANK PAGE" in r["suspicious_token"]]
print(f"\nSuspicious/unsupported-token check: {len(non_blank_suspicious)} tokens flagged across all pages/versions.")
print(f"  These are OCR output tokens with no plausible edit-distance relationship to any ground-truth token --")
print(f"  candidates for human review, NOT a confirmed count of 'hallucinations' (many are ordinary OCR recognition")
print(f"  errors, e.g. Tesseract's English language model reading misrecognized Devanagari glyphs as Latin fragments).")
if non_blank_suspicious:
    print("  Sample flagged tokens:")
    for r in non_blank_suspicious[:10]:
        print(f"    [{r['document']}_{r['page']}/{r['version']}] '{r['suspicious_token']}'")
if blank_page_failures:
    print(f"  Separately: {len(blank_page_failures)} case(s) where a BLANK ground-truth page produced non-empty OCR")
    print(f"  output entirely -- this is the strongest, least ambiguous finding in this check (see blank-page section above).")

print("\nCSV outputs written to evaluation/: results.csv, field_results.csv, suspicious_tokens.csv")
