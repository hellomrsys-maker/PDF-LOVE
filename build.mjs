/*
 * Produce frontend/dist — the minified build that ships inside the desktop
 * app and the Android APK.
 *
 *   node build.mjs
 *
 * What this is and is not for:
 *
 *   It makes casual copying impractical. It does NOT make the code secret,
 *   and nothing can — the code has to run on the user's machine, so they
 *   necessarily have it. Anyone determined will read it either way.
 *
 *   The public website deliberately keeps shipping readable source. The
 *   strongest claim this product makes is "open devtools, watch the Network
 *   tab, see that nothing fires" — and a reviewer, a journalist or a
 *   security researcher has to be able to confirm that. Obfuscating the web
 *   build would trade the thing that sells the product for protection it
 *   cannot actually deliver.
 *
 * Uses no dependencies. esbuild/terser would minify the inline script more
 * aggressively, but adding a toolchain to a project whose whole premise is
 * "no build step" is a poor trade for the last few percent — and this keeps
 * `node build.mjs` working on a clean checkout with nothing installed.
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(ROOT, 'frontend');
const OUT = path.join(SRC, 'dist');

// Copied verbatim: already minified, or binary, or must not be touched.
const VERBATIM = /\.(wasm|woff2?|png|jpg|jpeg|gif|svg|ico|gz|traineddata|txt|xml)$/i;
// Never enters the build.
const SKIP_DIRS = new Set(['dist', 'node_modules']);
const SKIP_FILES = new Set(['Dockerfile', 'nginx.conf', '_headers']);

/** Strip comments and collapse whitespace in CSS. */
function minifyCss(css) {
  return css
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\s*([{}:;,>~])\s*/g, '$1')
    .replace(/;\}/g, '}')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Minify JS conservatively.
 *
 * Deliberately does not rename identifiers or restructure code: without a
 * real parser that is how a build silently breaks a working app. Comments
 * and indentation are the bulk of the size anyway.
 *
 * The tokenizer below exists because the naive version of this is wrong in
 * a way that is easy to miss — "https://x" inside a string looks exactly
 * like a line comment, and stripping it corrupts the file. Strings,
 * template literals and regexes are all recognised and passed through
 * untouched.
 */
