// Home Browser Bridge - laptop side.
// Runs a real browser (system Chrome) with a persistent profile and exposes
// a tiny HTTP API on the tailnet IP only. The agent sends actions; the bridge
// drives the browser. No credentials ever leave this machine.
import http from 'node:http';
import { chromium } from 'playwright-core';

const HOST = process.env.BRIDGE_HOST || '100.102.34.34';
const PORT = Number(process.env.BRIDGE_PORT || 8787);
const PROFILE_DIR = process.env.BRIDGE_PROFILE || `${process.env.HOME}/.config/home-browser-bridge/profile`;
const CHROME_PATH = process.env.BRIDGE_CHROME || '/usr/bin/google-chrome-stable';

let context;
let page;

async function ensureBrowser() {
  if (page) return page;
  context = await chromium.launchPersistentContext(PROFILE_DIR, {
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox'],
  });
  page = context.pages()[0] || (await context.newPage());
  return page;
}

function send(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body) });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/health') {
      return send(res, 200, { ok: true, service: 'home-browser-bridge', version: '0.1.0' });
    }
    if (req.method === 'POST' && req.url === '/action') {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      const body = JSON.parse(Buffer.concat(chunks).toString() || '{}');
      const p = await ensureBrowser();
      if (body.goto) {
        await p.goto(body.goto, { waitUntil: 'domcontentloaded', timeout: 60000 });
      }
      if (body.waitMs) await p.waitForTimeout(body.waitMs);
      const result = {
        ok: true,
        url: p.url(),
        title: await p.title().catch(() => ''),
      };
      if (body.screenshot) {
        result.screenshot = (await p.screenshot({ type: 'png' })).toString('base64');
      }
      return send(res, 200, result);
    }
    return send(res, 404, { ok: false, error: 'not found' });
  } catch (err) {
    return send(res, 500, { ok: false, error: String((err && err.message) || err) });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`home-browser-bridge listening on http://${HOST}:${PORT}`);
});
