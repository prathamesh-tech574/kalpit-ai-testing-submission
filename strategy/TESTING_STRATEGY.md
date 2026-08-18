# Testing Strategy Document
## AI Testing Engineer Take-Home — OCR & Document AI Evaluation

---

## 1. Why these metrics (CER, WER, field-level exact match, suspicious/unsupported-token check)?

Each metric answers a different question, and none of them alone tells you whether the system is safe to trust in production.

- **CER (Character Error Rate)** answers *"how noisy is the transcription at the character level?"* It's the right metric for Devanagari, because Hindi is a conjunct/matra script where a single wrong character (e.g. a dropped matra) can silently change the reading of a whole word, and word-boundaries are less reliable delimiters than in English. CER also degrades more smoothly than WER, which makes it a better signal for tracking *gradual* quality drift (e.g. across scanner firmware updates).

- **WER (Word Error Rate)** answers *"how much would a human have to retype?"* It's the metric that maps most directly onto reviewer/operator cost, and it is far more punishing than CER — one wrong character in a word fails the whole word. Reporting both together is deliberate: a system can have low CER but high WER (many small errors spread across many different words) or the reverse (a few whole words dropped, or one badly-garbled string among otherwise perfect text) — and those two failure modes call for different fixes.

- **Critical-field exact-match accuracy** answers the question the business actually cares about: *"did we get the fields that carry legal and financial weight exactly right?"* CER/WER are computed over the whole page, so a document can score a very respectable CER while silently corrupting the one khasra number or registration date that matters. In a land registry, "95% CER" is meaningless if the 5% that's wrong is the owner's name. Field-level exact match (not fuzzy match) is deliberately strict, because land records don't tolerate "close enough" — a survey number off by one digit points to a different plot of land entirely.

- **Suspicious / unsupported-token check** answers a different question again: *"is any of this output actively unexplained by the source, rather than merely corrupted?"* This matters more for LLM-based or vision-model extraction pipelines than for classical OCR, but it's included here because the assignment explicitly asks for it, and it also catches a real classical-OCR failure mode worth watching for. To be precise about what this check can and can't claim: it flags OCR tokens with no plausible edit-distance relationship to any ground-truth token, as *candidates for human review* — it is a heuristic, not a proof of hallucination, since we only observe the final text rather than how the engine produced it. Token-similarity can be fooled in both directions (two correctly-read words merged by a missing space can look "unsupported"; a single wrong digit in a long ID can look "supported" by edit-distance despite being a materially different value). In this project's actual run, most of the 937 flagged tokens are ordinary OCR recognition errors — Tesseract's `eng` language-model component reading a misrecognized Devanagari glyph as a Latin-alphabet fragment (`fase`, `wart`, `args`) — not evidence of invented content. The one unambiguous, concrete finding from this check is a genuinely blank page (docB page 2) producing ~30 words of fabricated non-empty output while two other blank pages (4, 6) were handled correctly — that finding doesn't depend on the token-similarity heuristic at all, which is exactly why it's the strongest evidence in this category.

Together: CER/WER quantify "how much noise," field accuracy quantifies "does the noise touch anything that matters," and the suspicious-token check quantifies "is any of this worth a human's specific attention, even if the exact cause is ambiguous." A production gate should use all three, not just one.

**A related distinction worth being explicit about:** CER/WER measure *text recognition accuracy* — how close the transcription is to the source, character by character or word by word. Field accuracy measures something different and, for this system, more important: *business-critical accuracy* — whether the specific values that carry legal and financial weight (a khasra number, a registration date) came out exactly right. These two can diverge sharply: a page can score a very respectable CER while getting the one number that matters completely wrong, because CER/WER average over the whole page and a wrong khasra number is a handful of characters in a page of hundreds. This is why the assignment's evaluation criteria doesn't weight "high OCR accuracy" as the goal, and why this report always presents field accuracy as its own headline number rather than something inferred from the CER/WER average.

---

## 2. How would you expand this evaluation system for 100-200 real land registry documents?

The core pipeline (ground truth → OCR → metrics → report) doesn't need to change structurally, but several things must change to survive that scale:

- **Ground truth creation becomes the bottleneck, not the code.** At 3 documents it's feasible to hand-transcribe. At 100-200, full manual transcription of every page of every document is not realistic (these documents run 20-40 pages each; that's 2,000-8,000 pages). The fix is **tiered ground truth**: full manual transcription for a smaller "golden" stratified sample (e.g. 20-30 documents, chosen to cover the variety of formats/districts/scan quality seen in the corpus), and **critical-field-only** ground truth for the rest, captured via a lightweight double-entry / two-annotator-plus-adjudication workflow (two people independently key the 6-8 fields; a script flags disagreements for a third reviewer). Full-page CER/WER is then only reported reliably on the golden subset; field accuracy is reported across the whole 100-200.

