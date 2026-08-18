"""
Local web app: a UI with a real "Run" button per document. Clicking a
button calls the Flask server, which runs the actual evaluation code
(evaluation_lib.py) against that document's ground truth and OCR output
files on disk, and returns fresh results to display in the browser.

Run with:  python app.py
Then open: http://localhost:5000
"""
from flask import Flask, jsonify, render_template_string
from evaluation_lib import run_evaluation_for_doc, DOC_LABELS

app = Flask(__name__)

PAGE_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OCR Evaluation Console</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
  :root{
    --ink:#1B2A4A; --ink-deep:#101a30; --parchment:#F7F3EA; --paper:#FFFFFF;
    --seal-red:#A23B2E; --brass:#B8934A; --forest:#3F6B4F; --text:#262220;
    --text-soft:#5b5750; --line:#E3DACB;
  }
  *{box-sizing:border-box;}
  body{margin:0; background:var(--parchment); color:var(--text); font-family:'IBM Plex Sans',sans-serif; line-height:1.55;}
  h1,h2,h3{font-family:'Source Serif 4',serif; margin:0; color:var(--ink);}
  .mono{font-family:'IBM Plex Mono',monospace;}
  header{background:linear-gradient(180deg,var(--ink-deep),var(--ink)); color:var(--parchment); padding:40px 32px 32px; border-bottom:5px solid var(--brass);}
  header .inner{max-width:980px; margin:0 auto;}
  .eyebrow{font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:0.14em; text-transform:uppercase; color:var(--brass); margin-bottom:10px;}
  header h1{color:#fff; font-size:30px;}
  header p{color:#cdd6e8; font-size:14.5px; margin-top:8px; max-width:640px;}
  main{max-width:980px; margin:0 auto; padding:36px 32px 90px;}
  .btn-row{display:flex; gap:14px; flex-wrap:wrap; margin-bottom:32px;}
  .run-btn{
    flex:1; min-width:220px; background:var(--ink); color:#fff; border:none; border-radius:6px;
    padding:18px 20px; font-family:'IBM Plex Sans',sans-serif; font-size:15px; font-weight:600;
    cursor:pointer; text-align:left; transition:background 0.15s, transform 0.1s;
    border-left:4px solid var(--brass);
  }
  .run-btn:hover{background:#233a63;}
  .run-btn:active{transform:scale(0.98);}
  .run-btn:disabled{opacity:0.6; cursor:wait;}
  .run-btn .doc-name{display:block; font-size:11px; font-family:'IBM Plex Mono',monospace; color:var(--brass); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;}

  .console{
    background:var(--ink-deep); color:#a8f0c6; font-family:'IBM Plex Mono',monospace; font-size:13px;
    border-radius:6px; padding:18px 20px; min-height:60px; margin-bottom:32px; white-space:pre-wrap;
    display:none;
  }
  .console .line{opacity:0; animation:fadein 0.25s forwards;}
  @keyframes fadein{to{opacity:1;}}

  .results{display:none;}
  .metric-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:28px;}
  .metric-card{background:var(--paper); border:1px solid var(--line); border-radius:4px; padding:20px; cursor:pointer; transition:box-shadow 0.15s, border-color 0.15s;}
  .metric-card:hover{box-shadow:0 2px 10px rgba(27,42,74,0.12); border-color:var(--brass);}
  .metric-card .tag{font-family:'IBM Plex Mono',monospace; font-size:10.5px; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-soft); margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;}
  .metric-card .expand-hint{font-size:14px; color:var(--brass); transition:transform 0.15s;}
  .metric-card.open .expand-hint{transform:rotate(180deg);}
  .metric-row{display:flex; align-items:baseline; gap:8px;}
  .metric-val{font-family:'Source Serif 4',serif; font-size:28px; font-weight:600; color:var(--ink);}
  .metric-val.bad{color:var(--seal-red);}
  .metric-arrow{color:var(--text-soft);}

  table{width:100%; border-collapse:collapse; background:var(--paper); font-size:14px; margin-bottom:24px;}
  thead th{text-align:left; font-family:'IBM Plex Mono',monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.06em; color:var(--text-soft); padding:10px 14px; border-bottom:2px solid var(--ink);}
  tbody td{padding:10px 14px; border-bottom:1px solid var(--line);}
  .badge{display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; padding:3px 9px; border-radius:20px;}
  .badge.ok{background:rgba(63,107,79,0.12); color:var(--forest);}
  .badge.no{background:rgba(162,59,46,0.12); color:var(--seal-red);}

  .blank-section{display:none; margin-bottom:24px;}
  .stamp-row{display:flex; gap:14px; flex-wrap:wrap;}
  .stamp{flex:1; min-width:200px; border:2px solid; border-radius:6px; padding:14px 16px;}
  .stamp.fail{border-color:var(--seal-red); background:rgba(162,59,46,0.05);}
  .stamp.pass{border-color:var(--forest); background:rgba(63,107,79,0.05);}
  .stamp .verdict{font-family:'Source Serif 4',serif; font-weight:700; font-size:13.5px; text-transform:uppercase;}
  .stamp.fail .verdict{color:var(--seal-red);}
  .stamp.pass .verdict{color:var(--forest);}
  .stamp .sample{font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--text-soft); margin-top:6px; word-break:break-word;}

  h3.section-title{font-size:17px; margin-bottom:12px; padding-bottom:8px; border-bottom:2px solid var(--line);}

  .detail-panel{
    background:var(--paper); border:1.5px solid var(--brass); border-radius:6px;
    padding:20px 22px; margin-bottom:28px; max-height:420px; overflow-y:auto;
  }
  .detail-panel h4{font-family:'Source Serif 4',serif; font-size:15px; margin-bottom:12px; color:var(--ink);}
  .detail-panel table{margin-bottom:0;}
  .detail-panel .blank-tag{font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--brass); text-transform:uppercase; margin-left:6px;}
  .detail-note{font-size:12.5px; color:var(--text-soft); margin-top:10px; margin-bottom:0;}
