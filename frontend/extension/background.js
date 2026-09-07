importScripts('config.js');

const CACHE_MAX_SIZE = 100;
const SESSION_CACHE_MAX_SIZE = 50;
const ANALYSIS_TIMEOUT_MS = 20000;

// In-memory LRU fast path. Persisted to chrome.storage.session so the cache
// survives MV3 service worker restarts (in-memory Maps do not). Falls back to
// memory-only on browsers without session storage (Chrome < 102).
const cache = new Map();
const sessionStore = chrome.storage.session;
let cacheHydrated = false;
let hydrationPromise = null;
let sessionWriteTimer = null;

function ensureCache() {
  if (cacheHydrated) return Promise.resolve();
  if (!hydrationPromise) {
    hydrationPromise = (sessionStore
      ? sessionStore.get('analysisCache')
      : Promise.resolve({ analysisCache: null })
    )
      .then((data) => {
        const entries = (data && data.analysisCache) || [];
        for (const e of entries) cache.set(e.key, e.value);
      })
      .catch(() => { /* session storage unavailable — memory-only cache */ })
      .finally(() => { cacheHydrated = true; });
  }
  return hydrationPromise;
}

function persistCache() {
  if (!sessionStore || sessionWriteTimer) return;
  sessionWriteTimer = setTimeout(() => {
    sessionWriteTimer = null;
    const entries = [];
    for (const [key, value] of cache) entries.push({ key, value });
    const trimmed = entries.slice(-SESSION_CACHE_MAX_SIZE);
    sessionStore.set({ analysisCache: trimmed }).catch(() => {});
  }, 250);
}

function cacheSet(key, value) {
  if (cache.size >= CACHE_MAX_SIZE) {
    const oldest = cache.keys().next().value;
    cache.delete(oldest);
  }
  cache.set(key, value);
  persistCache();
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: 'analyze-selection',
      title: 'Check argument for fallacies',
      contexts: ['selection'],
      documentUrlPatterns: ['<all_urls>']
    });
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'analyze-selection' && info.selectionText) {
    const t = info.selectionText.trim();
    if (t.length > 0 && tab && tab.id != null) {
      // Delegate to the content script so the user gets immediate pill
      // feedback and an anchored result, with a retry button on errors.
      sendMessageToTab(tab.id, { action: 'runAnalysis', text: t }).catch((err) => {
        console.error('Context menu: content script unavailable:', err);
      });
    }
  }
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'analyze-selection') {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.id != null) {
      try {
        // Delegate to the content script so the user gets immediate feedback
        // (pill while analyzing, or "select some text first" error), then the
        // content script runs the analysis itself via chrome.runtime.sendMessage.
        await sendMessageToTab(tab.id, { action: 'hotkeyAnalyze' });
      } catch (err) {
        console.error('Keyboard shortcut: content script unavailable:', err);
      }
    }
  }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'analyze') {
    analyzeText(request.text, request.settings)
      .then((result) => sendResponse({ success: true, ...result }))
      .catch((err) => { console.error('API error:', err); sendResponse({ success: false, error: err.message }); });
    return true;
  }
  if (request.action === 'healthCheck') {
    healthCheck().then((d) => sendResponse({ success: true, ...d }));
    return true;
  }
  if (request.action === 'clearCache') {
    cache.clear();
    if (sessionStore) sessionStore.remove('analysisCache').catch(() => {});
    sendResponse({ success: true, message: 'done' });
    return true;
  }
});

// Send a message to a tab's content script. If the content script is not
// present (e.g. page loaded before the extension was installed, or a page
// where injection was deferred), inject it on the fly and retry.
async function sendMessageToTab(tabId, message) {
  try {
    return await chrome.tabs.sendMessage(tabId, message);
  } catch (err) {
    if (err && /receiving end does not exist/i.test(String(err.message))) {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['config.js', 'content_script.js'],
      });
      return await chrome.tabs.sendMessage(tabId, message);
    }
    throw err;
  }
}

async function analyzeText(text, overrideSettings) {
  const settings = overrideSettings ? normalizeSettings(overrideSettings) : getSettings();
  const base = normalizeServerUrl(settings.serverUrl);
  const key = base + ':' + hash(text);
  await ensureCache();
  if (cache.has(key)) {
    return { ...cache.get(key), cached: true };
  }
  const r = await fetch(base + '/api/v1/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text, skip_cache: false, generate_correction: true,
      localize: settings.localize || false,
      fast_track: settings.fastTrack || false,
      include_explanations: !settings.fastTrack,
    }),
    signal: AbortSignal.timeout(ANALYSIS_TIMEOUT_MS),
  });
  if (!r.ok) {
    let detail = `API error: ${r.status}`;
    try {
      const body = await r.json();
      if (body && body.detail) {
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      }
    } catch (_) { /* non-JSON error body */ }
    throw new Error(detail);
  }
  const data = await r.json();
  cacheSet(key, data);
  return data;
}

async function healthCheck() {
  const url = apiUrl('/health');
  const started = Date.now();
  const serverUrl = getSettings().serverUrl;
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) return { success: false, error: `HTTP ${r.status}`, serverUrl };
    const d = await r.json();
    return { success: true, ...d, latencyMs: Date.now() - started, serverUrl };
  } catch (e) {
    return {
      success: false,
      error: e.name === 'AbortError' ? 'timeout' : e.message,
      serverUrl,
    };
  }
}

function normalizeSettings(raw) {
  const s = { ...raw };
  if (s.serverUrl) s.serverUrl = normalizeServerUrl(s.serverUrl);
  return s;
}

function hash(text) {
  let h = 0;
  for (let i = 0; i < text.length; i++) { h = ((h << 5) - h) + text.charCodeAt(i); h = h & h; }
  return h.toString(36);
}