- **Document clustering matters before you average anything.** These documents aren't identical in structure — this exercise alone turned up a born-digital PDF format (docA/docC) and a true photographed scan (docB) with meaningfully different baseline OCR difficulty. At 100-200 documents you will see multiple sub-registrar offices, multiple template versions, urban vs rural land records, and documents with actual handwriting or stamps overlapping text (which none of these 3 samples had). Metrics must be broken out **per cluster** (e.g. by source office, by born-digital-vs-scanned, by document age/print quality), not just reported as one blended average — a blended average can look fine while one entire cluster is silently failing.

- **Sampling strategy for the pipeline itself**: instead of every page of every document, run full-page OCR + evaluation on a random or stratified sample of pages per document (e.g. the pages most likely to contain critical fields, identified by a lightweight layout/keyword heuristic), and spot-check the rest. This is what was done here at small scale (3 pages/document instead of all 27-37) and the same judgment call scales up, just needs to be made more systematically and probabilistically rather than by hand-picking pages.

- **Automate field extraction**, not just field *matching*. At 3 documents, checking whether a known ground-truth string appears in OCR text is fine. At scale you need an actual extraction step (regex/layout-based or a lightweight NER model) that pulls candidate field values *out of* raw OCR text so the field-accuracy check can run unattended over new, unseen documents where you don't already know the expected value from having read the PDF text layer.

- **Build the golden/regression set at this stage**, since 100-200 real documents is exactly the range where you have enough variety to select a durable regression suite (see Q3) — pick this as version 1 of that set, weighted toward difficult/edge cases (poor scans, unusual boundaries language, multi-owner splits) rather than a uniform random sample, since edge cases are what regress silently.

---

## 3. How would you design continuous/automated testing for a production OCR pipeline (golden set + confidence-based human review)?

**Golden set management:**
- A versioned, held-out set of documents (see Q2) with locked, reviewed ground truth, stored separately from any data the OCR model or its prompts/config could ever be tuned against. Every pipeline change (OCR engine version, image preprocessing change, prompt change if an LLM step is involved) must run the full evaluation suite against this set *before* deployment, with the CER/WER/field-accuracy/suspicious-token numbers tracked over time as a dashboard, not just a pass/fail gate.
- The golden set itself needs periodic refresh — add newly-discovered edge cases (a new district's document template, a new degradation pattern seen in production) as they're found, and re-baseline. Treat it like a test suite in software: it should grow, not stay frozen at v1.
- Regression gates: define hard thresholds per cluster (e.g. "field accuracy on born-digital-scanned cluster must not drop more than 2 points from the last approved baseline") that block a release, not just an "overall CER improved" check that can mask a regression in one subgroup while other subgroups improve.

**Production monitoring beyond the golden set:**
- Since production documents don't have ground truth, use **confidence signals as a proxy**: Tesseract (and most OCR engines) expose per-character/per-word confidence scores. Track the distribution of these scores over time; a sudden shift (more low-confidence output than the recent baseline) is an early warning even without ground truth.
- **Confidence-based human review routing**: route any document where (a) a critical field's OCR confidence falls below a threshold, (b) the suspicious-token check flags a token inside a critical field's expected location, or (c) the extracted field fails a validation rule (e.g. area doesn't match the sum of sub-plot areas, registration number doesn't match the expected format/checksum) to a human reviewer queue, rather than accepting it silently. This turns "we don't have ground truth in production" into "we don't need ground truth for every document — we need it for the ones the system itself is unsure about."
- **Shadow/canary testing**: when upgrading OCR engine version or model, run the new version alongside the old one in production on a sample of live traffic (without acting on its output yet), and diff the two outputs' critical fields. Large disagreement rates trigger a hold before full rollout.
- **Scheduled re-runs of the golden set** (e.g. nightly or per-deploy) as a CI gate, with the dashboard from above surfaced to the team, not buried in logs.

---

## 4. What are the biggest risks if OCR errors go undetected in a land registry system, and how does the testing approach help?

- **Wrong owner recorded → wrongful transfer of legal title.** If a name is misread and never caught, someone could be recorded as the legal owner of land they have no claim to, or the true owner could lose recorded title. This is the single highest-severity risk category, since Indian land disputes are already a major source of litigation, and an automated pipeline that silently corrupts ownership records could manufacture disputes at scale rather than reduce them.
  *Mitigation*: strict, non-fuzzy field-level exact match on owner/father-name fields specifically (not just averaged into overall CER), plus routing any low-confidence owner-name extraction to mandatory human review before it's committed anywhere (see Q3).

- **Wrong survey/khasra number → land parcel confusion.** A single misread digit in a khasra number can point to an entirely different, unrelated plot. Because these numbers are often visually similar strings of digits with hyphens/slashes (e.g. "54/1" vs "54/3", both real khasras in this very corpus, one character apart), this is exactly the kind of error classical CER/WER can under-report (a 1-in-20-character error looks trivial in an aggregate score) while being catastrophic in impact.
  *Mitigation*: field-level exact match specifically targets this; the strategy doc explicitly flags that "high OCR accuracy is not the goal" for this reason — a 98% CER pipeline that gets 2% of khasra numbers wrong is still unsafe if that 2% isn't caught before the record is finalized.

- **Wrong area/consideration amount → downstream stamp duty, registration fee, and tax miscalculation**, and potential grounds to challenge the registration's validity later. These are numeric fields where OCR digit confusion (0/8/6, 1/7, 3/8) is a known, well-documented weak point.
  *Mitigation*: numeric-field validation rules (e.g. sum of sub-plot areas equals stated total area, stamp duty is the expected percentage of guideline value) act as a sanity check independent of OCR confidence, catching internally-inconsistent extractions even when OCR "looks" confident.

- **Fabricated/unsupported text being trusted as if transcribed.** If any future stage of the pipeline uses an LLM or vision-language model to "clean up" or re-key OCR output, there's a real risk of the model producing plausible-sounding but wrong values (a name that "looks right" but isn't the actual name in the document) — arguably worse than a garbled OCR error, because a human reviewer is *less* likely to double-check text that reads cleanly.
  *Mitigation*: this is exactly what the suspicious/unsupported-token check is for — it exists specifically to surface output that has no traceable origin in the source for human review, and it should be run on any future LLM-assisted extraction stage as much as on raw Tesseract output. The clearest evidence of this failure mode in this project's own results is the blank-page finding (Q1 above and the report's "Blank Page Finding" sheet): a page with no source text at all still produced fabricated output, showing the risk is real even in a "boring" classical-OCR pipeline, not just a hypothetical LLM concern.

