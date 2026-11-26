#!/usr/bin/env node
/**
 * Builds a self-contained single-HTML portable distribution of Villa Aurelia 123
 * at `dist-single/villa-aurelia-123-standalone.html`, embedding compiled CSS,
 * bundled JS modules, and base64-encoded verified Blender GLB + JSON assets.
 */
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const distDir = path.join(root, 'dist');
const outDir = path.join(root, 'dist-single');
fs.mkdirSync(outDir, { recursive: true });

let html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');

// 1. Inline compiled CSS
html = html.replace(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"[^>]*>/g, (_, href) => {
  const cssPath = path.join(distDir, href.replace(/^\.\//, ''));
  const css = fs.readFileSync(cssPath, 'utf8');
  return `<style>\n${css}\n</style>`;
});

// 2. Embed verified GLB & JSON assets into window.__EMBEDDED_ASSETS__
const assetsDir = path.join(distDir, 'assets');
const embedded = {};
for (const file of fs.readdirSync(assetsDir)) {
  const full = path.join(assetsDir, file);
  if (file.endsWith('.json')) {
    embedded[file] = fs.readFileSync(full, 'utf8');
  } else if (file.endsWith('.glb')) {
    embedded[file] = fs.readFileSync(full).toString('base64');
  }
}

const embeddedScript = `<script>window.__EMBEDDED_ASSETS__ = ${JSON.stringify(embedded)};</script>`;

// 3. Inline JS bundles cleanly via blob URL import map / module data URLs
const jsFiles = fs
  .readdirSync(assetsDir)
  .filter((f) => f.endsWith('.js'));

// Build single self-contained ES module bootstrapper
const moduleMap = {};
for (const jf of jsFiles) {
  moduleMap[`./assets/${jf}`] = fs.readFileSync(path.join(assetsDir, jf), 'utf8');
}

// Find entry script tag
let entryHref = null;
html = html.replace(/<script[^>]+type="module"[^>]+src="([^"]+)"[^>]*><\/script>/g, (_, src) => {
  entryHref = src;
  return '';
});
html = html.replace(/<link[^>]+rel="modulepreload"[^>]*>/g, '');

if (!entryHref) {
  throw new Error('Could not locate entry module script in dist/index.html');
}

// Replace chunk imports inside entry script with blob URLs at runtime
const loaderScript = `
<script type="module">
const MODS = ${JSON.stringify(moduleMap)};
const blobUrls = {};
for (const [k, code] of Object.entries(MODS)) {
  if (k !== ${JSON.stringify(entryHref)}) {
    blobUrls[k] = URL.createObjectURL(new Blob([code], { type: 'text/javascript' }));
  }
}
let entryCode = MODS[${JSON.stringify(entryHref)}];
for (const [k, url] of Object.entries(blobUrls)) {
  const base = k.replace('./assets/', './');
  entryCode = entryCode.split(base).join(url);
}
const entryUrl = URL.createObjectURL(new Blob([entryCode], { type: 'text/javascript' }));
await import(entryUrl);
</script>`;

html = html.replace('</body>', `${embeddedScript}\n${loaderScript}\n</body>`);

const outPath = path.join(outDir, 'villa-aurelia-123-standalone.html');
fs.writeFileSync(outPath, html, 'utf8');
const mb = (fs.statSync(outPath).size / (1024 * 1024)).toFixed(2);
console.log(`Built standalone single-HTML distribution: ${outPath} (${mb} MB)`);
