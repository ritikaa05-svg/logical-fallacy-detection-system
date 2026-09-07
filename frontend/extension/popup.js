const inputText = document.getElementById('inputText');
const analyzeBtn = document.getElementById('analyzeBtn');
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const resultEl = document.getElementById('result');
const scorePct = document.getElementById('scorePct');
const scoreFill = document.getElementById('scoreFill');
const scoreLabel = document.getElementById('scoreLabel');
const badgeList = document.getElementById('badgeList');
const tagList = document.getElementById('tagList');
const structureEl = document.getElementById('structure');
const correctionEl = document.getElementById('correction');
const statusEl = document.getElementById('status');
const localizeCheck = document.getElementById('localizeCheck');
const fastTrackCheck = document.getElementById('fastTrackCheck');
const serverUrlInput = document.getElementById('serverUrl');
const dashboardUrlInput = document.getElementById('dashboardUrl');
const healthStatus = document.getElementById('healthStatus');
const dashLink = document.getElementById('dashLink');

let popupSettings = { ...DEFAULT_SETTINGS };

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

loadSettings((s) => {
  popupSettings = s;
  if (serverUrlInput) serverUrlInput.value = s.serverUrl;
  if (dashboardUrlInput) dashboardUrlInput.value = s.dashboardUrl || '';
  if (localizeCheck) localizeCheck.checked = !!s.localize;
  if (fastTrackCheck) fastTrackCheck.checked = !!s.fastTrack;
  checkHealth();
  updateDashLink();
});

let serverUrlDebounce = null;
let dashboardUrlDebounce = null;
if (serverUrlInput) {
  serverUrlInput.addEventListener('input', () => {
    clearTimeout(serverUrlDebounce);
    serverUrlDebounce = setTimeout(() => {
      const url = serverUrlInput.value.trim();
      if (!url) return;
      healthStatus.textContent = 'saving';
      healthStatus.className = 'health saving';
      saveSettings({ serverUrl: url }, (merged) => {
        popupSettings = merged;
        serverUrlInput.value = merged.serverUrl;
        updateDashLink();
        checkHealth();
      });
    }, 600);
  });
}
if (dashboardUrlInput) {
  dashboardUrlInput.addEventListener('input', () => {
    clearTimeout(dashboardUrlDebounce);
    dashboardUrlDebounce = setTimeout(() => {
      const url = dashboardUrlInput.value.trim();
      saveSettings({ dashboardUrl: url }, (merged) => {
        popupSettings = merged;
        dashboardUrlInput.value = merged.dashboardUrl || '';
        updateDashLink();
      });
    }, 600);
  });
}

if (localizeCheck) {
  localizeCheck.addEventListener('change', () => {
    popupSettings.localize = localizeCheck.checked;
    saveSettings({ localize: popupSettings.localize });
  });
}
if (fastTrackCheck) {
  fastTrackCheck.addEventListener('change', () => {
    popupSettings.fastTrack = fastTrackCheck.checked;
    saveSettings({ fastTrack: popupSettings.fastTrack });
  });
}

function updateDashLink() {
  const dash = popupSettings.dashboardUrl || popupSettings.serverUrl || DEFAULT_SETTINGS.dashboardUrl;
  dashLink.href = dash.replace(/\/+$/, '');
}

// Route API calls through the background service worker: it holds the
// host permissions (no CORS) and shares the analysis cache. The popup's own
// origin (chrome-extension://<id>) is not statically known, so direct fetches
// are only a last-resort fallback.
function sendViaBackground(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (response === undefined) reject(new Error('No response from the extension background worker.'));
      else resolve(response);
    });
  });
}

dashLink.addEventListener('click', (e) => {
  e.preventDefault();
  const dash = popupSettings.dashboardUrl || popupSettings.serverUrl || DEFAULT_SETTINGS.dashboardUrl;
  chrome.tabs.create({ url: dash.replace(/\/+$/, '') });
  window.close();
});

analyzeBtn.addEventListener('click', async () => {
  const text = inputText.value.trim();
  if (!text) { showError('Enter some text first.'); return; }
  if (text.split(/\s+/).length < 2) { showError('Need at least 2 words.'); return; }

  setLoading(true);
  hideError();
  hideResult();

  try {
    let response;
    try {
      response = await sendViaBackground({ action: 'analyze', text, settings: popupSettings });
    } catch (_) {
      // Background worker unreachable — fall back to a direct fetch.
      const fetchResponse = await fetch(apiUrl('/analyze'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text, skip_cache: false, generate_correction: true,
          localize: popupSettings.localize,
          fast_track: popupSettings.fastTrack,
          include_explanations: !popupSettings.fastTrack,
        }),
        signal: AbortSignal.timeout(20000),
      });
      if (!fetchResponse.ok) {
        const err = await fetchResponse.json().catch(() => ({}));
        throw new Error(err.detail || `API error: ${fetchResponse.status}`);
      }
      const data = await fetchResponse.json();
      response = { success: true, ...data };
    }
    if (response && response.success) {
      displayResult(response);
    } else {
      showError(response && response.error ? response.error : 'The analysis request failed.');
    }
  } catch (error) {
    showError(
      error.message === 'Failed to fetch'
        ? 'Backend not running. Check server URL above.'
        : error.message
    );
  } finally {
    setLoading(false);
  }
});

