"""
Reusable evaluation logic, refactored out of evaluate.py so it can be
called for ONE document at a time on demand (used by app.py's "Run"
buttons), instead of always processing all 3 documents at once.
"""
import os
import re
import json
from jiwer import wer, cer

GT_DIR = "ground_truth/page_text"
OCR_ORIG_DIR = "ocr_output/original"
OCR_DEG_DIR = "ocr_output/degraded"

DOC_PAGE_COUNT = {"docA": 27, "docB": 22, "docC": 37}
KNOWN_BLANK_PAGES = {("docB", "p2"), ("docB", "p4"), ("docB", "p6")}

DOC_LABELS = {
    "docA": "Document A -- MP22IGR17182026A100034741.pdf",
    "docB": "Document B -- DocScanner_Apr_21__2026_6-48_PM.pdf (scanned, no text layer)",
    "docC": "Document C -- MP22IGR17182025A100911603__2_.pdf",
}


def read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def normalize(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


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
        if len(tok) < min_len or tok in gt_tokens:
            continue
        best_ratio = 0
        for g in gt_tokens:
            if abs(len(g) - len(tok)) > max(len(tok), len(g)) * edit_ratio_threshold:
                continue
            dist = levenshtein(tok, g)
            ratio = 1 - dist / max(len(tok), len(g))
            best_ratio = max(best_ratio, ratio)
        if best_ratio < 0.5:
            flagged.append(tok)
    return flagged


def field_match(field_value, haystack_text):
    if isinstance(field_value, list):
        return any(field_match(v, haystack_text) for v in field_value)
    val_norm = re.sub(r"\s+", "", str(field_value)).lower()
    haystack_norm = re.sub(r"\s+", "", haystack_text).lower()
    return bool(val_norm) and val_norm in haystack_norm


def run_evaluation_for_doc(doc_key):
    """
    Runs the full evaluation (CER/WER, field accuracy, suspicious tokens,
    blank-page check) for ONE document, reading the already-generated
    ground truth and OCR output files from disk. Returns a plain dict,
    JSON-serializable, ready to send to the browser.
    """
    log = []
    log.append(f"Loading ground truth and OCR output for {doc_key}...")

    n_pages = DOC_PAGE_COUNT[doc_key]
    pages = [f"p{i}" for i in range(1, n_pages + 1)]

    page_rows = []
    for page in pages:
        gt = normalize(read(f"{GT_DIR}/{doc_key}_{page}.txt"))
        ocr_o = normalize(read(f"{OCR_ORIG_DIR}/{doc_key}_{page}.txt"))
        ocr_d = normalize(read(f"{OCR_DEG_DIR}/{doc_key}_{page}.txt"))
        is_blank = (doc_key, page) in KNOWN_BLANK_PAGES

        cer_o = cer(gt, ocr_o) if gt and ocr_o else (0.0 if not gt and not ocr_o else (1.0 if not gt else None))
        wer_o = wer(gt, ocr_o) if gt and ocr_o else (0.0 if not gt and not ocr_o else (1.0 if not gt else None))
        cer_d = cer(gt, ocr_d) if gt and ocr_d else (0.0 if not gt and not ocr_d else (1.0 if not gt else None))
        wer_d = wer(gt, ocr_d) if gt and ocr_d else (0.0 if not gt and not ocr_d else (1.0 if not gt else None))

        page_rows.append({
            "page": page, "is_blank": is_blank,
            "cer_original": cer_o, "wer_original": wer_o,
            "cer_degraded": cer_d, "wer_degraded": wer_d,
            "ocr_original_sample": ocr_o[:200], "ocr_degraded_sample": ocr_d[:200],
        })

    log.append(f"Scored {len(pages)} pages (CER/WER, original vs degraded).")

    scored = [r for r in page_rows if not r["is_blank"]]
    avg = lambda key: round(sum(r[key] for r in scored if r[key] is not None) / max(1, len([r for r in scored if r[key] is not None])), 4)

    log.append("Running critical-field exact-match check...")
    with open("ground_truth/critical_fields.json", encoding="utf-8") as f:
        all_fields = json.load(f)
    doc_fields = all_fields[doc_key]["fields"]
    combined_orig = " ".join(normalize(read(f"{OCR_ORIG_DIR}/{doc_key}_{p}.txt")) for p in pages)
    combined_deg = " ".join(normalize(read(f"{OCR_DEG_DIR}/{doc_key}_{p}.txt")) for p in pages)

    field_rows = []
    for fname, finfo in doc_fields.items():
        val = finfo["value"]
        field_rows.append({
            "field": fname,
            "value": val,
            "match_original": field_match(val, combined_orig),
            "match_degraded": field_match(val, combined_deg),
        })
    field_acc_orig = round(sum(r["match_original"] for r in field_rows) / len(field_rows), 4)
    field_acc_deg = round(sum(r["match_degraded"] for r in field_rows) / len(field_rows), 4)
    log.append(f"Field accuracy: {field_acc_orig:.1%} (original), {field_acc_deg:.1%} (degraded).")

    log.append("Running suspicious/unsupported-token check...")
    suspicious = []
    blank_findings = []
    for page in pages:
        gt = normalize(read(f"{GT_DIR}/{doc_key}_{page}.txt"))
        is_blank = (doc_key, page) in KNOWN_BLANK_PAGES
        for version, ocr_dir in [("original", OCR_ORIG_DIR), ("degraded", OCR_DEG_DIR)]:
            ocr_text = normalize(read(f"{ocr_dir}/{doc_key}_{page}.txt"))
            if is_blank:
                blank_findings.append({
                    "page": page, "version": version,
                    "result": "FAIL -- produced text on blank page" if ocr_text else "PASS -- correctly empty",
                    "sample": ocr_text[:150] if ocr_text else "",
                })
                continue
            if not gt or not ocr_text:
                continue
            for tok in suspicious_token_check(gt, ocr_text):
                suspicious.append({"page": page, "version": version, "token": tok})

    log.append(f"Flagged {len(suspicious)} suspicious tokens; {len(blank_findings)} blank-page checks.")
    log.append("Done.")

    return {
        "document": doc_key,
        "label": DOC_LABELS[doc_key],
        "pages_evaluated": len(pages),
        "cer_original": avg("cer_original"),
        "cer_degraded": avg("cer_degraded"),
        "wer_original": avg("wer_original"),
        "wer_degraded": avg("wer_degraded"),
        "field_accuracy_original": field_acc_orig,
        "field_accuracy_degraded": field_acc_deg,
        "field_details": field_rows,
        "blank_page_findings": blank_findings,
        "suspicious_token_count": len(suspicious),
        "sample_suspicious_tokens": suspicious[:12],
        "all_suspicious_tokens": suspicious,
        "per_page": page_rows,
        "log": log,
    }