</style>
</head>
<body>

<header>
  <div class="inner">
    <div class="eyebrow">OCR Evaluation Console</div>
    <h1>Run the evaluation live, per document</h1>
    <p>Click a button below to re-run the actual scoring code (evaluation_lib.py) against that document's ground truth and OCR output files, right now.</p>
  </div>
</header>

<main>
  <div class="btn-row">
    <button class="run-btn" onclick="runDoc('docA')"><span class="doc-name">Document A</span>Run Evaluation</button>
    <button class="run-btn" onclick="runDoc('docB')"><span class="doc-name">Document B (scanned)</span>Run Evaluation</button>
    <button class="run-btn" onclick="runDoc('docC')"><span class="doc-name">Document C</span>Run Evaluation</button>
  </div>

  <div class="console" id="console"></div>

  <div class="results" id="results">
    <h2 id="result-title" style="margin-bottom:20px;"></h2>

    <div class="metric-grid">
      <div class="metric-card" id="card-cer" onclick="toggleDetail('cer')">
        <div class="tag">Character Error Rate <span class="expand-hint">&#9660;</span></div>
        <div class="metric-row"><span class="metric-val" id="cer-o"></span><span class="metric-arrow">&rarr;</span><span class="metric-val bad" id="cer-d"></span></div>
      </div>
      <div class="metric-card" id="card-wer" onclick="toggleDetail('wer')">
        <div class="tag">Word Error Rate <span class="expand-hint">&#9660;</span></div>
        <div class="metric-row"><span class="metric-val" id="wer-o"></span><span class="metric-arrow">&rarr;</span><span class="metric-val bad" id="wer-d"></span></div>
      </div>
      <div class="metric-card" id="card-field" onclick="toggleDetail('field')">
        <div class="tag">Critical Field Accuracy <span class="expand-hint">&#9660;</span></div>
        <div class="metric-row"><span class="metric-val" id="field-o"></span><span class="metric-arrow">&rarr;</span><span class="metric-val" id="field-d"></span></div>
      </div>
      <div class="metric-card" id="card-susp" onclick="toggleDetail('susp')">
        <div class="tag">Suspicious Tokens Flagged <span class="expand-hint">&#9660;</span></div>
        <div class="metric-row"><span class="metric-val" id="susp-count"></span></div>
      </div>
    </div>

    <div class="detail-panel" id="detail-cer" style="display:none;"></div>
    <div class="detail-panel" id="detail-wer" style="display:none;"></div>
    <div class="detail-panel" id="detail-field" style="display:none;"></div>
    <div class="detail-panel" id="detail-susp" style="display:none;"></div>

    <div class="blank-section" id="blank-section">
      <h3 class="section-title">Blank Page Findings</h3>
      <div class="stamp-row" id="blank-stamps"></div>
    </div>

    <h3 class="section-title">Critical Field Results</h3>
    <table>
      <thead><tr><th>Field</th><th>Value</th><th>Original</th><th>Degraded</th></tr></thead>
      <tbody id="field-table-body"></tbody>
    </table>
  </div>
