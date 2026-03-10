// ─── MERMAID INIT ─────────────────────────────────────────
mermaid.initialize({
  startOnLoad: false, theme: 'dark', darkMode: true,
  fontFamily: "'DM Mono', monospace", fontSize: 13,
  themeVariables: {
    primaryColor: '#242840', primaryTextColor: '#e2e8f8', primaryBorderColor: '#353c58',
    lineColor: '#7c6af7', secondaryColor: '#1c2030', tertiaryColor: '#141720',
    background: '#141720', mainBkg: '#1c2030', nodeBorder: '#353c58',
    clusterBkg: '#1c2030', titleColor: '#e2e8f8', edgeLabelBackground: '#141720',
  },
  flowchart: { curve: 'basis', padding: 20 },
  sequence: { actorMargin: 50, messageMargin: 30 },
});

// ─── MARKED SETUP ─────────────────────────────────────────
// Marked v12+ uses token objects in renderer callbacks
const renderer = new marked.Renderer();
let mermaidBlocks = [], mermaidIdx = 0;

renderer.code = function (token) {
  // v12+: token is { text, lang, escaped }
  const code = typeof token === 'object' ? (token.text || '') : token;
  const lang = typeof token === 'object' ? (token.lang || '') : arguments[1] || '';

  if (lang === 'mermaid') {
    const id = `mermaid-${Date.now()}-${mermaidIdx++}`;
    mermaidBlocks.push({ id, code });
    return `<div class="mermaid-wrapper" id="wrapper-${id}"><div class="mermaid" id="${id}">${escapeHtml(code)}</div></div>`;
  }
  const validLang = hljs.getLanguage(lang) ? lang : 'plaintext';
  const highlighted = hljs.highlight(code, { language: validLang }).value;
  return `<pre><code class="hljs language-${validLang}">${highlighted}</code></pre>`;
};

renderer.heading = function (token) {
  // v12+: token is { text, depth, raw }
  const text = typeof token === 'object' ? (token.text || '') : token;
  const level = typeof token === 'object' ? (token.depth || 1) : arguments[1] || 1;
  const textStr = String(text);
  const slug = textStr.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
  return `<h${level} id="${slug}">${textStr}</h${level}>`;
};

marked.setOptions({ renderer, breaks: true, gfm: true });

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ─── STATE ────────────────────────────────────────────────
let currentResult = null;
let rawReport = '';

// ─── ANALYSIS FLOW ────────────────────────────────────────
async function startAnalysis() {
  const urlInput = document.getElementById('github-url');
  const url = urlInput.value.trim();
  const errorEl = document.getElementById('error-msg');
  errorEl.style.display = 'none';

  if (!url || !url.startsWith('https://github.com/') || url.split('/').length < 5) {
    errorEl.textContent = '⚠️ Please enter a valid public GitHub URL (e.g. https://github.com/owner/repo)';
    errorEl.style.display = 'block';
    return;
  }

  // Disable input
  document.getElementById('analyze-btn').disabled = true;
  showProgress();

  try {
    // Start analysis job
    const resp = await fetch('/analyze-github', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ github_url: url }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Failed to start analysis');
    }

    const { job_id } = await resp.json();
    await streamResults(job_id);
  } catch (err) {
    errorEl.textContent = `❌ ${err.message}`;
    errorEl.style.display = 'block';
    hideProgress();
    document.getElementById('analyze-btn').disabled = false;
  }
}