function displayResult(result) {
  const logicScore = result.logic_score == null ? 0.5 : Number(result.logic_score);
  const pct = Math.round(logicScore * 100);

  scorePct.textContent = pct + '%';
  scorePct.className = 'score-pct';
  let cls = 'low', label = 'fallacies likely present';
  if (logicScore > 0.6) { cls = 'high'; label = 'looks logically sound'; }
  else if (logicScore > 0.3) { cls = 'medium'; label = 'some issues found'; }
  scorePct.classList.add(cls);
  scoreFill.className = 'score-fill ' + cls;
  scoreFill.style.width = pct + '%';
  scoreLabel.textContent = label;

  badgeList.innerHTML = '';
  const badges = [];
  if (result.coarse_category) badges.push(['coarse:' + result.coarse_category.replace(/_/g, ' '), '']);
  const fallacies = result.fallacies || result.fine_labels || [];
  if (fallacies.length > 0 && typeof fallacies[0] === 'object') badges.push([fallacies.length + ' fallacy', 'fallacy']);
  if (result.degradation_tier && result.degradation_tier > 0) badges.push(['degraded:' + result.degradation_tier, 'degraded']);
  else if (result.mock_mode) badges.push(['mock', 'mock']);
  if (result.z3_status) {
    const z3ok = /^(valid|sat|true|ok)$/i.test(String(result.z3_status));
    badges.push(['z3:' + result.z3_status, z3ok ? 'z3-valid' : 'z3-invalid']);
  }
  badges.forEach(([t, c]) => {
    const el = document.createElement('span');
    el.className = 'badge ' + c;
    el.textContent = t;
    badgeList.appendChild(el);
  });

  tagList.innerHTML = '';
  if (fallacies.length > 0 && typeof fallacies[0] === 'object') {
    fallacies.forEach(f => {
      const el = document.createElement('span');
      el.className = 'tag';
      el.textContent = (f.name || f.label || '').replace(/_/g, ' ') + ' ' + Math.round((f.confidence || 0) * 100) + '%';
      tagList.appendChild(el);
    });
  } else {
    const scores = result.confidence_scores || [];
    fallacies.forEach((l, i) => {
      const el = document.createElement('span');
      el.className = 'tag';
      el.textContent = l.replace(/_/g, ' ') + ' ' + Math.round(scores[i] * 100) + '%';
      tagList.appendChild(el);
    });
  }
  if (!tagList.children.length) {
    const el = document.createElement('span');
    el.style.cssText = 'color:var(--green);font-size:11px;';
    el.textContent = 'none detected';
    tagList.appendChild(el);
  }

  structureEl.innerHTML = '';
  const as = result.argument_structure;
  if (as) {
    const premises = as.premises || as.premises_text || [];
    const conclusion = as.conclusion || as.conclusion_text || '';
    const rows = [];
    (Array.isArray(premises) ? premises : []).forEach(p => {
      if (p) rows.push('<div class="struct-row premise"><span class="struct-label">premise</span>' + esc(p) + '</div>');
    });
    if (conclusion) rows.push('<div class="struct-row conclusion"><span class="struct-label">conclusion</span>' + esc(conclusion) + '</div>');
    if (rows.length) structureEl.innerHTML = rows.join('');
  }

  correctionEl.textContent = result.correction_strategy || '';

  const cached = result.cached || false;
  const ms = Math.round(result.total_latency_ms || 0);
  const dev = result.device_info?.device_string || '?';
  statusEl.textContent = (cached ? 'cached' : 'fresh') + '  |  ' + ms + 'ms  |  ' + dev;

  resultEl.classList.add('visible');
}

function setLoading(v) {
  loadingEl.style.display = v ? 'block' : 'none';
  analyzeBtn.disabled = v;
  analyzeBtn.textContent = v ? '[ running ]' : '[ analyze ]';
}

function showError(m) {
  errorEl.textContent = 'err: ' + m;
  errorEl.classList.add('visible');
}

function hideError() { errorEl.classList.remove('visible'); }
function hideResult() { resultEl.classList.remove('visible'); }

document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); analyzeBtn.click(); }
});

async function checkHealth() {
  if (!healthStatus) return;
  healthStatus.textContent = 'checking';
  healthStatus.className = 'health';
  try {
    const d = await sendViaBackground({ action: 'healthCheck' });
    if (d && d.success) {
      healthStatus.textContent = 'online';
      healthStatus.className = 'health online';
    } else {
      healthStatus.textContent = 'offline';
      healthStatus.className = 'health offline';
    }
  } catch (_) {
    healthStatus.textContent = 'offline';
    healthStatus.className = 'health offline';
  }
}