function minifyJs(src) {
  let out = '';
  let i = 0;
  const n = src.length;
  // Tracks whether a '/' starts a regex or is a division operator.
  let prevSignificant = '';

  while (i < n) {
    const c = src[i];
    const next = src[i + 1];

    // line comment
    if (c === '/' && next === '/') {
      while (i < n && src[i] !== '\n') i++;
      continue;
    }
    // block comment
    if (c === '/' && next === '*') {
      i += 2;
      while (i < n && !(src[i] === '*' && src[i + 1] === '/')) i++;
      i += 2;
      continue;
    }
    // string
    if (c === '"' || c === "'") {
      const start = i++;
      while (i < n && src[i] !== c) {
        if (src[i] === '\\') i++;
        i++;
      }
      i++;
      out += src.slice(start, i);
      prevSignificant = '"';
      continue;
    }
    // template literal — may nest ${ ... } containing anything
    if (c === '`') {
      const start = i++;
      let depth = 0;
      while (i < n) {
        if (src[i] === '\\') { i += 2; continue; }
        if (src[i] === '`' && depth === 0) { i++; break; }
        if (src[i] === '$' && src[i + 1] === '{') { depth++; i += 2; continue; }
        if (src[i] === '}' && depth > 0) { depth--; i++; continue; }
        i++;
      }
      out += src.slice(start, i);
      prevSignificant = '`';
      continue;
    }
    // regex literal (only where a value is expected)
    if (c === '/' && !')]}'.includes(prevSignificant) &&
        !/[A-Za-z0-9_$"'`]/.test(prevSignificant)) {
      const start = i++;
      let inClass = false;
      while (i < n) {
        if (src[i] === '\\') { i += 2; continue; }
        if (src[i] === '[') inClass = true;
        else if (src[i] === ']') inClass = false;
        else if (src[i] === '/' && !inClass) { i++; break; }
        else if (src[i] === '\n') break;   // not a regex after all
        i++;
      }
      while (i < n && /[gimsuy]/.test(src[i])) i++;
      out += src.slice(start, i);
      prevSignificant = '/';
      continue;
    }
    // whitespace: collapse, but never join two tokens into one
    if (/\s/.test(c)) {
      let j = i;
      while (j < n && /\s/.test(src[j])) j++;
      const before = out[out.length - 1] || '';
      const after = src[j] || '';
      const needed = /[A-Za-z0-9_$]/.test(before) && /[A-Za-z0-9_$]/.test(after);
      // Keep one newline where ASI might depend on it.
      const hadNewline = src.slice(i, j).includes('\n');
      if (needed) out += ' ';
      else if (hadNewline && /[A-Za-z0-9_$)\]}'"`+-]/.test(before) &&
               /[A-Za-z0-9_$([{'"`+-]/.test(after)) out += '\n';
      i = j;
      continue;
    }

    out += c;
    prevSignificant = c;
    i++;
  }
  return out;
}

/** Minify an HTML document, including its inline <style> and <script>. */
function minifyHtml(html) {
  // Comments, except conditional ones (harmless to keep, risky to guess at).
  let out = html.replace(/<!--(?!\[if)[\s\S]*?-->/g, '');

  out = out.replace(/<style([^>]*)>([\s\S]*?)<\/style>/g,
    (_, attrs, css) => `<style${attrs}>${minifyCss(css)}</style>`);

  out = out.replace(/<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)<\/script>/g,
    (m, attrs, js) => {
      // Leave JSON-LD alone: it is data, and the JS tokenizer would mangle it.
      if (/type=["']application\/ld\+json["']/.test(attrs)) {
        return `<script${attrs}>${JSON.stringify(JSON.parse(js))}</script>`;
      }
      return `<script${attrs}>${minifyJs(js)}</script>`;
    });

  // Collapse inter-tag whitespace only — never inside a tag or text node,
  // where it is meaningful.
  out = out.replace(/>\s{2,}</g, '><');
  return out.trim();
}

async function copyDir(src, dest) {
  await fs.mkdir(dest, { recursive: true });
  let files = 0, bytesIn = 0, bytesOut = 0;

  for (const entry of await fs.readdir(src, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      const r = await copyDir(path.join(src, entry.name), path.join(dest, entry.name));
      files += r.files; bytesIn += r.bytesIn; bytesOut += r.bytesOut;
      continue;
    }
    if (SKIP_FILES.has(entry.name)) continue;

    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    const stat = await fs.stat(from);
    bytesIn += stat.size;
    files++;

    if (VERBATIM.test(entry.name) || entry.name.endsWith('.min.js')) {
      await fs.copyFile(from, to);
      bytesOut += stat.size;
      continue;
    }

    const text = await fs.readFile(from, 'utf8');
    let result;
    if (entry.name.endsWith('.html')) result = minifyHtml(text);
    else if (entry.name.endsWith('.css')) result = minifyCss(text);
    else if (entry.name.endsWith('.js')) result = minifyJs(text);
    else result = text;

    await fs.writeFile(to, result);
    bytesOut += Buffer.byteLength(result);
  }
  return { files, bytesIn, bytesOut };
}

const mb = b => (b / 1048576).toFixed(2) + ' MB';

await fs.rm(OUT, { recursive: true, force: true });
const { files, bytesIn, bytesOut } = await copyDir(SRC, OUT);

console.log(`\n  built frontend/dist`);
console.log(`  ${files} files`);
console.log(`  ${mb(bytesIn)} -> ${mb(bytesOut)}  (${((1 - bytesOut / bytesIn) * 100).toFixed(1)}% smaller)`);
console.log(`\n  The public site still ships readable source: the "no request`);
console.log(`  fires" claim has to stay checkable in devtools.\n`);