- **Systemic, silent degradation over time** (e.g. a scanner firmware update changes DPI/compression defaults, or a new sub-registrar office's documents use a different template) that erodes accuracy gradually enough that no single release looks alarming, but cumulative harm is large.
  *Mitigation*: the golden-set regression gate and production confidence monitoring (Q3) are designed precisely to catch this kind of slow drift, not just sudden, obvious breakage.

---

## 5. What additional robustness tests would you recommend beyond the degradations already performed?

This exercise covered a **combined** degradation (skew/rotation + reduced contrast/brightness + blur/noise + JPEG compression, applied together) on every page. One methodological change I'd make before relying on this for production decisions: **isolate degradation factors rather than always combining them**. A combined degradation answers "does quality matter overall," but not "which specific factor caused the failure" — if a page's field accuracy drops after degradation, a combined test can't say whether that was the rotation, the blur, or the compression. For production robustness testing I'd run each factor separately (rotation alone, blur alone, contrast alone, compression alone) plus the combination, and report a table like:

| Condition | CER | WER | Field Accuracy |
|---|---|---|---|
| Original | (baseline) | (baseline) | (baseline) |
| Rotation only | ... | ... | ... |
| Blur only | ... | ... | ... |
| Low contrast only | ... | ... | ... |
| Combined (this project's test) | ... | ... | ... |

That makes failure attribution possible, which a single combined number doesn't allow.

Beyond that, and beyond the degradations already performed:

- **Real handwriting.** Two of the 3 sample documents (docA, docC) are fully typeset/printed forms with no handwriting. The third (docB, the genuinely scanned document) does contain real handwriting — handwritten signatures from both parties and both witnesses on page 17 — which this project's OCR run already exercised, but a dedicated handwriting-focused test set (not just incidental coverage from one page) would be worth building, since handwriting recognition is a materially different problem from printed-text OCR and may need its own model/engine.
- **Stamps and seals overlapping text.** Real physical registry documents commonly have rubber-stamp impressions or embossed seals stamped directly over printed text — none of the 3 samples had this, but it's one of the most-cited real-world OCR failure modes for Indian government documents and should be explicitly represented in the test set (synthetically composited if real examples aren't available).
- **Multi-generation photocopies / re-scans** (a scan of a photocopy of a scan), which compounds noise and contrast loss in ways a single clean-image blur/JPEG pass doesn't fully capture.
- **Phone-camera-specific distortions**: perspective/keystone distortion (photographing a page at an angle, not just rotated in-plane), uneven lighting/shadow gradients across the page, and finger/thumb partially covering a corner — all common when field agents photograph documents rather than scan them, and different in character from the skew/blur/contrast tests already run.
- **Mixed-script and multilingual pages**: some fields in this corpus already mix Devanagari and Latin script on the same line (English translations of names in parentheses); a stress test with more aggressive script-mixing, or documents that switch primary language entirely (e.g. an English-language colonial-era record or an Urdu-script historical record), would test whether the language model configuration (`hin+eng` here) generalizes or needs per-cluster tuning.
- **Low-resolution source images.** All tests here started from a clean 300 DPI render; a realistic robustness suite should also test genuinely low-resolution inputs (e.g. 100-150 DPI, or a photo taken with an older phone camera), since resolution loss and blur are not the same failure mode and need separate coverage.
- **Adversarial/edge-case field values**: names with unusual characters or nukta marks, khasra numbers with fractional/compound formats (this corpus already has examples like "54/1", "120-121-122-123" — worth explicitly stress-testing parsers/matchers against these formats rather than assuming clean single integers), and multi-owner records with more than 2-3 parties (some pages in this corpus already list 4+ owners).
- **Redaction/masking artifacts**: these documents mask Aadhaar numbers as `XXXXXXXX1234` — worth testing that OCR/extraction doesn't misinterpret masked placeholder text as a real field value, or fail ungracefully on it.