</main>

<script>
let lastResult = null;

async function runDoc(docId) {
  const buttons = document.querySelectorAll('.run-btn');
  buttons.forEach(b => b.disabled = true);

  // Close any open detail panels from a previous run
  ['cer','wer','field','susp'].forEach(k => {
    document.getElementById('detail-'+k).style.display = 'none';
    document.getElementById('card-'+k).classList.remove('open');
  });

  const consoleEl = document.getElementById('console');
  consoleEl.style.display = 'block';
  consoleEl.innerHTML = '';
  document.getElementById('results').style.display = 'none';

  const addLine = (text) => {
    const div = document.createElement('div');
    div.className = 'line';
    div.textContent = '> ' + text;
    consoleEl.appendChild(div);
  };

  addLine('Sending request to evaluation server...');

  try {
    const resp = await fetch('/run/' + docId);
    const data = await resp.json();

    if (data.error) {
      addLine('ERROR: ' + data.error);
      buttons.forEach(b => b.disabled = false);
      return;
    }

    for (const line of data.log) {
      await new Promise(r => setTimeout(r, 220));
      addLine(line);
    }

    lastResult = data;

    // Populate results
    document.getElementById('result-title').textContent = data.label + ' -- ' + data.pages_evaluated + ' pages evaluated';
    document.getElementById('cer-o').textContent = (data.cer_original*100).toFixed(1) + '%';
    document.getElementById('cer-d').textContent = (data.cer_degraded*100).toFixed(1) + '%';
    document.getElementById('wer-o').textContent = (data.wer_original*100).toFixed(1) + '%';
    document.getElementById('wer-d').textContent = (data.wer_degraded*100).toFixed(1) + '%';
    document.getElementById('field-o').textContent = (data.field_accuracy_original*100).toFixed(0) + '%';
    document.getElementById('field-d').textContent = (data.field_accuracy_degraded*100).toFixed(0) + '%';
    document.getElementById('susp-count').textContent = data.suspicious_token_count;

    const fieldBody = document.getElementById('field-table-body');
    fieldBody.innerHTML = '';
    for (const f of data.field_details) {
      const val = Array.isArray(f.value) ? f.value.join(', ') : f.value;
      const row = document.createElement('tr');
      row.innerHTML = `<td>${f.field}</td><td class="mono" style="font-size:12.5px;">${val}</td>` +
        `<td><span class="badge ${f.match_original ? 'ok' : 'no'}">${f.match_original ? 'correct' : 'wrong'}</span></td>` +
        `<td><span class="badge ${f.match_degraded ? 'ok' : 'no'}">${f.match_degraded ? 'correct' : 'wrong'}</span></td>`;
      fieldBody.appendChild(row);
    }

    const blankSection = document.getElementById('blank-section');
    const blankStamps = document.getElementById('blank-stamps');
    blankStamps.innerHTML = '';
    if (data.blank_page_findings && data.blank_page_findings.length > 0) {
      blankSection.style.display = 'block';
      for (const b of data.blank_page_findings) {
        const isFail = b.result.startsWith('FAIL');
        const div = document.createElement('div');
        div.className = 'stamp ' + (isFail ? 'fail' : 'pass');
        div.innerHTML = `<div class="verdict">${isFail ? 'FAIL' : 'PASS'} -- ${b.page} (${b.version})</div>` +
          (b.sample ? `<div class="sample">"${b.sample}"</div>` : '');
        blankStamps.appendChild(div);
      }
    } else {
      blankSection.style.display = 'none';
    }

    document.getElementById('results').style.display = 'block';
  } catch (e) {
    addLine('ERROR: ' + e.message);
  }

  buttons.forEach(b => b.disabled = false);
}

