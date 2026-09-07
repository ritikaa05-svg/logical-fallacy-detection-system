(function() {
  'use strict';

  const HOST_ID = 'argcheck-host';
  const HOST_Z = 2147483647;
  const DEFAULT_DASHBOARD_URL = 'http://localhost:8000';
  const VIEWPORT_MARGIN = 12;
  const PILL_MAX_CHARS = 60;
  const PILL_TIMEOUT_MS = 20000;

  let SETTINGS = getSettings();

  loadSettings((s) => { SETTINGS = s; });
  chrome.storage.onChanged.addListener((changes, area) => {
    if ((area === 'local' || area === 'sync') && changes.settings) SETTINGS = getSettings();
  });

  let host = null;
  let root = null;
  let highlightLayer = null;
  let activeEl = null;       // current pill/popover/error element
  let activeKind = null;     // 'pill' | 'result' | 'error'
  let lastSelection = null;  // { text, rect, segs, range, element } captured at trigger time
  let pendingText = null;    // retained text for retry after error
  let lastQuote = null;      // quote used for page highlighting (for re-render on scroll)
  let analyzing = false;
  let analysisSeq = 0;        // guards against stale responses clobbering newer analyses
  let pillTimer = null;
  let viewportRaf = null;

  function createHost() {
    // Some SPAs replace <body> wholesale — if our overlay got detached,
    // rebuild it instead of appending to a dead subtree.
    if (host && host.isConnected) return;
    if (host && host.parentNode) host.parentNode.removeChild(host);
    host = document.createElement('div');
    host.id = HOST_ID;
    host.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:' + HOST_Z + ';';
    document.body.appendChild(host);
    root = host.attachShadow({ mode: 'open' });
    const s = document.createElement('style');
    s.textContent = getStyles();
    root.appendChild(s);
  }

  function createHighlightLayer() {
    if (highlightLayer && highlightLayer.isConnected) return highlightLayer;
    if (highlightLayer && highlightLayer.parentNode) highlightLayer.parentNode.removeChild(highlightLayer);
    highlightLayer = document.createElement('div');
    highlightLayer.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:' + (HOST_Z - 1) + ';';
    document.body.appendChild(highlightLayer);
    return highlightLayer;
  }

  function getStyles() {
    return `
      :host {
        --bg: #0d0d0d;
        --card: #1a1a1a;
        --card-alt: #222;
        --border: #2a2a2a;
        --border-strong: #333;
        --text: #d4d4d4;
        --text-secondary: #9ca3af;
        --text-muted: #6b7280;
        --green: #34d399;
        --green-bg: #064e3b;
        --amber: #fbbf24;
        --amber-bg: #451a03;
        --red: #f87171;
        --red-bg: #450a0a;
        --info: #93c5fd;
        --info-bg: #172554;
        --badge-red-bg: #450a0a;
        --badge-red-text: #fca5a5;
        --badge-red-border: #ef4444;
        --badge-blue-bg: #172554;
        --badge-blue-text: #93c5fd;
        --badge-blue-border: #3b82f6;
        --badge-amber-bg: #451a03;
        --badge-amber-text: #fcd34d;
        --badge-amber-border: #f59e0b;
        --badge-purple-bg: #2e1065;
        --badge-purple-text: #d8b4fe;
        --badge-purple-border: #a855f7;
        --badge-green-bg: #022c22;
        --badge-green-text: #6ee7b7;
        --badge-green-border: #10b981;
        --mock-bg: rgba(120, 53, 15, 0.3);
        --mock-text: #fbbf24;
        --mock-border: #92400e;
        --spinner: #10b981;
      }
      @media (prefers-color-scheme: light) {
        :host {
          --bg: #f8f9fa;
          --card: #ffffff;
          --card-alt: #f1f3f5;
          --border: #e2e8f0;
          --border-strong: #d1d5db;
          --text: #1a1a2e;
          --text-secondary: #64748b;
          --text-muted: #94a3b8;
          --green: #059669;
          --green-bg: #d1fae5;
          --amber: #b45309;
          --amber-bg: #fef3c7;
          --red: #b91c1c;
          --red-bg: #fee2e2;
          --info: #1e40af;
          --info-bg: #dbeafe;
          --badge-red-bg: #fee2e2;
          --badge-red-text: #991b1b;
          --badge-red-border: #ef4444;
          --badge-blue-bg: #dbeafe;
          --badge-blue-text: #1e40af;
          --badge-blue-border: #3b82f6;
          --badge-amber-bg: #fef3c7;
          --badge-amber-text: #92400e;
          --badge-amber-border: #f59e0b;
          --badge-purple-bg: #f3e8ff;
          --badge-purple-text: #6b21a8;
          --badge-purple-border: #a855f7;
          --badge-green-bg: #d1fae5;
          --badge-green-text: #047857;
          --badge-green-border: #10b981;
          --mock-bg: rgba(120, 53, 15, 0.15);
          --mock-text: #92400e;
          --mock-border: #92400e;
          --spinner: #059669;
        }
      }
      .ac-popover, .ac-pill, .ac-error {
        pointer-events: all;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        position: fixed;
        max-width: 380px;
        min-width: 280px;
        background: var(--card);
        border: 1px solid var(--border-strong);
        border-radius: 10px;
        color: var(--text);
        font-size: 13px;
        line-height: 1.5;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4);
        animation: acPop 0.14s ease-out;
        z-index: 1;
      }
      .ac-popover { padding: 10px 12px; }
      .ac-arrow {
        position: absolute;
        width: 10px; height: 10px;
        background: inherit;
        border-left: 1px solid var(--border-strong);
        border-top: 1px solid var(--border-strong);
        transform: rotate(45deg);
      }
      .ac-arrow.up { top: -6px; }
      .ac-arrow.down { bottom: -6px; transform: rotate(225deg); }
      @keyframes acPop { from { opacity: 0; transform: scale(0.96) translateY(4px); } to { opacity: 1; transform: scale(1) translateY(0); } }

      .ac-head { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
      .ac-verdict { font-size: 14px; font-weight: 700; line-height: 1.3; flex: 1; }
      .ac-verdict.good { color: var(--green); }
      .ac-verdict.warn { color: var(--amber); }
      .ac-verdict.bad { color: var(--red); }
      .ac-verdict.neutral { color: var(--info); }
      .ac-score {
        font-size: 12px; font-weight: 700; padding: 1px 7px; border-radius: 999px;
        background: var(--card-alt); border: 1px solid var(--border);
        white-space: nowrap;
      }
      .ac-score.good { color: var(--green); border-color: var(--badge-green-border); background: var(--badge-green-bg); }
      .ac-score.warn { color: var(--amber); border-color: var(--badge-amber-border); background: var(--badge-amber-bg); }
      .ac-score.bad { color: var(--red); border-color: var(--badge-red-border); background: var(--badge-red-bg); }
      .ac-score.neutral { color: var(--info); border-color: var(--badge-blue-border); background: var(--badge-blue-bg); }

      .ac-note { color: var(--text-secondary); font-size: 12px; margin-bottom: 6px; }
      .ac-quote {
        display: block; margin: 0 0 6px 0; padding: 6px 9px;
        background: var(--card-alt); border-left: 3px solid var(--border-strong);
        font-style: italic; font-size: 12px; color: var(--text-secondary);
        max-height: 72px; overflow-y: auto;
      }
      .ac-quote.bad { border-left-color: var(--red); }
      .ac-quote.warn { border-left-color: var(--amber); }
      .ac-correct {
        padding: 6px 9px; background: var(--green-bg); border-left: 3px solid var(--green);
        font-size: 12px; color: var(--green); max-height: 66px; overflow-y: auto; margin-bottom: 6px;
      }
      .ac-foot { display: flex; align-items: center; gap: 10px; font-size: 11px; color: var(--text-muted); }
      .ac-foot a, .ac-foot button {
        background: none; border: none; padding: 0; cursor: pointer; font: inherit;
        color: var(--text-secondary); text-decoration: none;
      }
      .ac-foot a:hover, .ac-foot button:hover { color: var(--text); text-decoration: underline; }
      .ac-foot .ac-spacer { flex: 1; }

      .ac-details { display: none; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); font-size: 11px; }
      .ac-details.open { display: block; }
      .ac-details .ac-dsection { margin-bottom: 6px; }
      .ac-details .ac-dlabel { color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; font-size: 9px; margin-bottom: 3px; }
      .ac-badges { display: flex; flex-wrap: wrap; gap: 4px; }
      .ac-badge {
        display: inline-block; padding: 1px 6px; font-size: 9px; letter-spacing: 0.05em;
        border: 1px solid var(--badge-blue-border); background: var(--badge-blue-bg); color: var(--badge-blue-text);
        border-radius: 999px;
      }
      .ac-badge.degraded { border-color: var(--badge-amber-border); background: var(--badge-amber-bg); color: var(--badge-amber-text); }
      .ac-badge.mock { border-color: var(--mock-border); background: var(--mock-bg); color: var(--mock-text); }
      .ac-badge.z3-valid { border-color: var(--badge-green-border); background: var(--badge-green-bg); color: var(--badge-green-text); }
      .ac-badge.z3-invalid { border-color: var(--badge-red-border); background: var(--badge-red-bg); color: var(--badge-red-text); }
      .ac-badge.fallacy { border-color: var(--badge-red-border); background: var(--badge-red-bg); color: var(--badge-red-text); }
      .ac-struct-row { padding: 3px 8px; margin-bottom: 2px; background: var(--card-alt); border-left: 2px solid var(--border-strong); }
      .ac-struct-label { color: var(--text-muted); font-size: 9px; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 6px; }
      .ac-struct-premise { border-left-color: var(--badge-blue-border); }
      .ac-struct-conclusion { border-left-color: var(--badge-purple-border); }
      .ac-evidence { padding: 4px 8px; background: var(--card-alt); border: 1px solid var(--border); font-style: italic; }
      .ac-tag {
        display: inline-block; border: 1px solid var(--badge-red-border); background: var(--card-alt);
        padding: 0 6px; font-size: 10px; color: var(--badge-red-text); border-radius: 999px; margin-right: 3px;
      }

      .ac-pill {
        display: flex; align-items: center; gap: 8px;
        padding: 6px 12px; font-size: 12px; color: var(--text-secondary);
      }
      .ac-spinner {
        width: 12px; height: 12px; border-radius: 50%;
        border: 2px solid var(--border-strong); border-top-color: var(--spinner);
        animation: acSpin 0.8s linear infinite;
      }
      @keyframes acSpin { to { transform: rotate(360deg); } }

      .ac-error { padding: 10px 12px; }
      .ac-error .ac-err-title { font-weight: 700; color: var(--red); margin-bottom: 4px; }
      .ac-error .ac-err-msg { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
      .ac-error .ac-err-server { font-size: 10px; color: var(--text-muted); margin-bottom: 8px; }
      .ac-error .ac-err-actions { display: flex; gap: 12px; font-size: 12px; }
      .ac-error .ac-err-actions button {
        background: none; border: none; padding: 0; cursor: pointer; font: inherit;
        color: var(--info); text-decoration: none;
      }
      .ac-error .ac-err-actions button:hover { text-decoration: underline; }

      .ac-highlight {
        pointer-events: none;
        background: rgba(239, 68, 68, 0.35);
        box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.6);
        border-radius: 2px;
      }
      @media (prefers-color-scheme: light) {
        .ac-highlight { background: rgba(220, 38, 38, 0.25); box-shadow: 0 0 0 1px rgba(220, 38, 38, 0.5); }
      }
    `;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  function humanize(name) {
    return String(name || '').replace(/_/g, ' ').trim();
  }

  function captureSelection() {
    // Selections inside inputs/textareas are invisible to window.getSelection().
    const active = document.activeElement;
    if (active && (active.tagName === 'TEXTAREA' ||
        (active.tagName === 'INPUT' && /^(text|search|url|email|tel|password)$/i.test(active.type)))) {
      const start = Math.min(active.selectionStart || 0, active.selectionEnd || 0);
      const end = Math.max(active.selectionStart || 0, active.selectionEnd || 0);
      const text = active.value.slice(start, end).trim();
      if (!text) return null;
      return { text, rect: active.getBoundingClientRect(), segs: [], range: null, element: active };
    }
    const sel = window.getSelection();
    if (!sel) return null;
    const text = sel.toString().trim();
    if (!text || !sel.rangeCount) return null;
    const range = sel.getRangeAt(0);
    let rect = null;
    try { rect = range.getBoundingClientRect(); } catch (_) { /* ignore */ }
    if (!rect || (rect.width === 0 && rect.height === 0)) {
      try { const r = range.getClientRects(); if (r && r.length) rect = r[0]; } catch (_) { /* ignore */ }
    }
    let segs = [];
    try { segs = collectTextSegments(range, text.length); } catch (_) { /* ignore */ }
    return { text, rect, segs, range, element: null };
  }

  function getCurrentRect() {
    if (!lastSelection) return null;
    if (lastSelection.range) {
      try {
        const r = lastSelection.range.getBoundingClientRect();
        if (r && (r.width > 0 || r.height > 0)) return r;
      } catch (_) { /* stale range */ }
      try {
        const rs = lastSelection.range.getClientRects();
        if (rs && rs.length) return rs[0];
      } catch (_) { /* stale range */ }
    }
    if (lastSelection.element && lastSelection.element.isConnected) {
      return lastSelection.element.getBoundingClientRect();
    }
    return lastSelection.rect || null;
  }

  function showPill(text, rect) {
    createHost();
    clearActive();
    const label = text.length > PILL_MAX_CHARS ? text.slice(0, PILL_MAX_CHARS) + '\u2026' : text;
    const pill = document.createElement('div');
    pill.className = 'ac-pill';
    pill.innerHTML = '<div class="ac-spinner"></div><span>' + esc(label) + '</span>';
    root.appendChild(pill);
    activeEl = pill;
    activeKind = 'pill';
    anchorEl(pill, rect, false);
    if (pillTimer) clearTimeout(pillTimer);
    pillTimer = setTimeout(() => { if (activeKind === 'pill') dismiss(); }, PILL_TIMEOUT_MS);
  }

  function showResult(result) {
    createHost();
    clearActive();
    clearHighlights();
    const verdict = buildVerdict(result);
    const top = (result.fallacies || [])[0];
    const quote = top && top.quote;
    const corr = result.correction_strategy || '';
    const dashboardUrl = (SETTINGS.dashboardUrl || SETTINGS.serverUrl || DEFAULT_DASHBOARD_URL).replace(/\/+$/, '');
    const ms = Math.round(result.total_latency_ms || 0);
    const hasDetails = result.coarse_category || result.z3_status || result.degradation_tier ||
      result.mock_mode || (result.argument_structure && (result.argument_structure.premises || result.argument_structure.conclusion)) ||
      (result.salient_tokens && result.salient_tokens.length) || result.analysis_id;

    const el = document.createElement('div');
    el.className = 'ac-popover';
    attachArrow(el);

    const detailsHtml = renderDetails(result, dashboardUrl, ms);

    el.innerHTML =
      '<div class="ac-head">' +
        '<div class="ac-verdict ' + verdict.cls + '">' + verdict.icon + ' ' + esc(verdict.text) + '</div>' +
        '<span class="ac-score ' + verdict.cls + '">' + verdict.scorePct + '%</span>' +
      '</div>' +
      (verdict.note ? '<div class="ac-note">' + esc(verdict.note) + '</div>' : '') +
      (quote ? '<div class="ac-quote ' + verdict.cls + '">\u201c' + esc(quote) + '\u201d</div>' : '') +
      (corr ? '<div class="ac-correct">' + esc(corr) + '</div>' : '') +
      (hasDetails
        ? '<div class="ac-foot">' +
            '<button class="ac-toggle">details \u25be</button>' +
            '<span class="ac-spacer"></span>' +
            '<button class="ac-close">dismiss</button>' +
          '</div>' +
          '<div class="ac-details">' + detailsHtml + '</div>'
        : '<div class="ac-foot"><span class="ac-spacer"></span><button class="ac-close">dismiss</button></div>');

    root.appendChild(el);
    activeEl = el;
    activeKind = 'result';

    const rect = getCurrentRect();
    anchorEl(el, rect, true);

    const closeBtn = el.querySelector('.ac-close');
    if (closeBtn) closeBtn.addEventListener('click', dismiss);
    const toggle = el.querySelector('.ac-toggle');
    if (toggle) toggle.addEventListener('click', (e) => {
      e.preventDefault();
      const det = el.querySelector('.ac-details');
      const open = det.classList.toggle('open');
      toggle.textContent = open ? 'details \u25b4' : 'details \u25be';
      // Re-anchor after expand (height changed)
      anchorEl(el, getCurrentRect(), true);
    });
    const traceLink = el.querySelector('.ac-trace');
    if (traceLink) traceLink.addEventListener('click', (e) => {
      e.preventDefault();
      window.open(dashboardUrl + '/traces/' + encodeURIComponent(result.analysis_id), '_blank');
    });
    const dashLink = el.querySelector('.ac-dash');
    if (dashLink) dashLink.addEventListener('click', (e) => {
      e.preventDefault();
      window.open(dashboardUrl, '_blank');
    });

    // Highlight the offending quote in the page
    lastQuote = quote || null;
    if (quote && lastSelection && lastSelection.segs && lastSelection.segs.length) {
      highlightQuote(lastSelection.segs, quote);
    }
  }

  function buildVerdict(result) {
    const ls = Number(result.logic_score) || 0;
    const pct = Math.round(ls * 100);
    const top = (result.fallacies || [])[0];
    const topFine = (result.fine_labels || [])[0] || (top && top.name) || '';

    if (topFine === 'factual_statement') {
      return { icon: '\u2139\ufe0f', text: 'Not an argument', note: 'This reads as a factual statement rather than an argument.', cls: 'neutral', scorePct: pct };
    }
    const topConf = top ? Number(top.confidence) || 0 : 0;
    if (topFine === 'valid_reasoning' || (ls >= 0.7 && topConf < 0.5)) {
      return { icon: '\u2713', text: 'No clear fallacy', note: 'The argument appears logically sound.', cls: 'good', scorePct: pct };
    }

    const name = humanize((top && top.name) || topFine || 'issue');
    const conf = top ? Math.round(Number(top.confidence) * 100) : pct;
    const note = top && top.explanation ? top.explanation : '';

    if (ls < 0.3) {
      return { icon: '\u2715', text: 'Likely ' + name, note, cls: 'bad', scorePct: conf };
    }
    if (ls >= 0.3) {
      return { icon: '\u26a0\ufe0f', text: 'Possible ' + name, note, cls: 'warn', scorePct: conf };
    }
    return { icon: '\u2715', text: name, note, cls: 'bad', scorePct: conf };
  }

  function renderDetails(result, dashboardUrl, ms) {
    let html = '';
    let badges = '';
    if (result.coarse_category) badges += '<span class="ac-badge">' + esc(humanize(result.coarse_category)) + '</span>';
    const fallacies = result.fallacies || [];
    if (fallacies.length > 0) badges += '<span class="ac-badge fallacy">' + fallacies.length + ' fallacy' + (fallacies.length > 1 ? 's' : '') + '</span>';
    if (result.degradation_tier && result.degradation_tier > 0) {
      badges += '<span class="ac-badge degraded">degraded:' + result.degradation_tier + '</span>';
    } else if (result.mock_mode) {
      badges += '<span class="ac-badge mock">mock</span>';
    }
    if (result.z3_status) {
      const z3ok = /^(valid|sat|true|ok)$/i.test(String(result.z3_status));
      badges += '<span class="ac-badge ' + (z3ok ? 'z3-valid' : 'z3-invalid') + '">z3:' + esc(String(result.z3_status)) + '</span>';
    }
    if (badges) html += '<div class="ac-dsection"><div class="ac-dlabel">classification</div><div class="ac-badges">' + badges + '</div></div>';

    const tags = fallacies.map(f => '<span class="ac-tag">' + esc(humanize(f.name)) + '</span>').join('');
    if (tags) html += '<div class="ac-dsection"><div class="ac-dlabel">detections</div>' + tags + '</div>';

    const argStruct = result.argument_structure;
    if (argStruct) {
      const prem = argStruct.premises || argStruct.premises_text || [];
      const concl = argStruct.conclusion || argStruct.conclusion_text || '';
      let rows = '';
      if (Array.isArray(prem)) prem.forEach(p => { if (p) rows += '<div class="ac-struct-row ac-struct-premise"><span class="ac-struct-label">premise</span>' + esc(p) + '</div>'; });
      else if (prem) rows += '<div class="ac-struct-row ac-struct-premise"><span class="ac-struct-label">premise</span>' + esc(prem) + '</div>';
      if (concl) rows += '<div class="ac-struct-row ac-struct-conclusion"><span class="ac-struct-label">conclusion</span>' + esc(concl) + '</div>';
      if (rows) html += '<div class="ac-dsection"><div class="ac-dlabel">argument structure</div>' + rows + '</div>';
    }

    if (result.salient_tokens && result.salient_tokens.length > 0) {
      const parts = result.salient_tokens.map(item => {
        try {
          let tok, sc2;
          if (Array.isArray(item)) { [tok, sc2] = item; }
          else if (item && typeof item === 'object') { tok = item.token || item.text || ''; sc2 = item.score || 0; }
          else return '';
          const clean = String(tok).replace('##', '').trim();
          if (!clean || ['[CLS]', '[SEP]', '<s>', '</s>', '<pad>', '[PAD]'].includes(tok)) return '';
          const a = Math.abs(Number(sc2));
          let bg = '';
          if (a >= 0.7) bg = 'background:rgba(239,68,68,' + Math.min(a, 1) * 0.35 + ');';
          else if (a >= 0.3) bg = 'background:rgba(245,158,11,' + Math.min(a, 1) * 0.35 + ');';
          return bg ? '<span style="' + bg + 'border-radius:1px;padding:0 1px;">' + esc(clean) + '</span>' : esc(clean);
        } catch (_) { return ''; }
      }).join(' ');
      if (parts) html += '<div class="ac-dsection"><div class="ac-dlabel">salient terms</div><div class="ac-evidence">' + parts + '</div></div>';
    }

    html += '<div class="ac-dsection"><div class="ac-dlabel">meta</div>' +
      '<span>' + ms + 'ms</span> &middot; <span>v' + esc(String(result.version || '?')) + '</span>' +
      (result.analysis_id ? ' &middot; <a href="#" class="ac-trace">trace \u2192</a>' : '') +
      ' &middot; <a href="#" class="ac-dash">dashboard \u2192</a></div>';

    return html;
  }

  function showError(msg, serverUrl, retryFn) {
    createHost();
    clearActive();
    clearHighlights();
    const el = document.createElement('div');
    el.className = 'ac-error';
    attachArrow(el);
    el.innerHTML =
      '<div class="ac-err-title">Analysis failed</div>' +
      '<div class="ac-err-msg">' + esc(msg) + '</div>' +
      '<div class="ac-err-server">' + esc(serverUrl || SETTINGS.serverUrl || 'http://localhost:8000') + '</div>' +
      '<div class="ac-err-actions">' +
        (retryFn ? '<button class="ac-retry">retry</button>' : '') +
        '<button class="ac-close">dismiss</button>' +
      '</div>';
    root.appendChild(el);
    activeEl = el;
    activeKind = 'error';
    anchorEl(el, getCurrentRect(), true);
    el.querySelector('.ac-close').addEventListener('click', dismiss);
    const retry = el.querySelector('.ac-retry');
    if (retry) retry.addEventListener('click', (e) => {
      e.preventDefault();
      dismiss();
      retryFn();
    });
  }

  function anchorEl(el, rect, withArrow) {
    const w = Math.max(280, Math.min(el.offsetWidth || 340, 380));
    const h = el.offsetHeight || 120;
    const vw = window.innerWidth || document.documentElement.clientWidth || 1280;
    const vh = window.innerHeight || document.documentElement.clientHeight || 800;
    let cx = vw / 2;
    let cy = vh / 2;
    if (rect && rect.width >= 0 && rect.height >= 0) { cx = rect.left + rect.width / 2; cy = rect.top; }

    const left = Math.min(Math.max(cx - w / 2, VIEWPORT_MARGIN), Math.max(VIEWPORT_MARGIN, vw - w - VIEWPORT_MARGIN));
    let top;
    let arrow = '';
    if (rect && rect.top - h - 10 >= 0) { top = rect.top - h - 10; arrow = 'down'; }
    else if (rect && rect.bottom + h + 10 <= vh) { top = rect.bottom + 10; arrow = 'up'; }
    else if (rect) { top = Math.min(Math.max(rect.top, VIEWPORT_MARGIN), Math.max(VIEWPORT_MARGIN, vh - h - VIEWPORT_MARGIN)); }
    else { top = Math.min(Math.max((vh - h) / 2, VIEWPORT_MARGIN), Math.max(VIEWPORT_MARGIN, vh - h - VIEWPORT_MARGIN)); }

    el.style.left = left + 'px';
    el.style.top = top + 'px';

    if (withArrow && rect) {
      const arrowEl = el.querySelector('.ac-arrow');
      if (arrowEl) {
        arrowEl.className = 'ac-arrow' + (arrow ? ' ' + arrow : '');
        const arrowLeft = Math.min(Math.max(rect.left + rect.width / 2 - left - 5, 16), w - 26);
        arrowEl.style.left = arrowLeft + 'px';
      }
    }
  }

  function renderArrow() {
    const a = document.createElement('div');
    a.className = 'ac-arrow';
    return a;
  }

  function attachArrow(el) {
    el.insertBefore(renderArrow(), el.firstChild);
  }

  function highlightQuote(segs, quote) {
    const layer = createHighlightLayer();
    while (layer.firstChild) layer.removeChild(layer.firstChild);
    const text = segs.map(s => s.text).join('');
    let start = -1;
    let match = quote;
    const candidates = [quote, quote.replace(/[.!?\u2019']+$/, '').trim(), quote.replace(/\u2019/g, "'")];
    for (const c of candidates) {
      const i = text.indexOf(c);
      if (i >= 0) { start = i; match = c; break; }
    }
    if (start < 0) return;

    const ranges = [];
    segs.forEach(seg => {
      const s = Math.max(start, seg.start);
      const e = Math.min(start + match.length, seg.end);
      if (s < e && seg.node && seg.node.nodeType === Node.TEXT_NODE) {
        ranges.push({ node: seg.node, start: seg.nodeOffset + (s - seg.start), end: seg.nodeOffset + (e - seg.start) });
      }
    });

    ranges.forEach(({ node, start: rs, end: re }) => {
      try {
        const r = document.createRange();
        r.setStart(node, rs);
        r.setEnd(node, re);
        const rect = r.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return;
        const hl = document.createElement('div');
        hl.className = 'ac-highlight';
        hl.style.cssText = 'position:absolute;pointer-events:none;left:' + rect.left + 'px;top:' + rect.top + 'px;width:' + rect.width + 'px;height:' + rect.height + 'px;';
        layer.appendChild(hl);
      } catch (_) { /* non-fatal */ }
    });
  }

  function collectTextSegments(range, maxLen) {
    const segs = [];
    let offset = 0;
    const walker = document.createTreeWalker(range.commonAncestorContainer, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    const startNode = range.startContainer.nodeType === Node.TEXT_NODE
      ? range.startContainer
      : range.startContainer.childNodes[range.startOffset];
    const endNode = range.endContainer.nodeType === Node.TEXT_NODE
      ? range.endContainer
      : range.endContainer.childNodes[Math.max(0, range.endOffset - 1)];

    for (const node of nodes) {
      const len = (node.textContent || '').length;
      const nodeStart = offset;
      offset += len;
      const isStart = node === startNode;
      const isEnd = node === endNode;
      const from = isStart ? Math.max(0, Math.min(range.startOffset, len)) : 0;
      const to = isEnd ? Math.max(0, Math.min(range.endOffset, len)) : len;
      if (to > from && offset <= maxLen) {
        segs.push({ node, nodeOffset: from, start: nodeStart + from, end: nodeStart + to, text: (node.textContent || '').slice(from, to) });
      }
      if (isEnd) break;
    }
    return segs;
  }

  function clearActive() {
    if (pillTimer) { clearTimeout(pillTimer); pillTimer = null; }
    if (activeEl && activeEl.parentNode) activeEl.parentNode.removeChild(activeEl);
    activeEl = null;
    activeKind = null;
  }

  function dismiss() {
    clearActive();
    clearHighlights();
    analyzing = false;
  }

  function clearHighlights() {
    if (highlightLayer) {
      while (highlightLayer.firstChild) highlightLayer.removeChild(highlightLayer.firstChild);
    }
  }

  function runAnalysis(useText) {
    if (analyzing) return;
    let captured;
    if (useText) {
      // Prefer a live re-capture (right-click on a selection keeps it active)
      // so the pill and result anchor to the real selection rect; fall back to
      // the supplied text if the selection is gone or differs.
      const live = captureSelection();
      captured = live && live.text === useText
        ? live
        : { text: useText, rect: null, segs: [], range: null, element: null };
    } else {
      captured = captureSelection();
    }
    if (!captured || !captured.text) {
      lastSelection = captured;
      showError('Select some text first, then press Ctrl+Shift+L again.', SETTINGS.serverUrl);
      return;
    }
    lastSelection = captured;
    pendingText = captured.text;
    showPill('Analyzing\u2026', captured.rect);
    analyzing = true;
    const seq = ++analysisSeq;
    chrome.runtime.sendMessage({ action: 'analyze', text: captured.text, settings: SETTINGS }, (response) => {
      if (seq !== analysisSeq) return; // superseded by a newer analysis
      analyzing = false;
      if (pillTimer) { clearTimeout(pillTimer); pillTimer = null; }
      if (chrome.runtime.lastError) {
        showError(chrome.runtime.lastError.message, SETTINGS.serverUrl, () => runAnalysis(pendingText));
        return;
      }
      if (response && response.success) {
        showResult(response);
      } else {
        showError(response && response.error ? response.error : 'The analysis request failed.', SETTINGS.serverUrl, () => runAnalysis(pendingText));
      }
    });
  }

  // Re-anchor the popover and re-render highlights when the page scrolls or
  // resizes, so fixed-position UI stays glued to the selection. Throttled via
  // requestAnimationFrame.
  function onViewportChange() {
    if (viewportRaf) return;
    viewportRaf = requestAnimationFrame(() => {
      viewportRaf = null;
      if (!lastSelection || !activeEl) return;
      const rect = getCurrentRect();
      if (!rect) return;
      lastSelection.rect = rect;
      anchorEl(activeEl, rect, activeKind !== 'pill');
      if (activeKind === 'result' && lastQuote && lastSelection.segs && lastSelection.segs.length) {
        highlightQuote(lastSelection.segs, lastQuote);
      }
    });
  }

  chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
    if (req.action === 'hotkeyAnalyze') {
      runAnalysis();
      sendResponse({ received: true });
      return true;
    }
    if (req.action === 'runAnalysis') {
      runAnalysis(req.text);
      sendResponse({ received: true });
      return true;
    }
    if (req.action === 'clearHighlights') { clearHighlights(); sendResponse({ received: true }); return true; }
  });

  // NOTE: Ctrl+Shift+L is handled by the browser-level chrome.commands
  // shortcut (manifest.json) — a local keydown listener would fire twice.
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && activeEl) dismiss();
  });

  document.addEventListener('click', e => {
    if (activeEl && !activeEl.contains(e.target)) dismiss();
  });

  window.addEventListener('scroll', onViewportChange, true);
  window.addEventListener('resize', onViewportChange);
})();
