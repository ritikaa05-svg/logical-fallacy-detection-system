import puppeteer from 'puppeteer-core';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const EXT_PATH = path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const CHROME = process.env.CHROME_BIN || '/usr/bin/chromium';
const PORT = 8123;
const EXPECTED_SHORTCUT = 'Ctrl+Shift+L';

const SAMPLE_TEXT = 'You cannot trust her argument about the budget because she is just a blogger, not an economist.';

const HTML = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>hotkey test</title></head>
<body>
  <p id="sample">${SAMPLE_TEXT}</p>
  <p id="other">The sky is blue because blue is the color of the sky.</p>
</body>
</html>`;

let passed = 0;
let failed = 0;

function check(name, ok, detail = '') {
  if (ok) { passed++; console.log('PASS  ' + name + (detail ? '  (' + detail + ')' : '')); }
  else { failed++; console.log('FAIL  ' + name + (detail ? '  (' + detail + ')' : '')); }
}

const server = http.createServer((req, res) => {
  res.setHeader('content-type', 'text/html; charset=utf-8');
  res.end(HTML);
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  await new Promise((r) => server.listen(PORT, '127.0.0.1', r));

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: [
      `--load-extension=${EXT_PATH}`,
      `--disable-extensions-except=${EXT_PATH}`,
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  });

  try {
    // ---- 1. Service worker + command registration ----
    const swTarget = await browser.waitForTarget((t) => t.type() === 'service_worker', { timeout: 15000 });
    const worker = await swTarget.worker();

    const commands = await worker.evaluate(() => chrome.commands.getAll());
    const cmd = commands.find((c) => c.name === 'analyze-selection');
    check('command "analyze-selection" registered', !!cmd, cmd ? JSON.stringify(cmd) : 'not found');
    check(`shortcut bound to ${EXPECTED_SHORTCUT}`, !!cmd && cmd.shortcut === EXPECTED_SHORTCUT,
      cmd ? `actual: "${cmd.shortcut}"` : 'n/a');

    // ---- 2. Open test page (content script auto-injects via <all_urls>) ----
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${PORT}/`);
    await sleep(500);

    // ---- 3. Select text, then fire the hotkey path from the SW ----
    await page.evaluate(() => {
      const el = document.getElementById('sample');
      const range = document.createRange();
      range.selectNodeContents(el);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    });
    await sleep(200);

    const hotkeyReply = await worker.evaluate(async () => {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || tab.id == null) return { ok: false, error: 'no active tab' };
      try {
        const reply = await chrome.tabs.sendMessage(tab.id, { action: 'hotkeyAnalyze' });
        return { ok: true, reply };
      } catch (e) {
        return { ok: false, error: String(e && e.message || e) };
      }
    });
    check('SW -> content script hotkeyAnalyze round-trip', hotkeyReply.ok, JSON.stringify(hotkeyReply));

    const pillSeen = await page.waitForFunction(() => {
      const host = document.getElementById('argcheck-host');
      return !!(host && host.shadowRoot && host.shadowRoot.querySelector('.ac-pill'));
    }, { timeout: 5000 }).then(() => true).catch(() => false);
    check('analyzing pill appears', pillSeen);

    const popoverSeen = await page.waitForFunction(() => {
      const host = document.getElementById('argcheck-host');
      return !!(host && host.shadowRoot && host.shadowRoot.querySelector('.ac-popover'));
    }, { timeout: 30000 }).then(() => true).catch(() => false);
    check('result popover appears', popoverSeen);

    if (popoverSeen) {
      const verdict = await page.evaluate(() => {
        const host = document.getElementById('argcheck-host');
        const sr = host.shadowRoot;
        return {
          verdict: sr.querySelector('.ac-verdict')?.textContent || null,
          score: sr.querySelector('.ac-score')?.textContent || null,
          error: sr.querySelector('.ac-error')?.textContent || null,
        };
      });
      check('verdict rendered (API round-trip)', !!verdict.verdict, JSON.stringify(verdict));
    }

    // ---- 4. Hotkey with no selection -> error card ----
    await page.evaluate(() => window.getSelection().removeAllRanges());
    await sleep(200);
    await worker.evaluate(async () => {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      await chrome.tabs.sendMessage(tab.id, { action: 'hotkeyAnalyze' });
    });
    const errSeen = await page.waitForFunction(() => {
      const host = document.getElementById('argcheck-host');
      return !!(host && host.shadowRoot && host.shadowRoot.querySelector('.ac-error'));
    }, { timeout: 5000 }).then(() => true).catch(() => false);
    check('no-selection hotkey shows error card', errSeen);

    // ---- 5. Informational: physical key via CDP (browser accelerators are
    // not reliably triggerable from CDP; real keypress is covered by the
    // registration check + manual step) ----
    await page.evaluate(() => {
      const el = document.getElementById('other');
      const range = document.createRange();
      range.selectNodeContents(el);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    });
    await sleep(200);
    try { await page.keyboard.press('Control+Shift+L'); } catch (e) { /* ignore */ }
    await sleep(1500);
    const kbTriggered = await page.evaluate(() => {
      const host = document.getElementById('argcheck-host');
      return !!(host && host.shadowRoot && host.shadowRoot.querySelector('.ac-pill'));
    }).catch(() => false);
    console.log('INFO  physical-key simulation via CDP triggered analysis: ' + kbTriggered +
      ' (expected false — browser-level commands are not fired by CDP key events; verified via registration check above)');
  } finally {
    await browser.close();
    server.close();
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error('ERROR:', err);
  server.close();
  process.exit(1);
});