function toggleDetail(kind) {
  if (!lastResult) return;
  const panel = document.getElementById('detail-' + kind);
  const card = document.getElementById('card-' + kind);
  const isOpen = panel.style.display === 'block';

  // Close all panels first (only one open at a time, keeps it tidy)
  ['cer','wer','field','susp'].forEach(k => {
    document.getElementById('detail-'+k).style.display = 'none';
    document.getElementById('card-'+k).classList.remove('open');
  });

  if (isOpen) return; // user clicked the already-open one -> just close it

  panel.style.display = 'block';
  card.classList.add('open');

  if (kind === 'cer' || kind === 'wer') {
    const metricLabel = kind === 'cer' ? 'Character Error Rate' : 'Word Error Rate';
    const origKey = kind + '_original', degKey = kind + '_degraded';
    let rows = lastResult.per_page.map(p => {
      const blankTag = p.is_blank ? '<span class="blank-tag">blank page</span>' : '';
      const o = p[origKey], d = p[degKey];
      const fmt = v => (v === null || v === undefined) ? '--' : (v*100).toFixed(1) + '%';
      return `<tr><td class="mono">${p.page}${blankTag}</td><td class="mono">${fmt(o)}</td><td class="mono">${fmt(d)}</td></tr>`;
    }).join('');
    panel.innerHTML = `<h4>${metricLabel} -- every page, this document</h4>
      <table><thead><tr><th>Page</th><th>Original</th><th>Degraded</th></tr></thead>
      <tbody>${rows}</tbody></table>
      <p class="detail-note">Blank pages are excluded from the headline average shown above, since a trivial 0% or 100% on an empty page would distort it -- see the Blank Page Findings section for how those are scored instead.</p>`;

  } else if (kind === 'field') {
    panel.innerHTML = `<h4>Critical field results are shown in the table below</h4>
      <p class="detail-note">Scroll down to "Critical Field Results" to see exactly which of the ${lastResult.field_details.length} fields matched and which didn't, for this document.</p>`;
    panel.style.display = 'block';
    card.classList.add('open');
    setTimeout(() => {
      document.querySelector('h3.section-title').scrollIntoView({behavior:'smooth', block:'start'});
    }, 150);

  } else if (kind === 'susp') {
    const tokens = lastResult.all_suspicious_tokens || [];
    if (tokens.length === 0) {
      panel.innerHTML = `<h4>No suspicious tokens flagged for this document.</h4>`;
    } else {
      let rows = tokens.map(t =>
        `<tr><td class="mono">${t.page}</td><td class="mono">${t.version}</td><td class="mono">${t.token}</td></tr>`
      ).join('');
      panel.innerHTML = `<h4>All ${tokens.length} suspicious tokens flagged for this document</h4>
        <table><thead><tr><th>Page</th><th>Version</th><th>Flagged Token</th></tr></thead>
        <tbody>${rows}</tbody></table>
        <p class="detail-note">These are OCR output words with no plausible relationship to anything in the real document -- candidates for human review, not confirmed fabrications (most are ordinary misreads of Devanagari characters as Latin fragments).</p>`;
    }
  }
}
</script>

</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE_TEMPLATE)


@app.route("/run/<doc_id>")
def run(doc_id):
    if doc_id not in ("docA", "docB", "docC"):
        return jsonify({"error": f"Unknown document '{doc_id}'"}), 400
    result = run_evaluation_for_doc(doc_id)
    return jsonify(result)


if __name__ == "__main__":
    print("Starting server... open http://localhost:5000 in your browser")
    app.run(debug=False, port=5000)
