#!/usr/bin/env node
/**
 * Live WebGL end-to-end verification script using Vite preview + headless Chrome CDP.
 * Captures desktop & mobile screenshots across Welcome, Exterior, Dollhouse,
 * Floor Plan, Style Switching, Sunset Lighting, and Guided Tour, asserting zero errors.
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const WEB_DIR = '/Users/macbookm2/.gemini/antigravity/scratch/luxury-residence-floorplan/web';
const SHOT_DIR = path.join(WEB_DIR, 'verification-shots');
fs.mkdirSync(SHOT_DIR, { recursive: true });

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = 4179;
const CDP_PORT = 9299;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const preview = spawn('npx', ['vite', 'preview', '--host', '127.0.0.1', '--port', String(PORT), '--strictPort'], {
  cwd: WEB_DIR,
  stdio: ['ignore', 'pipe', 'pipe'],
});

const chrome = spawn(CHROME, [
  '--headless=new',
  `--remote-debugging-port=${CDP_PORT}`,
  '--window-size=1440,900',
  '--enable-webgl',
  '--use-gl=angle',
  '--use-angle=metal',
  '--ignore-gpu-blocklist',
  '--no-first-run',
  '--no-default-browser-check',
  `http://127.0.0.1:${PORT}/`,
], { stdio: ['ignore', 'pipe', 'pipe'] });

async function waitForCDP() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`);
      const list = await res.json();
      const page = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error('Chrome CDP did not start in time');
}

let exitCode = 0;
try {
  await sleep(1400);
  const wsUrl = await waitForCDP();
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => {
    ws.addEventListener('open', res, { once: true });
    ws.addEventListener('error', rej, { once: true });
  });

  let nextId = 1;
  const pending = new Map();
  const errors = [];

  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(String(ev.data));
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
    } else if (msg.method === 'Runtime.exceptionThrown') {
      errors.push('Exception: ' + JSON.stringify(msg.params.exceptionDetails));
    } else if (msg.method === 'Log.entryAdded' && msg.params.entry.level === 'error') {
      errors.push('ConsoleError: ' + msg.params.entry.text);
    }
  });

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });

  await send('Runtime.enable');
  await send('Log.enable');
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/` });

  // Wait until __VILLA_APP__ is ready (all GLBs & JSON loaded)
  let ready = false;
  for (let i = 0; i < 40; i++) {
    const r = await send('Runtime.evaluate', { expression: 'Boolean(window.__VILLA_APP__)', returnByValue: true });
    if (r.result?.value === true) {
      ready = true;
      break;
    }
    await sleep(300);
  }
  if (!ready) throw new Error('App did not finish initializing within 12s');
  await sleep(700);

  const shot = async (name) => {
    const { data } = await send('Page.captureScreenshot', { format: 'png' });
    const p = path.join(SHOT_DIR, name);
    fs.writeFileSync(p, Buffer.from(data, 'base64'));
    console.log('Captured:', name);
  };

  // 1. Welcome Screen
  await shot('01_welcome_desktop.png');

  // 2. Dismiss Welcome -> Exterior Afternoon
  await send('Runtime.evaluate', { expression: 'document.getElementById("btn-start-exploring").click()' });
  await sleep(1100);
  await shot('02_exterior_desktop.png');

  // 3. Dollhouse View + Scandinavian Style
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.setMode("dollhouse"); window.__VILLA_APP__.switchStyle("scandinavian")', awaitPromise: true });
  await sleep(1000);
  await shot('03_dollhouse_scandinavian.png');

  // 4. Floor Plan Orthographic View (with room dimension badges)
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.setMode("floorplan")' });
  await sleep(600);
  await shot('04_floorplan_ortho.png');

  // 5. Guided Tour + Warm Luxury + Golden Hour Sunset
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.switchStyle("warm_luxury")', awaitPromise: true });
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.setTimeOfDay(17.75); window.__VILLA_APP__.startTour()' });
  await sleep(1200);
  await shot('05_guided_tour_sunset.png');

  // 5b. Interior Kitchen, Curved Gooseneck Faucet, Espresso Machine & Dining Close-Up (Desktop 1440x900)
  await send('Runtime.evaluate', { expression: 'document.getElementById("btn-tour-exit").click(); window.__VILLA_APP__.setTimeOfDay(10.0); window.__VILLA_APP__.toggleDoors(true); window.__VILLA_APP__.teleportTo(6.35, 1.62, -6.95, 8.20, 1.12, -5.85);' });
  await sleep(900);
  await shot('07_interior_living_desktop.png');

  // 5c. Carport Ultra-Detailed Luxury GT Car & Open Doors Close-Up + Verify WASD Auto-Open & All 8 Doors
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.toggleDoors(false); window.__VILLA_APP__.teleportTo(4.15, 1.80, -8.65, 2.50, 1.60, -8.80);' });
  await sleep(500);
  const autoOpenRes = await send('Runtime.evaluate', { expression: 'JSON.stringify(window.__VILLA_APP__.getDoorStates())', returnByValue: true });
  console.log('WASD PROXIMITY AUTO-OPEN DOOR STATES:', autoOpenRes.result?.value);
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.toggleDoors(true); window.__VILLA_APP__.teleportTo(2.85, 1.55, 1.25, 1.35, 0.78, -2.20); document.getElementById("side-panel").classList.add("is-collapsed");' });
  await sleep(900);
  await shot('08_carport_and_open_doors.png');

  // 5d. Aesthetic Programmer Studio & Window Battlestation (RM-04, Desktop 1440x900) + Verify Per-Lamp Toggle
  await send('Runtime.evaluate', { expression: 'document.getElementById("side-panel").classList.remove("is-collapsed"); window.__VILLA_APP__.teleportTo(6.85, 1.62, -4.55, 7.65, 1.18, -2.25);' });
  await sleep(600);
  const lampOff = await send('Runtime.evaluate', { expression: 'JSON.stringify(window.__VILLA_APP__.toggleLightGroup("Studio_Desk", false))', returnByValue: true });
  const lampOn = await send('Runtime.evaluate', { expression: 'JSON.stringify(window.__VILLA_APP__.toggleLightGroup("Studio_Desk", true))', returnByValue: true });
  console.log('PER-LAMP CLICK TOGGLE:', lampOff.result?.value, '->', lampOn.result?.value);
  await sleep(1100);
  const desktopHighPerf = await send('Runtime.evaluate', { expression: 'JSON.stringify(window.__VILLA_APP__.getState())', returnByValue: true });
  console.log('DESKTOP HIGH PERF (1440x900 + Half-Res GTAO + Baked AO):', desktopHighPerf.result?.value);
  await shot('09_programmer_studio_desktop.png');

  // 5e. Level 2 Tempat Jemuran & Sky Service Deck (RM-12) + Level 2 Sky Lounge & Front Balcony (RM-13 / EXT-05)
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.setTimeOfDay(14.0); window.__VILLA_APP__.teleportTo(1.25, 5.00, -10.85, 2.55, 4.30, -8.10);' });
  await sleep(900);
  await shot('10_l2_tempat_jemuran.png');

  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.teleportTo(6.95, 5.00, -9.85, 6.60, 4.45, -3.50);' });
  await sleep(900);
  await shot('11_l2_sky_lounge_balcony.png');

  // Benchmark Desktop Medium (Smooth 60 FPS direct render mode)
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.setQuality("medium")' });
  await sleep(1400);
  const desktopMedPerf = await send('Runtime.evaluate', { expression: 'JSON.stringify(window.__VILLA_APP__.getState())', returnByValue: true });
  console.log('DESKTOP MEDIUM PERF (1440x900 Direct Fast):', desktopMedPerf.result?.value);
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.setQuality("high")' });

  // 6. Mobile Viewport (390x844) First-Person Walkthrough with Virtual Joystick & WASD Door HUD
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send('Runtime.evaluate', { expression: 'window.__VILLA_APP__.teleportTo(4.70, 1.80, -2.80, 6.20, 1.65, -7.80); window.__VILLA_APP__.setTimeOfDay(10.0); document.getElementById("side-panel").classList.add("is-collapsed");' });
  await sleep(800);
  await shot('06_mobile_walkthrough.png');

  const stateRes = await send('Runtime.evaluate', { expression: 'JSON.stringify(window.__VILLA_APP__.getState())', returnByValue: true });
  console.log('FINAL APP STATE:', stateRes.result?.value);
  console.log('ERRORS COUNT:', errors.length);
  if (errors.length > 0) {
    console.error(errors.join('\n'));
    exitCode = 1;
  }
  ws.close();
} catch (err) {
  console.error('VERIFICATION FAILED:', err);
  exitCode = 1;
} finally {
  chrome.kill();
  preview.kill();
  process.exit(exitCode);
}