async function streamResults(jobId) {
  const stepList = document.getElementById('step-list');

  const resp = await fetch(`/analyze-github/stream/${jobId}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const event = JSON.parse(line.slice(6));
        handleEvent(event, stepList);
      } catch (e) { /* skip malformed */ }
    }
  }
}

const STEP_LABELS = {
  clone: '📦 Cloning repository',
  clone_done: '📦 Repository cloned',
  analyzing: '🔬 Initializing pipeline',
  scan_repo: '📁 Scanning repository',
  extract_entities: '🏷️ Extracting entities',
  analyse_workflows: '🔀 Analyzing workflows',
  business_context: '💼 Business context',
  analyse_architecture: '🏗️ Architecture analysis',
  gap_analysis: '📊 Gap analysis',
  generate_report: '📝 Generating report',
  cleanup: '🧹 Cleaning up',
  complete: '✅ Analysis complete',
  error: '❌ Error',
};

function handleEvent(event, stepList) {
  const progress = event.progress || 0;
  document.getElementById('progress-fill').style.width = progress + '%';
  document.getElementById('progress-pct').textContent = progress + '%';

  // Add step to list
  const label = STEP_LABELS[event.step] || event.step;
  const icon = event.step === 'error' ? '❌' : progress >= 100 ? '✅' : '⏳';

  const item = document.createElement('div');
  item.className = `step-item ${event.step === 'error' ? 'error' : 'done'} fade-in`;
  item.innerHTML = `<span class="step-icon">${icon}</span> ${label}`;
  stepList.appendChild(item);
  stepList.scrollTop = stepList.scrollHeight;

  // Handle completion
  if (event.step === 'complete' && event.result) {
    currentResult = event.result;
    rawReport = event.result.report || '';
    setTimeout(() => {
      hideProgress();
      showResults();
      document.getElementById('analyze-btn').disabled = false;
    }, 800);
  }

  if (event.step === 'error') {
    document.getElementById('error-msg').textContent = `❌ ${event.message}`;
    document.getElementById('error-msg').style.display = 'block';
    setTimeout(() => {
      hideProgress();
      document.getElementById('analyze-btn').disabled = false;
    }, 1000);
  }
}

// ─── UI HELPERS ───────────────────────────────────────────
function showProgress() {
  document.getElementById('progress-section').style.display = 'block';
  document.getElementById('step-list').innerHTML = '';
  document.getElementById('progress-fill').style.width = '0%';
  document.getElementById('progress-pct').textContent = '0%';
  document.getElementById('results-section').style.display = 'none';
}

function hideProgress() {
  document.getElementById('progress-section').style.display = 'none';
}

function showSection(section, el) {
  document.querySelectorAll('.nav-pill').forEach(p => p.classList.remove('active'));
  if (section === 'results' && currentResult) {
    document.getElementById('results-section').style.display = 'block';
    document.getElementById('hero-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'none';
    if (el) el.classList.add('active');
  } else {
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('hero-section').style.display = '';
    document.getElementById('input-section').style.display = '';
    document.querySelectorAll('.nav-pill')[0].classList.add('active');
  }
}

function showResults() {
  document.getElementById('nav-results').style.display = '';
  document.getElementById('results-section').style.display = 'block';
  document.getElementById('results-section').classList.add('fade-in');
  renderStats();
  switchTab('report');
}

// ─── STATS ────────────────────────────────────────────────
function renderStats() {
  const r = currentResult;
  const grid = document.getElementById('stats-grid');
  const metrics = r.complexity_metrics || {};
  const gap = r.gap_analysis || {};

  const cards = [
    { label: 'Maturity Score', value: `${r.maturity_score}/100`, cls: 'score' },
    { label: 'Total Files', value: metrics.total_files || '—', cls: 'files' },
    { label: 'Lines of Code', value: (metrics.total_loc || 0).toLocaleString(), cls: 'loc' },
    { label: 'Services', value: metrics.service_count || '—', cls: 'score' },
    { label: 'Architecture', value: (r.architecture || {}).pattern || '—', cls: '' },
    { label: 'Time', value: `${r.elapsed_seconds}s`, cls: 'files' },
  ];

  grid.innerHTML = cards.map(c => `
    <div class="stat-card fade-in">
      <div class="stat-label">${c.label}</div>
      <div class="stat-value ${c.cls}">${c.value}</div>
    </div>
  `).join('');
}

// ─── TABS ─────────────────────────────────────────────────
function switchTab(tab, el) {
  document.querySelectorAll('#result-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  if (el) {
    el.classList.add('active');
  } else {
    // Find the correct tab button by tab name
    const tabMap = { 'report': 0, 'architecture': 1, 'entities': 2, 'risks': 3 };
    const idx = tabMap[tab];
    const buttons = document.querySelectorAll('#result-tabs .tab-btn');
    if (idx !== undefined && buttons[idx]) buttons[idx].classList.add('active');
  }

  const content = document.getElementById('report-content');
  mermaidBlocks = [];
  mermaidIdx = 0;

  if (tab === 'report') {
    content.innerHTML = marked.parse(rawReport);
  } else if (tab === 'architecture') {
    content.innerHTML = marked.parse(buildArchitectureView());
  } else if (tab === 'entities') {
    content.innerHTML = marked.parse(buildEntitiesView());
  } else if (tab === 'risks') {
    content.innerHTML = marked.parse(buildRisksView());
  }

  renderMermaidDiagrams();
}

async function renderMermaidDiagrams() {
  for (const { id, code } of mermaidBlocks) {
    const el = document.getElementById(id);
    if (!el) continue;
    try {
      const { svg } = await mermaid.render(`msvg-${id}`, code);
      el.innerHTML = svg;
    } catch (err) {
      el.parentElement.innerHTML = `<div style="color:var(--danger);padding:12px;">Diagram error: ${err.message}</div>`;
    }
  }
}

// ─── TAB CONTENT BUILDERS ─────────────────────────────────
function buildArchitectureView() {
  const arch = currentResult.architecture || {};
  const deps = currentResult.dependencies || {};
  const modules = Object.keys(deps.module_graph || {});

  let md = '# 🏗️ Architecture Overview\n\n';
  md += `**Pattern:** ${arch.pattern || 'Unknown'}\n\n`;
  md += `**API Style:** ${arch.api_style || 'Unknown'}\n\n`;
  md += `**Auth:** ${arch.auth_mechanism || 'Unknown'}\n\n`;
  md += `**Database:** ${arch.database_type || 'Unknown'}\n\n`;

  if (arch.layers && arch.layers.length) {
    md += `**Layers:** ${arch.layers.join(' → ')}\n\n`;

    // Generate layer diagram
    md += '```mermaid\ngraph TB\n';
    arch.layers.forEach((layer, i) => {
      const id = `L${i}`;
      const safe = layer.replace(/["\[\]()]/g, '');
      md += `  ${id}["${safe}"]\n`;
      if (i > 0) md += `  L${i - 1} --> ${id}\n`;
    });
    md += '```\n\n';
  }

  if (modules.length) {
    md += '## Module Dependencies\n\n```mermaid\ngraph LR\n';
    const graph = deps.module_graph || {};
    const shown = new Set();
    for (const [mod, targets] of Object.entries(graph)) {
      const src = mod.replace(/[^a-zA-Z0-9_]/g, '_');
      for (const t of (targets || []).slice(0, 5)) {
        const tgt = t.replace(/[^a-zA-Z0-9_]/g, '_');
        const edge = `${src}->${tgt}`;
        if (!shown.has(edge)) { md += `  ${src} --> ${tgt}\n`; shown.add(edge); }
      }
    }
    md += '```\n\n';
  }

  const circular = deps.circular_dependencies || [];
  if (circular.length) {
    md += '## ⚠️ Circular Dependencies\n\n';
    circular.forEach(c => { md += `- 🔄 ${c.join(' → ')}\n`; });
  }

  return md;
}

function buildEntitiesView() {
  const ent = currentResult.entities || {};
  const wf = currentResult.workflows || {};

  let md = '# 🏷️ Domain Entities & Workflows\n\n';

  const de = ent.domain_entities || [];
  if (de.length) { md += '## Domain Models\n\n'; de.forEach(e => { md += `- ${e}\n`; }); md += '\n'; }

  const api = ent.api_endpoints || [];
  if (api.length) { md += '## API Endpoints\n\n'; api.forEach(e => { md += `- \`${e}\`\n`; }); md += '\n'; }

  const db = ent.database_models || [];
  if (db.length) { md += '## Database Models\n\n'; db.forEach(e => { md += `- ${e}\n`; }); md += '\n'; }

  const flows = wf.primary_flows || [];
  if (flows.length) {
    md += '## Primary Flows\n\n```mermaid\ngraph TD\n';
    flows.forEach((f, i) => {
      const safe = f.replace(/["\[\]()]/g, '').substring(0, 40);
      md += `  F${i}["${safe}"]\n`;
      if (i > 0) md += `  F${i - 1} --> F${i}\n`;
    });
    md += '```\n\n';
  }

  return md;
}

function buildRisksView() {
  const gap = currentResult.gap_analysis || {};
  let md = '# 🔥 Risk Assessment\n\n';
  md += `**Maturity Score:** ${currentResult.maturity_score}/100\n\n`;

  const sec = gap.security_issues || [];
  if (sec.length) { md += '## 🔴 Security Issues\n\n'; sec.forEach(s => { md += `- ⚠️ ${s}\n`; }); md += '\n'; }

  const risks = gap.risks || [];
  if (risks.length) { md += '## 🟠 Technical Risks\n\n'; risks.forEach(r => { md += `- ${r}\n`; }); md += '\n'; }

  const gaps = gap.gaps || [];
  if (gaps.length) { md += '## 🟡 Practice Gaps\n\n'; gaps.forEach(g => { md += `- ${g}\n`; }); md += '\n'; }

  const str = gap.strengths || [];
  if (str.length) { md += '## ✅ Strengths\n\n'; str.forEach(s => { md += `- ✓ ${s}\n`; }); md += '\n'; }

  const rec = gap.recommendations || [];
  if (rec.length) { md += '## 📌 Recommendations\n\n'; rec.forEach((r, i) => { md += `${i + 1}. ${r}\n`; }); }

  return md;
}

// ─── DOWNLOADS ────────────────────────────────────────────
function downloadReport(format) {
  if (!rawReport) return;
  const repoName = document.getElementById('github-url').value.split('/').pop() || 'report';

  if (format === 'md') {
    downloadBlob(rawReport, `${repoName}-report.md`, 'text/markdown');
  } else if (format === 'html') {
    const html = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>${repoName} Report</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600&family=Fraunces:wght@400;600&family=DM+Mono&display=swap" rel="stylesheet">
<style>body{font-family:'Plus Jakarta Sans',sans-serif;background:#0d0f12;color:#e2e8f8;max-width:900px;margin:0 auto;padding:60px 40px;line-height:1.8}h1,h2,h3{font-family:'Fraunces',serif}h1{font-size:2rem;border-bottom:2px solid #2a2f45;padding-bottom:12px}h2{font-size:1.5rem;border-bottom:1px solid #2a2f45;padding-bottom:8px;margin-top:2rem}code{font-family:'DM Mono',monospace;background:#1c2030;padding:2px 6px;border-radius:4px;color:#5eead4}pre{background:#1c2030;border:1px solid #2a2f45;border-radius:8px;padding:18px;overflow-x:auto}pre code{background:none;color:#e2e8f8}table{width:100%;border-collapse:collapse;margin:1rem 0}th{background:#1c2030;padding:10px;text-align:left;font-size:.8rem;text-transform:uppercase;color:#555d78}td{padding:9px 14px;border-top:1px solid #2a2f45;color:#8b93b0}blockquote{border-left:3px solid #7c6af7;background:rgba(124,106,247,.07);padding:12px 20px;margin:1rem 0;border-radius:0 8px 8px 0}hr{border:none;border-top:1px solid #2a2f45;margin:2rem 0}a{color:#5eead4}</style></head><body>${document.getElementById('report-content').innerHTML}</body></html>`;
    downloadBlob(html, `${repoName}-report.html`, 'text/html');
  } else if (format === 'pdf') {
    const w = window.open('', '_blank');
    w.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${repoName} Report</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600&family=Fraunces:wght@400;600&family=DM+Mono&display=swap" rel="stylesheet">
<style>body{font-family:'Plus Jakarta Sans',sans-serif;color:#1a1a2e;max-width:800px;margin:0 auto;padding:40px;line-height:1.8}h1,h2,h3{font-family:'Fraunces',serif}code{font-family:'DM Mono',monospace;background:#f4f4f8;padding:2px 6px;border-radius:4px;color:#6d28d9}pre{background:#f4f4f8;border:1px solid #e0e0e0;border-radius:8px;padding:16px;overflow-x:auto}pre code{background:none;color:#1a1a2e}table{width:100%;border-collapse:collapse}th{background:#f4f4f8;padding:10px;text-align:left;border-bottom:2px solid #ddd}td{padding:9px 14px;border-bottom:1px solid #eee}blockquote{border-left:3px solid #6d28d9;background:#f8f7ff;padding:12px 20px;margin:1rem 0;border-radius:0 8px 8px 0}hr{border:none;border-top:1px solid #e0e0e0;margin:2rem 0}@media print{body{padding:0}}</style></head><body>${document.getElementById('report-content').innerHTML}</body></html>`);
    w.document.close();
    setTimeout(() => { w.focus(); w.print(); }, 600);
  }
}

function downloadBlob(content, filename, type) {
  const blob = new Blob([content], { type });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ─── ENTER KEY ────────────────────────────────────────────
document.getElementById('github-url').addEventListener('keydown', e => {
  if (e.key === 'Enter') startAnalysis();
});
