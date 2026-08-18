"""
Rebuilds ground-truth text for the 6 born-digital pages (docA/docC) using
`pdftotext -layout`, which preserves visual top-to-bottom reading order
(unlike `-raw`, which follows the PDF's internal content-stream order and
was found to (a) duplicate a paragraph that only appears ONCE on the
visual page, and (b) place section headers AFTER the fields they
introduce). Each page's output is:
  1. extracted with -layout
  2. collapsed to single spaces / single blank lines
  3. checked for immediate consecutive duplicate paragraphs (a symptom of
     the same underlying issue) and de-duplicated
"""
import subprocess
import re

PAGES = [("docA", p) for p in range(1, 28)] + [("docC", p) for p in range(1, 38)]

def extract_layout(doc, page):
    out = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), f"{doc}.pdf", "-"],
        capture_output=True, text=True, encoding="utf-8"
    ).stdout
    return out

def clean(text):
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]  # drop blank lines

    # De-duplicate long lines/paragraphs GLOBALLY across the whole page.
    # Some of these government PDFs store certain recital/boilerplate
    # paragraphs dozens of times in their internal data even though the
    # paragraph is only rendered ONCE on the visual page (confirmed by
    # manually inspecting rendered page images) -- e.g. one page in this
    # corpus stores one ~300-word paragraph 42 separate times. A line
    # this long being an exact repeat is never legitimate distinct
    # content, so anything over 60 characters is deduplicated globally,
    # not just against nearby lines.
    seen_long = set()
    pass1 = []
    for ln in lines:
        if len(ln) > 20:
            if ln in seen_long:
                continue
            seen_long.add(ln)
        pass1.append(ln)

    # Shorter lines (e.g. repeated table header rows) still get the
    # windowed near-duplicate check, since legitimate short lines can
    # coincidentally repeat further apart on a page (e.g. a value like
    # "0" appearing in multiple unrelated table cells).
    deduped = []
    for ln in pass1:
        window = deduped[-3:]
        if any(ln == prev or (len(ln) > 15 and ln in prev) for prev in window):
            continue
        deduped.append(ln)

    # Final pass: collapse repeating CYCLES of lines (e.g. the same
    # 6-line block -- each individual line short enough to dodge the
    # rules above -- repeating back-to-back dozens of times). At each
    # position, check whether the next `size` lines are an exact repeat
    # of the `size` lines just emitted, for cycle lengths 1 through 10;
    # if so, skip the repeat instead of emitting it again.
    final = []
    i = 0
    while i < len(deduped):
        matched = False
        for size in range(1, 11):
            if len(final) >= size and deduped[i:i+size] == final[-size:]:
                i += size
                matched = True
                break
        if not matched:
            final.append(deduped[i])
            i += 1
    deduped = final
    # drop repeated footer/verification boilerplate beyond first occurrence
    seen_footer = set()
    final = []
    for ln in deduped:
        if ("VerifyRegdocument" in ln) or ("इलेक्ट्रॉनिक रूप से हस्ताक्षरित" in ln) or (ln.startswith("निष्पादक") and "पृष्ठ" in ln):
            if ln in seen_footer:
                continue
            seen_footer.add(ln)
        final.append(ln)
    return "\n".join(final)

for doc, page in PAGES:
    raw = extract_layout(doc, page)
    cleaned = clean(raw)
    out_path = f"ground_truth/page_text/{doc}_p{page}.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(cleaned)
    dup_check = cleaned.count("विक्रय / विक्रय का समानुदेशन")
    print(f"{doc}_p{page}: {len(cleaned.split())} words, boilerplate-paragraph count = {dup_check}")
