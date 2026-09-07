'use strict';

const DEFAULT_SETTINGS = {
  serverUrl: 'http://localhost:8000',
  dashboardUrl: 'http://localhost:8000',
  localize: false,
  fastTrack: false,
};

let settings = { ...DEFAULT_SETTINGS };

function normalizeServerUrl(url) {
  let u = String(url || '').trim().replace(/\/+$/, '');
  if (!u) u = DEFAULT_SETTINGS.serverUrl;
  if (!/^https?:\/\//i.test(u)) u = 'http://' + u;
  return u;
}

function loadSettings(callback) {
  chrome.storage.local.get('settings', (localResult) => {
    const stored = (localResult && localResult.settings) || null;
    if (stored) {
      applySettings(stored);
      if (callback) callback(settings);
      return;
    }
    // Pre-1.3.0 builds stored settings in chrome.storage.sync — migrate them
    // once so users keep their custom server/dashboard URLs.
    chrome.storage.sync.get('settings', (syncResult) => {
      const legacy = (syncResult && syncResult.settings) || null;
      if (legacy) {
        chrome.storage.local.set({ settings: legacy }, () => {
          if (chrome.runtime.lastError) console.error('Settings migration failed:', chrome.runtime.lastError);
        });
      }
      applySettings(legacy);
      if (callback) callback(settings);
    });
  });
}

function applySettings(stored) {
  settings = { ...DEFAULT_SETTINGS, ...(stored || {}) };
  settings.serverUrl = normalizeServerUrl(settings.serverUrl);
  settings.dashboardUrl = normalizeServerUrl(settings.dashboardUrl);
}

function saveSettings(next, callback) {
  const merged = { ...settings, ...next };
  if (merged.serverUrl) merged.serverUrl = normalizeServerUrl(merged.serverUrl);
  if (merged.dashboardUrl) merged.dashboardUrl = normalizeServerUrl(merged.dashboardUrl);
  settings = merged;
  chrome.storage.local.set({ settings: merged }, () => {
    if (chrome.runtime.lastError) console.error('Failed to save settings:', chrome.runtime.lastError);
    if (callback) callback(merged);
  });
}

function getSettings() {
  return { ...settings };
}

function apiUrl(path) {
  return normalizeServerUrl(settings.serverUrl) + '/api/v1' + path;
}

chrome.storage.onChanged.addListener((changes, area) => {
  if ((area === 'local' || area === 'sync') && changes.settings) {
    settings = { ...DEFAULT_SETTINGS, ...(changes.settings.newValue || {}) };
    settings.serverUrl = normalizeServerUrl(settings.serverUrl);
    settings.dashboardUrl = normalizeServerUrl(settings.dashboardUrl);
  }
});

if (typeof module !== 'undefined') {
  module.exports = { DEFAULT_SETTINGS, loadSettings, saveSettings, getSettings, apiUrl, normalizeServerUrl };
}
